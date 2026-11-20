"""
WebSocket endpoint для кассира
Обеспечивает real-time обновления при изменении платежей/визитов
"""

import asyncio
import json
import logging
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)

router = APIRouter()
CASHIER_WS_AUTH_RECHECK_SECONDS = 15


class CashierWSManager:
    """Менеджер WebSocket соединений для кассиров"""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.connections: set[WebSocket] = set()
        return cls._instance

    async def connect(self, websocket: WebSocket) -> None:
        """Подключение нового WebSocket"""
        await websocket.accept()
        self.connections.add(websocket)
        logger.info(f"Cashier WebSocket connected. Total connections: {len(self.connections)}")

    def disconnect(self, websocket: WebSocket) -> None:
        """Отключение WebSocket"""
        self.connections.discard(websocket)
        logger.info(f"Cashier WebSocket disconnected. Total connections: {len(self.connections)}")

    async def broadcast(self, message: dict[str, Any]) -> None:
        """Рассылка сообщения всем подключенным кассирам"""
        disconnected = set()

        for connection in self.connections:
            try:
                await connection.send_json(message)
            except Exception as e:
                logger.error(f"Error sending to WebSocket: {e}")
                disconnected.add(connection)

        # Удаляем отключенные соединения
        for ws in disconnected:
            self.connections.discard(ws)

        if disconnected:
            logger.info(f"Removed {len(disconnected)} disconnected WebSockets")


# Глобальный экземпляр менеджера
cashier_ws_manager = CashierWSManager()


def get_cashier_ws_manager() -> CashierWSManager:
    """Получить экземпляр менеджера WebSocket"""
    return cashier_ws_manager


def _cashier_token_close_code(token: str) -> int | None:
    """Revalidate the JWT, current user, epoch, revocation and cashier role."""
    import jwt

    from app.api.v1.endpoints.websocket_auth import resolve_websocket_token_user
    from app.core.config import settings
    from app.core.user_token_claims import is_user_access_claims
    from app.db.session import SessionLocal

    db = None
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        if not is_user_access_claims(payload) or payload.get("scope") == "patient_portal":
            return 4401
        db = SessionLocal()
        user = resolve_websocket_token_user(token, db)
        if user is None:
            return 4401
        if user.role not in ("Admin", "Cashier", "SuperAdmin"):
            return 4403
        return None
    except Exception:
        return 4401
    finally:
        if db is not None:
            db.close()


@router.websocket("/ws/cashier")
async def cashier_websocket(
    websocket: WebSocket,
):
    """
    WebSocket endpoint для кассиров.
    Получает real-time уведомления о:
    - Новых визитах
    - Новых платежах
    - Изменениях статусов

    PAY-REAUDIT-28 P0-3: JWT-токен обязателен. Без валидного токена и роли
    Admin/Cashier соединение закрывается с кодом 4401. Раньше эндпоинт
    принимал любые соединения и транслировал PHI (patient_id, visit_id,
    amount) всем подписчикам.

    PR-4: token is extracted via ``extract_ws_token`` — preferred sources
    are Sec-WebSocket-Protocol subprotocol ``bearer.<jwt>`` and
    Authorization header. Query param ``?token=`` still works but emits
    a deprecation warning (it leaks in proxy logs / Referer).
    """
    # PR-4: use shared helper for token extraction (preferred: subprotocol,
    # Authorization header; fallback: ?token= query param with warning).
    from app.api.v1.endpoints.ws_token import extract_ws_token
    token = extract_ws_token(websocket)
    if not token:
        await websocket.close(code=4401)
        return

    close_code = await asyncio.to_thread(_cashier_token_close_code, token)
    if close_code is not None:
        await websocket.close(code=close_code)
        return

    await cashier_ws_manager.connect(websocket)

    try:
        # Отправляем приветственное сообщение
        await websocket.send_json({
            "type": "connected",
            "message": "Connected to cashier WebSocket"
        })

        # Revalidate even on quiet sockets and even under continuous traffic.
        loop = asyncio.get_running_loop()
        last_auth_check = loop.time()
        while True:
            try:
                timeout = max(0.01, CASHIER_WS_AUTH_RECHECK_SECONDS - (loop.time() - last_auth_check))
                try:
                    data = await asyncio.wait_for(websocket.receive_text(), timeout=timeout)
                except TimeoutError:
                    data = None
                if loop.time() - last_auth_check >= CASHIER_WS_AUTH_RECHECK_SECONDS:
                    close_code = await asyncio.to_thread(_cashier_token_close_code, token)
                    if close_code is not None:
                        await websocket.close(code=close_code)
                        break
                    last_auth_check = loop.time()
                if data is None:
                    continue
                message = json.loads(data)

                # Обрабатываем ping
                if message.get("type") == "ping":
                    await websocket.send_json({
                        "type": "pong",
                        "timestamp": message.get("timestamp")
                    })

            except json.JSONDecodeError:
                logger.warning("Received invalid JSON from WebSocket")

    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.error("Cashier WebSocket error: %s", type(e).__name__)
    finally:
        cashier_ws_manager.disconnect(websocket)


async def broadcast_cashier_update(event_type: str, data: dict[str, Any]) -> None:
    """
    Вспомогательная функция для рассылки обновлений кассирам.
    Используется из других модулей.

    event_type: "payment_created", "payment_refunded", "visit_created", "visit_updated"
    """
    message = {
        "type": event_type,
        "data": data
    }
    await cashier_ws_manager.broadcast(message)
