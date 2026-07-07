"""
WebSocket endpoint для кассира
Обеспечивает real-time обновления при изменении платежей/визитов
"""

import json
import logging
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)

router = APIRouter()


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

    PAY-REAUDIT-28 P0-3: JWT-токен обязателен. Извлекается из query-параметра
    `token`. Без валидного токена и роли Admin/Cashier соединение закрывается
    с кодом 4401. Раньше эндпоинт принимал любые соединения и транслировал
    PHI (patient_id, visit_id, amount) всем подписчикам.
    """
    token = websocket.query_params.get("token")
    if not token:
        await websocket.close(code=4401)
        return

    # Декодируем JWT и проверяем валидность + роль.
    try:
        from jose import jwt as _jwt
        from app.core.config import settings as _settings
        from app.db.session import SessionLocal as _SessionLocal
        from app.models.user import User as _User

        payload = _jwt.decode(
            token,
            _settings.SECRET_KEY,
            algorithms=[_settings.ALGORITHM],
        )
        sub = payload.get("sub")
        # sub может быть числовым user_id или username
        user_id: int | None = None
        if isinstance(sub, str) and sub.isdigit():
            user_id = int(sub)
        elif isinstance(sub, int):
            user_id = sub

        if user_id is None:
            await websocket.close(code=4401)
            return

        # Проверяем blacklist (jti + sentinel all_user_tokens)
        jti = payload.get("jti")
        if jti:
            from app.services.token_blacklist_service import TokenBlacklistService
            db_check = _SessionLocal()
            try:
                if TokenBlacklistService.is_token_blacklisted(db_check, jti, user_id=user_id):
                    await websocket.close(code=4401)
                    return
            finally:
                db_check.close()

        # Загружаем пользователя и проверяем роль
        db_user = _SessionLocal()
        try:
            user = db_user.query(_User).filter(_User.id == user_id).first()
            if not user or not user.is_active:
                await websocket.close(code=4401)
                return
            if user.role not in ("Admin", "Cashier", "SuperAdmin"):
                await websocket.close(code=4403)
                return
        finally:
            db_user.close()

    except Exception:
        # Любая ошибка декодирования/валидации → отказ
        await websocket.close(code=4401)
        return

    await cashier_ws_manager.connect(websocket)

    try:
        # Отправляем приветственное сообщение
        await websocket.send_json({
            "type": "connected",
            "message": "Connected to cashier WebSocket"
        })

        # Ждем сообщений от клиента (для heartbeat/ping-pong)
        while True:
            try:
                data = await websocket.receive_text()
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
        cashier_ws_manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
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
