"""
WebSocket connection manager for real-time solver progress.
"""

from __future__ import annotations

import json
from typing import Any

import structlog
from fastapi import WebSocket

logger = structlog.get_logger(__name__)


class ConnectionManager:
    def __init__(self) -> None:
        self._subscribers: dict[str, set[WebSocket]] = {}

    async def connect(self, run_id: str, ws: WebSocket) -> None:
        await ws.accept()
        self._subscribers.setdefault(run_id, set()).add(ws)
        logger.info("ws_connected", run_id=run_id)

    def disconnect(self, run_id: str, ws: WebSocket) -> None:
        subs = self._subscribers.get(run_id)
        if subs:
            subs.discard(ws)
            if not subs:
                del self._subscribers[run_id]
        logger.info("ws_disconnected", run_id=run_id)

    async def broadcast(self, run_id: str, message: dict[str, Any]) -> None:
        subs = self._subscribers.get(run_id)
        if not subs:
            return
        payload = json.dumps(message)
        stale: list[WebSocket] = []
        for ws in subs:
            try:
                await ws.send_text(payload)
            except Exception:
                stale.append(ws)
        for ws in stale:
            self.disconnect(run_id, ws)

    @property
    def active_connections(self) -> int:
        return sum(len(v) for v in self._subscribers.values())


manager = ConnectionManager()
live_manager = ConnectionManager()
