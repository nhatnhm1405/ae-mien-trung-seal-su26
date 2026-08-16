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
    USE_SINGLE_TOPIC,
    SINGLE_TOPIC,
    topic_for,
)
from app.state import farm_state

logger = logging.getLogger("mqtt_client")
logging.basicConfig(level=logging.INFO)


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


def run_mqtt_client(host: str = MQTT_BROKER_HOST, port: int = MQTT_BROKER_PORT):
    """Kết nối vào broker MQTT thật và subscribe topic thiết bị.

    Broker BTC chạy sau Cloudflare trên cổng 443 -> bắt buộc dùng MQTT over
    WebSocket Secure (wss), không phải TCP thuần. Đường dẫn WS lấy từ
    MQTT_WS_PATH trong .env (mặc định "/mqtt", sửa theo giá trị thật đã xác
    nhận qua MQTTX nếu khác)."""
    import paho.mqtt.client as mqtt

    if not host:
        raise RuntimeError(
            "MQTT_BROKER_HOST chưa được set trong .env — điền host:port broker thật của BTC trước khi chạy."
        )

    def on_connect(client, userdata, flags, reason_code, properties=None):
        logger.info("Đã kết nối MQTT broker %s:%s (rc=%s)", host, port, reason_code)
        if USE_SINGLE_TOPIC:
            client.subscribe(SINGLE_TOPIC, qos=0)
            logger.info("Subscribed (single topic): %s", SINGLE_TOPIC)
        else:
            for code in DEVICES:
                topic = topic_for(code)
                client.subscribe(topic, qos=0)
                logger.info("Subscribed: %s", topic)

    def on_message(client, userdata, msg):
        devices, event_time, meta = parse_payload(msg.payload)
        if meta.get("scenario") and meta["scenario"] != "NORMAL":
            logger.warning("BTC scenario != NORMAL: %s (meta=%s)", meta["scenario"], meta)
        if not devices:
            logger.warning("Payload không có thiết bị hợp lệ nào: %s", msg.payload[:200])
            return
        for device_code, metrics in devices:
            ok = farm_state.ingest(device_code, metrics, event_time=event_time)
            if not ok:
                logger.warning("Nhận dữ liệu từ thiết bị lạ (ngoài danh mục): %s", device_code)

    client = mqtt.Client(
        mqtt.CallbackAPIVersion.VERSION2,
        protocol=mqtt.MQTTv311,
        transport=MQTT_TRANSPORT,
    )
    if MQTT_TRANSPORT == "websockets" and MQTT_WS_PATH:
        client.ws_set_options(path=MQTT_WS_PATH)
    if MQTT_USE_TLS:
        client.tls_set()
    if MQTT_USERNAME:
        client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)
    client.on_connect = on_connect
    client.on_message = on_message
    client.connect(host, port, keepalive=30)
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


def _simulate_reading(device_code: str) -> dict:
    """Sinh số liệu giả hợp lý cho từng loại thiết bị."""
    generators = {
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
    return generators[device_code]()


def start_simulator(interval_seconds: float = 3.0, stop_event: threading.Event | None = None):
    """Chạy trong 1 thread nền, tự phát dữ liệu định kỳ cho tất cả thiết bị.
    Dùng để dev/test khi chưa có broker BTC. KHÔNG dùng lúc thi thật."""
    stop_event = stop_event or threading.Event()

    def loop():
        logger.info("Simulator bắt đầu chạy (interval=%.1fs) — CHỈ dùng cho dev/test.", interval_seconds)
        while not stop_event.is_set():
            now = time.time()
            for code in DEVICES:
                if code in _frozen or _pinned_until.get(code, 0) > now:
                    continue  # đang demo (freeze/inject) — không ghi đè
                metrics = _simulate_reading(code)
                farm_state.ingest(code, metrics, event_time=time.time())
            stop_event.wait(interval_seconds)

    t = threading.Thread(target=loop, daemon=True)
    t.start()
    return t, stop_event


def inject_anomaly(device_code: str, overrides: dict, pin_seconds: float = PIN_SECONDS_DEFAULT) -> dict:
    """Bơm 1 giá trị bất thường thủ công (dùng cho nút demo 'inject anomaly' trên dashboard).
    'Khoá' thiết bị này trong pin_seconds để simulator không tự ghi đè giá trị vừa bơm
    trước khi Agent (LLM mất 1-3s round-trip) kịp đọc. Trả về bản ghi đã bơm để Frontend confirm."""
    base = _simulate_reading(device_code) if device_code in DEVICES else {}
    base.update(overrides)
    farm_state.ingest(device_code, base, event_time=time.time())
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
