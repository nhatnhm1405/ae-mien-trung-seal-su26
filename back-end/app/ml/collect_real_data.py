"""
Ket noi MQTT that cua BTC de thu thap telemetry that, phuc vu retrain
irrigation_model / anomaly_model bang du lieu thi dau thay vi synthetic.

KHONG dung script nay cho production pipeline — do la viec cua
app/mqtt_client.py (Backend, da co san farm_state.ingest()). Script nay
chi doc + ghi log CSV rieng, khong dung chung state voi backend.

Cau hinh doc tu app/config.py (tuc tu back-end/.env) — cung mot nguon voi
backend, khong con bo bien rieng cho script nay:
    MQTT_BROKER_HOST / MQTT_BROKER, MQTT_BROKER_PORT / MQTT_PORT,
    MQTT_USERNAME, MQTT_PASSWORD, MQTT_TOPIC_TEST,
    MQTT_TRANSPORT (tcp|websockets — mac dinh: websockets neu port=443)
    MQTT_WS_PATH   (mac dinh: /mqtt)

Vi du chay:
    cd back-end
    python -m app.ml.collect_real_data

Neu ket noi that bai voi transport=websockets, thu:
    $env:MQTT_TRANSPORT="tcp"
(mot so broker chay MQTT-TLS thuan tren 443 thay vi WSS).

Schema payload thuc te (khac hoan toan gia dinh trong app/mqtt_client.py::parse_payload()
— 1 topic DUY NHAT gui gop CA 6 THIET BI trong 1 message, khong phai topic rieng/thiet bi):
    {
        "timestamp": "2026-08-16T02:56:20.866Z", "epoch": 1786848980,
        "environment": "FARM", "scenario": "NORMAL",
        "devices": [
            {"deviceCode": "SOIL_01", "status": "ok", "metrics": {"soil_moisture": 32.8, "temperature": 25.3}},
            ...
        ],
        "teamCode": "AE_MIEN_TRUNG",
    }
Script nay tu flatten thanh cot phang SOIL_01_soil_moisture, SOIL_01_status, v.v.
truoc khi ghi CSV — KHONG ghi nguyen payload long nhau (repr cua list se khong
doc lai duoc bang pandas.read_csv thang).
"""

from __future__ import annotations

import csv
import json
import os
import ssl
import time
from datetime import datetime, timezone
from pathlib import Path

import paho.mqtt.client as mqtt

# Doc tu app.config — KHONG tu dat default host/credential o day. Truoc khi hop
# nhat, file nay dung bo ten bien rieng (MQTT_HOST) va hardcode san host cua BTC,
# nghia la sua .env cho backend xong thi script ML van tro vao cho khac.
from app.config import (
    MQTT_BROKER_HOST as HOST,
    MQTT_BROKER_PORT as PORT,
    MQTT_PASSWORD as PASSWORD,
    MQTT_TOPIC_TEST as TOPIC,
    MQTT_TRANSPORT as TRANSPORT,
    MQTT_USERNAME as USERNAME,
    MQTT_WS_PATH as WS_PATH,
)

MAX_SECONDS = float(os.environ.get("MQTT_MAX_SECONDS", "0"))  # 0 = chay vo han (loop_forever)

OUT_PATH = Path(__file__).parent / "real_telemetry_log.csv"

_csv_writer = None
_csv_file = None
_seen_fields: set[str] = set()


def _ensure_writer(fieldnames):
    global _csv_writer, _csv_file, _seen_fields
    new_fields = set(fieldnames) - _seen_fields
    if _csv_writer is None or new_fields:
        _seen_fields |= set(fieldnames)
        if _csv_file:
            _csv_file.close()
        _csv_file = open(OUT_PATH, "a", newline="", encoding="utf-8")
        _csv_writer = csv.DictWriter(_csv_file, fieldnames=sorted(_seen_fields), extrasaction="ignore")
        if OUT_PATH.stat().st_size == 0:
            _csv_writer.writeheader()
    return _csv_writer


def on_connect(client, userdata, flags, reason_code, properties=None):
    print(f"[mqtt] connected rc={reason_code}, subscribing to {TOPIC}")
    client.subscribe(TOPIC, qos=1)


def _flatten(payload: dict) -> dict:
    """1 message gop ca 6 thiet bi -> 1 dong phang, cot dat ten
    f"{device_code}_{metric}" / f"{device_code}_status"."""
    flat = {
        "timestamp": payload.get("timestamp"),
        "epoch": payload.get("epoch"),
        "environment": payload.get("environment"),
        "scenario": payload.get("scenario"),
        "teamCode": payload.get("teamCode"),
        "_received_at": payload.get("_received_at"),
    }
    for dev in payload.get("devices", []):
        code = dev.get("deviceCode")
        if not code:
            continue
        flat[f"{code}_status"] = dev.get("status")
        for metric, value in (dev.get("metrics") or {}).items():
            flat[f"{code}_{metric}"] = value
    return flat


def on_message(client, userdata, msg):
    try:
        payload = json.loads(msg.payload.decode("utf-8"))
    except json.JSONDecodeError:
        print(f"[mqtt] non-JSON payload on {msg.topic}: {msg.payload[:200]!r}")
        return

    payload["_received_at"] = datetime.now(timezone.utc).isoformat()
    flat = _flatten(payload)
    print(flat)

    writer = _ensure_writer(flat.keys())
    writer.writerow(flat)
    _csv_file.flush()


def run():
    if not PASSWORD:
        raise SystemExit("Chua co MQTT_PASSWORD trong bien moi truong — set truoc khi chay, dung paste vao code.")

    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, transport=TRANSPORT)
    if TRANSPORT == "websockets":
        client.ws_set_options(path=WS_PATH)
    if PORT in (443, 8883):
        client.tls_set(cert_reqs=ssl.CERT_REQUIRED)
    client.username_pw_set(USERNAME, PASSWORD)
    client.on_connect = on_connect
    client.on_message = on_message

    path_info = WS_PATH if TRANSPORT == "websockets" else "-"
    print(f"[mqtt] connecting to {HOST}:{PORT} transport={TRANSPORT} path={path_info}")
    client.connect(HOST, PORT, keepalive=30)

    if MAX_SECONDS > 0:
        client.loop_start()
        time.sleep(MAX_SECONDS)
        client.loop_stop()
        client.disconnect()
        print(f"[mqtt] stopped after {MAX_SECONDS:.0f}s, log saved at {OUT_PATH}")
    else:
        client.loop_forever()


if __name__ == "__main__":
    try:
        run()
    except KeyboardInterrupt:
        print(f"\n[mqtt] stopped, log saved at {OUT_PATH}")
