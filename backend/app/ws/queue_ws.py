from __future__ import annotations

import asyncio
import logging
import os
import re
from collections import defaultdict
from datetime import date as calendar_date
from weakref import WeakValueDictionary

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, status

from app.services.ws_redis_pubsub import RedisPubSubBridge

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
            cls._instance._pubsub = RedisPubSubBridge(
                channel_prefix="queue_ws",
                redis_url=(os.getenv("WS_REDIS_URL") or os.getenv("REDIS_URL")),
            )
            cls._instance._redis_handlers = {}
            log.info("WSManager: создан новый экземпляр")
        return cls._instance

    def __init__(self) -> None:
        # Инициализация уже выполнена в __new__
        pass

    async def connect(self, ws: WebSocket, room: str) -> None:
        log.info("WSManager: connecting to room %s", room)
        self.rooms[room].add(ws)
        await self._ensure_room_subscription(room)
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
            self._dispatch(self._remove_room_subscription(room))
            log.info("WSManager: room %s removed (empty)", room)
        else:
            log.info("WSManager: room %s now has %d connections", room, len(s))

    async def _send_one(self, ws: WebSocket, data) -> None:
        try:
            await ws.send_json(data)
            log.info("WSManager: sent message to websocket in room")
        except Exception as e:
            log.error("WSManager: error sending to websocket: %s", e)
            # Use the canonical room lifecycle: direct set.discard()
            # removed the last socket but skipped Redis unsubscribe,
            # leaving a stale handler for future connections. A socket
            # may belong to multiple rooms, so disconnect each one.
            for room, sockets in list(self.rooms.items()):
                if ws in sockets:
                    self.disconnect(ws, room)

    def broadcast(self, room: str, data) -> None:
        log.info("WSManager: broadcasting to room %s", room)
        log.info(
            "WSManager: room %s has %d connections",
            room,
            len(self.rooms.get(room, set())),
        )
        log.info("WSManager: all rooms: %s", list(self.rooms.keys()))

        self._dispatch(self._broadcast_room(room, data, publish=True))

    def _dispatch(self, coro) -> None:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            asyncio.run(coro)
        else:
            loop.create_task(coro)

    def _room_channel(self, room: str) -> str:
        return f"room:{room}"

    def _room_subscription_lock(self, room: str) -> asyncio.Lock:
        lock = self._subscription_locks.get(room)
        if lock is None:
            lock = asyncio.Lock()
            self._subscription_locks[room] = lock
        return lock

    async def _ensure_room_subscription(self, room: str) -> None:
        # Serialize per room so a new subscribe cannot race an old
        # in-flight Redis unsubscribe on the same channel.
        async with self._room_subscription_lock(room):
            if room in self._redis_handlers:
                return
            if not self.rooms.get(room):
                return

            async def _handler(payload, _room: str = room) -> None:
                remote_data = payload.get("data", payload)
                await self._broadcast_room(_room, remote_data, publish=False)

            self._redis_handlers[room] = _handler
            await self._pubsub.subscribe(self._room_channel(room), _handler)

    async def _remove_room_subscription(self, room: str) -> None:
        async with self._room_subscription_lock(room):
            # disconnect() scheduled cleanup when its last socket left,
            # but a new socket may already have rejoined this room.
            if self.rooms.get(room):
                return
            handler = self._redis_handlers.pop(room, None)
            if handler is None:
                return
            await self._pubsub.unsubscribe(self._room_channel(room), handler)

    async def _broadcast_room(self, room: str, data, publish: bool) -> None:
        for ws in list(self.rooms.get(room, set())):
            log.info("WSManager: sending to websocket in room %s", room)
            await self._send_one(ws, data)

        if publish:
            await self._pubsub.publish(self._room_channel(room), {"data": data})


ws_manager = WSManager()
log.info("WSManager: создан глобальный экземпляр %d", id(ws_manager))


# -----------------------------------------------------------------------------
# UX Audit Stage 3 (Queue WebSocket):
# Helper для broadcast'а обновлений очереди всем подписчикам room'а.
#
# Queue endpoints (qr_queue.py, queue.py) вызывают эту функцию после
# мутаций (call-next, join, open, cancel, no-show, restore), чтобы
# admin-панель на /ws/queue мгновенно получила обновление вместо
# 30-секундного polling'а.
#
# Room формат: "{department}::{date}" — совпадает с тем, что использует
# ws_queue() endpoint при подключении клиента.
#
# ВАЖНО: функция синхронная с точки зрения caller'а (HTTP endpoint),
# но broadcast происходит асинхронно через asyncio.create_task().
# Это не блокирует HTTP-ответ.
# -----------------------------------------------------------------------------
def queue_update_departments(db, queue) -> list[str]:
    """Admin queue-WS room identities for a queue (QD-2C, round-17/18/30).

    The queue manager subscribes to ``specialist_{selectedId}::{date}`` —
    the legacy doctor identity. A resource-owned queue carries
    ``specialist_id = NULL``: the literal ``specialist_None`` room has no
    subscribers, so mutation broadcasts (join/restore/no-show) would only
    reach the connected manager through the 60-second polling fallback.
    The room therefore follows the ROUTING identity: the legacy
    specialists whose specialty routes to the queue's tag (the
    dual-ownership bridge, same join the registrar payload match uses).
    A BRIDGED queue (Codex round-30 P2: the 0059 backfill rows carry
    BOTH ids) is addressable through ANY routing sibling id — each
    queue manager subscribes to its own selected id — so it expands
    through the routing ids too (the retained synthetic's room kept
    first); pure doctor queues keep the legacy room byte-identically;
    a resource queue without routing doctors keeps the old dead-room
    form (no subscriber either way).
    """
    if queue is None:
        return ["unknown"]
    resource_id = getattr(queue, "queue_resource_id", None)
    if resource_id is not None and queue.specialist_id is not None:
        from app.crud.queue_resource_routing import routing_specialist_ids

        rooms = [f"specialist_{rid}" for rid in routing_specialist_ids(db, queue)]
        legacy = f"specialist_{queue.specialist_id}"
        if legacy not in rooms:
            rooms.append(legacy)
        return rooms
    if queue.specialist_id is not None:
        return [f"specialist_{queue.specialist_id}"]
    if resource_id is not None:
        from app.crud.queue_resource_routing import routing_specialist_ids

        return [f"specialist_{rid}" for rid in routing_specialist_ids(db, queue)]
    return [f"specialist_{queue.specialist_id}"]


def broadcast_queue_update(
    department: str,
    date: str,
    event_type: str,
    data: dict | None = None,
) -> None:
    """
    Broadcast queue update to all WS subscribers in the room.

    Args:
        department: Department/specialist identifier (e.g. "specialist_42")
        date: Queue date in YYYY-MM-DD format
        event_type: Event type (e.g. "queue_update", "patient_called", "entry_added")
        data: Optional additional payload data

    Example:
        broadcast_queue_update(
            department=f"specialist_{specialist_id}",
            date="2026-07-04",
            event_type="queue_update",
            data={"action": "call_next", "entry_id": 123}
        )
    """
    import asyncio

    room = f"{department.strip()}::{date.strip()}"
    message = {
        "type": event_type,
        "room": room,
        "data": data or {},
    }

    try:
        asyncio.get_running_loop()
    except RuntimeError:
        # No event loop running (e.g., in sync test context) — log and skip.
        log.warning(
            "broadcast_queue_update: no event loop, skipping broadcast to %s",
            room,
        )
        return

    # WSManager.broadcast() is synchronous and already schedules its
    # _broadcast_room coroutine via _dispatch(). Passing its None return
    # value to create_task() raises TypeError and interrupts QR mutations.
    ws_manager.broadcast(room, message)
    log.info(
        "broadcast_queue_update: queued broadcast to room %s, event=%s",
        room,
        event_type,
    )


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
    """QUEUE-AUDIT-28 P0-1: validate JWT, not just check token exists.

    Раньше принимал любой `Bearer foo` или `?token=anything` — anonymous
    пользователи получали доступ ко всем обновлениям очереди (PHI leak).

    PR-4: prefer Authorization header over ?token= query param. Query
    param still accepted for backward compat but emits a deprecation
    warning via the caller.

    PR-5: WS_DEV_ALLOW bypass REMOVED — it was a security risk because CI
    used it and the flag could leak to production. Tests now use TESTING=1
    (set by pytest conftest) instead.
    """
    # TESTING is an in-process pytest convenience, not a deployment
    # authentication override. Only explicitly named local/test modes may
    # bypass JWT verification; staging, QA and production always verify.
    environment = os.getenv("ENV", "dev").strip().lower()
    if (
        os.getenv("TESTING", "0") == "1"
        and environment in ("dev", "development", "test", "testing")
    ):
        return True
    # Extract token from header (preferred) or query param (legacy)
    auth = headers.get("authorization") or headers.get("Authorization")
    token = None
    if auth and auth.lower().startswith("bearer "):
        token = auth.split(" ", 1)[1].strip()
    elif token_qs:
        # PR-4: query-string JWT is insecure — log deprecation
        log.warning(
            "WS auth via ?token= query param is deprecated and insecure "
            "(use Authorization header or Sec-WebSocket-Protocol subprotocol); "
            "path=ws/queue"
        )
        token = token_qs.strip()
    if not token:
        return False
    # Validate JWT
    try:
        import jwt as _jwt

        from app.core.config import settings as _settings
        payload = _jwt.decode(token, _settings.SECRET_KEY, algorithms=[_settings.ALGORITHM])
        # Resolve the principal before checking revocation: JWT "sub" may
        # be a username, not a numeric ID. Both exact-JTI and all-user
        # revocation sentinels require the stable database user ID.
        from app.api.v1.endpoints.websocket_auth import _resolve_websocket_user
        from app.db.session import SessionLocal as _SessionLocal
        from app.services.token_blacklist_service import TokenBlacklistService

        _db = _SessionLocal()
        try:
            user = _resolve_websocket_user(payload, _db)
            if user is None:
                return False
            jti = payload.get("jti")
            lookup_jti = jti if isinstance(jti, str) else ""
            if TokenBlacklistService.is_token_blacklisted(
                _db, lookup_jti, user_id=user.id
            ):
                return False
        finally:
            _db.close()
        return True
    except Exception:
        return False


def _queue_room_permitted(token: str | None, department: str, day: str) -> bool:
    """Allow only staff queue managers or the selected active doctor.

    This is a second, room-specific admission check after the legacy
    _auth_ok boolean gate. Do not trust JWT subjects or room identifiers
    without validation: specialist_N denotes Doctor.id, not User.id.
    """
    if not isinstance(department, str) or not isinstance(day, str):
        return False
    match = re.fullmatch(r"specialist_([1-9][0-9]*)", department.strip())
    if match is None or not token:
        return False
    try:
        parsed_day = calendar_date.fromisoformat(day.strip())
        if parsed_day.isoformat() != day.strip():
            return False
    except (TypeError, ValueError):
        return False

    try:
        import jwt as _jwt

        from app.core.config import settings as _settings

        payload = _jwt.decode(
            token, _settings.SECRET_KEY, algorithms=[_settings.ALGORITHM]
        )
    except Exception:
        return False

    from app.api.v1.endpoints.websocket_auth import _resolve_websocket_user
    from app.db.session import SessionLocal as _SessionLocal
    from app.models.clinic import Doctor
    from app.services.authorization.staff import staff_authorization_service
    from app.services.token_blacklist_service import TokenBlacklistService

    try:
        db = _SessionLocal()
    except Exception:
        log.warning("Queue room authorization DB unavailable; denying subscription")
        return False

    try:
        user = _resolve_websocket_user(payload, db)
        if user is None or not getattr(user, "is_active", False):
            return False

        # The all-user revocation sentinel needs the resolved database ID,
        # even for JWTs whose subject is a username or which lack a JTI.
        jti = payload.get("jti")
        lookup_jti = jti if isinstance(jti, str) else ""
        if TokenBlacklistService.is_token_blacklisted(
            db, lookup_jti, user_id=user.id
        ):
            return False

        if staff_authorization_service.can_manage_queue(user):
            return True
        if not staff_authorization_service.can_read_queue(user):
            return False

        # queue:read is granted to doctors, but not globally across the
        # clinic. Compare the selected Doctor.id, not the JWT User.id.
        doctor = (
            db.query(Doctor)
            .filter(Doctor.user_id == user.id, Doctor.active.is_(True))
            .first()
        )
        return doctor is not None and doctor.id == int(match.group(1))
    except Exception:
        log.warning("Queue room permission lookup failed; denying subscription")
        return False
    finally:
        db.close()


# -----------------------------------------------------------------------------
# PR-5: /ws/noauth endpoint REMOVED — was a literal no-auth WebSocket.
# Even though it was disabled in production, it's a security risk in
# dev/staging. Use authenticated /ws/queue instead.
# -----------------------------------------------------------------------------
@router.websocket("/ws/queue")
async def ws_queue(
    websocket: WebSocket, department: str, date: str, token: str | None = None
):
    origin = websocket.headers.get("origin")
    log.info(
        "WS connect origin=%s path=%s",
        origin,
        websocket.url.path,
    )

    # PR-4: also extract token from subprotocol/Authorization header
    # so clients don't need to put JWT in the URL.
    from app.api.v1.endpoints.ws_token import (
        accept_echoing_subprotocol,
        extract_ws_token,
    )
    secure_token = extract_ws_token(websocket)
    if secure_token and not token:
        token = secure_token

    # ✅ SECURITY: Check environment
    env = os.getenv("ENV", "dev").lower()
    is_production = env in ("prod", "production")

    # PR-5: WS_DEV_ALLOW bypass REMOVED — was a security risk. Tests use
    # TESTING=1 (handled in _auth_ok) instead.

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

    # Guard the specific room after token validation and before joining.
    # Existing local pytest fixtures may run without seeded users; deployed
    # environments, including a leaked TESTING=1 in production, never skip
    # this room authorization check.
    local_test_mode = (
        os.getenv("TESTING", "0") == "1"
        and env in ("dev", "development", "test", "testing")
    )
    if not local_test_mode and not _queue_room_permitted(token, department, date):
        await websocket.accept()
        await websocket.send_json(
            {"type": "error", "reason": "queue room access denied"}
        )
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    # Only after both checks: browsers offering bearer.<jwt> require the
    # server to select an offered Sec-WebSocket-Protocol. Keep the plain
    # accept() path for legacy Authorization/query-token clients.
    if websocket.headers.get("sec-websocket-protocol"):
        await accept_echoing_subprotocol(websocket)
    else:
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

            except WebSocketDisconnect:
                log.info("WebSocket disconnected: %s", room)
                break
            except TimeoutError:
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
            except Exception:
                log.warning("Queue WebSocket receive failed; closing")
                break
    except WebSocketDisconnect:
        log.info(f"WebSocket disconnected: {room}")
    finally:
        heartbeat_task.cancel()
        try:
            await heartbeat_task
        except asyncio.CancelledError:
            pass
        ws_manager.disconnect(websocket, room)
