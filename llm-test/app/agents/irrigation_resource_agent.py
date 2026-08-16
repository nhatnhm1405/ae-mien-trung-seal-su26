"""
Irrigation & Resource Agent — thuần Python, KHÔNG gọi LLM.

Gộp 2 vai trò gợi ý trong đề (Irrigation Planning Agent + Resource Agent) vào
1 module: vừa đề xuất kế hoạch tưới (dựa trên độ bất thường của soil_moisture,
KHÔNG hardcode ngưỡng cố định — dùng z-score tự tính từ rolling stats) vừa
kiểm tra ràng buộc tài nguyên (bồn nước, pH, công suất bơm) bằng cách tái sử
dụng guardrail cứng đã có sẵn trong app/tools.py.
"""

from __future__ import annotations

from app import tools
from app.agents.field_iot_agent import get_farm_snapshot


def _zscore(current: float, mean: float | None, std: float | None) -> float | None:
    if mean is None or std is None or std == 0:
        return None
    return (current - mean) / std


def assess_irrigation_need(zone: str = "A") -> dict:
    """Đề xuất có nên tưới hay không, cho khu vực `zone`.

    - Độ bất thường của soil_moisture: z-score = (giá trị hiện tại - mean) / std,
      cả mean/std đều tính từ sliding window 300s có sẵn trong rolling_stats() —
      model tự học "bình thường" từ chính dữ liệu gần đây, không so ngưỡng số cố định.
      TODO(AI/ML): thay z-score thủ công này bằng app.ml.detector (sklearn.IsolationForest)
      khi đã train xong — giữ nguyên shape trả về {"z_score":..., "level":...} để không
      phải sửa lại coordinator_agent.py.
    - Ràng buộc tài nguyên: gọi lại tools.check_irrigation_guardrail() / check_pump_guardrail()
      thay vì viết lại logic — nguồn sự thật duy nhất về ngưỡng an toàn vật lý vẫn là tools.py.
    """
    snap = get_farm_snapshot()
    soil = snap["devices"].get("SOIL_01", {})
    rolling = (soil.get("rolling") or {}).get("soil_moisture")

    anomaly = {"z_score": None, "level": "unknown"}
    if soil.get("is_stale") or rolling is None:
        anomaly["level"] = "no_data"
    else:
        z = _zscore(rolling["current"], rolling["mean"], rolling["std"])
        anomaly["z_score"] = z
        if z is None:
            anomaly["level"] = "insufficient_history"  # chưa đủ điểm dữ liệu để có std ổn định
        elif abs(z) < 1.0:
            anomaly["level"] = "normal"
        elif abs(z) < 2.0:
            anomaly["level"] = "moderate"
        else:
            anomaly["level"] = "severe"

    irrigation_guard = tools.check_irrigation_guardrail()
    pump_guard = tools.check_pump_guardrail()

    should_irrigate = (
        irrigation_guard["allowed"]
        and pump_guard["allowed"]
        and not soil.get("is_stale", True)
        and anomaly["level"] in ("moderate", "severe")
    )
    priority = "high" if anomaly["level"] == "severe" else ("normal" if should_irrigate else "low")

    return {
        "zone": zone,
        "should_irrigate": should_irrigate,
        "priority": priority,
        "soil_anomaly": anomaly,
        "guardrail": {"irrigation": irrigation_guard, "pump": pump_guard},
        "used_devices": ["SOIL_01", "TANK_01", "PH_01"],
        "rationale": (
            f"soil_moisture z-score={anomaly['z_score']}, mức={anomaly['level']}; "
            f"guardrail tưới: {irrigation_guard['reason']}; guardrail bơm: {pump_guard['reason']}"
        ),
    }


def review_irrigation_session(zone: str = "A") -> dict:
    """Kịch bản 2: kiểm tra phiên tưới hiện tại/gần nhất có gì bất thường không,
    dựa trên PUMP_01, SOIL_01, TANK_01."""
    snap = get_farm_snapshot()
    devices = snap["devices"]
    checks = (("PUMP_01", "flow_rate"), ("SOIL_01", "soil_moisture"), ("TANK_01", "level"))

    issues: list[str] = []
    checked: list[str] = []
    for code, metric in checks:
        dev = devices.get(code, {})
        checked.append(code)
        if dev.get("is_stale"):
            issues.append(f"{code} không có dữ liệu mới (stale) — không thể xác nhận phiên tưới.")
            continue
        rolling = (dev.get("rolling") or {}).get(metric)
        if rolling is None:
            continue
        z = _zscore(rolling["current"], rolling["mean"], rolling["std"])
        if z is not None and abs(z) >= 2.0:
            issues.append(f"{code}.{metric} lệch bất thường (z={round(z, 2)}) so với 300s gần nhất.")

    pump_guard = tools.check_pump_guardrail()
    if not pump_guard["allowed"]:
        issues.append(pump_guard["reason"])

    return {
        "zone": zone,
        "anomaly_found": len(issues) > 0,
        "issues": issues,
        "checked_devices": checked,
        "used_devices": checked,
    }
