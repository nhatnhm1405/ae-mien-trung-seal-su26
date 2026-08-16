"""
Train 1 EllipticEnvelope / thiet bi (uoc luong Gaussian manh + khoang cach
Mahalanobis) — DA THAY THE IsolationForest.

Ly do doi: kiem chung thuc nghiem tren 177 mau that cho thay IsolationForest
co "diem mu" — mot gia tri cuc doan that (soil_moisture=2.0 trong khi thuc te
quan sat 24.3-46.9) khong bi gan co (score=+0.06, "binh thuong"). Nguyen nhan:
IsolationForest do "can bao nhieu nhat cat de co lap", khong do khoang cach.
Diem truy van ngoai vung du lieu train luon roi ve 1 phia o moi nhat cat va
"di nho" cung do sau co lap voi cum diem that gan bien nhat — khong ti le
voi do cuc doan ve tri so. EllipticEnvelope dung khoang cach Mahalanobis
that su: cang xa tam phan phoi (co tinh tuong quan giua cac metric) thi
diem cang thap mot cach DON DIEU, khong co hien tuong "di nho" nay.

Uu tien train_from_csv() bang du lieu MQTT THAT (thu qua collect_real_data.py)
khi co du. train_all() (Gaussian synthetic) chi dung du phong khi CHUA co
ket noi MQTT that (vd dev/test o nha) — xem generate_normal_operating_data.py.

Chay voi du lieu that:
    python -m app.ml.train_anomaly_model --real app/ml/real_telemetry_log.csv

Chay voi du lieu synthetic (fallback):
    python -m app.ml.train_anomaly_model
"""

from __future__ import annotations

import sys
from pathlib import Path

import joblib
import pandas as pd
from sklearn.covariance import EllipticEnvelope

from app.config import DEVICES
from app.ml.generate_normal_operating_data import sample_normal

MODEL_DIR = Path(__file__).parent
# Da quet 0.005/0.01/0.02/0.03 tren du lieu that: moi muc deu bat injection cuc
# doan voi bien do rat lon (score -18 den -368 so nguong ~0), nen contamination
# chi anh huong ty le bao dong gia luc van hanh binh thuong, khong anh huong
# kha nang bat bat thuong that. Chon 0.01 (~1.1% flagged tren du lieu train)
# de can bang giua it on ao luc demo binh thuong va van du nhay.
CONTAMINATION = 0.01
N_SAMPLES = 3000
MIN_REAL_SAMPLES = 30  # duoi nguong nay, thong ke chua du tin cay de train


def model_path(device_code: str) -> Path:
    return MODEL_DIR / f"anomaly_{device_code}.pkl"


def atomic_dump(obj, path: Path) -> None:
    """Ghi ra file tam roi Path.replace() (atomic tren cung o dia) — tranh
    truong hop 1 process khac (anomaly_model.py::_load()) doc phai file dang
    ghi do trong luc live_train.py refit nen o process khac. Dung chung giua
    train_anomaly_model.py va live_train.py."""
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    joblib.dump(obj, tmp_path)
    tmp_path.replace(path)


def _fit_and_save(code: str, metrics: list[str], df: pd.DataFrame, n_desc: str) -> None:
    model = EllipticEnvelope(contamination=CONTAMINATION, random_state=42)
    model.fit(df[metrics])
    atomic_dump({"model": model, "metrics": metrics}, model_path(code))
    print(f"{code}: trained on {len(df)} {n_desc} samples, metrics={metrics}")


def train_all(n_samples: int = N_SAMPLES) -> None:
    for code, spec in DEVICES.items():
        df = sample_normal(code, n_samples)
        _fit_and_save(code, spec.metrics, df, "synthetic")


def train_from_csv(csv_path: Path) -> None:
    """csv_path: log tu collect_real_data.py, cot dat ten f'{device_code}_{metric}'."""
    df = pd.read_csv(csv_path)

    for code, spec in DEVICES.items():
        metrics = spec.metrics
        prefixed = [f"{code}_{m}" for m in metrics]

        missing_cols = [c for c in prefixed if c not in df.columns]
        if missing_cols:
            print(f"{code}: bo qua — thieu cot {missing_cols} trong {csv_path}")
            continue

        sub = df[prefixed].dropna()
        if len(sub) < MIN_REAL_SAMPLES:
            print(f"{code}: chi co {len(sub)} mau that (< {MIN_REAL_SAMPLES}), qua it de tin cay — bo qua")
            continue

        sub = sub.rename(columns=dict(zip(prefixed, metrics)))
        _fit_and_save(code, metrics, sub, "REAL")
        print(f"  {sub.describe().loc[['mean', 'std', 'min', 'max']].to_string()}")


if __name__ == "__main__":
    if "--real" in sys.argv:
        idx = sys.argv.index("--real")
        csv_arg = sys.argv[idx + 1] if idx + 1 < len(sys.argv) else str(MODEL_DIR / "real_telemetry_log.csv")
        train_from_csv(Path(csv_arg))
    else:
        train_all()
