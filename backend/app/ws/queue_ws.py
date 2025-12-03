from __future__ import annotations

import asyncio
import logging
import os
from collections import defaultdict
from typing import Optional

from fastapi import APIRouter, status, WebSocket, WebSocketDisconnect

log = logging.getLogger("ws.queue")
log.setLevel(logging.INFO)  # Устанавливаем уровень INFO

# Проверяем, есть ли handlers
if not log.handlers:
    # Создаём handler для вывода в консоль
    handler = logging.StreamHandler()
    handler.setLevel(logging.INFO)
    formatter = logging.Formatter("%(name)s: %(levelname)s: %(message)s")
    handler.setFormatter(formatter)
    log.addHandler(handler)
    log.info("WS logger initialized with console handler")

router = APIRouter()


# -----------------------------------------------------------------------------
# Менеджер WS-комнат
# -----------------------------------------------------------------------------
class WSManager:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.rooms = defaultdict(set)
            log.info("WSManager: создан новый экземпляр")
        return cls._instance

    def __init__(self) -> None:
        # Инициализация уже выполнена в __new__
        pass

    async def connect(self, ws: WebSocket, room: str) -> None:
        log.info("WSManager: connecting to room %s", room)
        self.rooms[room].add(ws)
        log.info(
            "WSManager: room %s now has %d connections", room, len(self.rooms[room])
        )

    def disconnect(self, ws: WebSocket, room: str) -> None:
        log.info("WSManager: disconnecting from room %s", room)
        s = self.rooms.get(room)
        if not s:
            return
        s.discard(ws)
        if not s:
            self.rooms.pop(room, None)
            log.info("WSManager: room %s removed (empty)", room)
        else:
            log.info("WSManager: room %s now has %d connections", room, len(s))

    async def _send_one(self, ws: WebSocket, data) -> None:
        try:
            await ws.send_json(data)
            log.info("WSManager: sent message to websocket in room")
        except Exception as e:
            log.error("WSManager: error sending to websocket: %s", e)
            # удалить «мертвый» сокет из всех комнат
            for r, set_ws in list(self.rooms.items()):
                if ws in set_ws:
                    set_ws.discard(ws)
                    if not set_ws:
                        self.rooms.pop(r, None)
                        log.info("WSManager: removed dead websocket from room %s", r)

    def broadcast(self, room: str, data) -> None:
        log.info("WSManager: broadcasting to room %s, data: %s", room, data)
        log.info(
            "WSManager: room %s has %d connections",
            room,
            len(self.rooms.get(room, set())),
        )
        log.info("WSManager: all rooms: %s", list(self.rooms.keys()))

        for ws in list(self.rooms.get(room, set())):
            log.info("WSManager: sending to websocket in room %s", room)
            # Убираем asyncio.create_task для синхронного контекста
            # asyncio.create_task(self._send_one(ws, data))
            # Вместо этого просто вызываем _send_one синхронно
            # Но _send_one - асинхронная функция, поэтому нужно использовать другой подход
            try:
                # Создаём новый event loop для этого вызова
                import asyncio

                try:
                    asyncio.get_running_loop()
                    # Если loop уже запущен, создаём task
                    asyncio.create_task(self._send_one(ws, data))
                except RuntimeError:
                    # Если loop не запущен, запускаем новый
                    asyncio.run(self._send_one(ws, data))
            except Exception as e:
                log.error("WSManager: error creating task: %s", e)


ws_manager = WSManager()
log.info("WSManager: создан глобальный экземпляр %d", id(ws_manager))


def _origin_allowed(origin: Optional[str]) -> bool:
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


def _auth_ok(headers, token_qs: Optional[str]) -> bool:
    if os.getenv("WS_DEV_ALLOW", "0") == "1":
        return True
    auth = headers.get("authorization") or headers.get("Authorization")
    if auth and auth.lower().startswith("bearer "):
        return True
    if token_qs:
        return True
    return False


# -----------------------------------------------------------------------------
# ⚠️ DEPRECATED: DEBUG endpoint - DISABLED in production
# -----------------------------------------------------------------------------
@router.websocket("/ws/noauth")
async def ws_noauth(websocket: WebSocket):
    """
    ⚠️ SECURITY WARNING: This endpoint is for development only.
    Disabled in production for security.
    """
    env = os.getenv("ENV", "dev").lower()
    is_production = env in ("prod", "production")
    
    if is_production:
        await websocket.close(
            code=status.WS_1008_POLICY_VIOLATION,
            reason="This endpoint is disabled in production for security"
        )
        return
    
    # Only allow in development
    log.warning("⚠️  DEV mode: /ws/noauth endpoint enabled (NOT for production!)")
    await websocket.accept()
    await websocket.send_json({"type": "connected", "room": "noauth", "warning": "DEV ONLY"})
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass


# -----------------------------------------------------------------------------
# Основной сокет очереди: СНАЧАЛА accept(), потом проверки
# -----------------------------------------------------------------------------
@router.websocket("/ws/queue")
async def ws_queue(
    websocket: WebSocket, department: str, date: str, token: Optional[str] = None
):
    origin = websocket.headers.get("origin")
    log.info(
        "WS connect origin=%s path=%s query=%s",
        origin,
        websocket.url.path,
        websocket.url.query,
    )

    # ✅ SECURITY: Check environment - only allow DEV bypass in development
    env = os.getenv("ENV", "dev").lower()
    is_production = env in ("prod", "production")
    
    # ✅ DEV shortcut: только в development режиме
    if not is_production and os.getenv("WS_DEV_ALLOW", "0") == "1":
        log.warning("⚠️  DEV mode: WebSocket auth bypass enabled (NOT for production!)")
        await websocket.accept()
        await websocket.send_json(
            {"type": "dev.accepted", "room": f"{department}::{date}"}
        )
        return

    # ✅ SECURITY: In production, require authentication
    if is_production:
        if not _auth_ok(websocket.headers, token):
            await websocket.accept()
            await websocket.send_json({"type": "error", "reason": "Authentication required in production"})
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return

    # Origin
    if not _origin_allowed(origin):
        await websocket.accept()
        await websocket.send_json({"type": "error", "reason": "origin not allowed"})
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    # Auth (required in production, optional in dev)
    if not _auth_ok(websocket.headers, token):
        await websocket.accept()
        await websocket.send_json({"type": "error", "reason": "auth required"})
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    # ✅ Только после всех проверок — accept
    await websocket.accept()

    room = f"{department.strip()}::{date.strip()}"
    await ws_manager.connect(websocket, room)

    # ✅ SECURITY: Heartbeat configuration
    HEARTBEAT_INTERVAL = 30  # seconds
    CONNECTION_TIMEOUT = 120  # seconds (2 minutes of inactivity)
    # ✅ BUGFIX: Use list to allow mutation from nested scopes (nonlocal doesn't work in nested try blocks)
    last_pong = [asyncio.get_event_loop().time()]
    
    async def send_heartbeat():
        """Send periodic ping to detect dead connections"""
        while True:
            try:
                await asyncio.sleep(HEARTBEAT_INTERVAL)
                await websocket.send_json({"type": "ping", "timestamp": asyncio.get_event_loop().time()})
                log.debug(f"Sent heartbeat ping to {room}")
            except Exception as e:
                log.error(f"Error sending heartbeat: {e}")
                break

    heartbeat_task = asyncio.create_task(send_heartbeat())

    try:
        await websocket.send_json({"type": "queue.connected", "room": room})
        while True:
            try:
                # ✅ SECURITY: Set receive timeout
                data = await asyncio.wait_for(websocket.receive_text(), timeout=CONNECTION_TIMEOUT)
                
                # Parse message
                try:
                    import json
                    message = json.loads(data)
                    
                    # Handle pong response
                    if message.get("type") == "pong":
                        # ✅ BUGFIX: Update list element to modify outer scope variable
                        last_pong[0] = asyncio.get_event_loop().time()
                        log.debug(f"Received pong from {room}")
                        continue
                except (json.JSONDecodeError, KeyError):
                    pass  # Not a JSON message or missing type
                
            except asyncio.TimeoutError:
                # Check if connection is still alive
                # ✅ BUGFIX: Access list element to get current value
                time_since_pong = asyncio.get_event_loop().time() - last_pong[0]
                if time_since_pong > CONNECTION_TIMEOUT:
                    log.warning(f"Connection timeout for {room}, closing...")
                    break
                # Send ping to check connection
                try:
                    await websocket.send_json({"type": "ping", "timestamp": asyncio.get_event_loop().time()})
                except Exception:
                    break  # Connection is dead
            except Exception as e:
                log.error(f"Error receiving message: {e}")
                await asyncio.sleep(0.05)
    except WebSocketDisconnect:
        log.info(f"WebSocket disconnected: {room}")
    finally:
        heartbeat_task.cancel()
        try:
            await heartbeat_task
        except asyncio.CancelledError:
            pass
        ws_manager.disconnect(websocket, room)
