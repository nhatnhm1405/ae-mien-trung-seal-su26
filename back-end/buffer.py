"""
buffer.py — Device-based Telemetry Buffer cho Smart Agriculture.

Luu tru du lieu cam bien theo device_code (SOIL_01, WEATHER_01, PUMP_01, PH_01, TANK_01, SUN_01).
Ho tro:
  - Stale detection (kiem tra do moi du lieu — Kich ban 3)
  - Farm snapshot (tong hop tat ca devices cho agents)
  - Thread-safe operations (goi tu MQTT callback thread)
"""
import os
import time
import logging
from collections import deque
from threading import Lock

logger = logging.getLogger("Buffer")

BUFFER_MAX_LEN = 500  # toi da 500 diem / device
STALE_THRESHOLD_SECONDS = int(os.getenv("STALE_THRESHOLD_SECONDS", 15))  # Du lieu >15s khong cap nhat = stale


class DeviceBuffer:
    """
    Thread-safe buffer luu tru telemetry data theo tung device.

    Usage:
        buffer = DeviceBuffer()
        buffer.add(telemetry_data)           # Goi tu MQTT callback
        snapshot = buffer.get_farm_snapshot() # Tong hop cho agents
    """

    def __init__(self, maxlen: int = BUFFER_MAX_LEN):
        self.maxlen = maxlen
        self._buffers: dict[str, deque] = {}
        self._lock = Lock()

    def add(self, data: dict):
        """
        Them mot diem du lieu telemetry vao buffer.

        Args:
            data: {"device_code": str, "timestamp": float, "metrics": dict, ...}
        """
        device_code = data.get("device_code", "UNKNOWN")
        with self._lock:
            if device_code not in self._buffers:
                self._buffers[device_code] = deque(maxlen=self.maxlen)
                logger.info(f"Created buffer for device: {device_code}")
            self._buffers[device_code].append(data)

    def get_latest(self, device_code: str) -> dict | None:
        """Lay du lieu moi nhat cua mot device."""
        with self._lock:
            buf = self._buffers.get(device_code)
            if not buf:
                return None
            return buf[-1]

    def get_history(self, device_code: str, n: int = 50) -> list[dict]:
        """Lay N diem du lieu gan nhat cua mot device."""
        with self._lock:
            buf = self._buffers.get(device_code)
            if not buf:
                return []
            return list(buf)[-n:]

    def get_all_devices(self) -> list[str]:
        """Liet ke tat ca device_code dang co du lieu."""
        with self._lock:
            return list(self._buffers.keys())

    def get_device_count(self, device_code: str) -> int:
        """Dem so diem du lieu hien co cua mot device."""
        with self._lock:
            buf = self._buffers.get(device_code)
            return len(buf) if buf else 0

    # ── Stale Detection (Kich ban 3: du lieu gian doan) ──

    def get_device_status(self, device_code: str, now: float | None = None) -> dict:
        """
        Kiem tra trang thai ket noi va do moi du lieu cua device.

        Returns:
            {
                "device_code": str,
                "connected": bool,       # co du lieu khong
                "stale": bool,           # du lieu qua cu
                "last_update": float,    # timestamp lan cuoi
                "age_seconds": float,    # bao lau roi chua cap nhat
                "data_points": int,
            }
        """
        if now is None:
            now = time.time()

        latest = self.get_latest(device_code)
        if latest is None:
            return {
                "device_code": device_code,
                "connected": False,
                "stale": True,
                "last_update": 0,
                "age_seconds": None,
                "data_points": 0,
            }

        last_ts = latest.get("timestamp", 0)
        age = now - last_ts

        return {
            "device_code": device_code,
            "connected": True,
            "stale": age > STALE_THRESHOLD_SECONDS,
            "last_update": last_ts,
            "age_seconds": round(age, 1),
            "data_points": self.get_device_count(device_code),
        }

    def get_all_device_status(self) -> list[dict]:
        """Trang thai ket noi cua tat ca devices."""
        from mqtt_client import DEVICE_REGISTRY

        now = time.time()
        statuses = []
        # Bao gom ca devices chua co du lieu (tu registry)
        all_codes = set(self.get_all_devices()) | set(DEVICE_REGISTRY.keys())
        for code in sorted(all_codes):
            statuses.append(self.get_device_status(code, now=now))
        return statuses

    # ── Farm Snapshot (tong hop cho agents) ──

    def get_farm_snapshot(self) -> dict:
        """
        Tong hop toan bo trang thai nong trai thanh 1 snapshot.
        Dung cho Coordinator Agent va IoT Agent.

        Returns:
            {
                "timestamp": float,
                "devices": {
                    "SOIL_01": {"metrics": {...}, "status": {...}},
                    ...
                },
                "stale_devices": ["PUMP_01", ...],
                "active_devices": ["SOIL_01", ...],
            }
        """
        from mqtt_client import DEVICE_REGISTRY

        now = time.time()
        latest_scenario = "NORMAL"
        snapshot = {
            "timestamp": now,
            "scenario": latest_scenario,
            "devices": {},
            "stale_devices": [],
            "active_devices": [],
        }

        for device_code in DEVICE_REGISTRY:
            status = self.get_device_status(device_code, now=now)
            latest = self.get_latest(device_code)

            if latest and latest.get("scenario"):
                latest_scenario = latest.get("scenario")

            device_info = {
                "status": status,
                "metrics": latest.get("metrics", {}) if latest else {},
                "scenario": latest.get("scenario", "NORMAL") if latest else "NORMAL",
                "last_timestamp": latest.get("timestamp", 0) if latest else 0,
            }
            snapshot["devices"][device_code] = device_info

            if status["stale"] or not status["connected"]:
                snapshot["stale_devices"].append(device_code)
            else:
                snapshot["active_devices"].append(device_code)

        snapshot["scenario"] = latest_scenario
        return snapshot

    def get_device_summary_for_llm(self, device_code: str, n: int = 10) -> dict:
        """
        Tao summary cua device de nhung vao LLM prompt.
        Chi giu cac truong can thiet, giam token.
        """
        history = self.get_history(device_code, n=n)
        status = self.get_device_status(device_code)

        readings = []
        for entry in history:
            readings.append({
                "ts": entry.get("timestamp"),
                **entry.get("metrics", {}),
            })

        return {
            "device_code": device_code,
            "status": "active" if not status["stale"] else "stale",
            "age_seconds": status["age_seconds"],
            "data_points": status["data_points"],
            "recent_readings": readings,
        }

    def get_farm_summary_for_llm(self) -> dict:
        """Tao summary toan bo farm cho LLM prompt (toi uu token)."""
        from mqtt_client import DEVICE_REGISTRY

        summary = {}
        for device_code, info in DEVICE_REGISTRY.items():
            latest = self.get_latest(device_code)
            status = self.get_device_status(device_code)
            summary[device_code] = {
                "name": info["name"],
                "status": "active" if not status["stale"] else "stale",
                "metrics": latest.get("metrics", {}) if latest else {},
            }
        return summary


# ─────────────────────────────────────────────────────
# Test doc lap
# ─────────────────────────────────────────────────────
if __name__ == "__main__":
    import random

    buf = DeviceBuffer(maxlen=100)
    base_time = time.time()

    # Gia lap 50 diem du lieu cho moi device
    for i in range(50):
        ts = base_time + i
        buf.add({"device_code": "SOIL_01", "timestamp": ts, "metrics": {"soil_moisture": 45 + random.gauss(0, 5), "temperature": 28 + random.gauss(0, 1)}})
        buf.add({"device_code": "WEATHER_01", "timestamp": ts, "metrics": {"temperature": 32 + random.gauss(0, 2), "humidity": 70 + random.gauss(0, 5)}})
        buf.add({"device_code": "PUMP_01", "timestamp": ts, "metrics": {"flow_rate": 15 + random.gauss(0, 2), "power": 250 + random.gauss(0, 20)}})
        buf.add({"device_code": "PH_01", "timestamp": ts, "metrics": {"ph": 6.5 + random.gauss(0, 0.3)}})
        buf.add({"device_code": "TANK_01", "timestamp": ts, "metrics": {"level": 75 - i * 0.3 + random.gauss(0, 1)}})
        buf.add({"device_code": "SUN_01", "timestamp": ts, "metrics": {"lux": 45000 + random.gauss(0, 5000)}})

    print("=== Device Status ===")
    for s in buf.get_all_device_status():
        print(f"  {s['device_code']:>12s} | connected={s['connected']}  stale={s['stale']}  points={s['data_points']}")

    print("\n=== Farm Snapshot ===")
    snap = buf.get_farm_snapshot()
    print(f"  Active: {snap['active_devices']}")
    print(f"  Stale:  {snap['stale_devices']}")
    for code, info in snap["devices"].items():
        print(f"  {code}: {info['metrics']}")
