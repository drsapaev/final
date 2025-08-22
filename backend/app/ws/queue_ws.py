from __future__ import annotations

import asyncio
import logging
import os
from collections import defaultdict
from typing import Dict, Set

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, status

log = logging.getLogger("ws.queue")

router = APIRouter()

# -----------------------------------------------------------------------------
# Менеджер WS-комнат
# -----------------------------------------------------------------------------
class WSManager:
    def __init__(self) -> None:
        self.rooms: Dict[str, Set[WebSocket]] = defaultdict(set)

    async def connect(self, ws: WebSocket, room: str) -> None:
        self.rooms[room].add(ws)

    def disconnect(self, ws: WebSocket, room: str) -> None:
        s = self.rooms.get(room)
        if not s:
            return
        s.discard(ws)
        if not s:
            self.rooms.pop(room, None)

    async def _send_one(self, ws: WebSocket, data) -> None:
        try:
            await ws.send_json(data)
        except Exception:
            # удалить «мертвый» сокет из всех комнат
            for r, set_ws in list(self.rooms.items()):
                if ws in set_ws:
                    set_ws.discard(ws)
                    if not set_ws:
                        self.rooms.pop(r, None)

    def broadcast(self, room: str, data) -> None:
        for ws in list(self.rooms.get(room, set())):
            asyncio.create_task(self._send_one(ws, data))


ws_manager = WSManager()

def _origin_allowed(origin: str | None) -> bool:
    if os.getenv("CORS_DISABLE", "0") == "1":
        return True
    if not origin:
        return False
    allowed = [
        o.strip()
        for o in os.getenv(
            "CORS_ORIGINS", "http://localhost:5173,http://localhost:3000"
        ).split(",")
        if o.strip()
    ]
    return origin in allowed

def _auth_ok(headers, token_qs: str | None) -> bool:
    if os.getenv("WS_DEV_ALLOW", "0") == "1":
        return True
    auth = headers.get("authorization") or headers.get("Authorization")
    if auth and auth.lower().startswith("bearer "):
        return True
    if token_qs:
        return True
    return False

# -----------------------------------------------------------------------------
# DEBUG: полностью безусловный сокет для диагностики
# -----------------------------------------------------------------------------
@router.websocket("/ws/noauth")
async def ws_noauth(websocket: WebSocket):
    # принимаем рукопожатие сразу и шлём привет
    await websocket.accept()
    await websocket.send_json({"type": "connected", "room": "noauth"})
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass

# -----------------------------------------------------------------------------
# Основной сокет очереди: СНАЧАЛА accept(), потом проверки
# -----------------------------------------------------------------------------
@router.websocket("/ws/queue")
async def ws_queue(websocket: WebSocket, department: str, date: str, token: str | None = None):
    origin = websocket.headers.get("origin")
    log.info("WS connect origin=%s path=%s query=%s", origin, websocket.url.path, websocket.url.query)

    # ✅ DEV shortcut: если разрешён DEV-режим, сразу принимаем
    if os.getenv("WS_DEV_ALLOW", "0") == "1":
        await websocket.accept()
        await websocket.send_json({"type": "dev.accepted", "room": f"{department}::{date}"})
        return

    # Origin
    if not _origin_allowed(origin):
        await websocket.accept()
        await websocket.send_json({"type": "error", "reason": "origin not allowed"})
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    # Auth
    if not _auth_ok(websocket.headers, token):
        await websocket.accept()
        await websocket.send_json({"type": "error", "reason": "auth required"})
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    # ✅ Только после всех проверок — accept
    await websocket.accept()

    room = f"{department.strip()}::{date.strip()}"
    await ws_manager.connect(websocket, room)

    try:
        await websocket.send_json({"type": "queue.connected", "room": room})
        while True:
            try:
                await websocket.receive_text()
            except Exception:
                await asyncio.sleep(0.05)
    except WebSocketDisconnect:
        pass
    finally:
        ws_manager.disconnect(websocket, room)
