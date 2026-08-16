"""
main.py — Data/Backend Server cho Smart Agriculture (Track B).

Vai tro:
  1. Khoi dong MQTT Listener (mqtt_client.py)
  2. Duy tri Telemetry Buffer (buffer.py) cho 6 thiet bi nong nghiep:
     SOIL_01, WEATHER_01, PUMP_01, PH_01, TANK_01, SUN_01
  3. Phat hien mat ket noi / gianduan du lieu (Stale Data Detection)
  4. Stream realtime telemetry qua WebSocket (/ws/telemetry)
  5. Cung cap REST API du lieu cho Frontend & AI Agents tieu thu

Chay server:
  uvicorn main:app --host 0.0.0.0 --port 8000 --reload
"""
import time
import json
import asyncio
import logging
import webbrowser
import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from dotenv import load_dotenv


load_dotenv()

# ── Import Data Modules & Services ──
from mqtt_client import MQTTHandler, DEVICE_REGISTRY
from buffer import DeviceBuffer
from websocket_manager import ws_manager
from services import irrigation_service, resource_service, verification_service


# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s"
)
logger = logging.getLogger("DataBackend")

# ── Shared Data State ──
telemetry_buffer = DeviceBuffer(maxlen=500)
mqtt_handler: MQTTHandler | None = None
_loop: asyncio.AbstractEventLoop | None = None


def on_mqtt_telemetry(data: dict):
    """
    Callback duoc goi moi khi co message MQTT tu cam bien.

    Pipeline:
      1. Luu du lieu vao DeviceBuffer
      2. Broadcast realtime telemetry qua WebSocket toi Dashboard/Clients
    """
    global _loop

    # 1. Day vao buffer
    telemetry_buffer.add(data)

    device_code = data.get("device_code", "UNKNOWN")
    logger.debug(f"Buffered telemetry for {device_code}: {data.get('metrics')}")

    # 2. Broadcast realtime qua WebSocket
    if _loop and ws_manager.connection_count > 0:
        asyncio.run_coroutine_threadsafe(
            ws_manager.broadcast_telemetry(data),
            _loop
        )


def _open_swagger_browser():
    """Tự động mở trang Swagger UI khi server khởi chạy."""
    time.sleep(1.2)
    url = "http://localhost:8000/docs"
    logger.info(f"🌐 Auto-opening Swagger UI in browser: {url}")
    try:
        webbrowser.open(url)
    except Exception as e:
        logger.warning(f"Could not auto-open browser: {e}")


# ══════════════════════════════════════════════════════
# FastAPI Lifespan (Startup / Shutdown)
# ══════════════════════════════════════════════════════

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle manager — Khoi dong MQTT Listener khi backend bat dau."""
    global mqtt_handler, _loop

    _loop = asyncio.get_event_loop()

    # Khoi tao MQTT Listener
    mqtt_handler = MQTTHandler(data_callback=on_mqtt_telemetry)
    mqtt_handler.start()
    logger.info("🚀 Data Backend started — MQTT Listener running")

    # Tự động mở Swagger UI trên trình duyệt
    threading.Thread(target=_open_swagger_browser, daemon=True).start()

    yield

    # Shutdown
    if mqtt_handler:
        mqtt_handler.stop()
    logger.info("Data Backend shutdown complete")



tags_metadata = [
    {
        "name": "1. Hệ thống & Health Check",
        "description": "Các API kiểm tra trạng thái hoạt động server, kết nối MQTT BTC và bơm dữ liệu test."
    },
    {
        "name": "2. Telemetry Cảm biến IoT",
        "description": "API truy vấn dữ liệu thô real-time từ 6 thiết bị nông nghiệp (SOIL_01, WEATHER_01, PUMP_01, PH_01, TANK_01, SUN_01)."
    },
    {
        "name": "3. Tools cho Multi-Agent AI",
        "description": "Bộ Function Tools hỗ trợ LLM Agents (IoT Agent, Irrigation Agent, Resource Agent, Action Agent, Verification Agent)."
    },
    {
        "name": "4. Lập & Phê duyệt Kế hoạch Tưới",
        "description": "Nghiệp vụ lập kế hoạch tưới (Kịch bản 1) và quy trình phê duyệt/từ chối của Người quản lý."
    },
    {
        "name": "5. Quản lý Tài nguyên & Nguồn nước",
        "description": "Đánh giá mực nước bồn TANK_01, tính dung tích khả dụng, ngưỡng an toàn và quản lý nhân sự."
    },
    {
        "name": "6. Quản lý Nhiệm vụ & Verification",
        "description": "Tạo phiếu kiểm tra/bảo trì (Kịch bản 2) và xác minh post-action kèm chứng cứ telemetry."
    },
    {
        "name": "7. Phân tích & Context cho LLM",
        "description": "Động cơ phát hiện sự cố tự động và cung cấp prompt context gọn nhẹ cho AI Agents."
    },
]

app = FastAPI(
    title="AE_MIEN_TRUNG — MQTT Data Backend",
    description="Backend xử lý dữ liệu IoT realtime & Nghiệp vụ điều hành Nông nghiệp thông minh (Track B)",
    version="2.0.0",
    lifespan=lifespan,
    openapi_tags=tags_metadata,
)


# Cho phap CORS de Frontend ket noi
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ══════════════════════════════════════════════════════
# WebSocket Stream (Realtime Data Push)
# ══════════════════════════════════════════════════════

@app.websocket("/ws/telemetry")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket Server cho Frontend/Agents nhan data realtime.

    Frontend ket noi: ws://localhost:8000/ws/telemetry
    Message nhan duoc co format:
    {
        "type": "telemetry",
        "data": {
            "device_code": "SOIL_01",
            "timestamp": 1786841234.5,
            "metrics": {"soil_moisture": 45.2, "temperature": 28.1}
        }
    }
    """
    await ws_manager.connect(websocket)

    # Nhan tin gui snaphot ban dau
    snapshot = telemetry_buffer.get_farm_snapshot()
    await websocket.send_json({
        "type": "initial_snapshot",
        "data": snapshot
    })

    try:
        while True:
            # Giai phong event loop, lang nghe neu client co gui request
            client_msg = await websocket.receive_text()
            try:
                cmd = json.loads(client_msg)
                if cmd.get("action") == "ping":
                    await websocket.send_json({"type": "pong", "timestamp": time.time()})
            except json.JSONDecodeError:
                pass
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)


# ══════════════════════════════════════════════════════
# REST API Endpoints (Data Access layer)
# ══════════════════════════════════════════════════════

@app.get("/", tags=["1. Hệ thống & Health Check"])
async def root():
    """Trang thai chung cua Data Backend."""
    return {
        "service": "AE_MIEN_TRUNG MQTT Data Backend",
        "status": "running",
        "track": "Track B: Smart Agriculture",
        "mqtt_connected": mqtt_handler.connected if mqtt_handler else False,
        "active_websocket_clients": ws_manager.connection_count,
        "registered_devices": list(DEVICE_REGISTRY.keys()),
        "buffered_devices": telemetry_buffer.get_all_devices(),
    }


@app.get("/api/devices", tags=["2. Telemetry Cảm biến IoT"])
async def get_all_devices():
    """
    Lay danh sach tat ca 6 thiet bi kem chi so telemetry moi nhat va trang thai.
    Dung cho Dashboard tong quan hoac IoT Agent.
    """
    snapshot = telemetry_buffer.get_farm_snapshot()
    return {
        "timestamp": snapshot["timestamp"],
        "registry": DEVICE_REGISTRY,
        "devices": snapshot["devices"],
        "active_count": len(snapshot["active_devices"]),
        "stale_count": len(snapshot["stale_devices"]),
    }


@app.get("/api/device/{device_code}", tags=["2. Telemetry Cảm biến IoT"])
async def get_device_detail(device_code: str):
    """Lay thong tin chi tiet va du lieu moi nhat cua 1 thiet bi."""
    code_upper = device_code.upper()
    if code_upper not in DEVICE_REGISTRY:
        return JSONResponse(
            status_code=404,
            content={"error": f"Device {device_code} not found in registry"}
        )

    latest = telemetry_buffer.get_latest(code_upper)
    status = telemetry_buffer.get_device_status(code_upper)

    return {
        "device_code": code_upper,
        "info": DEVICE_REGISTRY[code_upper],
        "status": status,
        "latest_data": latest,
    }


@app.get("/api/device/{device_code}/history", tags=["2. Telemetry Cảm biến IoT"])
async def get_device_history(device_code: str, limit: int = Query(default=50, ge=1, le=500)):
    """Lay chuoi du lieu lich su cua 1 thiet bi (cho bieu do / rolling stats)."""
    code_upper = device_code.upper()
    history = telemetry_buffer.get_history(code_upper, n=limit)
    return {
        "device_code": code_upper,
        "count": len(history),
        "history": history,
    }


# ══════════════════════════════════════════════════════
# Task Management & Action Verification Engine (Track B)
# ══════════════════════════════════════════════════════


tasks_db: dict[str, dict] = {}


@app.post("/api/actions/tasks", tags=["6. Quản lý Nhiệm vụ & Verification"])
async def create_field_task(payload: dict):
    """
    Tạo nhiệm vụ ngoài hiện trường (lịch tưới, phiếu kiểm tra, cảnh báo bảo trì).
    Đáp ứng yêu cầu Tool/API tạo công việc và Action Agent của Track B.
    """
    task_id = f"TASK_{int(time.time() * 1000)}"
    task = {
        "task_id": task_id,
        "title": payload.get("title", "Nhiệm vụ kiểm tra hiện trường"),
        "device_code": payload.get("device_code", "ZONE_A").upper(),
        "action_type": payload.get("action_type", "INSPECTION").upper(),
        "assigned_to": payload.get("assigned_to", "Đội vận hành hiện trường"),
        "created_by": payload.get("created_by", "Multi-Agent System"),
        "details": payload.get("details", ""),
        "status": "CREATED",  # CREATED -> PENDING -> VERIFIED -> COMPLETED
        "created_at": time.time(),
        "verified_at": None,
        "verification_proof": None,
    }

    tasks_db[task_id] = task
    logger.info(f"📋 Created task {task_id}: {task['title']}")

    # Broadcast task creation event qua WebSocket
    if _loop and ws_manager.connection_count > 0:
        asyncio.run_coroutine_threadsafe(
            ws_manager.broadcast({"type": "task_created", "data": task}),
            _loop
        )

    return {
        "status": "success",
        "message": "Nhiệm vụ đã được tạo thành công",
        "task": task,
    }


@app.get("/api/actions/tasks", tags=["6. Quản lý Nhiệm vụ & Verification"])
async def get_field_tasks(status: str | None = None):
    """Lấy danh sách nhiệm vụ hiện trường."""
    tasks = list(tasks_db.values())
    if status:
        tasks = [t for t in tasks if t["status"].upper() == status.upper()]

    return {
        "total": len(tasks),
        "tasks": sorted(tasks, key=lambda x: x["created_at"], reverse=True)
    }


@app.post("/api/actions/verify/{task_id}", tags=["6. Quản lý Nhiệm vụ & Verification"])
async def verify_field_task(task_id: str, payload: dict | None = None):
    """
    Xác minh (Verification) sau khi thực hiện hành động / tạo nhiệm vụ.
    Đáp ứng điều kiện chấp nhận Track B: "Có verification sau hành động".
    """
    if task_id not in tasks_db:
        return JSONResponse(
            status_code=404,
            content={"error": f"Task {task_id} not found"}
        )

    payload = payload or {}
    task = tasks_db[task_id]
    task["status"] = "VERIFIED"
    task["verified_at"] = time.time()
    task["verification_proof"] = {
        "verified_by": payload.get("verified_by", "Verification Agent"),
        "notes": payload.get("notes", "Đã xác minh sự tồn tại của nhiệm vụ và dữ liệu telemetry tương ứng"),
        "telemetry_snapshot": telemetry_buffer.get_farm_snapshot(),
    }

    logger.info(f"✅ Verified task {task_id}")

    # Broadcast verification event qua WebSocket
    if _loop and ws_manager.connection_count > 0:
        asyncio.run_coroutine_threadsafe(
            ws_manager.broadcast({"type": "task_verified", "data": task}),
            _loop
        )

    return {
        "status": "success",
        "verified": True,
        "message": f"Nhiệm vụ {task_id} đã được xác minh thành công",
        "task": task,
    }


# ══════════════════════════════════════════════════════
# Domain Business Engine (Track B: Smart Agriculture)
# ══════════════════════════════════════════════════════

@app.get("/api/analytics/irrigation-recommendation", tags=["7. Phân tích & Context cho LLM"])
async def get_irrigation_recommendation():
    """
    Phân tích dữ liệu IoT realtime và tạo khuyến nghị tưới / xử lý sự cố.
    Phục vụ trực tiếp cho Kịch bản 1 (Chuẩn bị kế hoạch tưới) & Kịch bản 2 (Kiểm tra hoạt động tưới).
    """
    snapshot = telemetry_buffer.get_farm_snapshot()
    devices = snapshot.get("devices", {})

    soil = devices.get("SOIL_01", {}).get("metrics", {})
    weather = devices.get("WEATHER_01", {}).get("metrics", {})
    pump = devices.get("PUMP_01", {}).get("metrics", {})
    ph = devices.get("PH_01", {}).get("metrics", {})
    tank = devices.get("TANK_01", {}).get("metrics", {})
    sun = devices.get("SUN_01", {}).get("metrics", {})

    soil_moisture = soil.get("soil_moisture")
    flow_rate = pump.get("flow_rate", 0)
    power = pump.get("power", 0)
    tank_level = tank.get("level", 0)
    temp = weather.get("temperature") or soil.get("temperature", 28.0)
    lux = sun.get("lux", 0)
    ph_val = ph.get("ph")

    stale_devices = snapshot.get("stale_devices", [])
    scenario = snapshot.get("scenario", "NORMAL")

    recommendations = []
    priority = "NORMAL"

    # Rule 1: Pump Failure Detection (Kịch bản 2 / BTC Scenario)
    if power > 100 and flow_rate < 0.5:
        priority = "CRITICAL"
        recommendations.append({
            "code": "PUMP_FAILURE",
            "level": "CRITICAL",
            "message": "Bơm PUMP_01 đang cấp nguồn nhưng lưu lượng bằng 0. Cần tạo phiếu kiểm tra bảo trì gấp!",
            "suggested_action": "CREATE_INSPECTION_TASK",
            "device_target": "PUMP_01",
        })
    elif flow_rate > 0 and tank_level < 15.0:
        priority = "HIGH"
        recommendations.append({
            "code": "LOW_WATER_SUPPLY",
            "level": "HIGH",
            "message": "Mực nước bồn TANK_01 sắp cạn (<15%). Cần tạm dừng tưới hoặc ngắt bơm để bảo vệ thiết bị.",
            "suggested_action": "STOP_PUMP",
            "device_target": "TANK_01",
        })

    # Rule 2: Soil Moisture Analysis (Kịch bản 1)
    if soil_moisture is not None:
        if soil_moisture < 30.0:
            if priority != "CRITICAL":
                priority = "HIGH"
            recommendations.append({
                "code": "DRY_SOIL",
                "level": "HIGH",
                "message": f"Độ ẩm đất khu A đang thấp ({soil_moisture}% < 30%). Khuyến nghị lên lịch tưới 20 phút.",
                "suggested_action": "SCHEDULE_IRRIGATION",
                "device_target": "SOIL_01",
                "params": {"duration_minutes": 20, "flow_target": 15.0}
            })
        elif soil_moisture > 75.0:
            recommendations.append({
                "code": "WET_SOIL",
                "level": "LOW",
                "message": f"Độ ẩm đất khu A rất cao ({soil_moisture}% > 75%). Không cần tưới thêm.",
                "suggested_action": "HOLD_IRRIGATION",
                "device_target": "SOIL_01",
            })

    # Rule 3: Stale Sensor Check (Kịch bản 3: Dữ liệu gián đoạn)
    if stale_devices:
        recommendations.append({
            "code": "SENSOR_STALE",
            "level": "WARNING",
            "message": f"Phát hiện {len(stale_devices)} thiết bị gián đoạn dữ liệu: {', '.join(stale_devices)}. Tiếp tục hoạt động ở chế độ partial.",
            "suggested_action": "VERIFY_SENSOR_CONNECTIVITY",
            "stale_devices": stale_devices,
        })

    return {
        "timestamp": time.time(),
        "btc_scenario": scenario,
        "priority": priority,
        "metrics_summary": {
            "soil_moisture": soil_moisture,
            "pump_flow_rate": flow_rate,
            "pump_power": power,
            "tank_level": tank_level,
            "temperature": temp,
            "lux": lux,
            "ph": ph_val,
        },
        "stale_devices": stale_devices,
        "recommendations": recommendations,
    }


# ══════════════════════════════════════════════════════
# 1. Irrigation Planning & Approval Workflow APIs (Track B)
# ══════════════════════════════════════════════════════

@app.post("/api/irrigation/plans", tags=["4. Lập & Phê duyệt Kế hoạch Tưới"])
async def create_irrigation_plan(payload: dict):
    """
    Tạo kế hoạch tưới mới (Irrigation Planning Agent).
    Phục vụ Kịch bản 1 — Lập kế hoạch tưới trong ngày.
    """
    plan = irrigation_service.create_plan(
        zone=payload.get("zone", "ZONE_A"),
        target_moisture=float(payload.get("target_moisture", 45.0)),
        duration_minutes=int(payload.get("duration_minutes", 20)),
        priority=payload.get("priority", "HIGH"),
        created_by=payload.get("created_by", "Irrigation Planning Agent"),
        reason=payload.get("reason", "Căn cứ độ ẩm đất SOIL_01 và thông số thời tiết WEATHER_01"),
        water_estimated_liters=float(payload.get("water_estimated_liters", 300.0)),
    )

    if _loop and ws_manager.connection_count > 0:
        asyncio.run_coroutine_threadsafe(
            ws_manager.broadcast({"type": "plan_created", "data": plan}),
            _loop
        )
    return {"status": "success", "plan": plan}


@app.get("/api/irrigation/plans", tags=["4. Lập & Phê duyệt Kế hoạch Tưới"])
async def get_irrigation_plans(status: str | None = None):
    """Lấy danh sách các kế hoạch tưới."""
    plans = irrigation_service.list_plans(status=status)
    return {"total": len(plans), "plans": plans}


@app.post("/api/irrigation/plans/{plan_id}/approve", tags=["4. Lập & Phê duyệt Kế hoạch Tưới"])
async def approve_irrigation_plan(plan_id: str, payload: dict | None = None):
    """
    Phê duyệt kế hoạch tưới (Khu vực phê duyệt quan trọng của Người quản lý).
    UX Requirement 7: "Có khu vực phê duyệt kế hoạch hoặc hành động quan trọng".
    """
    payload = payload or {}
    plan = irrigation_service.approve_plan(
        plan_id=plan_id,
        approved_by=payload.get("approved_by", "Người quản lý nông trại"),
        notes=payload.get("notes", "Đã duyệt kế hoạch tưới sau khi kiểm tra nguồn nước TANK_01")
    )
    if not plan:
        return JSONResponse(status_code=404, content={"error": f"Plan {plan_id} not found"})

    # Tự động tạo task tưới ngoài hiện trường sau khi được duyệt
    task_payload = {
        "title": f"Thực thi lịch tưới {plan['zone']} - {plan['duration_minutes']} phút",
        "device_code": "PUMP_01",
        "action_type": "IRRIGATION",
        "assigned_to": "Đội vận hành hiện trường",
        "created_by": "Irrigation Engine",
        "details": f"Mục tiêu độ ẩm: {plan['target_moisture']}%. Lý do: {plan['reason']}"
    }
    task_res = await create_field_task(task_payload)

    if _loop and ws_manager.connection_count > 0:
        asyncio.run_coroutine_threadsafe(
            ws_manager.broadcast({"type": "plan_approved", "data": {"plan": plan, "created_task": task_res["task"]}}),
            _loop
        )

    return {"status": "success", "message": "Kế hoạch đã được duyệt và tạo nhiệm vụ thực thi", "plan": plan, "task": task_res["task"]}


@app.post("/api/irrigation/plans/{plan_id}/reject", tags=["4. Lập & Phê duyệt Kế hoạch Tưới"])
async def reject_irrigation_plan(plan_id: str, payload: dict | None = None):
    """Từ chối kế hoạch tưới."""
    payload = payload or {}
    plan = irrigation_service.reject_plan(
        plan_id=plan_id,
        rejected_by=payload.get("rejected_by", "Người quản lý nông trại"),
        reason=payload.get("reason", "Cần điều chỉnh thêm thông số")
    )
    if not plan:
        return JSONResponse(status_code=404, content={"error": f"Plan {plan_id} not found"})

    return {"status": "success", "plan": plan}


# ══════════════════════════════════════════════════════
# 2. Resource Management APIs (Resource Agent)
# ══════════════════════════════════════════════════════

@app.get("/api/resources/water-budget", tags=["5. Quản lý Tài nguyên & Nguồn nước"])
async def get_water_budget():
    """
    Kiểm tra nguồn nước bồn TANK_01 và tính toán dung tích tưới khả dụng.
    Được sử dụng bởi Resource Agent.
    """
    tank_data = telemetry_buffer.get_latest("TANK_01")
    pump_data = telemetry_buffer.get_latest("PUMP_01")

    level = tank_data.get("metrics", {}).get("level", 50.0) if tank_data else 50.0
    flow = pump_data.get("metrics", {}).get("flow_rate", 0.0) if pump_data else 0.0

    eval_result = resource_service.evaluate_water_resource(tank_level_percent=level, flow_rate_lmin=flow)
    return {
        "timestamp": time.time(),
        "water_resource": eval_result,
    }


@app.get("/api/resources/staff", tags=["5. Quản lý Tài nguyên & Nguồn nước"])
async def get_field_staff():
    """Lấy danh sách nhân sự hiện trường khả dụng."""
    staff = resource_service.get_field_staff()
    return {"total": len(staff), "staff": staff}


# ══════════════════════════════════════════════════════
# 3. Multi-Agent Function Call Tools (/api/agent/tools/*)
# ══════════════════════════════════════════════════════

@app.post("/api/agent/tools/read-sensors", tags=["3. Tools cho Multi-Agent AI"])
async def tool_read_sensors(payload: dict | None = None):
    """
    [Agent Tool] Đọc dữ liệu cảm biến nông nghiệp (Field IoT Agent).
    """
    payload = payload or {}
    device_codes = payload.get("device_codes")

    snapshot = telemetry_buffer.get_farm_snapshot()
    devices = snapshot.get("devices", {})

    if device_codes and isinstance(device_codes, list):
        filtered = {code.upper(): devices.get(code.upper(), {}) for code in device_codes if code.upper() in DEVICE_REGISTRY}
    else:
        filtered = devices

    return {
        "tool": "read_sensors",
        "timestamp": snapshot["timestamp"],
        "btc_scenario": snapshot.get("scenario", "NORMAL"),
        "devices": filtered,
        "active_devices": snapshot.get("active_devices", []),
        "stale_devices": snapshot.get("stale_devices", []),
    }


@app.post("/api/agent/tools/check-stale", tags=["3. Tools cho Multi-Agent AI"])
async def tool_check_stale():
    """
    [Agent Tool] Đánh giá mức độ gián đoạn dữ liệu (Kịch bản 3).
    """
    statuses = telemetry_buffer.get_all_device_status()
    stale_list = [s["device_code"] for s in statuses if s["stale"] or not s["connected"]]
    active_list = [s["device_code"] for s in statuses if not s["stale"] and s["connected"]]

    return {
        "tool": "check_stale",
        "total_devices": len(statuses),
        "active_devices": active_list,
        "stale_devices": stale_list,
        "partial_mode": len(stale_list) > 0,
        "details": statuses,
    }


@app.post("/api/agent/tools/create-plan", tags=["3. Tools cho Multi-Agent AI"])
async def tool_create_plan(payload: dict):
    """
    [Agent Tool] Lập kế hoạch tưới (Irrigation Planning Agent).
    """
    res = await create_irrigation_plan(payload)
    return {"tool": "create_plan", "result": res}


@app.post("/api/agent/tools/create-ticket", tags=["3. Tools cho Multi-Agent AI"])
async def tool_create_ticket(payload: dict):
    """
    [Agent Tool] Tạo phiếu kiểm tra / sự cố hiện trường (Action Agent).
    """
    res = await create_field_task(payload)
    return {"tool": "create_ticket", "result": res}


@app.post("/api/agent/tools/verify-action", tags=["3. Tools cho Multi-Agent AI"])
async def tool_verify_action(payload: dict):
    """
    [Agent Tool] Thực hiện xác minh post-action (Verification Agent).
    """
    task_id = payload.get("task_id", "")
    snapshot = telemetry_buffer.get_farm_snapshot()
    proof = verification_service.verify_action(
        action_id=task_id,
        action_type=payload.get("action_type", "INSPECTION"),
        telemetry_snapshot=snapshot,
        verified_by=payload.get("verified_by", "Verification Agent"),
        notes=payload.get("notes", "Đã đối soát thành công với dữ liệu telemetry real-time")
    )
    if task_id and task_id in tasks_db:
        tasks_db[task_id]["status"] = "VERIFIED"
        tasks_db[task_id]["verified_at"] = proof["timestamp"]
        tasks_db[task_id]["verification_proof"] = proof

    return {"tool": "verify_action", "verification_proof": proof}


@app.get("/api/analytics/llm-context", tags=["7. Phân tích & Context cho LLM"])
async def get_llm_context():
    """
    Cung cấp cấu trúc context rút gọn cho Multi-Agent Prompts.
    Giúp các Agents (Coordinator, IoT, Irrigation, Resource, Action) truy vấn dữ liệu nhanh.
    """
    summary = telemetry_buffer.get_farm_summary_for_llm()
    snapshot = telemetry_buffer.get_farm_snapshot()
    tasks = list(tasks_db.values())
    plans = irrigation_service.list_plans()

    return {
        "timestamp": time.time(),
        "btc_scenario": snapshot.get("scenario", "NORMAL"),
        "mqtt_connected": mqtt_handler.connected if mqtt_handler else False,
        "devices": summary,
        "active_devices": snapshot.get("active_devices", []),
        "stale_devices": snapshot.get("stale_devices", []),
        "plans": {"total": len(plans), "pending_approval": [p for p in plans if p["status"] == "PENDING_APPROVAL"]},
        "tasks": {"total": len(tasks), "pending": [t for t in tasks if t["status"] != "COMPLETED"]},
    }


@app.post("/api/inject", tags=["1. Hệ thống & Health Check"])
async def inject_telemetry(payload: dict):
    """
    API test: bom du lieu thu nghiem vao buffer de gia lap du lieu cam bien.

    Body example:
    {
        "device_code": "SOIL_01",
        "metrics": {"soil_moisture": 25.0, "temperature": 31.0}
    }
    """
    device_code = payload.get("device_code", "SOIL_01").upper()
    metrics = payload.get("metrics", {})

    data = {
        "device_code": device_code,
        "timestamp": payload.get("timestamp", time.time()),
        "metrics": metrics,
        "raw_topic": "api/inject",
    }

    on_mqtt_telemetry(data)
    return {
        "status": "injected",
        "data": data,
    }


@app.get("/api/health", tags=["1. Hệ thống & Health Check"])
async def health_check():
    """Health check endpoint cho system status."""
    return {
        "status": "healthy",
        "mqtt_connected": mqtt_handler.connected if mqtt_handler else False,
        "websocket_clients": ws_manager.connection_count,
        "buffered_devices": len(telemetry_buffer.get_all_devices()),
        "tasks_in_db": len(tasks_db),
    }


# ── Standalone Runner ──
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info",
    )


