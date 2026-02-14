"""
WebSocket endpoints для табло очереди
Основа: passport.md стр. 2571-3324
"""

import json
import logging
from datetime import datetime
from typing import Any, Dict, Optional

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
    WebSocket,
    WebSocketDisconnect,
)
from jose import jwt, JWTError
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_roles
from app.core.config import settings
from app.crud import display_config as crud_display, user as crud_user
from app.db.session import SessionLocal
from app.models.user import User
from app.services.display_websocket import DisplayWebSocketManager, get_display_manager
from app.services.display_websocket_api_service import (
    DisplayWebSocketApiDomainError,
    DisplayWebSocketApiService,
)

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


# ===================== WEBSOCKET ПОДКЛЮЧЕНИЯ =====================


@router.websocket("/ws/board/{board_id}")
async def websocket_display_board(
    websocket: WebSocket, board_id: str, token: Optional[str] = None
):
    """
    WebSocket подключение для табло очереди с аутентификацией
    """
    manager = get_display_manager()
    db = SessionLocal()

    try:
        # Аутентификация по токену (опциональная для публичных табло)
        authenticated_user = None
        if token:
            authenticated_user = await authenticate_websocket_token(token, db)
            if not authenticated_user:
                await websocket.close(
                    code=status.WS_1008_POLICY_VIOLATION, reason="Invalid token"
                )
                return

        await manager.connect(websocket, board_id, authenticated_user)

        try:
            while True:
                # Ожидаем сообщения от клиента (ping/pong, команды управления)
                data = await websocket.receive_text()
                message = json.loads(data)

                # Обрабатываем команды от табло
                if message.get("type") == "ping":
                    await websocket.send_text(
                        json.dumps(
                            {"type": "pong", "timestamp": datetime.utcnow().isoformat()}
                        )
                    )
                elif message.get("type") == "request_update":
                    # Запрос обновления состояния
                    await manager._send_current_state(websocket, board_id)

        except WebSocketDisconnect:
            pass

    except Exception as e:
        logger.error("Ошибка WebSocket: %s", e, exc_info=True)
    finally:
        await manager.disconnect(websocket, board_id)


# ===================== УПРАВЛЕНИЕ ТАБЛО =====================


@router.post("/call-patient")
async def call_patient_to_board(
    request: Dict[str, Any],
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Doctor", "Registrar")),
):
    """
    Вызов пациента с трансляцией на табло
    """
    try:
        entry_id = request.get("entry_id")
        board_ids = request.get("board_ids", [])  # Конкретные табло или все

        if not entry_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Не указан ID записи в очереди",
            )

        return await DisplayWebSocketApiService(db).call_patient(
            entry_id=entry_id,
            board_ids=board_ids,
        )
    except DisplayWebSocketApiDomainError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка вызова пациента на табло: {str(e)}",
        ) from e


# ===================== WEBSOCKET ДЛЯ ОТДЕЛЕНИЙ =====================


@router.websocket("/ws/queue/{department}")
async def websocket_queue_department(
    websocket: WebSocket, department: str, token: Optional[str] = None
):
    """
    WebSocket подключение для очереди по отделению
    Согласно требованию: WS /ws/queue/{department}

    События:
    - queue.created: новая запись в очереди
    - queue.called: пациент вызван
    - queue.completed: пациент обслужен
    - queue.cancelled: запись отменена
    """
    manager = get_display_manager()

    # Используем department как board_id для совместимости с существующей системой
    board_id = f"dept_{department}"

    try:
        await manager.connect(websocket, board_id)

        # Отправляем начальное состояние очереди отделения
        await _send_department_queue_state(websocket, department)

        try:
            while True:
                # Ожидаем сообщения от клиента
                data = await websocket.receive_text()
                message = json.loads(data)

                # Обрабатываем команды
                if message.get("type") == "ping":
                    await websocket.send_text(
                        json.dumps(
                            {
                                "type": "pong",
                                "timestamp": datetime.utcnow().isoformat(),
                                "department": department,
                            }
                        )
                    )
                elif message.get("type") == "request_update":
                    # Запрос обновления состояния очереди отделения
                    await _send_department_queue_state(websocket, department)
                elif message.get("type") == "subscribe_events":
                    # Подписка на события очереди
                    logger.info(
                        f"Client subscribed to events for department {department}"
                    )

        except WebSocketDisconnect:
            pass

    except Exception as e:
        logger.error(f"WebSocket error for department {department}: {e}")
    finally:
        await manager.disconnect(websocket, board_id)


async def _send_department_queue_state(websocket: WebSocket, department: str):
    """Отправляет текущее состояние очереди отделения"""
    db = SessionLocal()
    try:
        payload = DisplayWebSocketApiService(db).get_department_queue_state_payload(
            department=department
        )
        await websocket.send_text(json.dumps(payload))

    except Exception as e:
        logger.error(f"Error sending department queue state: {e}")
        await websocket.send_text(
            json.dumps(
                {"type": "error", "message": "Ошибка получения состояния очереди"}
            )
        )
    finally:
        db.close()


@router.post("/announcement")
async def send_announcement_to_board(
    request: Dict[str, Any],
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Registrar")),
):
    """
    Отправка объявления на табло
    """
    try:
        text = request.get("text")
        announcement_type = request.get("type", "info")  # info, warning, emergency
        duration = request.get("duration", 60)
        board_ids = request.get("board_ids", [])

        if not text:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Текст объявления не указан",
            )

        # Транслируем объявление
        manager = get_display_manager()
        await manager.broadcast_announcement(
            announcement_text=text,
            announcement_type=announcement_type,
            duration=duration,
            board_ids=board_ids if board_ids else None,
        )

        return {
            "success": True,
            "message": "Объявление отправлено на табло",
            "announcement": {
                "text": text,
                "type": announcement_type,
                "duration": duration,
            },
            "boards_notified": (
                len(board_ids) if board_ids else len(manager.connections)
            ),
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка отправки объявления: {str(e)}",
        )


@router.get("/boards/status")
def get_boards_status(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Registrar")),
):
    """
    Получить статус всех табло
    """
    try:
        manager = get_display_manager()
        boards_status = manager.get_all_boards_status()

        # Получаем конфигурации табло из БД
        boards_config = crud_display.get_display_boards(db, active_only=True)

        # Объединяем данные
        result = []
        for board in boards_config:
            ws_status = boards_status.get(
                board.name, {"connections": 0, "last_update": None, "active": False}
            )

            result.append(
                {
                    "id": board.id,
                    "name": board.name,
                    "display_name": board.display_name,
                    "location": board.location,
                    "theme": board.theme,
                    "websocket_connections": ws_status["connections"],
                    "last_update": ws_status["last_update"],
                    "online": ws_status["active"],
                    "config": {
                        "show_patient_names": board.show_patient_names,
                        "queue_display_count": board.queue_display_count,
                        "sound_enabled": board.sound_enabled,
                        "voice_announcements": board.voice_announcements,
                    },
                }
            )

        return {
            "boards": result,
            "total_boards": len(result),
            "total_connections": sum(
                board["websocket_connections"] for board in result
            ),
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка получения статуса табло: {str(e)}",
        )


# ===================== БЫСТРЫЕ ДЕЙСТВИЯ =====================


@router.post("/quick/call-next")
async def quick_call_next_patient(
    specialty: str,
    board_id: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Doctor", "Registrar")),
):
    """
    Быстрый вызов следующего пациента
    """
    try:
        return await DisplayWebSocketApiService(db).quick_call_next(
            specialty=specialty,
            board_id=board_id,
        )
    except DisplayWebSocketApiDomainError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка быстрого вызова: {str(e)}",
        ) from e
