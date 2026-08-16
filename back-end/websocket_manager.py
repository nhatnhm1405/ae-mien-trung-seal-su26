"""
websocket_manager.py — WebSocket manager cho FastAPI.

Quản lý kết nối WebSocket tới frontend, broadcast dữ liệu realtime:
  - Telemetry data (stream liên tục)
  - Anomaly alerts (khi phát hiện bất thường)
  - AI diagnosis (khi LLM trả kết quả)

Ref: HACKATHON_CONTEXT.md — "FastAPI + WebSocket /ws/telemetry"
"""
import json
import logging
import asyncio
from typing import Any

from fastapi import WebSocket, WebSocketDisconnect

logger = logging.getLogger("WebSocketManager")


class WebSocketManager:
    """
    Quản lý nhiều kết nối WebSocket đồng thời.
    
    Frontend kết nối vào → nhận stream dữ liệu realtime.
    Backend gọi broadcast() → đẩy data tới tất cả clients.
    """

    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        """Accept kết nối WebSocket mới."""
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"✅ WebSocket connected. Active: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        """Xóa kết nối đã ngắt."""
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        logger.info(f"WebSocket disconnected. Active: {len(self.active_connections)}")

    async def broadcast(self, message: dict):
        """
        Broadcast message tới TẤT CẢ clients đang kết nối.
        
        Message format gửi xuống frontend:
        {
            "type": "telemetry" | "anomaly" | "diagnosis" | "guardrail_veto",
            "data": { ... }
        }
        """
        if not self.active_connections:
            return

        payload = json.dumps(message, default=str)
        disconnected = []

        for connection in self.active_connections:
            try:
                await connection.send_text(payload)
            except (WebSocketDisconnect, RuntimeError, Exception) as e:
                logger.debug(f"Failed to send to client: {e}")
                disconnected.append(connection)

        # Dọn dẹp kết nối đã mất
        for conn in disconnected:
            self.disconnect(conn)

    async def broadcast_telemetry(self, data: dict):
        """Broadcast dữ liệu telemetry realtime."""
        await self.broadcast({
            "type": "telemetry",
            "data": data,
        })

    async def broadcast_anomaly(self, anomaly_result: dict):
        """Broadcast cảnh báo anomaly."""
        await self.broadcast({
            "type": "anomaly",
            "data": anomaly_result,
        })

    async def broadcast_diagnosis(self, diagnosis: dict):
        """Broadcast kết quả chẩn đoán AI."""
        await self.broadcast({
            "type": "diagnosis",
            "data": diagnosis,
        })

    async def broadcast_guardrail(self, guardrail_result: dict):
        """Broadcast kết quả guardrail (đặc biệt khi VETO)."""
        await self.broadcast({
            "type": "guardrail_veto",
            "data": guardrail_result,
        })

    @property
    def connection_count(self) -> int:
        return len(self.active_connections)


# Singleton instance — import từ main.py
ws_manager = WebSocketManager()
