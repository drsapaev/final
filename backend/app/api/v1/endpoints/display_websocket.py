"""
WebSocket endpoints для табло очереди
Основа: passport.md стр. 2571-3324
"""

import asyncio
import json
import logging
import os
from datetime import UTC, datetime
from typing import Any

import jwt

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    Request,
    Response,
    WebSocket,
    WebSocketDisconnect,
    status,
)
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_roles
from app.api.v1.endpoints.websocket_auth import (
    _has_department_access,
    _resolve_doctor_for_user,
    authenticate_websocket_token,
    resolve_websocket_token_user,
)
from app.api.v1.endpoints.ws_token import extract_ws_token
from app.core.config import settings
from app.core.rate_limiter import limiter
from app.core.roles import DOCTOR_ROLE_SPELLINGS, Roles, normalize_role_value
from app.crud import display_config as crud_display
from app.models.user import User
from app.repositories.display_websocket_api_repository import (
    resolve_display_board_targets,
)
from app.schemas.misc_endpoints import AnnouncementRequest, CallPatientRequest
from app.services.display_websocket import get_display_manager
from app.services.display_websocket_api_service import (
    DisplayWebSocketApiDomainError,
    DisplayWebSocketApiService,
)
from app.db.session import SessionLocal
from app.schemas.display_device import (
    DisplayBoardDeviceTokenRequest,
    DisplayBoardDeviceTokenResponse,
)
from app.services.display_device_credentials import (
    DISPLAY_DEVICE_SESSION_TTL_SECONDS,
    DISPLAY_DEVICE_TOKEN_TTL_SECONDS,
    DISPLAY_DEVICE_TOKEN_TYPE,
    authenticate_display_device_token,
    display_device_session_cookie_name,
    display_device_session_cookie_prefix,
    exchange_display_device_session,
    exchange_display_device_secret,
)

logger = logging.getLogger(__name__)

router = APIRouter()
DISPLAY_WS_AUTH_RECHECK_SECONDS = 15

# ===================== WEBSOCKET АУТЕНТИФИКАЦИЯ =====================

# DISPLAYWS-BE-002 (audit PR #3961, round 30): the board WebSocket must not
# trust "a token resolved to some user" as an entitlement. The policy below
# mirrors the mounted display HTTP surface (require_roles Admin/Doctor/
# Registrar) extended with the canonical doctor-specialty spellings; Patient
# and every other role is rejected. The separate board-scoped device
# principal is checked through its credential-version and board-binding
# policy below.
_DISPLAY_WS_ALLOWED_ROLES: frozenset[str] = frozenset(
    value.strip().lower()
    for value in (
        Roles.ADMIN.value,
        Roles.SUPER_ADMIN.value,
        Roles.REGISTRAR.value,
        Roles.DOCTOR.value,
        *DOCTOR_ROLE_SPELLINGS,
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


def _is_authorized_display_staff(
    user: User | None, db: Session, *, department: str | None = None
) -> bool:
    """Apply live doctor eligibility and the canonical queue-room grant."""
    if user is None or not _is_display_staff(user):
        return False
    if bool(getattr(user, "is_superuser", False)):
        return True
    if department is not None:
        return _has_department_access(user, department, db)
    role = normalize_role_value(getattr(user, "role", None))
    if role in DOCTOR_ROLE_SPELLINGS and _resolve_doctor_for_user(db, user) is None:
        return False
    return True


def _resolve_display_socket_principal(
    token: str | None,
    db: Session,
    *,
    board_name: str | None = None,
    department: str | None = None,
    allow_device: bool = False,
    touch_device: bool = False,
) -> User | object | None:
    """Resolve either an existing staff JWT or a bound display-device JWT."""
    if not token:
        return None
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except jwt.PyJWTError:
        return None

    if payload.get("typ") == DISPLAY_DEVICE_TOKEN_TYPE:
        if not allow_device or board_name is None:
            return None
        return authenticate_display_device_token(
            db,
            token,
            board_name=board_name,
            touch_connection=touch_device,
        )

    user = resolve_websocket_token_user(token, db)
    return (
        user
        if _is_authorized_display_staff(user, db, department=department)
        else None
    )


def _token_is_display_device(token: str | None) -> bool:
    if not token:
        return False
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except jwt.PyJWTError:
        return False
    return payload.get("typ") == DISPLAY_DEVICE_TOKEN_TYPE


def _reauthorize_display_socket(
    token: str | None,
    *,
    board_name: str,
    allow_device: bool,
    department: str | None = None,
) -> User | object | None:
    db = SessionLocal()
    try:
        return _resolve_display_socket_principal(
            token,
            db,
            board_name=board_name,
            department=department,
            allow_device=allow_device,
        )
    finally:
        db.close()


@router.post("/devices/token", response_model=DisplayBoardDeviceTokenResponse)
@limiter.limit("5/minute")
def exchange_display_device_token(
    request: Request,
    body: DisplayBoardDeviceTokenRequest,
    response: Response,
    db: Session = Depends(get_db),
):
    """Exchange a provisioned secret or HttpOnly device session for a scoped JWT."""
    response.headers["Cache-Control"] = "no-store"
    session_device_id: int | None = None
    if body.secret is not None and body.device_id is not None:
        issued = exchange_display_device_secret(
            db,
            device_id=body.device_id,
            secret=body.secret,
            board_name=body.board_name,
        )
        session_device_id = body.device_id
    else:
        issued = None
        cookie_prefix = display_device_session_cookie_prefix(body.board_name)
        for cookie_name, cookie_value in request.cookies.items():
            if not cookie_name.startswith(cookie_prefix):
                continue
            raw_device_id = cookie_name[len(cookie_prefix):]
            if not raw_device_id.isascii() or not raw_device_id.isdecimal():
                continue
            candidate_device_id = int(raw_device_id)
            candidate = exchange_display_device_session(
                db,
                device_id=candidate_device_id,
                board_name=body.board_name,
                session_token=cookie_value,
            )
            if candidate is not None:
                issued = candidate
                session_device_id = candidate_device_id
                break

    if issued is None:
        # Keep unknown, revoked, inactive-board and wrong-secret responses
        # indistinguishable so the endpoint does not disclose device state.
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid display device credentials",
        )
    token, expires_in, board_name, session_token = issued
    if session_device_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid display device credentials",
        )
    _set_display_device_session_cookie(
        request,
        response,
        device_id=session_device_id,
        board_name=board_name,
        session_token=session_token,
    )
    return DisplayBoardDeviceTokenResponse(
        access_token=token,
        expires_in=expires_in or DISPLAY_DEVICE_TOKEN_TTL_SECONDS,
        board_name=board_name,
    )


def _display_device_cookie_policy(request: Request) -> tuple[str, bool]:
    same_site = (
        os.getenv("DISPLAY_DEVICE_COOKIE_SAMESITE")
        or os.getenv("CSRF_COOKIE_SAMESITE")
        or "lax"
    ).strip().lower()
    if same_site not in {"strict", "lax", "none"}:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="DISPLAY_DEVICE_COOKIE_SAMESITE must be strict, lax, or none",
        )
    is_production = os.getenv("ENV", "dev").strip().lower() in {
        "prod",
        "production",
    }
    secure = is_production or same_site == "none" or request.url.scheme == "https"
    return same_site, secure


def _set_display_device_session_cookie(
    request: Request,
    response: Response,
    *,
    device_id: int,
    board_name: str,
    session_token: str,
) -> None:
    same_site, secure = _display_device_cookie_policy(request)
    response.set_cookie(
        key=display_device_session_cookie_name(device_id, board_name),
        value=session_token,
        max_age=DISPLAY_DEVICE_SESSION_TTL_SECONDS,
        path="/api/v1/display/devices/token",
        secure=secure,
        httponly=True,
        samesite=same_site,
    )


@router.delete("/devices/token", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("5/minute")
def forget_display_device_session(
    request: Request,
    response: Response,
    board_name: str = Query(min_length=1, max_length=120),
) -> None:
    """Clear this browser's HttpOnly device sessions for one public board."""
    response.headers["Cache-Control"] = "no-store"
    same_site, secure = _display_device_cookie_policy(request)
    cookie_prefix = display_device_session_cookie_prefix(board_name)
    for cookie_name in request.cookies:
        if cookie_name.startswith(cookie_prefix):
            response.delete_cookie(
                key=cookie_name,
                path="/api/v1/display/devices/token",
                secure=secure,
                httponly=True,
                samesite=same_site,
            )


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
        # Staff JWTs use the canonical user/JTI/sentinel validator. Device
        # JWTs are a separate principal and must be bound to this exact,
        # active board before the manager is allowed to subscribe it.
        if _token_is_display_device(token):
            principal = _resolve_display_socket_principal(
                token,
                db,
                board_name=board_id,
                allow_device=True,
                touch_device=True,
            )
        else:
            principal = await authenticate_websocket_token(token, db)
            if not _is_authorized_display_staff(principal, db):
                principal = None
        if principal is None:
            await websocket.close(
                code=status.WS_1008_POLICY_VIOLATION, reason="Invalid token"
            )
            return
        authenticated_user = principal if isinstance(principal, User) else None

        # DISPLAYSESSION-BE-002: authentication is complete — release the DB
        # session BEFORE suspending in the long-lived receive loop (close is
        # idempotent; the finally below keeps failure paths covered).
        db.close()

        await manager.connect(websocket, board_id, authenticated_user)

        try:
            loop = asyncio.get_running_loop()
            last_auth_check = loop.time()
            while True:
                timeout = max(
                    0.01,
                    DISPLAY_WS_AUTH_RECHECK_SECONDS - (loop.time() - last_auth_check),
                )
                try:
                    data = await asyncio.wait_for(
                        websocket.receive_text(), timeout=timeout
                    )
                except TimeoutError:
                    data = None

                if loop.time() - last_auth_check >= DISPLAY_WS_AUTH_RECHECK_SECONDS:
                    current_principal = _reauthorize_display_socket(
                        token,
                        board_name=board_id,
                        allow_device=True,
                    )
                    if current_principal is None:
                        await websocket.close(
                            code=status.WS_1008_POLICY_VIOLATION,
                            reason="Display authorization expired or revoked",
                        )
                        break
                    last_auth_check = loop.time()

                if data is None:
                    continue
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
        if not _is_authorized_display_staff(
            authenticated_user, db, department=department
        ):
            authenticated_user = None
        if not authenticated_user:
            await websocket.close(
                code=status.WS_1008_POLICY_VIOLATION, reason="Invalid token"
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
            loop = asyncio.get_running_loop()
            last_auth_check = loop.time()
            while True:
                # Ожидаем сообщения от клиента
                timeout = max(
                    0.01,
                    DISPLAY_WS_AUTH_RECHECK_SECONDS - (loop.time() - last_auth_check),
                )
                try:
                    data = await asyncio.wait_for(
                        websocket.receive_text(), timeout=timeout
                    )
                except TimeoutError:
                    data = None

                if loop.time() - last_auth_check >= DISPLAY_WS_AUTH_RECHECK_SECONDS:
                    current_user = _reauthorize_display_socket(
                        token,
                        board_name=board_id,
                        allow_device=False,
                        department=department,
                    )
                    if not isinstance(current_user, User):
                        await websocket.close(
                            code=status.WS_1008_POLICY_VIOLATION,
                            reason="Display authorization expired or revoked",
                        )
                        break
                    authenticated_user = current_user
                    last_auth_check = loop.time()

                if data is None:
                    continue
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

        # DISPLAYTARGET-BE-001 (audit PR #3961): REST board_ids are integer
        # DB ids while WS rooms are keyed by the board NAME string — resolve
        # int ids to their DisplayBoard.name room keys before the broadcast.
        # Unresolvable ids are reported; an explicit unresolvable request
        # must NOT silently fall back to broadcasting on every live room.
        explicit_targets = bool(board_ids)
        resolved_names: list[str] = []
        unknown_ids: list[int] = []
        if explicit_targets:
            resolved_names, unknown_ids = resolve_display_board_targets(db, board_ids)
        target_board_ids = resolved_names if explicit_targets else None

        delivery_raw = await manager.broadcast_announcement(
            announcement_text=text,
            announcement_type=announcement_type,
            duration=duration,
            board_ids=target_board_ids,
        )
        delivery = delivery_raw if isinstance(delivery_raw, dict) else {}

        # DISPLAYDELIVERY-BE-001 (audit PR #3961): the response reports the
        # actual transport outcome. boards_notified counts ONLY boards with
        # a live local delivery — never the raw request count; a failed
        # broadcast is reported as failed, never as an unconditional "sent".
        boards_notified = sum(
            1 for board_status in delivery.values() if board_status == "delivered_local"
        )
        status_set = set(delivery.values())
        if explicit_targets and not resolved_names:
            display_delivery = "failed"
        elif not delivery:
            display_delivery = "unknown"
        elif status_set == {"delivered_local"}:
            display_delivery = "delivered"
        elif status_set == {"failed"}:
            display_delivery = "failed"
        elif "failed" in status_set:
            display_delivery = "partial"
        else:
            display_delivery = "unknown"

        response: dict[str, Any] = {
            "success": True,
            "announcement_accepted": True,
            "message": "Объявление принято для трансляции на табло",
            "announcement": {
                "text": text,
                "type": announcement_type,
                "duration": duration,
            },
            "boards_requested": len(resolved_names)
            if explicit_targets
            else len(delivery),
            "boards_notified": boards_notified,
            "display_delivery": display_delivery,
            "board_delivery": delivery,
        }
        if unknown_ids:
            response["unknown_board_ids"] = unknown_ids
        return response

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
                    # DISPLAYSTATUS-BE-001 (audit PR #3961): соединения
                    # пер-воркерные. Ноль ЛОКАЛЬНЫХ сокетов — это
                    # «неизвестно» (None), а не системный офлайн: реальный
                    # TV может держать соединение с другим воркером.
                    "online": True if ws_status["active"] else None,
                    "online_scope": "worker_local",
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
            "connections_scope": "worker_local",
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
