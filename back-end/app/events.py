"""
events.py — Tầng phát sự kiện realtime dùng chung cho toàn backend.

Trước khi hợp nhất, mỗi backend có 1 WebSocket manager riêng với format message
khác nhau (`{"type","data"}` vs `{"event","data"}`), nên Frontend không thể viết
1 handler duy nhất. File này là nguồn sự thật duy nhất về:

  1. Danh sách kết nối WebSocket đang mở (ws_manager)
  2. Format envelope gửi xuống client  -> xem ENVELOPE bên dưới
  3. Cầu nối thread MQTT (đồng bộ) -> asyncio event loop (bất đồng bộ)

ENVELOPE — MỌI message đẩy xuống client đều đúng dạng này, không ngoại lệ:

    {
      "type": "telemetry" | "anomaly" | "agent_insight" | "plan" | "task"
              | "notification" | "guardrail_veto" | "snapshot" | "system",
      "ts": 1786848903.151,   # epoch giây
      "payload": { ... }      # nội dung, tuỳ type
    }

Vì sao cần cầu nối thread: callback MQTT của paho chạy trong thread riêng của nó,
không phải trong event loop của uvicorn. Gọi thẳng `await ws.send()` từ đó sẽ ném
"no running event loop". Phải đi qua asyncio.run_coroutine_threadsafe() với tham
chiếu tới loop chính đã lưu lúc startup.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any

from fastapi import WebSocket

logger = logging.getLogger("events")


class WebSocketManager:
    """Quản lý nhiều kết nối WebSocket đồng thời và broadcast tới tất cả."""

    def __init__(self) -> None:
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info("WebSocket connected. Active: %d", len(self.active_connections))

    def disconnect(self, websocket: WebSocket) -> None:
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        logger.info("WebSocket disconnected. Active: %d", len(self.active_connections))

    async def send_json(self, websocket: WebSocket, message: dict) -> None:
        await websocket.send_text(json.dumps(message, default=str, ensure_ascii=False))

    async def broadcast(self, message: dict) -> None:
        if not self.active_connections:
            return
        payload = json.dumps(message, default=str, ensure_ascii=False)
        dead: list[WebSocket] = []
        for connection in self.active_connections:
            try:
                await connection.send_text(payload)
            except Exception as exc:  # client đã đóng / mạng rớt
                logger.debug("Gửi WS thất bại, sẽ dọn kết nối: %s", exc)
                dead.append(connection)
        for connection in dead:
            self.disconnect(connection)

    @property
    def connection_count(self) -> int:
        return len(self.active_connections)


ws_manager = WebSocketManager()


# ---------------------------------------------------------------------------
# Cầu nối thread MQTT -> asyncio loop
# ---------------------------------------------------------------------------
_loop: asyncio.AbstractEventLoop | None = None


def bind_loop(loop: asyncio.AbstractEventLoop) -> None:
    """Gọi 1 lần lúc startup của FastAPI, lưu lại loop chính để thread nền dùng."""
    global _loop
    _loop = loop
    logger.info("events: đã gắn asyncio loop cho cầu nối thread MQTT.")


def envelope(event_type: str, payload: Any, ts: float | None = None) -> dict:
    """Đóng gói 1 message đúng format ENVELOPE."""
    return {
        "type": event_type,
        "ts": ts if ts is not None else time.time(),
        "payload": payload,
    }


async def emit(event_type: str, payload: Any, ts: float | None = None) -> None:
    """Phát sự kiện từ trong async context (route handler)."""
    await ws_manager.broadcast(envelope(event_type, payload, ts))


def emit_threadsafe(event_type: str, payload: Any, ts: float | None = None) -> None:
    """Phát sự kiện từ thread nền (callback MQTT, simulator, pipeline).

    Bỏ qua im lặng nếu chưa có client nào — tránh tạo task vô ích khi chưa ai mở
    dashboard. Cũng bỏ qua nếu loop chưa gắn (VD: chạy script CLI không có server).
    """
    if _loop is None or ws_manager.connection_count == 0:
        return
    try:
        asyncio.run_coroutine_threadsafe(
            ws_manager.broadcast(envelope(event_type, payload, ts)), _loop
        )
    except Exception as exc:
        logger.debug("emit_threadsafe thất bại: %s", exc)
