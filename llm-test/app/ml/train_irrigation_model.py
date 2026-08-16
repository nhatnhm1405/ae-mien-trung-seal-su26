"""
Train Irrigation Priority Model — chay 1 lan, luu model_checkpoint.pkl.

Thiet ke 2 tang de tranh leakage: model CHI hoc toc do bay hoi (%/h) tu
[temperature, humidity, lux]. "Con bao lau thi kho" la phep tru/chia minh
bach o tang ung dung (irrigation_model.py), khong giau logic trong model.
(Lan dau de model doan thang time_to_dry tu ca soil_moisture -> R2=0.965 nhung
feature_importances_ cho soil_moisture chiem 98.9%, tuc la model khong thuc su
hoc gi tu thoi tiet — leakage. Sau khi tach tang, R2 giam con ~0.54 nhung
feature importance can bang, dung voi vat ly bay hoi.)

Chay:
    python -m app.ml.train_irrigation_model
"""

from __future__ import annotations

from pathlib import Path

import joblib
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.model_selection import train_test_split

from app.ml.generate_synthetic_data import build_dataset

FEATURE_COLUMNS = ["temperature", "humidity", "lux"]
TARGET_COLUMN = "drying_rate_per_hour"
MODEL_PATH = Path(__file__).parent / "irrigation_model_checkpoint.pkl"


def train(n_zones: int = 40, n_steps: int = 432) -> None:
    df = build_dataset(n_zones=n_zones, n_steps=n_steps)
    X, y = df[FEATURE_COLUMNS], df[TARGET_COLUMN]

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

    model = GradientBoostingRegressor(n_estimators=200, max_depth=3, learning_rate=0.05, random_state=42)
    model.fit(X_train, y_train)

    pred = model.predict(X_test)
    mae = mean_absolute_error(y_test, pred)
    r2 = r2_score(y_test, pred)
    print(f"MAE: {mae:.3f} %/h   R2: {r2:.3f}")

    importances = sorted(zip(FEATURE_COLUMNS, model.feature_importances_), key=lambda x: -x[1])
    print("Feature importances:", [(name, round(val, 3)) for name, val in importances])

    joblib.dump({"model": model, "features": FEATURE_COLUMNS}, MODEL_PATH)
    print(f"Saved model to {MODEL_PATH}")


if __name__ == "__main__":
    train()
