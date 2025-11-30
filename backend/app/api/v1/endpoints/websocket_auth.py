"""
Аутентифицированные WebSocket endpoints
"""

import json
import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, status, WebSocket, WebSocketDisconnect
from jose import jwt, JWTError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.crud import user as crud_user
from app.db.session import SessionLocal
from app.models.user import User
from app.ws.queue_ws import ws_manager

logger = logging.getLogger(__name__)
router = APIRouter()

# ===================== WEBSOCKET АУТЕНТИФИКАЦИЯ =====================


async def authenticate_websocket_token(
    token: Optional[str], db: Session
) -> Optional[User]:
    """
    Аутентификация WebSocket соединения по JWT токену
    """
    if not token:
        return None

    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
        user_id: int = payload.get("sub")
        if user_id is None:
            return None
    except JWTError:
        return None

    user = crud_user.get(db, id=user_id)
    return user


# ===================== АУТЕНТИФИЦИРОВАННЫЕ WEBSOCKET ENDPOINTS =====================


@router.websocket("/ws/queue/auth")
async def ws_queue_authenticated(
    websocket: WebSocket, department: str, date: str, token: str
):
    """
    Аутентифицированное WebSocket соединение для очереди
    Требует обязательный JWT токен
    """
    db = SessionLocal()

    try:
        # Обязательная аутентификация
        authenticated_user = await authenticate_websocket_token(token, db)
        if not authenticated_user:
            await websocket.close(
                code=status.WS_1008_POLICY_VIOLATION, reason="Invalid or missing token"
            )
            return

        # Проверяем права доступа к отделению
        if not _has_department_access(authenticated_user, department):
            await websocket.close(
                code=status.WS_1003_UNSUPPORTED_DATA,
                reason="Access denied to department",
            )
            return

        await websocket.accept()

        room = f"{department}:{date}"
        ws_manager.connect(websocket, room)

        logger.info(
            f"Аутентифицированное WebSocket подключение: пользователь {authenticated_user.username}, отделение {department}, дата {date}"
        )

        try:
            while True:
                data = await websocket.receive_text()
                message = json.loads(data)

                # Обрабатываем сообщения от аутентифицированного клиента
                await _handle_authenticated_message(
                    websocket, message, authenticated_user, department, date, db
                )

        except WebSocketDisconnect:
            logger.info(
                f"Аутентифицированное WebSocket отключено: пользователь {authenticated_user.username}"
            )
        except Exception as e:
            logger.error(f"Ошибка в аутентифицированном WebSocket: {e}")

    except Exception as e:
        logger.error(f"Ошибка аутентификации WebSocket: {e}")
        try:
            await websocket.close(
                code=status.WS_1011_INTERNAL_ERROR, reason="Authentication error"
            )
        except:
            pass
    finally:
        if 'room' in locals():
            ws_manager.disconnect(websocket, room)
        db.close()


@router.websocket("/ws/queue/optional-auth")
async def ws_queue_optional_auth(
    websocket: WebSocket, department: str, date: str, token: Optional[str] = None
):
    """
    WebSocket соединение для очереди с опциональной аутентификацией
    Анонимные пользователи получают ограниченный доступ
    """
    db = SessionLocal()
    authenticated_user = None

    try:
        # Опциональная аутентификация
        if token:
            authenticated_user = await authenticate_websocket_token(token, db)
            if not authenticated_user:
                logger.warning(
                    "Недействительный токен в WebSocket, продолжаем как анонимный"
                )

        await websocket.accept()

        room = f"{department}:{date}"
        ws_manager.connect(websocket, room)

        if authenticated_user:
            logger.info(
                f"Аутентифицированное WebSocket подключение: пользователь {authenticated_user.username}, отделение {department}"
            )
        else:
            logger.info(f"Анонимное WebSocket подключение: отделение {department}")

        try:
            while True:
                data = await websocket.receive_text()
                message = json.loads(data)

                # Обрабатываем сообщения с учетом уровня доступа
                await _handle_message_with_auth_level(
                    websocket, message, authenticated_user, department, date, db
                )

        except WebSocketDisconnect:
            if authenticated_user:
                logger.info(
                    f"Аутентифицированное WebSocket отключено: пользователь {authenticated_user.username}"
                )
            else:
                logger.info("Анонимное WebSocket отключено")
        except Exception as e:
            logger.error(f"Ошибка в WebSocket: {e}")

    except Exception as e:
        logger.error(f"Ошибка WebSocket: {e}")
        try:
            await websocket.close(
                code=status.WS_1011_INTERNAL_ERROR, reason="Connection error"
            )
        except:
            pass
    finally:
        if 'room' in locals():
            ws_manager.disconnect(websocket, room)
        db.close()


# ===================== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ =====================


def _has_department_access(user: User, department: str) -> bool:
    """
    Проверяет, имеет ли пользователь доступ к отделению
    """
    # Админы имеют доступ ко всем отделениям
    if user.role == "Admin":
        return True

    # Регистраторы имеют доступ ко всем отделениям
    if user.role == "Registrar":
        return True

    # Врачи имеют доступ только к своему отделению
    if user.role in ["Doctor", "Cardiologist", "Dermatologist", "Dentist"]:
        # Здесь можно добавить более сложную логику проверки отделения
        return True

    return False


async def _handle_authenticated_message(
    websocket: WebSocket,
    message: dict,
    user: User,
    department: str,
    date: str,
    db: Session,
):
    """
    Обработка сообщений от аутентифицированных пользователей
    """
    message_type = message.get("type")

    if message_type == "ping":
        await websocket.send_text(
            json.dumps(
                {
                    "type": "pong",
                    "timestamp": datetime.utcnow().isoformat(),
                    "authenticated": True,
                    "user": user.username,
                }
            )
        )
    elif message_type == "call_patient":
        # Только врачи и регистраторы могут вызывать пациентов
        if user.role in [
            "Doctor",
            "Registrar",
            "Admin",
            "Cardiologist",
            "Dermatologist",
            "Dentist",
        ]:
            patient_id = message.get("patient_id")
            await _broadcast_patient_call(department, date, patient_id, user.username)
        else:
            await websocket.send_text(
                json.dumps(
                    {
                        "type": "error",
                        "message": "Недостаточно прав для вызова пациента",
                    }
                )
            )
    elif message_type == "update_queue":
        # Только регистраторы и админы могут изменять очередь
        if user.role in ["Registrar", "Admin"]:
            await _handle_queue_update(message, department, date, db)
        else:
            await websocket.send_text(
                json.dumps(
                    {
                        "type": "error",
                        "message": "Недостаточно прав для изменения очереди",
                    }
                )
            )


async def _handle_message_with_auth_level(
    websocket: WebSocket,
    message: dict,
    user: Optional[User],
    department: str,
    date: str,
    db: Session,
):
    """
    Обработка сообщений с учетом уровня аутентификации
    """
    message_type = message.get("type")

    if message_type == "ping":
        response = {
            "type": "pong",
            "timestamp": datetime.utcnow().isoformat(),
            "authenticated": user is not None,
        }
        if user:
            response["user"] = user.username
        await websocket.send_text(json.dumps(response))

    elif message_type == "get_queue_status":
        # Все могут получать статус очереди
        await _send_queue_status(websocket, department, date, db)

    elif message_type in ["call_patient", "update_queue"]:
        # Только аутентифицированные пользователи с правами
        if not user:
            await websocket.send_text(
                json.dumps(
                    {
                        "type": "error",
                        "message": "Требуется аутентификация для этого действия",
                    }
                )
            )
        else:
            await _handle_authenticated_message(
                websocket, message, user, department, date, db
            )


async def _broadcast_patient_call(
    department: str, date: str, patient_id: str, caller: str
):
    """
    Рассылка вызова пациента всем подключенным клиентам
    """
    room = f"{department}:{date}"
    message = {
        "type": "patient_called",
        "patient_id": patient_id,
        "department": department,
        "caller": caller,
        "timestamp": datetime.utcnow().isoformat(),
    }

    # Используем существующий ws_manager для рассылки
    if hasattr(ws_manager, 'broadcast'):
        await ws_manager.broadcast(room, json.dumps(message))


async def _handle_queue_update(message: dict, department: str, date: str, db: Session):
    """
    Обработка обновления очереди
    """
    # Здесь можно добавить логику обновления очереди в БД
    pass


async def _send_queue_status(
    websocket: WebSocket, department: str, date: str, db: Session
):
    """
    Отправка текущего статуса очереди
    """
    # Здесь можно добавить логику получения статуса очереди из БД
    status_message = {
        "type": "queue_status",
        "department": department,
        "date": date,
        "timestamp": datetime.utcnow().isoformat(),
        "queue_length": 0,  # Заглушка
        "current_number": 1,  # Заглушка
    }

    await websocket.send_text(json.dumps(status_message))
