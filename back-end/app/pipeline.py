"""
pipeline.py — Mắt xích nối ingest -> ML -> Agent -> Dashboard.

Trước khi hợp nhất, 3 mảnh này tồn tại nhưng KHÔNG gọi nhau: dữ liệu vào
farm_state rồi dừng, `app/ml/` không được import ở đâu cả, agents chỉ chạy khi
người dùng gõ câu hỏi. File này là chỗ chúng nối lại.

Trình tự (bám đúng sequence diagram của BTC):

    1. Thiết bị bắn telemetry            -> farm_state.ingest()
    2. Tự tính anomaly score, so ngưỡng  -> ml.predict_anomaly()   RẺ (<1ms), chạy MỌI điểm
    3. CHỈ khi vượt ngưỡng mới emit event -> broadcast "anomaly"
    4. Event trigger AI Decision Agent   -> coordinator_agent      ĐẮT (1-3s), có cooldown
    5. Agent tra guardrail + SOP         -> tools.check_*_guardrail()
    8. Agent giải thích quyết định       -> broadcast "agent_insight"

Hai nguyên tắc chi phối thiết kế ở đây, cả hai đều lấy từ vị trí bước 2 và 5:

  - Phát hiện bất thường rẻ -> chạy trên mọi điểm dữ liệu, inline luôn.
  - LLM đắt và chậm -> chỉ chạy khi có bất thường, có cooldown theo thiết bị, và
    chạy trong thread riêng. Gọi thẳng trong callback MQTT sẽ block luồng nhận
    message 1-3 giây, message dồn ứ và dashboard giật.
"""

from __future__ import annotations

import logging
import threading
import time
from collections import deque

from app.config import AGENT_COOLDOWN_SECONDS, AGENT_ON_ANOMALY, DEVICES
from app import events
from app.state import farm_state

logger = logging.getLogger("pipeline")

# Thiết bị nào đã cảnh báo "chưa có model" rồi thì thôi, không log lại mỗi 3 giây.
_missing_model_warned: set[str] = set()

# device_code -> thời điểm cuối cùng đã gọi LLM cho thiết bị này
_last_agent_call: dict[str, float] = {}
_agent_lock = threading.Lock()

# ---------------------------------------------------------------------------
# Incident Log — bước 8 trong sequence diagram của BTC: "Agent cập nhật
# Incident Log và giải thích quyết định lên Dashboard". Trước đây chỗ này chỉ
# giữ ĐÚNG 1 bản ghi (last_insight = insight), nên chẩn đoán trước bị chẩn
# đoán sau ghi đè mất — demo 2 kịch bản liên tiếp thì kịch bản đầu biến mất
# khỏi dashboard không cách nào xem lại. Giờ giữ tối đa INSIGHT_LOG_MAXLEN bản
# ghi gần nhất, mới nhất ở đầu.
# ---------------------------------------------------------------------------
INSIGHT_LOG_MAXLEN = 30
insight_log: deque[dict] = deque(maxlen=INSIGHT_LOG_MAXLEN)
_insight_lock = threading.Lock()
_next_insight_id = 1


def record_insight(insight: dict) -> dict:
    """Gắn id + ts rồi thêm vào đầu Incident Log (mới nhất trước). Thread-safe
    vì nhiều thiết bị bất thường cùng lúc sẽ chạy _run_agent song song."""
    global _next_insight_id
    with _insight_lock:
        insight = {"id": _next_insight_id, "ts": time.time(), **insight}
        _next_insight_id += 1
        insight_log.appendleft(insight)
    return insight


def get_insights(limit: int = 20) -> list[dict]:
    with _insight_lock:
        return list(insight_log)[:limit]


def _predict(device_code: str, reading: dict) -> dict | None:
    """Chạy anomaly model. Trả None nếu chưa train model (fail-soft — thiếu model
    thì server vẫn chạy và vẫn stream dữ liệu, chỉ là không có tầng phát hiện)."""
    try:
        from app.ml.anomaly_model import predict_anomaly

        return predict_anomaly(device_code, reading)
    except FileNotFoundError:
        if device_code not in _missing_model_warned:
            _missing_model_warned.add(device_code)
            logger.warning(
                "Chưa có anomaly model cho %s — chạy `python -m app.ml.train_anomaly_model`. "
                "Pipeline vẫn chạy nhưng KHÔNG phát hiện bất thường cho thiết bị này.",
                device_code,
            )
        return None
    except Exception as exc:
        logger.error("predict_anomaly(%s) lỗi: %s", device_code, exc, exc_info=True)
        return None


def _should_call_agent(device_code: str) -> bool:
    """Cooldown theo từng thiết bị. SOIL_01 bất thường liên tục 20 tick trong 1
    phút vẫn chỉ tốn đúng 1 lần gọi LLM."""
    now = time.time()
    with _agent_lock:
        last = _last_agent_call.get(device_code, 0.0)
        if now - last < AGENT_COOLDOWN_SECONDS:
            return False
        _last_agent_call[device_code] = now
        return True


def _run_agent(device_code: str, anomaly: dict, reading: dict) -> None:
    """Gọi Coordinator Agent để chẩn đoán 1 bất thường. Chạy trong thread riêng."""
    from app.agents import coordinator_agent

    spec = DEVICES.get(device_code)
    device_name = spec.name if spec else device_code
    rolling = farm_state.devices[device_code].rolling_stats() if device_code in farm_state.devices else {}

    question = (
        f"Hệ thống vừa phát hiện bất thường ở thiết bị {device_code} ({device_name}). "
        f"Giá trị hiện tại: {reading}. "
        f"Điểm bất thường của model: {anomaly.get('anomaly_score')} "
        f"(càng âm càng bất thường). "
        f"Thống kê 300 giây gần nhất: {rolling}. "
        "Hãy đọc dữ liệu các thiết bị liên quan, xác định nguyên nhân gốc, "
        "kiểm tra ràng buộc an toàn, và nếu cần thì tạo kế hoạch tưới hoặc "
        "phiếu kiểm tra hiện trường. Giải thích ngắn gọn vì sao."
    )

    started = time.time()
    try:
        result = coordinator_agent.handle_request(question)
    except Exception as exc:
        logger.error("Agent xử lý anomaly %s thất bại: %s", device_code, exc, exc_info=True)
        insight = record_insight({
            "trigger": f"anomaly:{device_code}",
            "device_code": device_code,
            "device_name": device_name,
            "error": str(exc),
            "answer": None,
            "trace": [],
        })
        events.emit_threadsafe("agent_insight", insight)
        return

    insight = record_insight({
        "trigger": f"anomaly:{device_code}",
        "device_code": device_code,
        "device_name": device_name,
        "anomaly": anomaly,
        # `answer` là văn xuôi tiếng Việt do LLM sinh; `trace` là danh sách tool
        # đã thực sự chạy (kèm kết quả) — chính là phần "giải thích quyết định".
        "answer": result.get("answer"),
        "trace": result.get("trace", []),
        "latency_ms": round((time.time() - started) * 1000),
    })
    events.emit_threadsafe("agent_insight", insight)

    # Tool nào đã tạo ra hành động thật thì đẩy riêng 1 sự kiện để dashboard
    # cập nhật danh sách plan/task mà không phải gọi lại REST.
    for call in result.get("trace", []):
        payload = call.get("result") or {}
        if call.get("tool") == "create_irrigation_plan" and "plan_id" in payload:
            events.emit_threadsafe("plan", payload)
        elif call.get("tool") == "create_inspection_task" and "task_id" in payload:
            events.emit_threadsafe("task", payload)
        elif call.get("tool") == "send_notification" and "notification_id" in payload:
            events.emit_threadsafe("notification", payload)


def on_reading(device_code: str, metrics: dict, event_time: float | None = None,
               meta: dict | None = None) -> bool:
    """Handler duy nhất cho mọi bản ghi telemetry, bất kể đến từ MQTT thật,
    simulator hay nút inject. Được gắn vào mqtt_client lúc startup."""
    meta = meta or {}

    # --- Bước 1: vào state ---
    ok = farm_state.ingest(device_code, metrics, event_time=event_time)
    if not ok:
        return False

    device = farm_state.devices[device_code]
    spec = DEVICES.get(device_code)

    events.emit_threadsafe(
        "telemetry",
        {
            "device_code": device_code,
            "name": spec.name if spec else device_code,
            "units": spec.units if spec else {},
            "metrics": metrics,
            "latest": device.latest,
            "is_stale": device.is_stale,
            "source": meta.get("source", "mqtt"),
            "scenario": meta.get("scenario"),
        },
        ts=event_time,
    )

    # --- Bước 2: anomaly detection, chạy trên MỌI điểm dữ liệu ---
    anomaly = _predict(device_code, metrics)
    if not anomaly or not anomaly.get("is_anomaly"):
        return True

    # --- Bước 3: chỉ khi bất thường mới emit event ---
    anomaly_payload = {
        "device_code": device_code,
        "name": spec.name if spec else device_code,
        "reading": metrics,
        "rolling": device.rolling_stats(),
        **anomaly,
    }
    events.emit_threadsafe("anomaly", anomaly_payload, ts=event_time)
    logger.info("Bất thường ở %s: score=%s reading=%s",
                device_code, anomaly.get("anomaly_score"), metrics)

    # --- Bước 4: chỉ khi bất thường (và hết cooldown) mới gọi LLM ---
    if not AGENT_ON_ANOMALY:
        return True
    if not _should_call_agent(device_code):
        logger.debug("Bỏ qua gọi Agent cho %s — còn trong cooldown %.0fs",
                     device_code, AGENT_COOLDOWN_SECONDS)
        return True

    threading.Thread(
        target=_run_agent,
        args=(device_code, anomaly_payload, metrics),
        daemon=True,
        name=f"agent-{device_code}",
    ).start()
    return True
