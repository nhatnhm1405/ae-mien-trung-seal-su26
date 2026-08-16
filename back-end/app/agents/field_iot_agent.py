"""
Field IoT Agent — thuần I/O, KHÔNG gọi LLM.

Vai trò: đọc dữ liệu 6 thiết bị từ farm_state, gắn thêm data_age_seconds,
trả về snapshot sạch cho Irrigation & Resource Agent và Coordinator & Action
Agent dùng làm ngữ cảnh. Không tự suy luận, không tự quyết định gì — chỉ đọc
và chuẩn hoá.
"""

from __future__ import annotations

import time

from app.state import farm_state


def get_farm_snapshot() -> dict:
    """Snapshot dữ liệu IoT hiện tại, đã gắn độ mới (data_age_seconds) cho từng thiết bị.

    Đây là tool đầu tiên mà Coordinator & Action Agent BẮT BUỘC phải gọi trước khi
    suy luận bất cứ điều gì — không có agent nào khác được phép tự bịa số liệu thay nó.
    """
    now = time.time()
    auxiliary = set(farm_state.auxiliary_devices())

    # Chỉ trả 6 thiết bị Track B. Thiết bị phụ của BTC (AC_01) không được phát trên
    # topic nông nghiệp nên luôn stale — đưa vào ngữ cảnh thì Agent coi đó là sự cố
    # và lần chạy nào cũng đẻ thêm một phiếu "kiểm tra kết nối AC_01".
    snap = {code: dev for code, dev in farm_state.snapshot().items() if code not in auxiliary}
    for dev in snap.values():
        ts = dev.get("last_seen_ts")
        dev["data_age_seconds"] = None if ts is None else round(now - ts, 1)

    readable = [c for c in farm_state.readable_devices() if c not in auxiliary]
    return {
        "devices": snap,
        "readable_devices": readable,
        "stale_devices": farm_state.stale_devices(),
        "data_completeness": f"{len(readable)}/{len(snap)}",
    }
