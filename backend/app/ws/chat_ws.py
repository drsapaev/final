"""
WebSocket для системы сообщений в реальном времени.

Security fixes applied (audit Wave 1):
- F-001: JWT token передаётся в первом сообщении, а не в URL Query String
- F-005: Rate limiting по IP + per-event-type token bucket
- F-006: Проверка существующей переписки для typing / get_online_status
"""

import asyncio
import json
import logging
import time
from collections import defaultdict
from contextlib import suppress

import jwt
from fastapi import WebSocket, WebSocketDisconnect
from fastapi.encoders import jsonable_encoder
from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.messaging_contract import (
    CONTRACT_VERSION,
    MessageEventType,
    build_ws_event_payload,
    is_supported_contract_version,
)
from app.db.session import SessionLocal
from app.middleware.websocket_rate_limit import websocket_rate_limiter
from app.models.message import Message
from app.models.user import User

settings = get_settings()
logger = logging.getLogger(__name__)

WS_AUTH_TIMEOUT_SECONDS = 5.0
WS_AUTH_RECHECK_SECONDS = 15.0
WS_AUTH_DB_TIMEOUT_SECONDS = 5.0
WS_SEND_TIMEOUT_SECONDS = 2.0


class WebSocketAuthorizationRevoked(Exception):
    """The socket has been revoked or its outbound path has stalled."""


async def close_revoked_websocket(websocket, revoked, close_lock):
    """Serialize competing revocation paths and send at most one close frame."""
    async with close_lock:
        # Revocation may have been marked before acquiring the lock, so it
        # cannot also serve as the marker that a close was already attempted.
        if getattr(revoked, "_ws_close_started", False):
            return
        revoked.set()
        revoked._ws_close_started = True
        try:
            await asyncio.wait_for(
                websocket.close(code=4001, reason="Authorization expired"),
                timeout=2.0,
            )
        except Exception:
            pass


async def send_authorized_websocket(
    websocket, payload, revoked, close_lock, on_timeout=None, is_current=None
):
    """Bound the whole send, including queueing, and serialize it with close."""
    try:
        async with asyncio.timeout(WS_SEND_TIMEOUT_SECONDS):
            async with close_lock:
                if revoked.is_set() or (is_current is not None and not is_current()):
                    raise WebSocketAuthorizationRevoked
                await websocket.send_json(payload)
    except TimeoutError:
        revoked.set()
        if on_timeout is not None:
            on_timeout()
        await close_revoked_websocket(websocket, revoked, close_lock)
        raise WebSocketAuthorizationRevoked from None


async def monitor_websocket_authorization(websocket, check, revoked, owner_task, close_lock):
    """Close idle or busy sockets after revocation without sharing a DB session."""
    while True:
        await asyncio.sleep(WS_AUTH_RECHECK_SECONDS)
        try:
            allowed = await asyncio.wait_for(
                asyncio.to_thread(check), timeout=WS_AUTH_DB_TIMEOUT_SECONDS
            )
        except Exception:
            allowed = False
        if not allowed:
            await close_revoked_websocket(websocket, revoked, close_lock)
            owner_task.cancel()
            return


class ChatEventRateLimiter:
    """Per-user, per-event-type token bucket rate limiter (F-005)."""

    LIMITS = {
        "typing": (5, 1.0),
        "get_online_status": (1, 1.0),
        "ping": (1, 30.0),
    }

    def __init__(self):
        self._buckets: dict[int, dict[str, list]] = defaultdict(lambda: defaultdict(list))

    def check(self, user_id: int, event_type: str) -> bool:
        if event_type not in self.LIMITS:
            return True
        capacity, refill_period = self.LIMITS[event_type]
        now = time.monotonic()
        bucket = self._buckets[user_id][event_type]
        if not bucket:
            bucket.extend([now, capacity - 1])
            return True
        last_refill, tokens = bucket
        elapsed = now - last_refill
        refill_rate = capacity / refill_period
        new_tokens = min(capacity, tokens + elapsed * refill_rate)
        if new_tokens < 1:
            return False
        bucket[0] = now
        bucket[1] = new_tokens - 1
        return True


_chat_event_limiter = ChatEventRateLimiter()


class ChatConnectionManager:
    """Менеджер WebSocket соединений для чата.

    F-014: supports multi-instance deployment via Redis Pub/Sub bridge.
    Local connections are stored in active_connections; cross-instance
    delivery is handled by RedisPubSubBridge (graceful degradation if Redis unavailable).
    """

    def __init__(self):
        self.active_connections: dict[int, WebSocket] = {}
        self._connection_states: dict[int, tuple] = {}
        # F-014: Redis bridge for cross-instance delivery
        self._redis_bridge = None
        self._redis_initialized = False

    async def _ensure_redis_bridge(self):
        """F-014: lazily initialize Redis Pub/Sub bridge."""
        if self._redis_initialized:
            return
        self._redis_initialized = True
        try:
            from app.services.ws_redis_pubsub import RedisPubSubBridge

            self._redis_bridge = RedisPubSubBridge(channel_prefix="chat")

            # Subscribe to cross-instance events
            async def _handle_cross_instance(payload: dict):
                """Deliver messages from other instances to local connections."""
                target_user_id = payload.get("target_user_id")
                event_data = payload.get("event_data")
                if target_user_id and event_data:
                    await self._local_deliver(int(target_user_id), event_data)

            await self._redis_bridge.subscribe("cross_instance", _handle_cross_instance)
            logger.info("F-014: Chat Redis Pub/Sub bridge initialized")
        except Exception as e:
            logger.warning(f"F-014: Redis bridge unavailable (single-instance mode): {e}")
            self._redis_bridge = None

    async def _publish_cross_instance(self, target_user_id: int, event_data: dict):
        """F-014: publish to other instances via Redis."""
        await self._ensure_redis_bridge()
        if self._redis_bridge and self._redis_bridge.enabled:
            try:
                await self._redis_bridge.publish("cross_instance", {
                    "target_user_id": target_user_id,
                    "event_data": event_data,
                })
            except Exception as e:
                logger.debug(f"F-014: Redis publish failed (local-only delivery): {e}")

    async def _local_deliver(self, user_id: int, data: dict) -> bool:
        """Deliver message to local WebSocket connection only."""
        connection = self.active_connections.get(user_id)
        if connection is not None:
            state = self._connection_states.get(user_id)
            if state is None or state[0] is not connection:
                state = (connection, asyncio.Event(), asyncio.Lock(), None)
                self._connection_states[user_id] = state
            _, revoked, close_lock, owner_task = state

            def cleanup_target():
                if self._connection_states.get(user_id) is state:
                    self.disconnect(user_id, connection)
                if (owner_task is not None and owner_task is not asyncio.current_task()
                        and not owner_task.done() and not owner_task.cancelling()):
                    owner_task.cancel()

            try:
                await send_authorized_websocket(
                    connection, jsonable_encoder(data), revoked, close_lock,
                    on_timeout=cleanup_target,
                    is_current=lambda: (
                        self.active_connections.get(user_id) is connection
                        and self._connection_states.get(user_id) is state
                    ),
                )
                return True
            except WebSocketAuthorizationRevoked:
                cleanup_target()
            except Exception as e:
                logger.error(f"Chat WebSocket send error: {e}")
                if self._connection_states.get(user_id) is state:
                    self.disconnect(user_id, connection)
        return False

    async def connect(self, user_id: int, websocket: WebSocket,
                      revoked=None, close_lock=None, owner_task=None) -> bool:
        try:
            previous = self.active_connections.get(user_id)
            previous_state = self._connection_states.get(user_id)
            self.active_connections[user_id] = websocket
            self._connection_states[user_id] = (
                websocket, revoked if revoked is not None else asyncio.Event(),
                close_lock if close_lock is not None else asyncio.Lock(), owner_task,
            )
            if previous is not None:
                try:
                    if previous_state is not None and previous_state[0] is previous:
                        _, previous_revoked, previous_lock, previous_owner = previous_state
                        try:
                            await close_revoked_websocket(previous, previous_revoked, previous_lock)
                        finally:
                            if (previous_owner is not None and previous_owner is not asyncio.current_task()
                                    and not previous_owner.done() and not previous_owner.cancelling()):
                                previous_owner.cancel()
                    else:
                        await asyncio.wait_for(previous.close(), timeout=2.0)
                except Exception:
                    pass
            # ASGI: хендлер уже вызвал accept() до аутентификации — повторный
            # accept() даёт протокольную ошибку ("Expected websocket.send or
            # websocket.close, but got websocket.accept") и роняет соединение.
            await self._ensure_redis_bridge()
            logger.info(f"Chat WebSocket connected: user_id={user_id}")
            return True
        except Exception as e:
            logger.error(f"Chat WebSocket connect error: {e}")
            return False

    def disconnect(self, user_id: int, websocket: WebSocket | None = None):
        if user_id in self.active_connections and (
            websocket is None or self.active_connections[user_id] is websocket
        ):
            del self.active_connections[user_id]
            self._connection_states.pop(user_id, None)
            logger.info(f"Chat WebSocket disconnected: user_id={user_id}")

    async def send_to_user(self, user_id: int, data: dict) -> bool:
        """F-014: deliver locally + publish to other instances via Redis."""
        # Try local delivery first
        delivered = await self._local_deliver(user_id, data)
        # F-014: also publish to other instances (in case user is connected elsewhere)
        await self._publish_cross_instance(user_id, data)
        return delivered

    def is_online(self, user_id: int) -> bool:
        return user_id in self.active_connections

    def get_online_users(self) -> list:
        return list(self.active_connections.keys())

    async def broadcast_typing(self, sender_id: int, recipient_id: int, is_typing: bool):
        await self.send_to_user(
            recipient_id,
            build_ws_event_payload(
                MessageEventType.TYPING,
                {"sender_id": sender_id, "is_typing": is_typing},
            ),
        )

    async def notify_new_message(self, recipient_id: int, message_data: dict):
        is_online = recipient_id in self.active_connections
        logger.info(
            "WS: Notifying user %s about new message. Online: %s",
            recipient_id, is_online,
        )
        if is_online:
            await self.broadcast_event([recipient_id], "new_message", {"message": message_data})
        else:
            logger.info("WS: User %s is offline, skipping notification", recipient_id)

    async def notify_message_read(self, sender_id: int, message_id: int):
        await self.broadcast_event([sender_id], "message_read", {"message_id": message_id})

    async def notify_messages_read(self, sender_id: int, message_ids: list[int]):
        if not message_ids:
            return
        await self.broadcast_event([sender_id], "messages_read", {"message_ids": message_ids})

    async def broadcast_event(self, user_ids: list[int], event_type: str, data: dict):
        if not user_ids:
            return
        payload = build_ws_event_payload(event_type, data)
        recipients = []
        for raw_user_id in dict.fromkeys(user_ids):
            try:
                user_id = int(raw_user_id)
            except (TypeError, ValueError):
                continue
            recipients.append(user_id)
        await asyncio.gather(*(self.send_to_user(user_id, payload) for user_id in recipients))


chat_manager = ChatConnectionManager()


# ============================================================================
# F-006: Хелперы для проверки существующей переписки
# ============================================================================

def _users_have_conversation(db: Session, user1_id: int, user2_id: int) -> bool:
    exists = db.query(Message.id).filter(
        or_(
            and_(Message.sender_id == user1_id, Message.recipient_id == user2_id),
            and_(Message.sender_id == user2_id, Message.recipient_id == user1_id),
        )
    ).first()
    return exists is not None


def _get_user_conversation_partners(db: Session, user_id: int) -> set[int]:
    rows = db.query(
        Message.sender_id, Message.recipient_id
    ).filter(
        or_(Message.sender_id == user_id, Message.recipient_id == user_id)
    ).all()
    partners = set()
    for sender_id, recipient_id in rows:
        if sender_id == user_id:
            partners.add(recipient_id)
        else:
            partners.add(sender_id)
    return partners


# ============================================================================
# F-001: Аутентификация по токену из первого сообщения
# ============================================================================

def _resolve_chat_user(token: str, db: Session) -> User | None:
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[getattr(settings, "ALGORITHM", "HS256")],
        )
        from app.core.user_token_claims import is_user_access_claims

        # Keep the patient-scoped token boundary even with live reauthorization.
        if not is_user_access_claims(payload) or payload.get("scope") == "patient_portal":
            return None
        from app.api.v1.endpoints.websocket_auth import resolve_websocket_token_user

        return resolve_websocket_token_user(token, db)
    except Exception:
        logger.warning("Chat WebSocket authorization failed")
        return None


async def _authenticate_by_token(token: str, db: Session) -> User | None:
    return _resolve_chat_user(token, db)


def _chat_session_is_current(token: str, user_id: int) -> bool:
    db = SessionLocal()
    try:
        user = _resolve_chat_user(token, db)
        return user is not None and user.id == user_id
    except Exception:
        return False
    finally:
        db.close()


def _authenticate_chat_fresh(token: str) -> User | None:
    db = SessionLocal()
    try:
        return _resolve_chat_user(token, db)
    finally:
        db.close()


def _chat_partners_fresh(user_id: int) -> set[int]:
    db = SessionLocal()
    try:
        return _get_user_conversation_partners(db, user_id)
    finally:
        db.close()


def _chat_conversation_exists_fresh(user_id: int, recipient_id: int) -> bool:
    db = SessionLocal()
    try:
        return _users_have_conversation(db, user_id, recipient_id)
    finally:
        db.close()


# Backward-compat alias for tests/external callers that import the old name.
# The alias accepts both the 2-arg form ``authenticate_websocket(token, db)``
# and the 3-arg form ``authenticate_websocket(websocket, token, db)`` so that
# callers (including the real websocket handler) and unit tests that pass a
# ``websocket`` placeholder as the first positional argument can both succeed.
async def authenticate_websocket(*args):  # type: ignore[no-untyped-def]
    if len(args) == 3:
        _websocket, token, db = args
    elif len(args) == 2:
        token, db = args
    else:
        raise TypeError(
            "authenticate_websocket() expected 2 or 3 positional arguments, "
            f"got {len(args)}"
        )
    return await _authenticate_by_token(token, db)


async def chat_websocket_handler(websocket: WebSocket):
    """
    WebSocket endpoint для чата.

    F-001: JWT-токен передаётся в первом сообщении, а не в URL Query String.
    """
    await websocket.accept()

    try:
        raw = await asyncio.wait_for(
            websocket.receive_text(),
            timeout=WS_AUTH_TIMEOUT_SECONDS,
        )
    except TimeoutError:
        await websocket.close(code=4001, reason="Auth timeout")
        return
    except WebSocketDisconnect:
        return

    try:
        auth_msg = json.loads(raw)
    except json.JSONDecodeError:
        await websocket.close(code=4001, reason="Invalid JSON in auth")
        return

    if not isinstance(auth_msg, dict) or auth_msg.get("type") != "auth" or not isinstance(auth_msg.get("token"), str) or not auth_msg["token"]:
        await websocket.close(code=4001, reason="Auth message required")
        return

    try:
        user = await asyncio.wait_for(
            asyncio.to_thread(_authenticate_chat_fresh, auth_msg["token"]),
            timeout=WS_AUTH_DB_TIMEOUT_SECONDS,
        )
    except Exception:
        user = None

    if not user:
        await websocket.close(code=4001, reason="Invalid token")
        return

    logger.info("Chat WebSocket authenticated")

    # F-005: IP-based rate limit
    ip_address = websocket.client.host if websocket.client else "unknown"
    allowed, reason = websocket_rate_limiter.check_rate_limit(ip_address)
    if not allowed:
        logger.warning("Chat WS rate limit exceeded for IP %s: %s", ip_address, reason)
        await websocket.close(code=4008, reason=f"Rate limit: {reason}")
        return
    websocket_rate_limiter.record_connection(ip_address)

    token = auth_msg["token"]
    revoked = asyncio.Event()
    close_lock = asyncio.Lock()
    owner_task = asyncio.current_task()
    watchdog = asyncio.create_task(
        monitor_websocket_authorization(
            websocket, lambda: _chat_session_is_current(token, user.id), revoked, owner_task, close_lock
        )
    )
    try:
        if not await chat_manager.connect(user.id, websocket, revoked, close_lock, owner_task):
            return
        async def send_authorized(payload):
            await send_authorized_websocket(websocket, payload, revoked, close_lock)
        partner_ids = list(await asyncio.to_thread(_chat_partners_fresh, user.id))
        await send_authorized(
            build_ws_event_payload("init", {"conversation_partners": partner_ids})
        )
        contract_version_mismatch_logged = False
        while True:
            data = await websocket.receive_text()

            try:
                message = json.loads(data)
                msg_type = message.get("type")
                incoming_contract_version = message.get("contract_version")

                if (
                    incoming_contract_version
                    and not is_supported_contract_version(incoming_contract_version)
                    and not contract_version_mismatch_logged
                ):
                    contract_version_mismatch_logged = True
                    logger.warning(
                        "Chat WS contract version mismatch: expected=%s, received=%s, user_id=%s, type=%s",
                        CONTRACT_VERSION, incoming_contract_version, user.id, msg_type,
                    )

                # F-005: per-event rate limiting
                if not _chat_event_limiter.check(user.id, msg_type or ""):
                    await send_authorized(
                        build_ws_event_payload(
                            "error",
                            {"message": f"Rate limit exceeded for event: {msg_type}"},
                        )
                    )
                    continue

                if msg_type == MessageEventType.TYPING.value:
                    recipient_id = message.get("recipient_id")
                    is_typing = message.get("is_typing", False)
                    if not recipient_id:
                        continue
                    try:
                        recipient_id_int = int(recipient_id)
                    except (TypeError, ValueError):
                        continue

                    # F-006: проверяем существующую переписку
                    if not await asyncio.to_thread(
                        _chat_conversation_exists_fresh, user.id, recipient_id_int
                    ):
                        continue

                    await chat_manager.broadcast_typing(
                        sender_id=user.id,
                        recipient_id=recipient_id_int,
                        is_typing=is_typing,
                    )

                elif msg_type == MessageEventType.PING.value:
                    await send_authorized(
                        build_ws_event_payload(MessageEventType.PONG)
                    )

                elif msg_type == MessageEventType.GET_ONLINE_STATUS.value:
                    requested_ids = message.get("user_ids", [])
                    if not isinstance(requested_ids, list) or len(requested_ids) > 50:
                        await send_authorized(
                            build_ws_event_payload(
                                "error",
                                {"message": "Invalid user_ids (max 50)"},
                            )
                        )
                        continue

                    # F-006: только собеседники
                    allowed_partners = await asyncio.to_thread(_chat_partners_fresh, user.id)

                    safe_ids = []
                    for uid in requested_ids:
                        try:
                            uid_int = int(uid)
                        except (TypeError, ValueError):
                            continue
                        if uid_int in allowed_partners:
                            safe_ids.append(uid_int)

                    online_status = {uid: chat_manager.is_online(uid) for uid in safe_ids}
                    await send_authorized(
                        build_ws_event_payload(
                            MessageEventType.ONLINE_STATUS,
                            {"users": online_status},
                        )
                    )

                elif msg_type == MessageEventType.PONG.value:
                    continue

                else:
                    await send_authorized(
                        build_ws_event_payload(
                            "error",
                            {"message": f"Unknown message type: {msg_type}"},
                        )
                    )

            except json.JSONDecodeError:
                await send_authorized(
                    build_ws_event_payload("error", {"message": "Invalid JSON"})
                )

    except WebSocketAuthorizationRevoked:
        pass
    except WebSocketDisconnect:
        pass
    except asyncio.CancelledError:
        if not revoked.is_set():
            raise
    except Exception as e:
        # Starlette: 'WebSocket is not connected. Need to call "accept"
        # first.' — приложение шлёт в сокет, который уже разорвала вторая
        # сторона (типично для простаивающих WS за Cloudflare-туннелем).
        # Это штатная гонка отключения, а не ошибка — не создаём issue.
        if isinstance(e, RuntimeError) and "not connected" in str(e):
            logger.info(
                "Chat WebSocket peer dropped mid-send (treated as disconnect): user_id=%s",
                user.id,
            )
        else:
            logger.error("Chat WebSocket error: %s", type(e).__name__)
    finally:
        watchdog.cancel()
        with suppress(asyncio.CancelledError):
            await watchdog
        chat_manager.disconnect(user.id, websocket)
        websocket_rate_limiter.remove_connection(ip_address)
