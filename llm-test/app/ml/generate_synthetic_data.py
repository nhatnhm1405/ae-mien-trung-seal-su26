"""
Synthetic training data cho Irrigation Priority Model.

Vi sao khong dung thang GET /api/devices/{code}/history tu simulator that:
app/mqtt_client.py::_simulate_reading() sinh so ngau nhien doc lap moi tick
(vd soil_moisture = uniform(20,60) khong lien quan gi den thoi tiet truoc do),
nen khong co quan he nhan qua thoi tiet -> do am de model hoc. Phai tu mo phong
vat ly (bay hoi phu thuoc nhiet do/do am/nang) de co nhan (label) that.

Dem 3 ngay/khu voi chu ky ngay-dem cho nhiet do/nang, moi khu co climate/soil-type
rieng de model khong overfit vao 1 kieu thoi tiet duy nhat.
"""

import numpy as np
import pandas as pd

STEP_MINUTES = 10
DRY_THRESHOLD = 25.0
MAX_HORIZON_STEPS = 144  # cap 24h ahead
RATE_HORIZON_STEPS = 6  # target = toc do bay hoi trung binh trong 1h toi


def simulate_zone(n_steps: int = 432, seed: int = 0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    hours = np.arange(n_steps) * (STEP_MINUTES / 60.0)
    day_phase = (hours % 24) / 24.0 * 2 * np.pi

    climate_heat = rng.uniform(0.8, 1.3)
    base_temp = rng.uniform(24, 30)
    lux_amp = rng.uniform(60000, 95000)
    drying_rate_scale = rng.uniform(0.35, 0.65)

    temperature = base_temp + 6 * climate_heat * np.sin(day_phase - np.pi / 2) + rng.normal(0, 0.8, n_steps)
    lux = np.clip(lux_amp * np.sin(day_phase - np.pi / 2), 0, None) + rng.normal(0, 500, n_steps)
    lux = np.clip(lux, 0, None)
    humidity = np.clip(78 - 1.0 * (temperature - 27) + rng.normal(0, 3, n_steps), 20, 95)

    moisture = np.zeros(n_steps)
    moisture[0] = rng.uniform(55, 95)
    for t in range(1, n_steps):
        temp_norm = max((temperature[t] - 15) / 20, 0)
        humidity_factor = (100 - humidity[t]) / 100
        lux_norm = lux[t] / 80000
        loss = drying_rate_scale * (0.4 * temp_norm + 0.3 * humidity_factor + 0.3 * lux_norm)
        loss = max(loss + rng.normal(0, 0.05), 0)
        moisture[t] = max(moisture[t - 1] - loss, 0)

    return pd.DataFrame(
        {
            "step": np.arange(n_steps),
            "temperature": temperature,
            "humidity": humidity,
            "lux": lux,
            "soil_moisture": moisture,
            "zone_id": f"zone_seed{seed}",
        }
    )


def compute_time_to_dry(moisture: np.ndarray) -> np.ndarray:
    n = len(moisture)
    result = np.full(n, float(MAX_HORIZON_STEPS))
    below = moisture <= DRY_THRESHOLD
    next_dry = None
    for t in range(n - 1, -1, -1):
        if below[t]:
            next_dry = t
        result[t] = min(next_dry - t, MAX_HORIZON_STEPS) if next_dry is not None else float(MAX_HORIZON_STEPS)
    return result


def add_features(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["moisture_slope"] = df["soil_moisture"].diff(3).fillna(0) / 3
    df["time_to_dry_steps"] = compute_time_to_dry(df["soil_moisture"].to_numpy())
    df["time_to_dry_hours"] = df["time_to_dry_steps"] * STEP_MINUTES / 60.0

    horizon_hours = RATE_HORIZON_STEPS * STEP_MINUTES / 60.0
    future_moisture = df["soil_moisture"].shift(-RATE_HORIZON_STEPS)
    df["drying_rate_per_hour"] = (df["soil_moisture"] - future_moisture) / horizon_hours
    return df


def build_dataset(n_zones: int = 40, n_steps: int = 432) -> pd.DataFrame:
    frames = [add_features(simulate_zone(n_steps=n_steps, seed=s)) for s in range(n_zones)]
    dataset = pd.concat(frames, ignore_index=True)
    return dataset.dropna(subset=["drying_rate_per_hour"]).reset_index(drop=True)


if __name__ == "__main__":
    dataset = build_dataset()
    print(f"Generated {len(dataset)} rows across {dataset['zone_id'].nunique()} simulated zones")
    print(dataset[["soil_moisture", "temperature", "humidity", "lux", "drying_rate_per_hour"]].describe())
