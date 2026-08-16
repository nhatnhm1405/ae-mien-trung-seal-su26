"""
predict_anomaly(device_code, reading) -> {is_anomaly, anomaly_score, ...}

Day la ham Field IoT Agent goi cho MOI thiet bi doc duoc, de phat hien gia
tri lech bat thuong (khac voi is_stale — la_stale la "khong co du lieu moi",
con is_anomaly la "co du lieu moi nhung gia tri vo ly").

Model o day la EllipticEnvelope (khoang cach Mahalanobis toi tam phan phoi
Gaussian manh), khong phai IsolationForest — da doi vi IsolationForest co
diem mu voi gia tri cuc doan ngoai vung train (xem train_anomaly_model.py).
anomaly_score o day cang AM cang bat thuong (khac dau voi quy uoc cu).

_load() tu so mtime cua file .pkl moi lan goi va load lai neu da doi — de
live_train.py (refit dinh ky nen sau tu du lieu MQTT that) co tac dung ngay
voi process dang goi predict_anomaly(), khong bi cache model cu vinh vien
trong suot vong doi process (backend/agent thuong chay lien tuc nhieu gio).
"""

from __future__ import annotations

import joblib

from app.ml.train_anomaly_model import model_path

_models: dict = {}  # device_code -> {"bundle": ..., "mtime": float}


def _load(device_code: str):
    path = model_path(device_code)
    if not path.exists():
        raise FileNotFoundError(
            f"Chua co anomaly model cho {device_code} — chay `python -m app.ml.train_anomaly_model` truoc."
        )

    current_mtime = path.stat().st_mtime
    cached = _models.get(device_code)
    if cached is None or cached["mtime"] != current_mtime:
        _models[device_code] = {"bundle": joblib.load(path), "mtime": current_mtime}

    return _models[device_code]["bundle"]


def predict_anomaly(device_code: str, reading: dict) -> dict:
    import pandas as pd

    bundle = _load(device_code)
    model, metrics = bundle["model"], bundle["metrics"]

    missing = [m for m in metrics if reading.get(m) is None]
    if missing:
        return {
            "is_anomaly": None,
            "anomaly_score": None,
            "confidence": "low",
            "missing_features": missing,
        }

    X = pd.DataFrame([{m: reading[m] for m in metrics}], columns=metrics)
    pred = model.predict(X)[0]  # 1 = normal, -1 = anomaly
    score = float(model.decision_function(X)[0])  # cang thap cang bat thuong

    return {
        "is_anomaly": bool(pred == -1),
        "anomaly_score": round(score, 3),
        "confidence": "high",
        "metrics_used": metrics,
    }
