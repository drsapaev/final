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

import jwt
from fastapi import WebSocket, WebSocketDisconnect
from fastapi.encoders import jsonable_encoder
from jwt import PyJWTError as JWTError
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
    """Менеджер WebSocket соединений для чата"""

    def __init__(self):
        self.active_connections: dict[int, WebSocket] = {}

    async def connect(self, user_id: int, websocket: WebSocket) -> bool:
        try:
            if user_id in self.active_connections:
                try:
                    await self.active_connections[user_id].close()
                except Exception:
                    pass
            await websocket.accept()
            self.active_connections[user_id] = websocket
            logger.info(f"Chat WebSocket connected: user_id={user_id}")
            return True
        except Exception as e:
            logger.error(f"Chat WebSocket connect error: {e}")
            return False

    def disconnect(self, user_id: int):
        if user_id in self.active_connections:
            del self.active_connections[user_id]
            logger.info(f"Chat WebSocket disconnected: user_id={user_id}")

    async def send_to_user(self, user_id: int, data: dict) -> bool:
        if user_id in self.active_connections:
            try:
                await self.active_connections[user_id].send_json(jsonable_encoder(data))
                return True
            except Exception as e:
                logger.error(f"Chat WebSocket send error: {e}")
                self.disconnect(user_id)
        return False

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
        for raw_user_id in dict.fromkeys(user_ids):
            try:
                user_id = int(raw_user_id)
            except (TypeError, ValueError):
                continue
            await self.send_to_user(user_id, payload)


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

async def _authenticate_by_token(token: str, db: Session) -> User | None:
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[getattr(settings, "ALGORITHM", "HS256")],
        )
        user_id = payload.get("sub")
        if not user_id:
            return None
        if isinstance(user_id, str) and user_id.isdigit():
            user_id = int(user_id)
        elif isinstance(user_id, str):
            return db.query(User).filter(User.username == user_id).first()
        return db.query(User).filter(User.id == int(user_id)).first()
    except JWTError as e:
        logger.warning("Chat WebSocket JWT error: %s", e)
        return None
    except Exception as e:
        logger.error("Chat WebSocket auth error: %s", e)
        return None


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

    if auth_msg.get("type") != "auth" or not auth_msg.get("token"):
        await websocket.close(code=4001, reason="Auth message required")
        return

    db = SessionLocal()
    try:
        user = await _authenticate_by_token(auth_msg["token"], db)
    finally:
        db.close()

    if not user:
        await websocket.close(code=4001, reason="Invalid token")
        return

    logger.info(
        "Chat WebSocket authenticated: user_id=%s, username=%s",
        user.id, user.username,
    )

    # F-005: IP-based rate limit
    ip_address = websocket.client.host if websocket.client else "unknown"
    allowed, reason = websocket_rate_limiter.check_rate_limit(ip_address)
    if not allowed:
        logger.warning("Chat WS rate limit exceeded for IP %s: %s", ip_address, reason)
        await websocket.close(code=4008, reason=f"Rate limit: {reason}")
        return
    websocket_rate_limiter.record_connection(ip_address)

    if not await chat_manager.connect(user.id, websocket):
        websocket_rate_limiter.remove_connection(ip_address)
        return

    # F-006: отправляем init с собеседниками
    init_db = SessionLocal()
    try:
        partner_ids = list(_get_user_conversation_partners(init_db, user.id))
    finally:
        init_db.close()

    try:
        await websocket.send_json(
            build_ws_event_payload("init", {"conversation_partners": partner_ids})
        )
    except Exception:
        pass

    try:
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
                    await websocket.send_json(
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
                    conv_db = SessionLocal()
                    try:
                        if not _users_have_conversation(conv_db, user.id, recipient_id_int):
                            logger.info(
                                "Typing rejected (no conversation): user_id=%s -> recipient_id=%s",
                                user.id, recipient_id_int,
                            )
                            continue
                    finally:
                        conv_db.close()

                    await chat_manager.broadcast_typing(
                        sender_id=user.id,
                        recipient_id=recipient_id_int,
                        is_typing=is_typing,
                    )

                elif msg_type == MessageEventType.PING.value:
                    await websocket.send_json(
                        build_ws_event_payload(MessageEventType.PONG)
                    )

                elif msg_type == MessageEventType.GET_ONLINE_STATUS.value:
                    requested_ids = message.get("user_ids", [])
                    if not isinstance(requested_ids, list) or len(requested_ids) > 50:
                        await websocket.send_json(
                            build_ws_event_payload(
                                "error",
                                {"message": "Invalid user_ids (max 50)"},
                            )
                        )
                        continue

                    # F-006: только собеседники
                    partner_db = SessionLocal()
                    try:
                        allowed_partners = _get_user_conversation_partners(partner_db, user.id)
                    finally:
                        partner_db.close()

                    safe_ids = []
                    for uid in requested_ids:
                        try:
                            uid_int = int(uid)
                        except (TypeError, ValueError):
                            continue
                        if uid_int in allowed_partners:
                            safe_ids.append(uid_int)

                    online_status = {uid: chat_manager.is_online(uid) for uid in safe_ids}
                    await websocket.send_json(
                        build_ws_event_payload(
                            MessageEventType.ONLINE_STATUS,
                            {"users": online_status},
                        )
                    )

                elif msg_type == MessageEventType.PONG.value:
                    continue

                else:
                    await websocket.send_json(
                        build_ws_event_payload(
                            "error",
                            {"message": f"Unknown message type: {msg_type}"},
                        )
                    )

            except json.JSONDecodeError:
                await websocket.send_json(
                    build_ws_event_payload("error", {"message": "Invalid JSON"})
                )

    except WebSocketDisconnect:
        chat_manager.disconnect(user.id)
        websocket_rate_limiter.remove_connection(ip_address)
    except Exception as e:
        logger.error(f"Chat WebSocket error: {e}")
        chat_manager.disconnect(user.id)
        websocket_rate_limiter.remove_connection(ip_address)
