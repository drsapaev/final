"""
Аутентифицированные WebSocket endpoints
"""

import asyncio
import json
import logging
from datetime import UTC, datetime

import jwt
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, status
from jwt import PyJWTError as JWTError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.roles import is_login_blocked_role
from app.crud import user as crud_user
from app.db.session import SessionLocal
from app.middleware.websocket_rate_limit import websocket_rate_limiter
from app.models.user import User
from app.ws.queue_ws import ws_manager

logger = logging.getLogger(__name__)
router = APIRouter()

# ===================== WEBSOCKET АУТЕНТИФИКАЦИЯ =====================


def _resolve_websocket_user(payload: dict, db: Session) -> User | None:
    """Resolve JWT subject to a user record for WebSocket authentication."""
    subject = payload.get("sub")
    if subject is None:
        logger.warning("WebSocket auth rejected: token is missing 'sub'")
        return None

    if isinstance(subject, int):
        user = crud_user.get(db, id=subject)
    elif isinstance(subject, str):
        if subject.isdigit():
            user = crud_user.get(db, id=int(subject))
        else:
            user = db.query(User).filter(User.username == subject).first()
    else:
        logger.warning(
            "WebSocket auth rejected: unsupported 'sub' type %s", type(subject).__name__
        )
        return None

    if user is None:
        logger.warning(
            "WebSocket auth rejected: no user matched token subject %r", subject
        )
        return None

    # QD-1.1 (queue resource role cleanup, Codex round-2): internal-only
    # sentinel roles are structural non-logins — both the queue WebSocket
    # (this module) and the display-board WebSocket (which imports this
    # resolver) must reject their tokens like every HTTP surface.
    if is_login_blocked_role(getattr(user, "role", None)):
        logger.warning(
            "WebSocket auth rejected: internal-only role user_id=%s", user.id
        )
        return None

    # DISPLAYAUTH-BE-002 (audit PR #3961, round 34): a disabled account must
    # not authenticate ANY WebSocket handshake. Canonical HTTP auth denies
    # deactivated principals (deps.get_current_user_strict family); the
    # WebSocket resolver previously did not, so a signed unexpired token of
    # ``is_active=False`` user opened board/queue/notify sockets. Enforced
    # here — the single SSOT resolver — so every WS surface inherits it.
    if not bool(getattr(user, "is_active", True)):
        logger.warning("WebSocket auth rejected: inactive user_id=%s", user.id)
        return None

    return user


async def authenticate_websocket_token(token: str | None, db: Session) -> User | None:
    """
    Аутентификация WebSocket соединения по JWT токену
    """
    if not token:
        return None

    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
        # AUTH-REAUDIT-28 P1: check token blacklist (jti + sentinel)
        jti = payload.get("jti")
        sub = payload.get("sub")
        token_user_id = None
        if isinstance(sub, str) and sub.isdigit():
            token_user_id = int(sub)
        elif isinstance(sub, int):
            token_user_id = sub
        if jti:
            from app.services.token_blacklist_service import TokenBlacklistService

            if TokenBlacklistService.is_token_blacklisted(
                db, jti, user_id=token_user_id
            ):
                logger.warning("WebSocket auth rejected: token blacklisted jti=%s", jti)
                return None
    except JWTError:
        return None

    return _resolve_websocket_user(payload, db)


# ===================== АУТЕНТИФИЦИРОВАННЫЕ WEBSOCKET ENDPOINTS =====================


@router.websocket("/ws/queue/auth")
async def ws_queue_authenticated(
    websocket: WebSocket, department: str, date: str, token: str
):
    """
    Аутентифицированное WebSocket соединение для очереди
    Требует обязательный JWT токен
    ✅ SECURITY: Authentication and rate limiting enforced
    """
    db = SessionLocal()
    ip_address = websocket.client.host if websocket.client else "unknown"

    try:
        # ✅ SECURITY: Rate limiting check
        allowed, reason = websocket_rate_limiter.check_rate_limit(ip_address)
        if not allowed:
            logger.warning(
                f"WebSocket rate limit exceeded for IP {ip_address}: {reason}"
            )
            await websocket.close(
                code=status.WS_1008_POLICY_VIOLATION,
                reason=f"Rate limit exceeded: {reason}",
            )
            return

        # Обязательная аутентификация
        authenticated_user = await authenticate_websocket_token(token, db)
        if not authenticated_user:
            await websocket.close(
                code=status.WS_1008_POLICY_VIOLATION, reason="Invalid or missing token"
            )
            return

        # Проверяем права доступа к отделению (WS-POSTMERGE-03: ownership
        # через SSOT doctors.user_id; сессия уже в скоупе — передаём её).
        if not _has_department_access(authenticated_user, department, db):
            await websocket.close(
                code=status.WS_1003_UNSUPPORTED_DATA,
                reason="Access denied to department",
            )
            return

        # ✅ SECURITY: Record connection after successful auth
        websocket_rate_limiter.record_connection(ip_address)

        await websocket.accept()

        # WS-POSTMERGE-04: canonical room identity ("{department}::{date}",
        # double colon) — the legacy single-colon form subscribed to a dead
        # room no broadcaster ever targets. connect() is async and must be
        # awaited: the un-awaited call left the accepted socket OUT of the
        # manager room (coroutine-never-awaited), so it could never receive
        # queue broadcasts.
        room = f"{department.strip()}::{date.strip()}"
        await ws_manager.connect(websocket, room)

        logger.info(
            f"Аутентифицированное WebSocket подключение: пользователь {authenticated_user.username}, отделение {department}, дата {date}, комната {room}"
        )

        # ✅ SECURITY: Heartbeat configuration
        HEARTBEAT_INTERVAL = 30  # seconds
        CONNECTION_TIMEOUT = 120  # seconds
        # ✅ BUGFIX: Use list to allow mutation from nested scopes (nonlocal doesn't work in nested try blocks)
        last_pong = [asyncio.get_event_loop().time()]

        async def send_heartbeat():
            """Send periodic ping to detect dead connections"""
            while True:
                try:
                    await asyncio.sleep(HEARTBEAT_INTERVAL)
                    await websocket.send_json(
                        {"type": "ping", "timestamp": asyncio.get_event_loop().time()}
                    )
                    logger.debug(
                        f"Sent heartbeat ping to user {authenticated_user.username}"
                    )
                except Exception as e:
                    logger.error(f"Error sending heartbeat: {e}")
                    break

        heartbeat_task = asyncio.create_task(send_heartbeat())

        try:
            while True:
                try:
                    # ✅ SECURITY: Set receive timeout
                    data = await asyncio.wait_for(
                        websocket.receive_text(), timeout=CONNECTION_TIMEOUT
                    )
                    message = json.loads(data)

                    # Handle pong response
                    if message.get("type") == "pong":
                        # ✅ BUGFIX: Update list element to modify outer scope variable
                        last_pong[0] = asyncio.get_event_loop().time()
                        logger.debug(
                            f"Received pong from user {authenticated_user.username}"
                        )
                        continue

                    # Обрабатываем сообщения от аутентифицированного клиента
                    await _handle_authenticated_message(
                        websocket, message, authenticated_user, department, date, db
                    )

                except TimeoutError:
                    # Check if connection is still alive
                    # ✅ BUGFIX: Access list element to get current value
                    time_since_pong = asyncio.get_event_loop().time() - last_pong[0]
                    if time_since_pong > CONNECTION_TIMEOUT:
                        logger.warning(
                            f"Connection timeout for user {authenticated_user.username}, closing..."
                        )
                        break
                    # Send ping to check connection
                    try:
                        await websocket.send_json(
                            {
                                "type": "ping",
                                "timestamp": asyncio.get_event_loop().time(),
                            }
                        )
                    except Exception:
                        break  # Connection is dead

        except WebSocketDisconnect:
            logger.info(
                f"Аутентифицированное WebSocket отключено: пользователь {authenticated_user.username}"
            )
        except Exception as e:
            logger.error(f"Ошибка в аутентифицированном WebSocket: {e}")
        finally:
            # Cancel heartbeat task
            heartbeat_task.cancel()
            try:
                await heartbeat_task
            except asyncio.CancelledError:
                pass

    except Exception as e:
        logger.error(f"Ошибка аутентификации WebSocket: {e}")
        try:
            await websocket.close(
                code=status.WS_1011_INTERNAL_ERROR, reason="Authentication error"
            )
        except Exception:
            pass
    finally:
        # ✅ SECURITY: Remove connection from rate limiter
        websocket_rate_limiter.remove_connection(ip_address)
        if "room" in locals():
            ws_manager.disconnect(websocket, room)
        db.close()


@router.websocket("/ws/queue/optional-auth")
async def ws_queue_optional_auth(
    websocket: WebSocket, department: str, date: str, token: str | None = None
):
    """
    ⚠️ DEPRECATED: WebSocket соединение с опциональной аутентификацией

    ✅ SECURITY: This endpoint is deprecated. Use /ws/queue/auth instead.
    Authentication is now REQUIRED for all WebSocket connections.
    """
    # ✅ SECURITY: Require authentication - reject anonymous connections
    if not token:
        await websocket.close(
            code=status.WS_1008_POLICY_VIOLATION,
            reason="Authentication required. Use /ws/queue/auth endpoint.",
        )
        return

    db = SessionLocal()
    authenticated_user = None

    try:
        # ✅ SECURITY: Require valid authentication
        authenticated_user = await authenticate_websocket_token(token, db)
        if not authenticated_user:
            await websocket.close(
                code=status.WS_1008_POLICY_VIOLATION, reason="Invalid or missing token"
            )
            return

        # WS-POSTMERGE-04: the latent RBAC trap — any authenticated JWT
        # (including Patient) used to be accepted here. The same canonical
        # department policy as /ws/queue/auth now runs BEFORE accept, so a
        # repaired transport can never become a Patient/foreign-specialist
        # subscription vector.
        if not _has_department_access(authenticated_user, department, db):
            await websocket.close(
                code=status.WS_1008_POLICY_VIOLATION,
                reason="Access denied to department",
            )
            return

        await websocket.accept()

        # WS-POSTMERGE-04: canonical room identity + awaited connect (see
        # the authenticated endpoint for the full rationale).
        room = f"{department.strip()}::{date.strip()}"
        await ws_manager.connect(websocket, room)

        logger.info(
            f"Аутентифицированное WebSocket подключение (deprecated optional-auth): пользователь {authenticated_user.username}, отделение {department}, комната {room}"
        )

        try:
            while True:
                data = await websocket.receive_text()
                message = json.loads(data)

                # Обрабатываем сообщения (только для аутентифицированных пользователей)
                await _handle_authenticated_message(
                    websocket, message, authenticated_user, department, date, db
                )

        except WebSocketDisconnect:
            logger.info(
                f"Аутентифицированное WebSocket отключено: пользователь {authenticated_user.username}"
            )
        except Exception as e:
            logger.error(f"Ошибка в WebSocket: {e}")

    except Exception as e:
        logger.error(f"Ошибка WebSocket: {e}")
        try:
            await websocket.close(
                code=status.WS_1011_INTERNAL_ERROR, reason="Connection error"
            )
        except Exception:
            pass
    finally:
        if "room" in locals():
            ws_manager.disconnect(websocket, room)
        db.close()


# ===================== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ =====================


# WS-POSTMERGE-02: the staff role family is matched case-insensitively so
# the canonical specialty spellings used across the codebase
# (messages_api_service, context_facades/iam_facade) — cardio, derma,
# dentist, cardiology, cardiologist, dermatologist — are no longer closed
# with WS 1008 on their own departments' queue rooms. Deliberately NOT
# widened: lab/laboratory, Nurse, Cashier and unknown roles keep being
# rejected, exactly as before.
_STAFF_DOCTOR_ROLES = frozenset(
    {
        "doctor",
        "cardio",
        "cardiology",
        "cardiologist",
        "derma",
        "dermatologist",
        "dentist",
    }
)

_SPECIALIST_ROOM_PREFIX = "specialist_"


def _resolve_doctor_for_user(db: Session, user: User):
    """WS-POSTMERGE-03: identity SSOT for queue-room ownership.

    A doctor principal's queue rooms are the ``specialist_{doctors.id}``
    rooms broadcast by ``queue_update_departments`` — the doctor row is
    resolved through the UNIQUE ``doctors.user_id`` bridge (1 doctor = 1
    User). No ``active`` filter, mirroring the routing SSOT
    (``queue_resource_routing.routing_specialist_ids``): a deactivated
    synthetic still names the surface for already-connected subscribers,
    and employment status is enforced at the JWT/active-user layer.
    """
    from app.crud.clinic import get_doctor_by_user_id

    return get_doctor_by_user_id(db, int(user.id))


def _doctor_owns_queue_room(db: Session, user: User, department: str) -> bool:
    """WS-POSTMERGE-03 (P1): the department argument must bind to the principal.

    The role-family check alone admitted ANY doctor into ANY client-named
    room (cross-specialty queue event disclosure). Ownership is resolved
    from the same SSOT the broadcasters use:

    - ``specialist_<id>`` rooms: the id must be the principal's own
      ``doctors.id``. Shared/bridged queues need no sibling access — the
      routing fan-out (``queue_update_departments``) already broadcasts to
      every routing sibling's own room.
    - Department-name rooms: the principal's own ``Department.key`` or the
      canonical specialty family of their ``Doctor.specialty``
      (``specialty_variants``) must match the requested name
      case-insensitively. Forged/foreign department strings are denied.
    - A doctor-family role WITHOUT a doctor row owns nothing (fail
      closed).
    """
    doctor = _resolve_doctor_for_user(db, user)
    if doctor is None:
        return False

    room_department = (department or "").strip()
    if not room_department:
        return False

    if room_department.startswith(_SPECIALIST_ROOM_PREFIX):
        specialist_suffix = room_department[len(_SPECIALIST_ROOM_PREFIX) :]
        if not specialist_suffix.isdigit():
            return False
        return int(specialist_suffix) == int(doctor.id)

    # Department-name room: own department key first, then the specialty
    # family vocabulary of the doctor row itself.
    department_obj = getattr(doctor, "department", None)
    department_key = str(getattr(department_obj, "key", "") or "").strip()
    if department_key and department_key.casefold() == room_department.casefold():
        return True

    specialty = str(getattr(doctor, "specialty", "") or "").strip()
    if specialty:
        from app.core.specialties import specialty_variants

        for variant in specialty_variants(specialty):
            if variant.strip().casefold() == room_department.casefold():
                return True

    return False


def _has_department_access(
    user: User, department: str, db: Session | None = None
) -> bool:
    """
    Проверяет, имеет ли пользователь доступ к отделению

    WS-POSTMERGE-03 (P1): for the staff doctor family the ``department``
    argument is now enforced against the principal's own doctor identity
    (own ``specialist_{id}`` rooms, own department key / specialty family
    for department-name rooms) instead of being ignored. ``Admin`` /
    ``Registrar`` keep full cross-department access; non-staff roles stay
    rejected.

    ``db`` may be omitted by callers without a session in scope (the
    canonical ``/ws/queue`` endpoint); a short-lived session is opened
    internally in that case.
    """
    # Админы имеют доступ ко всем отделениям
    if user.role == "Admin":
        return True

    # Регистраторы имеют доступ ко всем отделениям
    if user.role == "Registrar":
        return True

    # Врачи имеют доступ только к своему отделению — теперь это не только
    # комментарий, а проверка владения комнатой через SSOT doctors.user_id.
    if str(user.role).casefold() in _STAFF_DOCTOR_ROLES:
        if db is not None:
            return _doctor_owns_queue_room(db, user, department)
        session = SessionLocal()
        try:
            return _doctor_owns_queue_room(session, user, department)
        finally:
            session.close()

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
                    "timestamp": datetime.now(UTC).isoformat(),
                    "authenticated": True,
                    "user": user.username,
                }
            )
        )
    elif message_type == "call_patient":
        # Только врачи и регистраторы могут вызывать пациентов
        # WS-POSTMERGE-04: the staff doctor family is matched
        # case-insensitively (same contract as _has_department_access
        # after WS-POSTMERGE-02) — canonical specialty roles (cardio,
        # derma, dentist, …) were silently rejected by the literal list.
        if user.role in ("Admin", "Registrar") or (
            str(user.role).casefold() in _STAFF_DOCTOR_ROLES
        ):
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
    user: User | None,
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
            "timestamp": datetime.now(UTC).isoformat(),
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
    # WS-POSTMERGE-04: canonical room identity (double colon) and a dict
    # payload — the legacy form broadcast a json.dumps STRING into a
    # single-colon dead room. WSManager.broadcast is a SYNCHRONOUS
    # self-scheduling dispatcher (QUEUEWSDISPATCH-BE-001): awaiting it
    # raised ``TypeError: object NoneType can't be used in 'await'``
    # on every authorized call_patient.
    room = f"{department.strip()}::{date.strip()}"
    message = {
        "type": "patient_called",
        "patient_id": patient_id,
        "department": department,
        "caller": caller,
        "timestamp": datetime.now(UTC).isoformat(),
    }

    # Используем существующий ws_manager для рассылки
    if hasattr(ws_manager, "broadcast"):
        ws_manager.broadcast(room, message)


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
        "timestamp": datetime.now(UTC).isoformat(),
        "queue_length": 0,  # Заглушка
        "current_number": 1,  # Заглушка
    }

    await websocket.send_text(json.dumps(status_message))
