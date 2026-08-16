"""
Backend chính: FastAPI + WebSocket. Đây là "hai container bên phải" mà đội
phải tự viết (weather-stream-engine + weather-web-dashboard tương đương,
áp dụng cho domain Smart Agriculture).

Chạy dev/test (không cần broker thật):
    uvicorn app.main:app --reload --port 8000
    (mặc định tự bật simulator nội bộ — xem biến SIMULATE bên dưới)

Chạy thi thật (có broker BTC):
    1. Sửa app/config.py: MQTT_BROKER_HOST/PORT/TOPIC_PREFIX
    2. SIMULATE=false uvicorn app.main:app --port 8000
    3. Chạy song song: python -m app.mqtt_client   (kết nối broker thật)
"""

from __future__ import annotations

import os
import asyncio
import json
import logging
from typing import Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.state import farm_state
from app.mqtt_client import start_simulator, inject_anomaly, freeze_device, unfreeze_device
from app import tools
from app.agents import coordinator_agent, irrigation_resource_agent

logger = logging.getLogger("main")
logging.basicConfig(level=logging.INFO)

SIMULATE = os.environ.get("SIMULATE", "true").lower() == "true"

app = FastAPI(title="Smart Agriculture — Data/Backend API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # demo/hackathon — thu hẹp lại nếu có thời gian
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Simulator lifecycle (chỉ dùng dev/test)
# ---------------------------------------------------------------------------
_sim_thread = None
_sim_stop_event = None


@app.on_event("startup")
def on_startup():
    global _sim_thread, _sim_stop_event
    if SIMULATE:
        _sim_thread, _sim_stop_event = start_simulator(interval_seconds=3.0)
        logger.info("SIMULATE=true -> đang dùng dữ liệu giả lập, không phải MQTT thật.")
    else:
        logger.info("SIMULATE=false -> chạy app/mqtt_client.py song song để nhận dữ liệu thật.")


# ---------------------------------------------------------------------------
# REST: đọc dữ liệu thiết bị (Field IoT Agent, Frontend đều gọi endpoint này)
# ---------------------------------------------------------------------------
@app.get("/api/devices")
def get_devices():
    """Trạng thái + dữ liệu mới nhất + rolling stats của tất cả thiết bị."""
    return farm_state.snapshot()


@app.get("/api/devices/{device_code}")
def get_device(device_code: str):
    snap = farm_state.snapshot()
    if device_code not in snap:
        raise HTTPException(404, f"Không có thiết bị {device_code}")
    return snap[device_code]


@app.get("/api/devices/{device_code}/history")
def get_device_history(device_code: str, limit: int = 200):
    if device_code not in farm_state.devices:
        raise HTTPException(404, f"Không có thiết bị {device_code}")
    buf = list(farm_state.devices[device_code].buffer)[-limit:]
    return {"device_code": device_code, "count": len(buf), "records": buf}


@app.get("/api/status")
def get_status():
    """Dùng để tự-chấm điều kiện chấp nhận 'tối thiểu 4/6 thiết bị có dữ liệu'."""
    return {
        "readable_devices": farm_state.readable_devices(),
        "stale_devices": farm_state.stale_devices(),
        "total_devices": len(farm_state.devices),
    }


# ---------------------------------------------------------------------------
# REST: Tool/API cho Agent — Irrigation plan
# ---------------------------------------------------------------------------
class CreatePlanRequest(BaseModel):
    zone: str
    scheduled_time: str
    priority: str
    rationale: str
    used_devices: list[str]
    duration_minutes: int = 20
    require_approval: bool = True


@app.post("/api/irrigation/plan")
async def api_create_plan(req: CreatePlanRequest):
    try:
        plan = tools.create_irrigation_plan(**req.dict())
    except tools.GuardrailRejected as e:
        raise HTTPException(status_code=403, detail=str(e))
    await broadcast({"event": "plan_created", "data": plan})
    return plan


@app.get("/api/irrigation/plan")
def api_list_plans():
    return list(farm_state.plans.values())


@app.get("/api/irrigation/plan/{plan_id}")
def api_get_plan(plan_id: str):
    plan = farm_state.plans.get(plan_id)
    if not plan:
        raise HTTPException(404, "Không tìm thấy plan")
    return plan  # đây chính là bước "verification": đọc lại sau khi tạo


@app.post("/api/irrigation/plan/{plan_id}/approve")
def api_approve_plan(plan_id: str, approved_by: str = "manager"):
    try:
        plan = tools.approve_plan(plan_id, approved_by)
    except ValueError as e:
        raise HTTPException(404, str(e))
    return plan


# ---------------------------------------------------------------------------
# REST: Tool/API cho Agent — Inspection task
# ---------------------------------------------------------------------------
class CreateTaskRequest(BaseModel):
    title: str
    zone: str
    reason: str
    used_devices: list[str]
    severity: str = "normal"
    assigned_to: str = "field_team"


@app.post("/api/tasks")
async def api_create_task(req: CreateTaskRequest):
    task = tools.create_inspection_task(**req.dict())
    await broadcast({"event": "task_created", "data": task})
    return task


@app.get("/api/tasks")
def api_list_tasks():
    return list(farm_state.tasks.values())


@app.get("/api/tasks/{task_id}")
def api_get_task(task_id: str):
    task = farm_state.tasks.get(task_id)
    if not task:
        raise HTTPException(404, "Không tìm thấy task")
    return task


@app.post("/api/tasks/{task_id}/complete")
def api_complete_task(task_id: str, resolution_note: str):
    try:
        task = tools.complete_task(task_id, resolution_note)
    except ValueError as e:
        raise HTTPException(404, str(e))
    return task


# ---------------------------------------------------------------------------
# REST: Notification + Report
# ---------------------------------------------------------------------------
@app.post("/api/notifications")
async def api_send_notification(message: str, channel: str = "dashboard", severity: str = "info"):
    note = tools.send_notification(message, channel, severity)
    await broadcast({"event": "notification", "data": note})
    return note


@app.get("/api/report")
def api_report(zone: Optional[str] = None):
    return tools.generate_report(zone)


# ---------------------------------------------------------------------------
# REST: Multi-Agent — điểm vào duy nhất gọi LLM (Farm Coordinator & Action Agent)
# ---------------------------------------------------------------------------
class AgentRequest(BaseModel):
    message: str


@app.post("/api/agent/request")
async def api_agent_request(req: AgentRequest):
    """Nhận 1 yêu cầu tiếng Việt của người quản lý (VD: 'chuẩn bị kế hoạch tưới khu A hôm
    nay'), Coordinator & Action Agent tự điều phối Field IoT Agent + Irrigation & Resource
    Agent, gọi Tool/API tương ứng, rồi trả câu trả lời + trace các tool đã dùng."""
    result = coordinator_agent.handle_request(req.message)

    # Đẩy realtime cho dashboard dựa trên các tool Action đã thực sự chạy thành công
    # trong lúc Agent xử lý (bỏ qua nếu tool đó lỗi/bị guardrail chặn).
    for call in result["trace"]:
        tool_name = call["tool"]
        payload = call["result"]
        if tool_name == "create_irrigation_plan" and "plan_id" in payload:
            await broadcast({"event": "plan_created", "data": payload})
        elif tool_name == "create_inspection_task" and "task_id" in payload:
            await broadcast({"event": "task_created", "data": payload})
        elif tool_name == "send_notification" and "notification_id" in payload:
            await broadcast({"event": "notification", "data": payload})

    return result


@app.get("/api/agent/debug/assess-irrigation")
def api_debug_assess_irrigation(zone: str = "A"):
    """DEBUG — gọi thẳng Irrigation & Resource Agent (không qua LLM), dùng để test
    logic z-score/guardrail ngay lập tức, tránh race condition với simulator (LLM
    thật mất 1-3s round-trip, đủ để simulator nền tick đè giá trị vừa inject)."""
    return irrigation_resource_agent.assess_irrigation_need(zone)


# ---------------------------------------------------------------------------
# REST: Demo helpers — nút "bơm dữ liệu bất thường" bắt buộc phải có cho pitch
# ---------------------------------------------------------------------------
@app.post("/api/simulate/inject")
async def api_inject(device_code: str, overrides: dict):
    """VD: POST /api/simulate/inject?device_code=SOIL_01  body: {"soil_moisture": 3.0}
    Dùng trong pitch để demo hệ thống tự phát hiện bất thường theo yêu cầu ngay lúc trình bày."""
    if device_code not in farm_state.devices:
        raise HTTPException(404, f"Không có thiết bị {device_code}")
    record = inject_anomaly(device_code, overrides)
    await broadcast({"event": "telemetry", "device_code": device_code, "data": record})
    return {"injected": True, "device_code": device_code, "record": record}


@app.post("/api/simulate/freeze/{device_code}")
def api_freeze_device(device_code: str):
    """Giả lập thiết bị ngừng gửi dữ liệu (kịch bản 3) — không xoá lịch sử, và simulator sẽ
    KHÔNG ghi đè thiết bị này nữa (giữ stale thật sự) cho tới khi gọi /unfreeze."""
    if device_code not in farm_state.devices:
        raise HTTPException(404, f"Không có thiết bị {device_code}")
    freeze_device(device_code)
    farm_state.devices[device_code].last_seen_ts = 0  # ép is_stale = True ngay lập tức
    return {"frozen": device_code, "is_stale": farm_state.devices[device_code].is_stale}


@app.post("/api/simulate/unfreeze/{device_code}")
def api_unfreeze_device(device_code: str):
    """Bỏ freeze — simulator ghi dữ liệu lại bình thường cho thiết bị này."""
    if device_code not in farm_state.devices:
        raise HTTPException(404, f"Không có thiết bị {device_code}")
    unfreeze_device(device_code)
    return {"unfrozen": device_code}


# ---------------------------------------------------------------------------
# WebSocket: đẩy dữ liệu realtime cho Frontend dashboard
# ---------------------------------------------------------------------------
class ConnectionManager:
    def __init__(self):
        self.active: list[WebSocket] = []

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.active.append(ws)

    def disconnect(self, ws: WebSocket):
        if ws in self.active:
            self.active.remove(ws)

    async def broadcast(self, message: dict):
        dead = []
        for ws in self.active:
            try:
                await ws.send_text(json.dumps(message, default=str))
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)


manager = ConnectionManager()


async def broadcast(message: dict):
    await manager.broadcast(message)


@app.websocket("/ws/telemetry")
async def ws_telemetry(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        # gửi snapshot ngay khi client vừa kết nối
        await websocket.send_text(json.dumps({"event": "snapshot", "data": farm_state.snapshot()}, default=str))
        while True:
            # server chủ động đẩy định kỳ; vẫn lắng nghe để phát hiện disconnect
            await asyncio.sleep(3)
            await websocket.send_text(json.dumps({"event": "snapshot", "data": farm_state.snapshot()}, default=str))
    except WebSocketDisconnect:
        manager.disconnect(websocket)
