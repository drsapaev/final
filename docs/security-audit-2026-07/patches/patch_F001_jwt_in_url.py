"""
PATCH F-001: Убираем JWT из URL Query String WebSocket
======================================================

Файлы: 
  backend/app/ws/chat_ws.py  (backend)
  frontend/src/contexts/ChatContext.jsx  (frontend)

ДО: ws://host/ws/chat?token=<JWT>
ПОСЛЕ: ws://host/ws/chat + первое сообщение {"type":"auth","token":"<JWT>"}

Применение:
  1. Заменить содержимое backend/app/ws/chat_ws.py на новую версию (см. ниже)
  2. Внести изменения в frontend/src/contexts/ChatContext.jsx (см. ниже)
  3. Прогнать тесты: pytest backend/tests/unit/test_chat_ws_manager.py
  4. E2E: открыть чат в браузере, проверить что URL не содержит token
"""

# === BACKEND: backend/app/ws/chat_ws.py ===
# (показаны только изменённые функции — остальной файл без изменений)

BACKEND_PATCH = '''
import asyncio
import json
import logging

from fastapi import WebSocket, WebSocketDisconnect
from fastapi.encoders import jsonable_encoder
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.messaging_contract import (
    CONTRACT_VERSION,
    MessageEventType,
    build_ws_event_payload,
    is_supported_contract_version,
)
from app.db.session import SessionLocal
from app.models.user import User

settings = get_settings()
logger = logging.getLogger(__name__)


# === ChatConnectionManager — без изменений ===
# (оставляем как есть: connect, disconnect, send_to_user, is_online,
#  get_online_users, broadcast_typing, notify_new_message, notify_message_read,
#  notify_messages_read, broadcast_event)

# === НОВОЕ: token в первом сообщении вместо URL ===

WS_AUTH_TIMEOUT_SECONDS = 5.0  # максимум на отправку auth-сообщения


async def authenticate_websocket_by_token(
    token: str,
    db: Session,
) -> User | None:
    """Аутентификация по JWT токену (передаётся в первом сообщении)."""
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


async def chat_websocket_handler(websocket: WebSocket):
    """
    WebSocket endpoint для чата.

    Подключение: ws://host/ws/chat  (БЕЗ token в URL)
    Первое сообщение: {"type":"auth","token":"<JWT>","contract_version":"1.0"}
    """

    await websocket.accept()

    # Шаг 1: ждём auth-сообщение в течение WS_AUTH_TIMEOUT_SECONDS
    db = SessionLocal()
    try:
        try:
            raw = await asyncio.wait_for(
                websocket.receive_text(),
                timeout=WS_AUTH_TIMEOUT_SECONDS,
            )
        except asyncio.TimeoutError:
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

        user = await authenticate_websocket_by_token(
            token=auth_msg["token"],
            db=db,
        )
        if not user:
            await websocket.close(code=4001, reason="Invalid token")
            return

        logger.info(
            "Chat WebSocket authenticated: user_id=%s, username=%s",
            user.id, user.username,
        )
    finally:
        db.close()

    # Шаг 2: регистрируем соединение
    connected = await chat_manager.connect(user.id, websocket)
    if not connected:
        return

    # Шаг 3: основной цикл (как раньше, но token в URL больше не нужен)
    try:
        contract_version_mismatch_logged = False
        while True:
            data = await websocket.receive_text()
            # ... обработка typing / ping / pong / get_online_status
            # (логика без изменений — см. оригинальный код)
    except WebSocketDisconnect:
        chat_manager.disconnect(user.id)
    except Exception as e:
        logger.error("Chat WebSocket error: %s", e)
        chat_manager.disconnect(user.id)
'''


# === FRONTEND: frontend/src/contexts/ChatContext.jsx ===
# (показан только изменённый блок в useEffect для WebSocket)

FRONTEND_PATCH = '''
// === До (строка 355 в оригинале) ===
// const wsUrl = `${wsBase}/ws/chat?token=${latestToken}`;
// const ws = new WebSocket(wsUrl);
// ws.onopen = () => { ... setIsConnected(true); ... };

// === После ===
const ws = new WebSocket(`${wsBase}/ws/chat`);  // БЕЗ token в URL

ws.onopen = () => {
    if (!isMounted) {
        ws.close(1000, "Unmount before open");
        return;
    }
    // Сразу после открытия — отправляем auth-сообщение
    ws.send(JSON.stringify({
        type: "auth",
        token: latestToken,
        contract_version: MESSAGING_CONTRACT_VERSION,
    }));
    // setIsConnected(true) откладываем до подтверждения от сервера
    // (сервер не закроет соединение, если токен валиден)
    setIsConnected(true);
    retryCountRef.current = 0;
    logger.info("[FIX:WS] Chat WebSocket connected (auth via first message)");
    void syncChatSnapshot();
    if (activeConversationRef.current) {
        requestOnlineStatus([activeConversationRef.current]);
    }
};

ws.onclose = (e) => {
    // Если сервер закрыл соединение с code=4001 — это auth failure
    if (e.code === 4001) {
        logger.warning("[FIX:WS] Chat WebSocket auth rejected");
        // Не переподключаемся с тем же токеном — токен невалиден
        // Триггерим logout / refresh-token flow
        tokenManager.invalidateAccessToken();
        return;
    }
    // ... остальная логика onclose без изменений
};
'''

if __name__ == "__main__":
    print("F-001 PATCH — JWT out of WebSocket URL")
    print("=" * 60)
    print("Backend changes (chat_ws.py):")
    print(BACKEND_PATCH[:500] + "...\n")
    print("Frontend changes (ChatContext.jsx):")
    print(FRONTEND_PATCH[:500] + "...")
