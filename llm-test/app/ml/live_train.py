"""
Real-time (dinh ky) refit anomaly_model tu MQTT that dang chay.

CHI ap dung cho anomaly_model (EllipticEnvelope) — KHONG dung cho
irrigation_model. Da chung minh bang thuc nghiem (xem lich su train
irrigation_model voi du lieu that): feed TEST dao dong ngau nhien quanh 0
(mean(diff)~=0, std(diff)~3.1), khong co xu huong vat ly nao de hoc; refit
irrigation_model bang du lieu nay cho MAE te hon ca doan trung binh (R2 am).
irrigation_model tiep tuc dung synthetic vat ly, khong dung trong loop nay.

Co che: buffer truot trong RAM (deque maxlen=MQTT_BUFFER_SIZE, mac dinh 2000)
nhan tung message MQTT (da flatten qua collect_real_data._flatten). Cu moi
REFIT_INTERVAL_SECONDS giay (mac dinh 30s), neu buffer >= MIN_REAL_SAMPLES thi
refit lai CA 6 EllipticEnvelope tren toan bo buffer hien tai va ghi de .pkl.

Day la BATCH-REFIT DINH KY, khong phai online/incremental learning that
(EllipticEnvelope khong ho tro partial_fit) — nhung du de model "theo kip"
dieu kien van hanh dang thay doi ma khong can chay tay lai 2 buoc
collect_real_data.py + train_anomaly_model.py --real.

2 diem ky thuat quan trong da xu ly de "real-time" that su co tac dung:
- Ghi file dung atomic_dump() (train_anomaly_model.py) — ghi ra .pkl.tmp roi
  Path.replace() — tranh 1 process khac doc phai file .pkl dang ghi do.
- anomaly_model.py::_load() tu so mtime moi lan goi predict_anomaly() va load
  lai neu file da doi — neu khong, process Agent/backend chay lau se cache
  model cu vinh vien, refit o day se khong co tac dung gi ben phia doc.

Chay (dien MQTT_* nhu collect_real_data.py):
    cd llm-test
    python -m app.ml.live_train
    Ctrl+C de dung — se refit 1 lan cuoi truoc khi thoat.

Gioi han thoi gian de test (khong treo vo han):
    MQTT_MAX_SECONDS=90 python -m app.ml.live_train
"""

from __future__ import annotations

import json
import os
import ssl
import threading
import time
from collections import deque
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import paho.mqtt.client as mqtt
from sklearn.covariance import EllipticEnvelope

from app.config import DEVICES
from app.ml.collect_real_data import (
    HOST, PORT, USERNAME, PASSWORD, TOPIC, TRANSPORT, WS_PATH, _flatten,
)
from app.ml.train_anomaly_model import atomic_dump, model_path, CONTAMINATION, MIN_REAL_SAMPLES

BUFFER_SIZE = int(os.environ.get("MQTT_BUFFER_SIZE", "2000"))
REFIT_INTERVAL_SECONDS = float(os.environ.get("REFIT_INTERVAL_SECONDS", "30"))
MAX_SECONDS = float(os.environ.get("MQTT_MAX_SECONDS", "0"))  # 0 = chay vo han

LOG_PATH = Path(__file__).parent / "real_telemetry_log.csv"

_buffer: deque = deque(maxlen=BUFFER_SIZE)
_lock = threading.Lock()
_refit_count = 0

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
        import csv
        _csv_file = open(LOG_PATH, "a", newline="", encoding="utf-8")
        _csv_writer = csv.DictWriter(_csv_file, fieldnames=sorted(_seen_fields), extrasaction="ignore")
        if LOG_PATH.stat().st_size == 0:
            _csv_writer.writeheader()
    return _csv_writer


def on_connect(client, userdata, flags, reason_code, properties=None):
    print(f"[live_train] connected rc={reason_code}, subscribing to {TOPIC}")
    client.subscribe(TOPIC, qos=1)


def on_message(client, userdata, msg):
    try:
        payload = json.loads(msg.payload.decode("utf-8"))
    except json.JSONDecodeError:
        return

    payload["_received_at"] = datetime.now(timezone.utc).isoformat()
    flat = _flatten(payload)

    with _lock:
        _buffer.append(flat)
        writer = _ensure_writer(flat.keys())
        writer.writerow(flat)
        _csv_file.flush()


def _refit_once() -> None:
    global _refit_count
    with _lock:
        if len(_buffer) < MIN_REAL_SAMPLES:
            print(f"[live_train] buffer={len(_buffer)} < {MIN_REAL_SAMPLES} mau — chua du de refit")
            return
        df = pd.DataFrame(list(_buffer))

    trained = []
    for code, spec in DEVICES.items():
        metrics = spec.metrics
        cols = [f"{code}_{m}" for m in metrics]
        if not all(c in df.columns for c in cols):
            continue
        sub = df[cols].dropna()
        if len(sub) < MIN_REAL_SAMPLES:
            continue
        sub = sub.rename(columns=dict(zip(cols, metrics)))

        model = EllipticEnvelope(contamination=CONTAMINATION, random_state=42)
        model.fit(sub)
        atomic_dump({"model": model, "metrics": metrics}, model_path(code))
        trained.append(f"{code}({len(sub)})")

    _refit_count += 1
    print(f"[live_train] refit #{_refit_count} luc {time.strftime('%H:%M:%S')} — buffer={len(df)} mau — {', '.join(trained)}")


def _refit_loop(stop_event: threading.Event) -> None:
    while not stop_event.wait(REFIT_INTERVAL_SECONDS):
        _refit_once()


def run() -> None:
    if not PASSWORD:
        raise SystemExit("Chua co MQTT_PASSWORD trong bien moi truong — set truoc khi chay.")

    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, transport=TRANSPORT)
    if TRANSPORT == "websockets":
        client.ws_set_options(path=WS_PATH)
    if PORT in (443, 8883):
        client.tls_set(cert_reqs=ssl.CERT_REQUIRED)
    client.username_pw_set(USERNAME, PASSWORD)
    client.on_connect = on_connect
    client.on_message = on_message

    print(f"[live_train] connecting to {HOST}:{PORT} transport={TRANSPORT}, refit moi {REFIT_INTERVAL_SECONDS:.0f}s")
    client.connect(HOST, PORT, keepalive=30)
    client.loop_start()

    stop_event = threading.Event()
    refit_thread = threading.Thread(target=_refit_loop, args=(stop_event,), daemon=True)
    refit_thread.start()

    try:
        if MAX_SECONDS > 0:
            time.sleep(MAX_SECONDS)
        else:
            while True:
                time.sleep(1)
    except KeyboardInterrupt:
        print("\n[live_train] dang dung...")
    finally:
        stop_event.set()
        client.loop_stop()
        client.disconnect()
        _refit_once()
        print(f"[live_train] da dung. Tong {_refit_count} lan refit. Log: {LOG_PATH}")


if __name__ == "__main__":
    run()
