"""
Hot storage trong RAM — thay thế Redis Streams theo đúng khuyến nghị
"đơn giản hoá triệt để" trong file context (deque thay vì Redis/Kafka).

Mỗi thiết bị có 1 deque(maxlen=BUFFER_MAXLEN) chứa các bản ghi telemetry gần nhất.
Đây là nơi Field IoT Agent (AI/ML teammate) và Dashboard (Frontend teammate) đọc dữ liệu.
"""

from __future__ import annotations

import time
import threading
from collections import deque
from datetime import datetime, timezone

import pandas as pd

from app.config import DEVICES, BUFFER_MAXLEN, STALE_THRESHOLD_SECONDS, SLIDING_WINDOW_SECONDS


class DeviceState:
    """Giữ toàn bộ lịch sử gần đây + trạng thái kết nối của 1 thiết bị."""

    def __init__(self, device_code: str):
        self.device_code = device_code
        self.buffer: deque = deque(maxlen=BUFFER_MAXLEN)
        self.last_seen_ts: float | None = None  # epoch seconds, dùng event-time từ payload

    def add_reading(self, metrics: dict, event_time: float | None = None):
        """Thêm 1 bản ghi. event_time = timestamp cảm biến (event-time), KHÔNG dùng giờ hệ thống
        nếu payload có cung cấp — đúng nguyên tắc event-time vs processing-time."""
        ts = event_time if event_time is not None else time.time()
        record = {"ts": ts, **metrics}
        self.buffer.append(record)
        # last_seen dùng giờ nhận thật (processing time) để tính độ mới/staleness cho UI,
        # còn windowing tính toán dùng event-time trong buffer.
        self.last_seen_ts = time.time()

    @property
    def is_stale(self) -> bool:
        if self.last_seen_ts is None:
            return True
        return (time.time() - self.last_seen_ts) > STALE_THRESHOLD_SECONDS

    @property
    def latest(self) -> dict | None:
        return self.buffer[-1] if self.buffer else None

    def to_dataframe(self) -> pd.DataFrame:
        if not self.buffer:
            return pd.DataFrame()
        df = pd.DataFrame(list(self.buffer))
        df["dt"] = pd.to_datetime(df["ts"], unit="s", utc=True)
        return df.set_index("dt").sort_index()

    def rolling_stats(self, window_seconds: int = SLIDING_WINDOW_SECONDS) -> dict:
        """Sliding window stats: mean, std, và độ dốc (diff) — bắt xu hướng,
        không chỉ giá trị tức thời. Ví dụ dùng: 'độ ẩm đất đang giảm X%/giờ'."""
        df = self.to_dataframe()
        if df.empty:
            return {}
        numeric_cols = [c for c in df.columns if c != "ts"]
        out = {}
        window = f"{window_seconds}s"
        for col in numeric_cols:
            series = df[col].astype(float)
            roll = series.rolling(window)
            mean = roll.mean().iloc[-1]
            std = roll.std().iloc[-1]
            # tốc độ thay đổi (đơn vị/giờ) giữa điểm đầu và cuối cửa sổ
            # (Series.last() đã bị xoá từ pandas 3.0 — cắt thủ công theo mốc thời gian)
            cutoff = series.index[-1] - pd.Timedelta(seconds=window_seconds)
            windowed = series[series.index >= cutoff]
            slope_per_hour = None
            if len(windowed) >= 2:
                dt_hours = (windowed.index[-1] - windowed.index[0]).total_seconds() / 3600
                if dt_hours > 0:
                    slope_per_hour = (windowed.iloc[-1] - windowed.iloc[0]) / dt_hours
            out[col] = {
                "current": float(series.iloc[-1]),
                "mean": None if pd.isna(mean) else float(mean),
                "std": None if pd.isna(std) else float(std),
                "slope_per_hour": None if slope_per_hour is None else round(slope_per_hour, 3),
            }
        return out


class FarmState:
    """Singleton trạng thái toàn nông trại: tất cả DeviceState + kế hoạch + nhiệm vụ."""

    def __init__(self):
        self._lock = threading.Lock()
        self.devices: dict[str, DeviceState] = {
            code: DeviceState(code) for code in DEVICES
        }
        self.plans: dict[str, dict] = {}     # irrigation plans (Action Agent tạo)
        self.tasks: dict[str, dict] = {}     # inspection tasks / công việc hiện trường
        self.notifications: list[dict] = []  # thông báo đã gửi
        self._next_id = 1

    def new_id(self, prefix: str) -> str:
        with self._lock:
            _id = f"{prefix}-{self._next_id:04d}"
            self._next_id += 1
            return _id

    def ingest(self, device_code: str, metrics: dict, event_time: float | None = None):
        if device_code not in self.devices:
            # thiết bị lạ không có trong danh mục -> vẫn log nhưng không tạo state ngoài spec
            return False
        self.devices[device_code].add_reading(metrics, event_time=event_time)
        return True

    def snapshot(self) -> dict:
        """Trạng thái tổng hợp toàn nông trại — dùng cho REST /api/devices và cho Agent đọc."""
        result = {}
        for code, dev in self.devices.items():
            spec = DEVICES[code]
            result[code] = {
                "device_code": code,
                "name": spec.name,
                "units": spec.units,
                "latest": dev.latest,
                "is_stale": dev.is_stale,
                "last_seen_ts": dev.last_seen_ts,
                "last_seen_iso": (
                    datetime.fromtimestamp(dev.last_seen_ts, tz=timezone.utc).isoformat()
                    if dev.last_seen_ts else None
                ),
                "rolling": dev.rolling_stats(),
            }
        return result

    def readable_devices(self) -> list[str]:
        """Danh sách thiết bị đang có dữ liệu và KHÔNG stale — dùng để tự chấm
        điều kiện 'tối thiểu 4/6 thiết bị' và để Agent biết phần nào tin được."""
        return [c for c, d in self.devices.items() if d.latest is not None and not d.is_stale]

    def stale_devices(self) -> list[str]:
        return [c for c, d in self.devices.items() if d.is_stale]


# instance dùng chung toàn app (import cái này ở nơi khác)
farm_state = FarmState()
