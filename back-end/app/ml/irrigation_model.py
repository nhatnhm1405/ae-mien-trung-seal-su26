"""
predict(reading) -> {priority_score, time_to_dry_hours, confidence, ...}

Day la ham ma Irrigation Planning Agent goi nhu 1 tool. Model chi lo phan
kho hardcode (toc do bay hoi hoc tu thoi tiet), phan "con bao lau thi kho"
la toan tru minh bach tu soil_moisture song hien tai.
"""

from __future__ import annotations

from pathlib import Path

import joblib
import pandas as pd

from app.ml.generate_synthetic_data import DRY_THRESHOLD

MODEL_PATH = Path(__file__).parent / "irrigation_model_checkpoint.pkl"
MAX_HORIZON_HOURS = 24.0
MIN_RATE_PER_HOUR = 0.01

_bundle = None


def _load():
    global _bundle
    if _bundle is None:
        if not MODEL_PATH.exists():
            raise FileNotFoundError(
                f"Chua co model tai {MODEL_PATH} — chay `python -m app.ml.train_irrigation_model` truoc."
            )
        _bundle = joblib.load(MODEL_PATH)
    return _bundle


def predict(reading: dict) -> dict:
    """reading: {soil_moisture, temperature, humidity, lux}"""
    bundle = _load()
    model, weather_features = bundle["model"], bundle["features"]

    required = weather_features + ["soil_moisture"]
    missing = [f for f in required if reading.get(f) is None]
    if missing:
        return {
            "priority_score": None,
            "time_to_dry_hours": None,
            "confidence": "low",
            "missing_features": missing,
        }

    X = pd.DataFrame([{f: reading[f] for f in weather_features}], columns=weather_features)
    rate_per_hour = float(model.predict(X)[0])
    soil_moisture = reading["soil_moisture"]

    if rate_per_hour <= MIN_RATE_PER_HOUR:
        time_to_dry = MAX_HORIZON_HOURS
    else:
        time_to_dry = min(max(soil_moisture - DRY_THRESHOLD, 0.0) / rate_per_hour, MAX_HORIZON_HOURS)

    priority_score = round(max(0.0, 100.0 * (1 - time_to_dry / MAX_HORIZON_HOURS)), 1)

    return {
        "priority_score": priority_score,
        "time_to_dry_hours": round(time_to_dry, 1),
        "predicted_drying_rate_per_hour": round(rate_per_hour, 3),
        "confidence": "high",
        "features_used": required,
    }
