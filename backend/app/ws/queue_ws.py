from __future__ import annotations

import asyncio
import logging
import os
from collections import defaultdict
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
            # Per-room critical sections survive while operations await; unused
            # locks are released once no task is holding or awaiting them.
            cls._instance._subscription_locks = WeakValueDictionary()
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
            # удалить «мертвый» сокет из всех комнат
            for r, set_ws in list(self.rooms.items()):
                if ws in set_ws:
                    set_ws.discard(ws)
                    if not set_ws:
                        self.rooms.pop(r, None)
                        # QUEUEWSRELAY-BE-001: the last socket of a room died
                        # mid-send — mirror disconnect() and drop the Redis
                        # handler too. Previously the room was popped while
                        # _redis_handlers[room] stayed registered forever, so
                        # remote events kept invoking a dead-room handler
                        # (dead-room subscription leak). Scheduling via
                        # _dispatch keeps the send loop non-blocking.
                        self._dispatch(self._remove_room_subscription(r))
                        log.info("WSManager: removed dead websocket from room %s", r)

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
        # QUEUEWS-POST4008-SUBSCRIBE-01: a handler is cached only after the bridge
        # confirms Redis SUBSCRIBE. Serializing first connects also prevents a
        # second socket from treating an in-flight subscription as established.
        async with self._room_subscription_lock(room):
            if room in self._redis_handlers or not self.rooms.get(room):
                return

            async def _handler(payload, _room: str = room) -> None:
                remote_data = payload.get("data", payload)
                await self._broadcast_room(_room, remote_data, publish=False)

            channel = self._room_channel(room)
            try:
                subscribed = await self._pubsub.subscribe(channel, _handler)
            except Exception as exc:
                log.warning(
                    "WSManager: Redis subscribe failed for room %s: %s",
                    room,
                    type(exc).__name__,
                )
                subscribed = False

            if subscribed is True:
                self._redis_handlers[room] = _handler
                return

            # RedisPubSubBridge.subscribe can return False after adding its
            # handler if _ensure_ready failed. Explicitly undo that state,
            # otherwise a subsequent connect may get a false True result.
            try:
                await self._pubsub.unsubscribe(channel, _handler)
            except Exception as exc:
                log.warning(
                    "WSManager: Redis failed-subscribe cleanup for room %s: %s",
                    room,
                    type(exc).__name__,
                )
            log.warning(
                "WSManager: Redis room %s not subscribed; will retry on next connect",
                room,
            )

    async def _remove_room_subscription(self, room: str) -> None:
        # A queued unsubscribe can run after a new socket joins the same
        # room; do not remove its live handler. Holding this lock also
        # prevents an old in-flight unsubscribe from erasing a new subscribe.
        async with self._room_subscription_lock(room):
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
    room = f"{department.strip()}::{date.strip()}"
    message = {
        "type": event_type,
        "room": room,
        "data": data or {},
    }

    # QUEUEWSDISPATCH-BE-001: ws_manager.broadcast is a SYNCHRONOUS,
    # self-scheduling function — its own _dispatch() layer handles both the
    # running-loop and no-loop cases. The previous
    # ``loop.create_task(ws_manager.broadcast(room, message))`` first ran the
    # sync call (which scheduled the broadcast), then handed the returned
    # ``None`` to asyncio.create_task — a guaranteed
    # "TypeError: a coroutine was expected" on every queue mutation,
    # surfacing as false broadcast errors in endpoint logs while the inner
    # broadcast actually ran. Schedule through the manager's single
    # scheduling layer instead and never wrap a sync result in create_task.
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        # No event loop running (e.g., in sync test context) — log and skip.
        log.warning(
            "broadcast_queue_update: no event loop, skipping broadcast to %s",
            room,
        )
        return
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


class _TestingBypassPrincipal:
    """Dev/test-only marker principal for the TESTING=1 queue-WS bypass.

    QUEUEWSAUTH-BE-001: the bypass must never silence auth in production,
    and it carries no real identity — the room authorization gate treats it
    as "no identity to authorize" and lets the pytest harness through only
    while ENV is not production.
    """

    id = None
    role = "__ws_testing_bypass__"
    username = "__ws_testing__"


_WS_TESTING_PRINCIPAL = _TestingBypassPrincipal()


def _resolve_ws_auth(headers, token_qs: str | None):
    """QUEUE-AUDIT-28 P0-1: validate JWT, not just check token exists.

    Раньше принимал любой `Bearer foo` или `?token=anything` — anonymous
    пользователи получали доступ ко всем обновлениям очереди (PHI leak).

    PR-4: prefer Authorization header over ?token= query param. Query
    param still accepted for backward compat but emits a deprecation
    warning via the caller.

    PR-5: WS_DEV_ALLOW bypass REMOVED — it was a security risk because CI
    used it and the flag could leak to production. Tests now use TESTING=1
    (set by pytest conftest) instead.

    QUEUEWSAUTH-BE-001: the TESTING=1 bypass is now refused whenever
    ENV=production — the misconfigured combination "ENV=production,
    TESTING=1" no longer turns the mounted /ws/queue into an anonymous
    queue stream. Test harnesses keep the bypass in dev/test environments
    only.

    QUEUEWSAUTH-BE-002: the validated subject is resolved to a stable user
    BEFORE revocation is applied, so username-sub JWTs now go through the
    same exact-jti + all-user-sentinel blacklist checks as numeric-sub
    tokens. Previously the blacklist ran only under ``if jti and
    user_id`` with ``user_id`` derived from a numeric subject, so a
    revoked or bulk-invalidated username-sub token kept passing the
    standalone queue stream.

    Returns the resolved user (or the dev/test bypass principal), or None
    when the caller must be rejected.
    """
    env = os.getenv("ENV", "dev").lower()
    # PR-5: WS_DEV_ALLOW bypass removed. Only TESTING=1 (pytest) skips auth
    # so unit tests that don't seed users can still connect — and never in
    # production (QUEUEWSAUTH-BE-001).
    if os.getenv("TESTING", "0") == "1" and env not in ("prod", "production"):
        return _WS_TESTING_PRINCIPAL
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
        return None
    # Validate JWT
    try:
        import jwt as _jwt

        from app.core.config import settings as _settings
        payload = _jwt.decode(token, _settings.SECRET_KEY, algorithms=[_settings.ALGORITHM])
        from app.api.v1.endpoints.websocket_auth import _resolve_websocket_user
        from app.db.session import SessionLocal as _SessionLocal

        jti = payload.get("jti")
        _db = _SessionLocal()
        try:
            # QUEUEWSAUTH-BE-002: resolve the validated subject to a stable
            # user FIRST, then apply revocation for that user — one policy
            # for numeric and username subjects alike. The shared resolver
            # returns None for internal-only roles, missing users and
            # malformed subjects (QD-1.1 Codex round-3 P2).
            user = _resolve_websocket_user(payload, _db)
            if user is None:
                return None
            if jti:
                from app.services.token_blacklist_service import (
                    TokenBlacklistService,
                )

                if TokenBlacklistService.is_token_blacklisted(
                    _db, jti, user_id=user.id
                ):
                    log.warning(
                        "WS auth rejected: blacklisted token (jti=%s) "
                        "for user_id=%s",
                        jti,
                        user.id,
                    )
                    return None
        finally:
            _db.close()
        return user
    except Exception:
        return None


def _auth_ok(headers, token_qs: str | None) -> bool:
    """Boolean view of :func:`_resolve_ws_auth`.

    Kept as a named helper because existing tests assert the boolean
    contract directly (test_queue_resource_sentinel.py)."""
    return _resolve_ws_auth(headers, token_qs) is not None


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
    from app.api.v1.endpoints.ws_token import extract_ws_token
    secure_token = extract_ws_token(websocket)
    if secure_token and not token:
        token = secure_token

    # ✅ SECURITY: Check environment
    env = os.getenv("ENV", "dev").lower()
    is_production = env in ("prod", "production")

    # PR-5: WS_DEV_ALLOW bypass REMOVED — was a security risk. Tests use
    # TESTING=1 (handled in _resolve_ws_auth) instead — and the bypass is
    # refused in production (QUEUEWSAUTH-BE-001).

    # ✅ SECURITY: single JWT resolution for both checks below. The legacy
    # flow called _auth_ok twice (production gate, then unconditional gate);
    # both share one resolution now.
    user = _resolve_ws_auth(websocket.headers, token)

    # ✅ SECURITY: In production, require authentication
    if is_production:
        if user is None:
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

    # Auth (required in every environment; the dev/test bypass principal
    # from TESTING=1 counts as authenticated here)
    if user is None:
        await websocket.accept()
        await websocket.send_json({"type": "error", "reason": "auth required"})
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    # ✅ SECURITY: QUEUEWSSCOPE-BE-001 — a valid JWT alone does not grant an
    # arbitrary caller-provided room. Apply the canonical authenticated-
    # queue policy (_has_department_access) BEFORE the subscription: a
    # Patient-role token is closed with 1008 without ever joining the room
    # or receiving a single queue event. The dev/test bypass principal has
    # no identity to authorize and is skipped (pytest harness only).
    if user is not _WS_TESTING_PRINCIPAL:
        from app.api.v1.endpoints.websocket_auth import _has_department_access

        if not _has_department_access(user, department):
            log.warning(
                "WS auth rejected: user %s (role=%s) may not subscribe to "
                "queue room department=%r",
                getattr(user, "username", None),
                getattr(user, "role", None),
                department,
            )
            await websocket.accept()
            await websocket.send_json(
                {
                    "type": "error",
                    "reason": "not allowed to subscribe to this queue room",
                }
            )
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return

    # ✅ Только после всех проверок — accept
    # QUEUEWSHANDSHAKE-BE-001: browsers that offer Sec-WebSocket-Protocol
    # (the active useQueueWebSocket hook offers bearer.<jwt>) MUST receive
    # one of the offered subprotocols in the handshake response, otherwise
    # the browser aborts the connection. Reuse the canonical echoing accept
    # instead of a bare accept().
    from app.api.v1.endpoints.ws_token import accept_echoing_subprotocol

    await accept_echoing_subprotocol(websocket)

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
