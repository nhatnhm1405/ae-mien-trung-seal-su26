"""
main.py — Backend DUY NHẤT cho Smart Agriculture (Track B).

Đây là kết quả hợp nhất hai backend từng chạy song song và tranh nhau cổng 8000:
`back-end/main.py` (MQTT thật + nghiệp vụ + Swagger) và `llm-test/app/main.py`
(state + agents + simulator). Một process, một kho dữ liệu (`farm_state`), một
đường ống (`pipeline.on_reading`), một format sự kiện (`app/events.py`).

Chạy dev/test (không cần broker, tự sinh dữ liệu giả):
    cd back-end
    uvicorn app.main:app --reload --port 8000

Chạy với broker thật của BTC:
    cd back-end
    # điền MQTT_* trong .env trước
    SIMULATE=false uvicorn app.main:app --host 0.0.0.0 --port 8000

Trước khi chạy lần đầu, train model để tầng phát hiện bất thường có tác dụng:
    python -m app.ml.train_anomaly_model
    python -m app.ml.train_irrigation_model
"""

from __future__ import annotations

import asyncio
import logging
import os
import threading
import time
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app import events, pipeline, tools
from app.agents import coordinator_agent, irrigation_resource_agent
from app.config import TRACK_B_DEVICES
from app.mqtt_client import (
    freeze_device,
    inject_anomaly,
    mqtt_status,
    run_mqtt_client,
    set_reading_handler,
    start_simulator,
    unfreeze_device,
)
from app.services import resource_service, verification_service
from app.state import farm_state

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
)
logger = logging.getLogger("main")

SIMULATE = os.environ.get("SIMULATE", "true").lower() in ("true", "1", "yes")

_sim_stop_event: threading.Event | None = None


# ══════════════════════════════════════════════════════
# Lifecycle
# ══════════════════════════════════════════════════════

@asynccontextmanager
async def lifespan(app: FastAPI):
    global _sim_stop_event

    # 1. Cho tầng sự kiện biết event loop chính, để thread MQTT đẩy được WebSocket.
    events.bind_loop(asyncio.get_running_loop())

    # 2. Gắn pipeline làm handler cho MỌI bản ghi telemetry. Đây là dòng nối
    #    ingest -> ML -> Agent; thiếu nó thì dữ liệu vào state rồi nằm im.
    set_reading_handler(pipeline.on_reading)

    # 3. Nguồn dữ liệu: simulator (dev) hoặc broker thật (thi đấu).
    if SIMULATE:
        _, _sim_stop_event = start_simulator(interval_seconds=3.0)
        logger.info("SIMULATE=true — đang dùng dữ liệu giả lập, KHÔNG phải MQTT thật.")
    else:
        # Chạy cùng process với uvicorn (thread nền), không tách tiến trình:
        # farm_state là biến RAM, process riêng sẽ không chia sẻ được dữ liệu.
        threading.Thread(target=run_mqtt_client, daemon=True, name="mqtt").start()
        logger.info("SIMULATE=false — đã khởi động MQTT client thật trong thread nền.")

    yield

    if _sim_stop_event:
        _sim_stop_event.set()
    logger.info("Backend shutdown hoàn tất.")


tags_metadata = [
    {"name": "1. Hệ thống", "description": "Health check, trạng thái kết nối MQTT."},
    {"name": "2. Telemetry", "description": "Dữ liệu realtime từ cảm biến IoT."},
    {"name": "3. Kế hoạch tưới", "description": "Lập & phê duyệt kế hoạch tưới (human-in-the-loop)."},
    {"name": "4. Nhiệm vụ & Verification", "description": "Phiếu kiểm tra hiện trường và xác minh sau hành động."},
    {"name": "5. Tài nguyên", "description": "Bồn nước, ngân sách nước, nhân sự."},
    {"name": "6. Phân tích & AI", "description": "Khuyến nghị từ model, chẩn đoán của Agent."},
    {"name": "7. Demo", "description": "Bơm sự cố / ngắt cảm biến theo ý muốn khi pitch."},
]

app = FastAPI(
    title="AE_MIEN_TRUNG — Smart Agriculture Backend",
    description="Backend hợp nhất: MQTT ingest + windowing + anomaly detection + multi-agent LLM.",
    version="3.0.0",
    lifespan=lifespan,
    openapi_tags=tags_metadata,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # demo/hackathon
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _scenario() -> str:
    return mqtt_status.get("last_scenario", "NORMAL")


# ══════════════════════════════════════════════════════
# 1. Hệ thống
# ══════════════════════════════════════════════════════

@app.get("/", tags=["1. Hệ thống"])
def root():
    return {
        "service": "AE_MIEN_TRUNG Smart Agriculture Backend",
        "status": "running",
        "track": "Track B: Smart Agriculture",
        "mode": "SIMULATE" if SIMULATE else "MQTT_LIVE",
        "docs": "/docs",
        "websocket": "/ws/telemetry",
    }


@app.get("/api/health", tags=["1. Hệ thống"])
def health_check():
    return {
        "status": "healthy",
        "mode": "SIMULATE" if SIMULATE else "MQTT_LIVE",
        "mqtt": mqtt_status,
        "websocket_clients": events.ws_manager.connection_count,
        "plans": len(farm_state.plans),
        "tasks": len(farm_state.tasks),
    }


@app.get("/api/status", tags=["1. Hệ thống"])
def get_status():
    """Tự chấm điều kiện chấp nhận của đề: tối thiểu 4/6 thiết bị Track B có dữ liệu."""
    readable = farm_state.readable_devices()
    track_b_readable = [c for c in readable if c in TRACK_B_DEVICES]
    return {
        "readable_devices": readable,
        "stale_devices": farm_state.stale_devices(),
        "total_devices": len(farm_state.devices),
        "track_b_readable": f"{len(track_b_readable)}/{len(TRACK_B_DEVICES)}",
        "meets_minimum": len(track_b_readable) >= 4,
        "scenario": _scenario(),
    }


# ══════════════════════════════════════════════════════
# 2. Telemetry
# ══════════════════════════════════════════════════════

@app.get("/api/devices", tags=["2. Telemetry"])
def get_devices():
    """Trạng thái + dữ liệu mới nhất + rolling stats (mean/std/slope) của tất cả thiết bị."""
    return farm_state.snapshot()


@app.get("/api/devices/{device_code}", tags=["2. Telemetry"])
def get_device(device_code: str):
    code = device_code.upper()
    snap = farm_state.snapshot()
    if code not in snap:
        raise HTTPException(404, f"Không có thiết bị {device_code}")
    return snap[code]


@app.get("/api/devices/{device_code}/history", tags=["2. Telemetry"])
def get_device_history(device_code: str, limit: int = Query(default=200, ge=1, le=1000)):
    code = device_code.upper()
    if code not in farm_state.devices:
        raise HTTPException(404, f"Không có thiết bị {device_code}")
    buf = list(farm_state.devices[code].buffer)[-limit:]
    return {"device_code": code, "count": len(buf), "records": buf}


# ══════════════════════════════════════════════════════
# 3. Kế hoạch tưới
# ══════════════════════════════════════════════════════

class CreatePlanRequest(BaseModel):
    zone: str
    scheduled_time: str
    priority: str
    rationale: str
    used_devices: list[str]
    duration_minutes: int = 20
    require_approval: bool = True


@app.post("/api/irrigation/plans", tags=["3. Kế hoạch tưới"])
async def create_plan(req: CreatePlanRequest):
    try:
        plan = tools.create_irrigation_plan(**req.model_dump())
    except tools.GuardrailRejected as exc:
        # Guardrail cứng phủ quyết — báo cho dashboard biết để hiện "VETO".
        await events.emit("guardrail_veto", {"action": "create_irrigation_plan", "reason": str(exc)})
        raise HTTPException(status_code=403, detail=str(exc))
    await events.emit("plan", plan)
    return plan


@app.get("/api/irrigation/plans", tags=["3. Kế hoạch tưới"])
def list_plans(status: Optional[str] = None):
    plans = list(farm_state.plans.values())
    if status:
        plans = [p for p in plans if p.get("status", "").lower() == status.lower()]
    return {"total": len(plans), "plans": plans}


@app.get("/api/irrigation/plans/{plan_id}", tags=["3. Kế hoạch tưới"])
def get_plan(plan_id: str):
    plan = farm_state.plans.get(plan_id)
    if not plan:
        raise HTTPException(404, f"Không tìm thấy plan {plan_id}")
    return plan


@app.post("/api/irrigation/plans/{plan_id}/approve", tags=["3. Kế hoạch tưới"])
async def approve_plan(plan_id: str, approved_by: str = "Người quản lý nông trại"):
    """Human-in-the-loop. Duyệt xong tự sinh phiếu công việc cho đội hiện trường."""
    try:
        plan = tools.approve_plan(plan_id, approved_by)
    except ValueError as exc:
        raise HTTPException(404, str(exc))

    task = tools.create_inspection_task(
        title=f"Thực thi lịch tưới {plan['zone']} — {plan['duration_minutes']} phút",
        zone=plan["zone"],
        reason=f"Kế hoạch {plan_id} đã được {approved_by} phê duyệt. Lý do: {plan['rationale']}",
        used_devices=plan.get("used_devices", ["PUMP_01"]),
        severity="normal",
    )

    await events.emit("plan", plan)
    await events.emit("task", task)
    return {"plan": plan, "task": task}


@app.post("/api/irrigation/plans/{plan_id}/reject", tags=["3. Kế hoạch tưới"])
async def reject_plan(plan_id: str, rejected_by: str = "Người quản lý nông trại", reason: str = ""):
    try:
        plan = tools.reject_plan(plan_id, rejected_by, reason)
    except ValueError as exc:
        raise HTTPException(404, str(exc))
    await events.emit("plan", plan)
    return plan


# ══════════════════════════════════════════════════════
# 4. Nhiệm vụ & Verification
# ══════════════════════════════════════════════════════

class CreateTaskRequest(BaseModel):
    title: str
    zone: str
    reason: str
    used_devices: list[str]
    severity: str = "normal"
    assigned_to: str = "field_team"


@app.post("/api/tasks", tags=["4. Nhiệm vụ & Verification"])
async def create_task(req: CreateTaskRequest):
    task = tools.create_inspection_task(**req.model_dump())
    await events.emit("task", task)
    return task


@app.get("/api/tasks", tags=["4. Nhiệm vụ & Verification"])
def list_tasks(status: Optional[str] = None):
    tasks = list(farm_state.tasks.values())
    if status:
        tasks = [t for t in tasks if t.get("status", "").lower() == status.lower()]
    return {"total": len(tasks), "tasks": tasks}


@app.get("/api/tasks/{task_id}", tags=["4. Nhiệm vụ & Verification"])
def get_task(task_id: str):
    task = farm_state.tasks.get(task_id)
    if not task:
        raise HTTPException(404, f"Không tìm thấy task {task_id}")
    return task


@app.post("/api/tasks/{task_id}/complete", tags=["4. Nhiệm vụ & Verification"])
async def complete_task(task_id: str, resolution_note: str):
    try:
        task = tools.complete_task(task_id, resolution_note)
    except ValueError as exc:
        raise HTTPException(404, str(exc))
    await events.emit("task", task)
    return task


@app.post("/api/tasks/{task_id}/verify", tags=["4. Nhiệm vụ & Verification"])
async def verify_task(task_id: str, verified_by: str = "Verification Agent", notes: str = ""):
    """Xác minh post-action kèm chứng cứ telemetry thật tại thời điểm xác minh."""
    task = farm_state.tasks.get(task_id)
    if not task:
        raise HTTPException(404, f"Không tìm thấy task {task_id}")

    proof = verification_service.verify_action(
        action_id=task_id,
        action_type=task.get("type", "inspection_task"),
        telemetry_snapshot=farm_state.summary(scenario=_scenario()),
        verified_by=verified_by,
        notes=notes,
    )
    task["status"] = "verified"
    task["verification_proof"] = proof

    await events.emit("task", task)
    return {"task": task, "verification_proof": proof}


# ══════════════════════════════════════════════════════
# 5. Tài nguyên
# ══════════════════════════════════════════════════════

@app.get("/api/resources/water-budget", tags=["5. Tài nguyên"])
def get_water_budget():
    tank = farm_state.devices["TANK_01"].latest or {}
    pump = farm_state.devices["PUMP_01"].latest or {}
    return {
        "timestamp": time.time(),
        "water_resource": resource_service.evaluate_water_resource(
            tank_level_percent=tank.get("level", 0.0),
            flow_rate_lmin=pump.get("flow_rate", 0.0),
        ),
    }


@app.get("/api/resources/staff", tags=["5. Tài nguyên"])
def get_field_staff():
    staff = resource_service.get_field_staff()
    return {"total": len(staff), "staff": staff}


# ══════════════════════════════════════════════════════
# 6. Phân tích & AI
# ══════════════════════════════════════════════════════

@app.get("/api/analytics/irrigation-recommendation", tags=["6. Phân tích & AI"])
def irrigation_recommendation():
    """Khuyến nghị tưới — dựa trên MODEL, không phải ngưỡng hardcode.

    Ba tầng, tách bạch để khi pitch nói được rõ cái nào là AI cái nào không:
      1. `ml_forecast`  — GradientBoostingRegressor dự đoán tốc độ bay hơi -> còn
         bao lâu đất chạm ngưỡng khô. Đây là chỗ nói "cảnh báo trước N giờ".
      2. `anomaly`      — z-score trên sliding window 300s, ngưỡng tự học từ chính
         dữ liệu gần đây chứ không phải con số cố định.
      3. `safety_checks`— kiểm tra nhất quán vật lý (bơm có điện mà không có nước).
         Cái này CỐ TÌNH là luật cứng: nó là guardrail, không phải phần AI.
    """
    assessment = irrigation_resource_agent.assess_irrigation_need(zone="A")

    soil = farm_state.devices["SOIL_01"].latest or {}
    weather = farm_state.devices["WEATHER_01"].latest or {}
    sun = farm_state.devices["SUN_01"].latest or {}
    pump = farm_state.devices["PUMP_01"].latest or {}
    tank = farm_state.devices["TANK_01"].latest or {}

    ml_forecast: dict = {"available": False, "reason": "Chưa train irrigation model."}
    try:
        from app.ml.irrigation_model import predict as predict_irrigation

        ml_forecast = predict_irrigation({
            "soil_moisture": soil.get("soil_moisture"),
            "temperature": weather.get("temperature") or soil.get("temperature"),
            "humidity": weather.get("humidity"),
            "lux": sun.get("lux"),
        })
        ml_forecast["available"] = True
    except FileNotFoundError:
        pass
    except Exception as exc:
        ml_forecast = {"available": False, "reason": str(exc)}

    # Kiểm tra nhất quán vật lý — deterministic guardrail, không phải AI.
    safety_checks = []
    flow = pump.get("flow_rate")
    power = pump.get("power")
    level = tank.get("level")
    if power is not None and flow is not None and power > 100 and flow < 0.5:
        safety_checks.append({
            "code": "PUMP_FAILURE",
            "level": "CRITICAL",
            "message": "Bơm PUMP_01 đang tiêu thụ điện nhưng lưu lượng bằng 0 — nghi bơm hỏng hoặc tắc đường ống.",
            "suggested_action": "CREATE_INSPECTION_TASK",
        })
    if level is not None and flow is not None and flow > 0 and level < 15.0:
        safety_checks.append({
            "code": "LOW_WATER_SUPPLY",
            "level": "HIGH",
            "message": f"Bồn TANK_01 còn {level}% (<15%) trong khi vẫn đang bơm — cần dừng để bảo vệ thiết bị.",
            "suggested_action": "STOP_PUMP",
        })

    stale = farm_state.stale_devices()
    if stale:
        safety_checks.append({
            "code": "SENSOR_STALE",
            "level": "WARNING",
            "message": f"{len(stale)} thiết bị gián đoạn dữ liệu: {', '.join(stale)}. Hệ thống chạy ở chế độ partial.",
            "suggested_action": "VERIFY_SENSOR_CONNECTIVITY",
        })

    return {
        "timestamp": time.time(),
        "scenario": _scenario(),
        "should_irrigate": assessment["should_irrigate"],
        "priority": assessment["priority"],
        "anomaly": assessment["soil_anomaly"],
        "guardrail": assessment["guardrail"],
        "ml_forecast": ml_forecast,
        "safety_checks": safety_checks,
        "rationale": assessment["rationale"],
        "stale_devices": stale,
    }


@app.get("/api/analytics/llm-context", tags=["6. Phân tích & AI"])
def llm_context():
    """Context rút gọn cho prompt Agent — nhẹ hơn /api/devices (không có rolling)."""
    summary = farm_state.summary(scenario=_scenario())
    plans = list(farm_state.plans.values())
    tasks = list(farm_state.tasks.values())
    return {
        "timestamp": summary["timestamp"],
        "scenario": summary["scenario"],
        "mqtt_connected": mqtt_status.get("connected", False),
        "devices": summary["devices"],
        "active_devices": summary["active_devices"],
        "stale_devices": summary["stale_devices"],
        "plans": {
            "total": len(plans),
            "pending_approval": [p for p in plans if p.get("status") == "pending_approval"],
        },
        "tasks": {"total": len(tasks), "open": [t for t in tasks if t.get("status") == "open"]},
    }


class AgentRequest(BaseModel):
    message: str


@app.post("/api/agent/request", tags=["6. Phân tích & AI"])
async def agent_request(req: AgentRequest):
    """Người quản lý hỏi bằng tiếng Việt; Coordinator điều phối các Agent con,
    gọi tool thật, rồi trả câu trả lời kèm trace các tool đã dùng."""
    result = coordinator_agent.handle_request(req.message)

    for call in result.get("trace", []):
        payload = call.get("result") or {}
        if call.get("tool") == "create_irrigation_plan" and "plan_id" in payload:
            await events.emit("plan", payload)
        elif call.get("tool") == "create_inspection_task" and "task_id" in payload:
            await events.emit("task", payload)
        elif call.get("tool") == "send_notification" and "notification_id" in payload:
            await events.emit("notification", payload)

    return result


@app.get("/api/agent/insights", tags=["6. Phân tích & AI"])
def agent_insights(limit: int = Query(default=20, ge=1, le=pipeline.INSIGHT_LOG_MAXLEN)):
    """Incident Log — mọi chẩn đoán mà pipeline tự sinh khi phát hiện bất
    thường, mới nhất trước. Đây là bước 8 trong sequence diagram của BTC
    ("Agent cập nhật Incident Log và giải thích quyết định lên Dashboard") —
    trước đây chỉ giữ đúng 1 bản ghi, chẩn đoán trước bị chẩn đoán sau ghi đè
    và không xem lại được. Dashboard gọi cái này lúc mới load để không trống
    trơn, và làm phương án dự phòng khi LLM hết quota giữa buổi demo."""
    insights = pipeline.get_insights(limit)
    return {"available": len(insights) > 0, "insights": insights}


@app.get("/api/agent/debug/assess-irrigation", tags=["6. Phân tích & AI"])
def debug_assess_irrigation(zone: str = "A"):
    """DEBUG — gọi thẳng Irrigation & Resource Agent, không qua LLM. Dùng để test
    logic z-score/guardrail tức thì, tránh race với simulator (LLM mất 1-3s, đủ
    để simulator tick đè lên giá trị vừa inject)."""
    return irrigation_resource_agent.assess_irrigation_need(zone)


@app.post("/api/notifications", tags=["6. Phân tích & AI"])
async def send_notification(message: str, channel: str = "dashboard", severity: str = "info"):
    note = tools.send_notification(message, channel, severity)
    await events.emit("notification", note)
    return note


@app.get("/api/report", tags=["6. Phân tích & AI"])
def report(zone: Optional[str] = None):
    return tools.generate_report(zone)


# ══════════════════════════════════════════════════════
# 7. Demo helpers
# ══════════════════════════════════════════════════════

class InjectRequest(BaseModel):
    device_code: str
    metrics: dict


@app.post("/api/simulate/inject", tags=["7. Demo"])
def simulate_inject(req: InjectRequest):
    """Nút "Bơm sự cố" cho lúc pitch. Giá trị bơm vào đi qua đúng đường ống như
    dữ liệu thật (state -> ML -> Agent), nên hệ thống phản ứng y hệt sự cố thật.

    VD body: {"device_code": "SOIL_01", "metrics": {"soil_moisture": 3.0}}
    """
    code = req.device_code.upper()
    if code not in farm_state.devices:
        raise HTTPException(404, f"Không có thiết bị {code}")
    record = inject_anomaly(code, req.metrics)
    return {"injected": True, "device_code": code, "record": record}


@app.post("/api/simulate/freeze/{device_code}", tags=["7. Demo"])
def simulate_freeze(device_code: str):
    """Giả lập cảm biến ngừng gửi dữ liệu (Kịch bản 3). Giữ stale thật sự cho tới
    khi unfreeze — simulator sẽ bỏ qua thiết bị này."""
    code = device_code.upper()
    if code not in farm_state.devices:
        raise HTTPException(404, f"Không có thiết bị {code}")
    freeze_device(code)
    farm_state.devices[code].last_seen_ts = 0  # ép is_stale = True ngay
    return {"frozen": code, "is_stale": farm_state.devices[code].is_stale}


@app.post("/api/simulate/unfreeze/{device_code}", tags=["7. Demo"])
def simulate_unfreeze(device_code: str):
    code = device_code.upper()
    if code not in farm_state.devices:
        raise HTTPException(404, f"Không có thiết bị {code}")
    unfreeze_device(code)
    return {"unfrozen": code}


# ══════════════════════════════════════════════════════
# WebSocket — kênh realtime duy nhất
# ══════════════════════════════════════════════════════

@app.websocket("/ws/telemetry")
async def ws_telemetry(websocket: WebSocket):
    """Mọi message đều theo envelope {type, ts, payload} — xem app/events.py.

    Client nhận `snapshot` ngay khi kết nối (để vẽ được màn hình đầu tiên mà
    không cần gọi REST), sau đó nhận `telemetry` / `anomaly` / `agent_insight` /
    `plan` / `task` đẩy theo sự kiện, xen kẽ `snapshot` định kỳ 10s làm nhịp tim
    và để client tự đồng bộ lại nếu lỡ mất message.
    """
    await events.ws_manager.connect(websocket)
    try:
        await events.ws_manager.send_json(
            websocket, events.envelope("snapshot", farm_state.snapshot())
        )
        while True:
            await asyncio.sleep(10)
            await events.ws_manager.send_json(
                websocket, events.envelope("snapshot", farm_state.snapshot())
            )
    except WebSocketDisconnect:
        events.ws_manager.disconnect(websocket)
    except Exception as exc:
        logger.debug("WebSocket đóng bất thường: %s", exc)
        events.ws_manager.disconnect(websocket)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True, log_level="info")
