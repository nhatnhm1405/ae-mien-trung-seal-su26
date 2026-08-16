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
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from dotenv import load_dotenv

load_dotenv()

# ── Import Data Modules ──
from mqtt_client import MQTTHandler, DEVICE_REGISTRY
from buffer import DeviceBuffer
from websocket_manager import ws_manager

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

    yield

    # Shutdown
    if mqtt_handler:
        mqtt_handler.stop()
    logger.info("Data Backend shutdown complete")


app = FastAPI(
    title="AE_MIEN_TRUNG — MQTT Data Backend",
    description="Backend xu ly du lieu IoT realtime tu 6 thiet bi nong nghiep (Track B)",
    version="2.0.0",
    lifespan=lifespan,
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

@app.get("/")
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


@app.get("/api/devices")
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


@app.get("/api/device/{device_code}")
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


@app.get("/api/device/{device_code}/history")
async def get_device_history(device_code: str, limit: int = Query(default=50, ge=1, le=500)):
    """Lay chuoi du lieu lich su cua 1 thiet bi (cho bieu do / rolling stats)."""
    code_upper = device_code.upper()
    history = telemetry_buffer.get_history(code_upper, n=limit)
    return {
        "device_code": code_upper,
        "count": len(history),
        "history": history,
    }


@app.get("/api/devices/status")
async def get_devices_status():
    """
    Kiem tra do moi va trang thai ket noi cua tat ca 6 thiet bi (Stale Data Detection).
    Dap ung Kich ban 3 tu de bai.
    """
    statuses = telemetry_buffer.get_all_device_status()
    stale_list = [s["device_code"] for s in statuses if s["stale"] or not s["connected"]]

    return {
        "timestamp": time.time(),
        "total_devices": len(statuses),
        "stale_devices": stale_list,
        "device_statuses": statuses,
    }


@app.post("/api/inject")
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


@app.get("/api/health")
async def health_check():
    """Health check endpoint cho system status."""
    return {
        "status": "healthy",
        "mqtt_connected": mqtt_handler.connected if mqtt_handler else False,
        "websocket_clients": ws_manager.connection_count,
        "buffered_devices": len(telemetry_buffer.get_all_devices()),
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
