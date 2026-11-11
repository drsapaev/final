"""
WebSocket endpoints для табло очереди
Основа: passport.md стр. 2571-3324
"""

import json
import logging
from datetime import UTC, datetime
from typing import Any

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    WebSocket,
    WebSocketDisconnect,
    status,
)
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_roles
from app.api.v1.endpoints.websocket_auth import authenticate_websocket_token
from app.api.v1.endpoints.ws_token import extract_ws_token
from app.core.roles import DOCTOR_ROLES, Roles, normalize_role_value
from app.crud import display_config as crud_display
from app.db.session import SessionLocal
from app.models.user import User
from app.schemas.misc_endpoints import AnnouncementRequest, CallPatientRequest
from app.services.display_websocket import get_display_manager
from app.services.display_websocket_api_service import (
    DisplayWebSocketApiDomainError,
    DisplayWebSocketApiService,
)

logger = logging.getLogger(__name__)

router = APIRouter()

# ===================== WEBSOCKET АУТЕНТИФИКАЦИЯ =====================

# DISPLAYWS-BE-002 (audit PR #3961, round 30): the board WebSocket must not
# trust "a token resolved to some user" as an entitlement. The policy below
# mirrors the mounted display HTTP surface (require_roles Admin/Doctor/
# Registrar) extended with the canonical doctor-specialty spellings; Patient
# and every other role is rejected. Board-scoped kiosk credentials remain a
# separate product decision (DISPLAYBOOT-FE-001) and are NOT invented here.
_DISPLAY_WS_ALLOWED_ROLES: frozenset[str] = frozenset(
    value.strip().lower()
    for value in (
        Roles.ADMIN.value,
        Roles.REGISTRAR.value,
        Roles.DOCTOR.value,
        *(role.value for role in DOCTOR_ROLES),
    )
)


def _is_display_staff(user: User | None) -> bool:
    """Display-plane authorization: staff principals only."""
    if user is None:
        return False
    if bool(getattr(user, "is_superuser", False)):
        return True
    role = normalize_role_value(getattr(user, "role", None))
    return role in _DISPLAY_WS_ALLOWED_ROLES


# Canonical WebSocket authentication (JWT decode + TokenBlacklist jti/
# all_user_tokens revocation + subject resolution) is reused from
# websocket_auth — DISPLAYAUTH-BE-001 removed the display-local decode fork
# that silently skipped revocation checks.


# ===================== WEBSOCKET ПОДКЛЮЧЕНИЯ =====================


@router.websocket("/ws/board/{board_id}")
async def websocket_display_board(
    websocket: WebSocket,
    board_id: str,
):
    """
    WebSocket подключение для табло очереди с аутентификацией.

    PR-4: token is extracted via ``extract_ws_token`` — preferred
    sources are Sec-WebSocket-Protocol subprotocol ``bearer.<jwt>`` and
    Authorization header. Query param ``?token=`` still works but emits
    a deprecation warning (it leaks in proxy logs / Referer).
    """
    manager = get_display_manager()
    db = SessionLocal()

    try:
        # QUEUE-AUDIT-28 P0-2: token REQUIRED (was optional).
        # Раньше anonymous пользователи получали все patient names + positions
        # + doctors + cabinets через /ws/board/{board_id}.
        token = extract_ws_token(websocket)
        if not token:
            await websocket.close(
                code=status.WS_1008_POLICY_VIOLATION, reason="Token required"
            )
            return
        # DISPLAYAUTH-BE-001: canonical auth now also rejects blacklisted
        # tokens (exact jti + all_user_tokens sentinel).
        authenticated_user = await authenticate_websocket_token(token, db)
        if not authenticated_user:
            await websocket.close(
                code=status.WS_1008_POLICY_VIOLATION, reason="Invalid token"
            )
            return
        # DISPLAYWS-BE-002: knowing a board_id is not an entitlement —
        # staff-only subscription policy.
        if not _is_display_staff(authenticated_user):
            await websocket.close(
                code=status.WS_1008_POLICY_VIOLATION,
                reason="Insufficient role for board subscription",
            )
            return

        # DISPLAYSESSION-BE-002: authentication is complete — release the DB
        # session BEFORE suspending in the long-lived receive loop (close is
        # idempotent; the finally below keeps failure paths covered).
        db.close()

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
                            {"type": "pong", "timestamp": datetime.now(UTC).isoformat()}
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
        # DISPLAYSESSION-BE-002: the handshake session must not outlive the
        # handler on rejected/errored paths either.
        db.close()
        await manager.disconnect(websocket, board_id)


# ===================== УПРАВЛЕНИЕ ТАБЛО =====================


@router.post("/call-patient", response_model=dict[str, Any])
async def call_patient_to_board(
    request: CallPatientRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Doctor", "Registrar")),
):
    """
    Вызов пациента с трансляцией на табло
    """
    try:
        entry_id = request.entry_id
        board_ids = request.board_ids
        # Validation already done by Pydantic

        return await DisplayWebSocketApiService(db).call_patient(
            entry_id=entry_id,
            board_ids=board_ids,
            current_user=current_user,
        )
    except DisplayWebSocketApiDomainError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        ) from e


# ===================== WEBSOCKET ДЛЯ ОТДЕЛЕНИЙ =====================


@router.websocket("/ws/queue/{department}")
async def websocket_queue_department(
    websocket: WebSocket,
    department: str,
):
    """
    WebSocket подключение для очереди по отделению
    Согласно требованию: WS /ws/queue/{department}

    События:
    - queue.created: новая запись в очереди
    - queue.called: пациент вызван
    - queue.completed: пациент обслужен
    - queue.cancelled: запись отменена

    DISPLAYWS-BE-001 (audit PR #3961, round 30): this route previously had
    NO authentication at all — an anonymous socket received patient names,
    queue numbers and statuses for the department snapshot. Contract now:
    a valid, unrevoked JWT of an active display-staff principal is required
    BEFORE ``manager.connect`` and BEFORE any snapshot payload; otherwise
    the socket is closed with policy code 1008. Public-kiosk credential
    provisioning remains the separate DISPLAYBOOT-FE-001 product decision.
    """
    manager = get_display_manager()

    # Используем department как board_id для совместимости с существующей системой
    board_id = f"dept_{department}"

    db = SessionLocal()
    try:
        token = extract_ws_token(websocket)
        if not token:
            await websocket.close(
                code=status.WS_1008_POLICY_VIOLATION, reason="Token required"
            )
            return
        authenticated_user = await authenticate_websocket_token(token, db)
        if not authenticated_user:
            await websocket.close(
                code=status.WS_1008_POLICY_VIOLATION, reason="Invalid token"
            )
            return
        if not _is_display_staff(authenticated_user):
            await websocket.close(
                code=status.WS_1008_POLICY_VIOLATION,
                reason="Insufficient role for department queue",
            )
            return
    finally:
        # Auth is done either way; never hold the session into the
        # long-lived receive loop (DISPLAYSESSION-BE-002 parity).
        db.close()

    try:
        await manager.connect(websocket, board_id, authenticated_user)

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
                                "timestamp": datetime.now(UTC).isoformat(),
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


@router.post("/announcement", response_model=dict[str, Any])
async def send_announcement_to_board(
    request: AnnouncementRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Registrar")),
):
    """
    Отправка объявления на табло
    """
    try:
        text = request.text
        announcement_type = request.type
        duration = request.duration
        board_ids = request.board_ids
        # Validation already done by Pydantic

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
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.get("/boards/status", response_model=dict[str, Any])
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

    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


# ===================== БЫСТРЫЕ ДЕЙСТВИЯ =====================


@router.post("/quick/call-next", response_model=dict[str, Any])
async def quick_call_next_patient(
    specialty: str,
    board_id: str | None = None,
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
            current_user=current_user,
        )
    except DisplayWebSocketApiDomainError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        ) from e
