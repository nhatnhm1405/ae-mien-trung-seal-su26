"""
Lớp ingest dữ liệu — có 2 chế độ:

1. MQTT thật (paho-mqtt): dùng khi thi đấu, kết nối vào broker của BTC.
2. Simulator nội bộ: dùng để dev/test ở nhà khi CHƯA có broker thật.
   (Chạy: python -m app.mqtt_client --simulate)

Cả hai đều đổ dữ liệu vào cùng 1 chỗ: farm_state.ingest(...), nên phần
buffer/API/WebSocket phía sau không cần biết dữ liệu đến từ đâu.
"""

from __future__ import annotations

import json
import random
import ssl
import time
import threading
import logging

from app.config import (
    DEVICES,
    MQTT_BROKER_HOST,
    MQTT_BROKER_PORT,
    MQTT_USERNAME,
    MQTT_PASSWORD,
    MQTT_TRANSPORT,
    MQTT_USE_TLS,
    MQTT_WS_PATH,
    subscribe_topics,
)
from app.state import farm_state

logger = logging.getLogger("mqtt_client")
logging.basicConfig(level=logging.INFO)


# ---------------------------------------------------------------------------
# Điểm nối duy nhất giữa lớp ingest và phần xử lý phía sau
# ---------------------------------------------------------------------------
# Mọi bản ghi — dù đến từ MQTT thật, simulator, hay nút inject demo — đều đi qua
# đúng 1 hàm này. Mặc định chỉ ghi vào farm_state; lúc startup, main.py thay bằng
# pipeline.on_reading để gắn thêm ML + Agent. Dùng callback thay vì import thẳng
# pipeline để tránh vòng import (pipeline cần state/ml/agents, agents cần tools...).
def _default_handler(device_code: str, metrics: dict, event_time: float | None, meta: dict) -> bool:
    return farm_state.ingest(device_code, metrics, event_time=event_time)


_reading_handler = _default_handler


def set_reading_handler(handler) -> None:
    """Thay handler mặc định (main.py gọi lúc startup để gắn pipeline)."""
    global _reading_handler
    _reading_handler = handler
    logger.info("mqtt_client: đã gắn reading handler -> %s", getattr(handler, "__name__", handler))


def dispatch_reading(device_code: str, metrics: dict, event_time: float | None = None,
                     meta: dict | None = None) -> bool:
    """Đẩy 1 bản ghi vào handler đang gắn. Dùng chung cho MQTT thật/simulator/inject.

    Thiết bị đang bị freeze thì bản ghi bị chặn TẠI ĐÂY, không phải chỉ trong vòng
    lặp simulator — nếu không, ở chế độ MQTT thật (lúc thi) message kế tiếp của
    broker sẽ hồi sinh thiết bị sau ~1 giây và Kịch bản 3 "cảm biến mất kết nối"
    không demo được.
    """
    if device_code in _frozen and (meta or {}).get("source") != "inject":
        return True  # coi như đã nhận nhưng cố ý bỏ qua — giữ stale thật sự
    return _reading_handler(device_code, metrics, event_time, meta or {})


# Trạng thái kết nối broker — /api/health và /api/status đọc cái này để biết
# server đang chạy bằng dữ liệu thật hay đang mù.
mqtt_status: dict = {
    "connected": False,
    "broker": None,
    "transport": None,
    "subscribed_topics": [],
    "message_count": 0,
    "last_message_ts": None,
    "last_scenario": "NORMAL",
    "last_error": None,
}


# ---------------------------------------------------------------------------
# Chế độ 1: MQTT thật
# ---------------------------------------------------------------------------
def parse_payload(payload_bytes: bytes) -> tuple[list[tuple[str, dict]], float | None, dict]:
    """Parse JSON payload MQTT thật của BTC — xác nhận qua MQTTX thực tế:

        {
          "timestamp": "2026-08-16T02:55:03.151Z", "epoch": 1786848903,
          "environment": "FARM", "scenario": "NORMAL",
          "devices": [
            {"deviceCode": "PH_01", "status": "ok", "metrics": {"ph": 7.8}},
            {"deviceCode": "PUMP_01", "status": "ok", "metrics": {"flow_rate": 20.6, "power": 574.8}},
            ...
          ],
          "teamCode": "AE_MIEN_TRUNG"
        }

    Khác hẳn giả định ban đầu (1 message/1 thiết bị) — BTC gộp CẢ 6 thiết bị vào 1
    message duy nhất trên 1 topic chung. Trả về:
      - list[(device_code, metrics)] cho từng thiết bị trong message
      - event_time chung (epoch giây) cho cả message
      - meta: {"environment":..., "scenario":..., "teamCode":...} — "scenario" đặc biệt
        đáng chú ý, có thể BTC đổi thành "ANOMALY" lúc demo/chấm điểm.
    """
    try:
        data = json.loads(payload_bytes.decode("utf-8"))
    except Exception:
        logger.warning("Payload không phải JSON hợp lệ: %r", payload_bytes[:200])
        return [], None, {}

    event_time = None
    if data.get("epoch") is not None:
        try:
            event_time = float(data["epoch"])
        except (TypeError, ValueError):
            event_time = None
    if event_time is None and data.get("timestamp"):
        try:
            from datetime import datetime
            event_time = datetime.fromisoformat(str(data["timestamp"]).replace("Z", "+00:00")).timestamp()
        except Exception:
            event_time = None

    devices_raw = data.get("devices")
    parsed: list[tuple[str, dict]] = []
    if isinstance(devices_raw, list):
        for dev in devices_raw:
            if not isinstance(dev, dict):
                continue
            device_code = dev.get("deviceCode") or dev.get("device_code")
            metrics = dev.get("metrics") or {}
            metrics = {k: v for k, v in metrics.items() if isinstance(v, (int, float))}
            if device_code and metrics:
                parsed.append((device_code, metrics))
    else:
        # fallback: payload dạng phẳng cũ (1 message/1 thiết bị) — phòng khi BTC đổi schema
        device_code = data.get("device_code") or data.get("device") or data.get("id")
        metrics = {
            k: v for k, v in data.items()
            if k not in ("device_code", "device", "id", "timestamp", "ts", "epoch", "event_time")
            and isinstance(v, (int, float))
        }
        if device_code and metrics:
            parsed.append((device_code, metrics))

    meta = {
        "environment": data.get("environment"),
        "scenario": data.get("scenario"),
        "teamCode": data.get("teamCode"),
    }
    return parsed, event_time, meta


def build_mqtt_client(host: str = MQTT_BROKER_HOST, port: int = MQTT_BROKER_PORT):
    """Dựng paho client đã cấu hình đúng cho broker BTC (chưa connect).

    Broker BTC chạy sau Cloudflare trên cổng 443 -> bắt buộc dùng MQTT over
    WebSocket Secure (wss), không phải TCP thuần. Các chi tiết dưới đây đều đã
    được xác nhận bằng kết nối thật, đừng "đơn giản hoá" lại:
      - client_id phải là duy nhất, broker đá client trùng id ra ngay lập tức
      - ws_set_options(path=...) bắt buộc khi transport=websockets
      - tls_set() có nhánh dự phòng vì một số máy thiếu CA bundle hệ thống
      - reconnect_delay_set() để tự nối lại khi mạng chập chờn giữa buổi demo
    """
    import paho.mqtt.client as mqtt

    if not host:
        raise RuntimeError(
            "MQTT_BROKER_HOST chưa được set trong .env — điền host:port broker thật của BTC trước khi chạy."
        )

    client_id = f"AE_MIEN_TRUNG_{int(time.time())}_{random.randint(1000, 9999)}"

    client = mqtt.Client(
        mqtt.CallbackAPIVersion.VERSION2,
        client_id=client_id,
        protocol=mqtt.MQTTv311,
        transport=MQTT_TRANSPORT,
    )

    if MQTT_TRANSPORT == "websockets" and MQTT_WS_PATH:
        client.ws_set_options(path=MQTT_WS_PATH)
        logger.info("MQTT transport=websockets (path=%s, client_id=%s)", MQTT_WS_PATH, client_id)

    if MQTT_USE_TLS:
        try:
            client.tls_set()  # xác thực CA chuẩn
        except Exception as exc:
            logger.warning("tls_set() chuẩn thất bại, dùng fallback không xác thực CA: %s", exc)
            client.tls_set(cert_reqs=ssl.CERT_NONE)
            client.tls_insecure_set(True)

    if MQTT_USERNAME:
        client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)
        logger.info("MQTT auth: username/password (user=%s)", MQTT_USERNAME)
    else:
        logger.info("MQTT auth: ẩn danh (không có MQTT_USERNAME trong .env)")

    client.reconnect_delay_set(min_delay=1, max_delay=30)

    def on_connect(client, userdata, flags, reason_code, properties=None):
        rc = reason_code.value if hasattr(reason_code, "value") else int(reason_code)
        if rc != 0:
            mqtt_status["connected"] = False
            mqtt_status["last_error"] = f"connect rc={rc}"
            logger.error("Kết nối broker thất bại (rc=%s)", rc)
            return

        mqtt_status.update({"connected": True, "broker": f"{host}:{port}",
                            "transport": MQTT_TRANSPORT, "last_error": None})
        logger.info("Đã kết nối broker BTC %s:%s qua %s", host, port, MQTT_TRANSPORT.upper())

        topics = subscribe_topics()
        for topic in topics:
            client.subscribe(topic, qos=1)
        mqtt_status["subscribed_topics"] = topics
        logger.info("Đã subscribe %d topic: %s", len(topics), topics)

    def on_message(client, userdata, msg):
        devices, event_time, meta = parse_payload(msg.payload)

        mqtt_status["message_count"] += 1
        mqtt_status["last_message_ts"] = time.time()
        if meta.get("scenario"):
            mqtt_status["last_scenario"] = meta["scenario"]
            if meta["scenario"] != "NORMAL":
                logger.warning("BTC đổi scenario != NORMAL: %s", meta["scenario"])

        if not devices:
            logger.warning("Payload không có thiết bị hợp lệ nào: %s", msg.payload[:200])
            return

        for device_code, metrics in devices:
            ok = dispatch_reading(device_code, metrics, event_time=event_time, meta=meta)
            if not ok:
                logger.warning("Nhận dữ liệu từ thiết bị lạ (ngoài danh mục): %s", device_code)

    def on_disconnect(client, userdata, flags, reason_code, properties=None):
        mqtt_status["connected"] = False
        rc = reason_code.value if hasattr(reason_code, "value") else int(reason_code)
        logger.warning("Mất kết nối broker (rc=%s). paho sẽ tự nối lại...", rc)

    client.on_connect = on_connect
    client.on_message = on_message
    client.on_disconnect = on_disconnect
    return client


def run_mqtt_client(host: str = MQTT_BROKER_HOST, port: int = MQTT_BROKER_PORT):
    """Kết nối broker thật và chạy vòng lặp nhận message (blocking).

    Hàm này chạy trong thread nền CÙNG process với uvicorn — không được tách ra
    tiến trình riêng: farm_state là biến RAM trong 1 process, chạy tách rời thì
    server sẽ không bao giờ thấy dữ liệu (bug này đã bị dính một lần khi test
    broker thật, đừng lặp lại).
    """
    client = build_mqtt_client(host, port)
    try:
        client.connect(host, port, keepalive=60)
    except Exception as exc:
        mqtt_status["last_error"] = str(exc)
        logger.error("Không connect được broker (%s) — chuyển sang connect_async + retry.", exc)
        client.connect_async(host, port, keepalive=60)
    client.loop_forever()


# ---------------------------------------------------------------------------
# Chế độ 2: Simulator — để Frontend/AI code song song mà không cần chờ broker BTC
# ---------------------------------------------------------------------------

# Thiết bị đang bị "khoá" tạm thời để giá trị demo (inject/freeze) không bị simulator
# ghi đè trước khi Agent kịp đọc — LLM thật mất 1-3s round-trip, nếu simulator tick
# (mỗi 3s) đúng lúc đó thì giá trị bất thường vừa bơm sẽ biến mất trước khi ai thấy.
_pinned_until: dict[str, float] = {}  # device_code -> epoch time hết hạn pin
_frozen: set[str] = set()  # device_code -> đang freeze (Kịch bản 3), giữ tới khi unfreeze
PIN_SECONDS_DEFAULT = 20.0


_GENERATORS = {
    "SOIL_01": lambda: {"soil_moisture": round(random.uniform(20, 60), 1),
                         "temperature": round(random.uniform(24, 34), 1)},
    "WEATHER_01": lambda: {"temperature": round(random.uniform(24, 36), 1),
                            "humidity": round(random.uniform(40, 90), 1)},
    "PUMP_01": lambda: {"flow_rate": round(random.uniform(0, 40), 1),
                         "power": round(random.uniform(300, 1500), 1)},
    "PH_01": lambda: {"ph": round(random.uniform(5.8, 7.2), 2)},
    "TANK_01": lambda: {"level": round(random.uniform(20, 95), 1)},
    "SUN_01": lambda: {"lux": round(random.uniform(500, 90000), 0)},
}

# Simulator chỉ phát 6 thiết bị Track B. AC_01 có trong DEVICES (để nhận được dữ
# liệu thật của BTC) nhưng KHÔNG có generator — lặp qua DEVICES ở đây sẽ KeyError.
_SIMULATED_DEVICES = list(_GENERATORS.keys())


def _simulate_reading(device_code: str) -> dict:
    """Sinh số liệu giả hợp lý cho từng loại thiết bị."""
    return _GENERATORS[device_code]()


def start_simulator(interval_seconds: float = 3.0, stop_event: threading.Event | None = None):
    """Chạy trong 1 thread nền, tự phát dữ liệu định kỳ cho tất cả thiết bị.
    Dùng để dev/test khi chưa có broker BTC. KHÔNG dùng lúc thi thật."""
    stop_event = stop_event or threading.Event()

    def loop():
        logger.info("Simulator bắt đầu chạy (interval=%.1fs) — CHỈ dùng cho dev/test.", interval_seconds)
        while not stop_event.is_set():
            now = time.time()
            for code in _SIMULATED_DEVICES:
                if code in _frozen or _pinned_until.get(code, 0) > now:
                    continue  # đang demo (freeze/inject) — không ghi đè
                metrics = _simulate_reading(code)
                dispatch_reading(code, metrics, event_time=time.time(),
                                 meta={"source": "simulator"})
            stop_event.wait(interval_seconds)

    t = threading.Thread(target=loop, daemon=True)
    t.start()
    return t, stop_event


def inject_anomaly(device_code: str, overrides: dict, pin_seconds: float = PIN_SECONDS_DEFAULT) -> dict:
    """Bơm 1 giá trị bất thường thủ công (dùng cho nút demo 'inject anomaly' trên dashboard).
    'Khoá' thiết bị này trong pin_seconds để simulator không tự ghi đè giá trị vừa bơm
    trước khi Agent (LLM mất 1-3s round-trip) kịp đọc. Trả về bản ghi đã bơm để Frontend confirm."""
    base = _simulate_reading(device_code) if device_code in _GENERATORS else {}
    base.update(overrides)
    # Đi qua dispatch_reading (không phải farm_state.ingest) để dữ liệu bơm tay
    # cũng chạy qua ML + Agent — đây chính là thứ nút "Bơm sự cố" lúc pitch cần.
    dispatch_reading(device_code, base, event_time=time.time(), meta={"source": "inject"})
    _pinned_until[device_code] = time.time() + pin_seconds
    return base


def freeze_device(device_code: str) -> None:
    """Giả lập thiết bị ngừng gửi dữ liệu (Kịch bản 3) — giữ stale THẬT SỰ cho tới khi
    unfreeze_device(), không tự hồi sau 3s như trước (simulator sẽ bỏ qua thiết bị này)."""
    _frozen.add(device_code)


def unfreeze_device(device_code: str) -> None:
    """Bỏ freeze — simulator ghi dữ liệu lại bình thường cho thiết bị này."""
    _frozen.discard(device_code)


if __name__ == "__main__":
    import sys
    if "--simulate" in sys.argv:
        _, stop_event = start_simulator(interval_seconds=3.0)
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            stop_event.set()
    else:
        run_mqtt_client()
