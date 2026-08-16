"""
Du lieu "van hanh binh thuong" de train IsolationForest.

Khong dung app/mqtt_client.py::_simulate_reading() vi no sinh so theo phan
phoi DEU (uniform) — khong co "cum binh thuong" nao de IsolationForest hoc
ranh gioi, nen tin hieu co lap gan nhu bang nhau o moi diem (da kiem chung:
model bo sot ca soil_moisture=90 o nhiet do giua khoang). Thay bang phan
phoi chuan (Gaussian) quanh diem van hanh thuc te — vua sua loi ky thuat,
vua thuc te hon (cam bien nong trai that dao dong quanh 1 diem, khong deu tam tap).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

# (mean, std) cho tung metric — diem van hanh "binh thuong" dien hinh
NORMAL_PARAMS: dict[str, dict[str, tuple[float, float]]] = {
    "SOIL_01": {"soil_moisture": (42.0, 8.0), "temperature": (29.0, 2.5)},
    "WEATHER_01": {"temperature": (29.0, 2.5), "humidity": (65.0, 10.0)},
    "PUMP_01": {"flow_rate": (18.0, 6.0), "power": (850.0, 200.0)},
    "PH_01": {"ph": (6.5, 0.25)},
    "TANK_01": {"level": (60.0, 14.0)},
    "SUN_01": {"lux": (40000.0, 18000.0)},
}

# gioi han vat ly cung de clip (khong am, khong vuot khung thiet bi)
CLIP_RANGES: dict[str, tuple[float, float]] = {
    "soil_moisture": (0.0, 100.0),
    "humidity": (0.0, 100.0),
    "level": (0.0, 100.0),
    "ph": (0.0, 14.0),
    "lux": (0.0, 120000.0),
    "flow_rate": (0.0, 60.0),
    "power": (0.0, 3000.0),
    "temperature": (-10.0, 55.0),
}


def sample_normal(device_code: str, n: int, seed: int = 0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    params = NORMAL_PARAMS[device_code]
    data = {}
    for metric, (mean, std) in params.items():
        values = rng.normal(mean, std, n)
        lo, hi = CLIP_RANGES.get(metric, (-np.inf, np.inf))
        data[metric] = np.clip(values, lo, hi)
    return pd.DataFrame(data)
