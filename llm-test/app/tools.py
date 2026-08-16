"""
Tool/API layer — đây là các "tool" mà Farm Action Agent (thường do bạn AI/ML
hoặc LLM+Pitch trong đội implement phần logic gọi) sẽ invoke qua function calling.

Nguyên tắc quan trọng (đề bài + file context nhấn mạnh):
- Không có tool nào ở đây tự out quyết định dựa trên ngưỡng cố định kiểu
  `if x > 80: alert()`. Các tool CHỈ THỰC THI quyết định đã có (từ model/Agent),
  và có 1 lớp guardrail cứng để chặn hành động vật lý nguy hiểm — đúng vai trò
  "Deterministic Guardrail" chứ không phải vai trò "AI ra quyết định".
- Mọi hành động đều ghi lại input data đã dùng -> phục vụ yêu cầu UX
  "thể hiện rõ dữ liệu IoT đã ảnh hưởng đến quyết định nào".
- Mọi hành động có verification (đọc lại ngay sau khi tạo) theo đúng chu trình
  Nhận yêu cầu → ... → Tool/API → Verification → Báo cáo.
"""

from __future__ import annotations

from datetime import datetime, timezone

from app.config import GUARDRAILS
from app.state import farm_state


class GuardrailRejected(Exception):
    """Guardrail cứng từ chối hành động — Agent/LLM không có quyền phủ quyết."""
    pass


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Guardrail cứng — Python thuần, không phụ thuộc LLM
# ---------------------------------------------------------------------------
def check_irrigation_guardrail() -> dict:
    """Kiểm tra trước khi cho phép tạo lệnh tưới. Trả {"allowed": bool, "reason": str}."""
    tank = farm_state.devices.get("TANK_01")
    ph = farm_state.devices.get("PH_01")

    if tank and tank.latest is not None:
        level = tank.latest.get("level")
        if level is not None and level < GUARDRAILS["min_tank_level_to_irrigate"]:
            return {"allowed": False,
                    "reason": f"VETO: mực nước bồn ({level}%) dưới ngưỡng an toàn "
                               f"({GUARDRAILS['min_tank_level_to_irrigate']}%)."}

    if ph and ph.latest is not None:
        ph_val = ph.latest.get("ph")
        lo, hi = GUARDRAILS["ph_safe_range"]
        if ph_val is not None and not (lo <= ph_val <= hi):
            return {"allowed": False,
                    "reason": f"VETO: pH nước ({ph_val}) ngoài khoảng an toàn ({lo}-{hi})."}

    return {"allowed": True, "reason": "Đạt điều kiện guardrail."}


def check_pump_guardrail() -> dict:
    pump = farm_state.devices.get("PUMP_01")
    if pump and pump.latest is not None:
        power = pump.latest.get("power")
        if power is not None and power > GUARDRAILS["max_pump_power_w"]:
            return {"allowed": False,
                    "reason": f"VETO: công suất bơm ({power}W) vượt ngưỡng vật lý an toàn "
                               f"({GUARDRAILS['max_pump_power_w']}W) — nghi bơm kẹt/lỗi."}
    return {"allowed": True, "reason": "Đạt điều kiện guardrail."}


# ---------------------------------------------------------------------------
# Tool 1: Tạo kế hoạch tưới (Kịch bản 1)
# ---------------------------------------------------------------------------
def create_irrigation_plan(
    zone: str,
    scheduled_time: str,
    priority: str,
    rationale: str,
    used_devices: list[str],
    duration_minutes: int = 20,
    require_approval: bool = True,
) -> dict:
    """Tool/API: Action Agent gọi hàm này SAU KHI Irrigation Planning Agent + Resource Agent
    đã quyết định thời điểm/ưu tiên. Hàm này KHÔNG tự quyết định gì — chỉ thực thi + guardrail + verify.
    """
    guard = check_irrigation_guardrail()
    if not guard["allowed"]:
        raise GuardrailRejected(guard["reason"])

    plan_id = farm_state.new_id("PLAN")
    snapshot = {d: farm_state.devices[d].latest for d in used_devices if d in farm_state.devices}

    plan = {
        "plan_id": plan_id,
        "type": "irrigation_plan",
        "zone": zone,
        "scheduled_time": scheduled_time,
        "priority": priority,
        "duration_minutes": duration_minutes,
        "rationale": rationale,
        "used_devices": used_devices,
        "data_snapshot": snapshot,     # dữ liệu IoT thực tế đã dùng để quyết định
        "status": "pending_approval" if require_approval else "confirmed",
        "created_at": _now_iso(),
        "guardrail_check": guard,
    }
    farm_state.plans[plan_id] = plan

    # Verification: đọc lại ngay để đảm bảo đã lưu đúng
    verified = farm_state.plans.get(plan_id)
    assert verified is not None and verified["plan_id"] == plan_id, "Verification thất bại"

    return plan


def approve_plan(plan_id: str, approved_by: str = "manager") -> dict:
    """Human-in-the-loop: người quản lý xác nhận kế hoạch (Dual-Mode Execution)."""
    plan = farm_state.plans.get(plan_id)
    if not plan:
        raise ValueError(f"Không tìm thấy plan {plan_id}")
    plan["status"] = "confirmed"
    plan["approved_by"] = approved_by
    plan["approved_at"] = _now_iso()
    return plan


# ---------------------------------------------------------------------------
# Tool 2: Tạo nhiệm vụ kiểm tra hiện trường (Kịch bản 2 & 3)
# ---------------------------------------------------------------------------
def create_inspection_task(
    title: str,
    zone: str,
    reason: str,
    used_devices: list[str],
    severity: str = "normal",       # normal | urgent
    assigned_to: str = "field_team",
) -> dict:
    """Tool/API: tạo phiếu kiểm tra ngoài hiện trường. Dùng cho:
    - Kịch bản 2: kết quả tưới không như mong đợi.
    - Kịch bản 3: cảm biến ngừng cập nhật -> cần người ra kiểm tra kết nối.
    """
    task_id = farm_state.new_id("TASK")
    snapshot = {d: farm_state.devices[d].latest for d in used_devices if d in farm_state.devices}
    stale_flags = {d: farm_state.devices[d].is_stale for d in used_devices if d in farm_state.devices}

    task = {
        "task_id": task_id,
        "type": "inspection_task",
        "title": title,
        "zone": zone,
        "reason": reason,
        "severity": severity,
        "assigned_to": assigned_to,
        "used_devices": used_devices,
        "data_snapshot": snapshot,
        "stale_flags": stale_flags,   # rõ ràng ghi nhận thiết bị nào đang mất kết nối
        "status": "open",
        "created_at": _now_iso(),
    }
    farm_state.tasks[task_id] = task

    verified = farm_state.tasks.get(task_id)
    assert verified is not None and verified["task_id"] == task_id, "Verification thất bại"

    return task


def complete_task(task_id: str, resolution_note: str) -> dict:
    task = farm_state.tasks.get(task_id)
    if not task:
        raise ValueError(f"Không tìm thấy task {task_id}")
    task["status"] = "completed"
    task["resolution_note"] = resolution_note
    task["completed_at"] = _now_iso()
    return task


# ---------------------------------------------------------------------------
# Tool 3: Gửi thông báo
# ---------------------------------------------------------------------------
def send_notification(message: str, channel: str = "dashboard", severity: str = "info") -> dict:
    note = {
        "notification_id": farm_state.new_id("NOTI"),
        "message": message,
        "channel": channel,
        "severity": severity,
        "created_at": _now_iso(),
    }
    farm_state.notifications.append(note)
    return note


# ---------------------------------------------------------------------------
# Tool 4: Báo cáo canh tác (tổng hợp cho kỹ sư nông nghiệp - persona phụ)
# ---------------------------------------------------------------------------
def generate_report(zone: str | None = None) -> dict:
    """Tổng hợp: dữ liệu hiện tại, kế hoạch, nhiệm vụ, thiết bị stale.
    KHÔNG bịa số liệu cho thiết bị stale — chỉ báo cáo 'thiếu dữ liệu, cần xác minh'."""
    readable = farm_state.readable_devices()
    stale = farm_state.stale_devices()

    plans = [p for p in farm_state.plans.values() if zone is None or p.get("zone") == zone]
    tasks = [t for t in farm_state.tasks.values() if zone is None or t.get("zone") == zone]

    return {
        "generated_at": _now_iso(),
        "zone": zone,
        "devices_reporting": readable,
        "devices_stale_or_missing": stale,
        "data_completeness": f"{len(readable)}/{len(farm_state.devices)}",
        "plans": plans,
        "tasks": tasks,
        "note": (
            "Các thiết bị trong 'devices_stale_or_missing' không có dữ liệu đủ mới; "
            "báo cáo này KHÔNG suy diễn giá trị cho các thiết bị đó."
        ),
    }
