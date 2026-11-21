"""
API endpoints для интеграции с Telegram ботом
Основа: passport.md стр. 2064-2570

P0-6 FIX (ENDPOINT-VALIDATION-AUDIT):
Previously these endpoints accepted `request: dict[str, Any]` with no
validation. Replaced with typed Pydantic request models from
app.schemas.notifications.
"""

from collections.abc import Callable
from datetime import UTC, datetime
from html import escape
from typing import Any
from urllib.parse import urlencode

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    HTTPException,
    Request,
    status,
)
from pydantic import BaseModel
from sqlalchemy import or_, select, true
from sqlalchemy.orm import Session

from app.api.deps import get_current_active_user, get_db, require_roles
from app.core.config import settings
from app.core.rate_limiter import limiter
from app.core.roles import DOCTOR_FAMILY_GATE_ROLES
from app.crud import telegram_config as crud_telegram
from app.models.online_queue import QueueToken
from app.models.patient import Patient
from app.models.telegram_config import TelegramUser
from app.models.user import User
from app.schemas.notifications import (
    SendAppointmentReminderIntegrationRequest,
    SendLabResultsNotificationRequest,
    SendQrCodeRequest,
    SendTelegramIntegrationNotificationRequest,
)
from app.services.notifications_pkg._helpers import (
    _is_private_telegram_chat_id,
    _patient_telegram_event_message,
)
from app.services.patient_phone_scope import canonical_phone_identity
from app.services.telegram_bot import get_telegram_bot_service
from app.services.telegram_delivery_authorization import (
    TelegramDeliveryError,
    _current_actor,
    _link,
    _not_found,
    appointment_payload,
    authorize_appointment,
    authorize_lab_result,
)
from app.services.telegram_service import (
    get_telegram_service,
)
from app.services.telegram_token_store import resolve_patient_bot_token

router = APIRouter()
_PATIENT_DELIVERY_RESPONSES = {
    400: {"model": TelegramDeliveryError, "description": "Missing or ambiguous resource identifier"},
    403: {"model": TelegramDeliveryError, "description": "Staff role is not authorized"},
    404: {"model": TelegramDeliveryError, "description": "Recipient or authorized resource is unavailable"},
    409: {"model": TelegramDeliveryError, "description": "The clinical resource changed or is not ready"},
    502: {"model": TelegramDeliveryError, "description": "Telegram did not confirm delivery"},
    503: {"model": TelegramDeliveryError, "description": "Telegram is unavailable"},
}

# Mobile-contract router (Android client, M-CONTRACT-FIX lineage): mounted at
# /telegram-integration in api.py. The staff notification surface above stays
# on /telegram unchanged.
mobile_router = APIRouter()

_MOBILE_SELF_TEST_TEXT = (
    "🧪 Тестовое уведомление Clinic System — интеграция с Telegram работает."
)


async def _send_verified_patient_message(
    db: Session, link: TelegramUser, message: str, event_type: str,
    verify_resource: Callable[[], None],
) -> None:
    """Send only after ownership/consent and a fresh canonical bot-token check."""
    patient_id, chat_id = link.patient_id, link.chat_id
    service = await get_telegram_bot_service()
    try:
        token = resolve_patient_bot_token(db)
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Telegram credential state is unavailable") from exc
    if not token:
        raise HTTPException(status_code=503, detail="Telegram bot is not configured")
    if not service.active or service.bot_token != token:
        initialized = await service.initialize(db)
        if not initialized or service.bot_token != token:
            raise HTTPException(status_code=503, detail="Telegram bot is not configured")
    config = crud_telegram.get_telegram_config(db)
    if not service.active or (config is not None and not config.active):
        raise HTTPException(status_code=503, detail="Telegram bot is disabled")
    # Re-read the original identity and its current consent after any awaited
    # token initialization; stale ORM state must not authorize a revoked link.
    verify_resource()
    _link(db, patient_id, event_type, chat_id)
    # This is the last check before dispatch, not an atomic revocation barrier:
    # a consent/link change can commit while the Telegram request is in flight.
    # Telegram cannot retract an already accepted message after revocation.
    if not await service.send_plain_message(int(chat_id), message):
        raise HTTPException(status_code=502, detail="Telegram delivery failed")


def _patient_by_exact_phone(db: Session, phone: str) -> Patient:
    """Fail closed on ambiguous matches; never use the old substring lookup."""
    canonical = canonical_phone_identity(phone)
    if not canonical:
        raise _not_found()
    # A bounded scan protects the endpoint on corrupt legacy data. A truncated
    # scan is indeterminate, not proof of uniqueness.
    dialect = db.get_bind().dialect.name
    non_ascii = (Patient.phone.op("~")(r"[^ -~]") if dialect == "postgresql"
                 else Patient.phone.op("GLOB")("*[^ -~]*") if dialect == "sqlite"
                 else true())
    pattern = "%" + "%".join(canonical[-9:]) + "%"
    matches = []
    candidates = db.query(Patient).filter(
        Patient.is_deleted.is_(False), or_(Patient.phone.like(pattern), non_ascii)
    ).populate_existing()
    for index, patient in enumerate(candidates.yield_per(200)):
        if index >= 10000:
            raise _not_found()
        if canonical_phone_identity(patient.phone or "") == canonical:
            matches.append(patient)
            if len(matches) > 1:
                raise _not_found()
    if len(matches) != 1:
        raise _not_found()
    return matches[0]


def _verify_appointment_snapshot(
    db: Session, user: User, data: dict[str, Any], snapshot: dict[str, Any],
    *, phone: str | None = None, chat_id: int | None = None,
) -> None:
    appointment, _, _ = authorize_appointment(db, user, data, phone=phone, chat_id=chat_id)
    if appointment_payload(db, appointment) != snapshot:
        raise HTTPException(status_code=409, detail="Appointment changed; retry")


def _verify_lab_snapshot(
    db: Session, user: User, data: dict[str, Any], *, phone: str | None = None,
    chat_id: int | None = None,
) -> None:
    authorize_lab_result(db, user, data, phone=phone, chat_id=chat_id)


class MobileTelegramSelfTestResponse(BaseModel):
    """Concrete response contract for the mobile self-test endpoint."""

    success: bool
    message: str
    chat_id: int


# ===================== УВЕДОМЛЕНИЯ =====================


@router.post("/send-notification", response_model=dict[str, Any], responses=_PATIENT_DELIVERY_RESPONSES)
async def send_notification(
    request: SendTelegramIntegrationNotificationRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Registrar", *DOCTOR_FAMILY_GATE_ROLES)),
):
    """
    Send a supported appointment or lab event to its verified patient chat.

    ``data`` must contain the matching canonical appointment or lab result ID.
    Caller-supplied clinical content is ignored.
    """
    try:
        if request.template_key == "appointment_reminder":
            appointment, _, link = authorize_appointment(
                db, current_user, request.data, chat_id=request.chat_id
            )
            payload = appointment_payload(db, appointment)
            event_type = "appointment_reminder"
            def verify() -> None:
                _verify_appointment_snapshot(db, current_user, request.data, payload, chat_id=request.chat_id)
        elif request.template_key in {"lab_results", "lab_results_ready"}:
            _, _, _, link = authorize_lab_result(
                db, current_user, request.data, chat_id=request.chat_id
            )
            payload = {}
            event_type = "lab_results"
            def verify() -> None:
                _verify_lab_snapshot(db, current_user, request.data, chat_id=request.chat_id)
        else:
            # Arbitrary templates/data have no patient/visit provenance and
            # cannot satisfy the recipient and doctor-assignment contract.
            raise HTTPException(status_code=400, detail="A supported clinical event and resource identifier are required")
        message = _patient_telegram_event_message(event_type, link.language_code, payload)
        if not message:
            raise HTTPException(status_code=503, detail="Telegram notification is unavailable")
        await _send_verified_patient_message(db, link, message, event_type, verify)
        return {"success": True, "message": "Уведомление отправлено"}

    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.post("/appointment-reminder", response_model=dict[str, Any], responses=_PATIENT_DELIVERY_RESPONSES)
async def send_appointment_reminder(
    request: SendAppointmentReminderIntegrationRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Registrar")),
):
    """
    Send the canonical appointment; an unambiguous appointment ID is required.
    """
    try:
        appointment_data = request.appointment_data.model_dump(exclude_none=True)
        appointment, _, link = authorize_appointment(
            db, current_user, appointment_data, phone=request.patient_phone
        )
        payload = appointment_payload(db, appointment)
        expected_chat = int(link.chat_id)
        message = _patient_telegram_event_message("appointment_reminder", link.language_code, payload)
        if not message:
            raise HTTPException(status_code=503, detail="Telegram notification is unavailable")
        await _send_verified_patient_message(
            db, link, message, "appointment_reminder",
            lambda: _verify_appointment_snapshot(
                db, current_user, appointment_data, payload,
                phone=request.patient_phone, chat_id=expected_chat,
            ),
        )
        return {"success": True, "message": "Напоминание отправлено"}

    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.post("/lab-results-notification", response_model=dict[str, Any], responses=_PATIENT_DELIVERY_RESPONSES)
async def send_lab_results_notification(
    request: SendLabResultsNotificationRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Lab", *DOCTOR_FAMILY_GATE_ROLES)),
):
    """
    Send a readiness notification; a finalized lab result ID is required.
    """
    try:
        lab_data = request.lab_data.model_dump(exclude_none=True)
        _, _, _, link = authorize_lab_result(
            db, current_user, lab_data, phone=request.patient_phone
        )
        expected_chat = int(link.chat_id)
        message = _patient_telegram_event_message("lab_results", link.language_code, {})
        if not message:
            raise HTTPException(status_code=503, detail="Telegram notification is unavailable")
        await _send_verified_patient_message(
            db, link, message, "lab_results",
            lambda: _verify_lab_snapshot(
                db, current_user, lab_data, phone=request.patient_phone, chat_id=expected_chat
            ),
        )
        return {"success": True, "message": "Уведомление о результатах отправлено"}

    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


# ===================== QR КОДЫ =====================


@router.post("/send-qr-code", response_model=dict[str, Any], responses=_PATIENT_DELIVERY_RESPONSES)
async def send_qr_code(
    request: SendQrCodeRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Registrar")),
):
    """
    Отправка QR кода для онлайн-очереди
    """
    try:
        if getattr(current_user, "is_active", None) is not True:
            raise _not_found()
        qr_data = request.qr_data.model_dump(exclude_none=True)
        raw_token = qr_data.get("token")
        if not isinstance(raw_token, str) or not raw_token:
            raise HTTPException(status_code=400, detail="A valid queue token is required")
        token = db.query(QueueToken).filter(QueueToken.token == raw_token).first()
        now = datetime.now(UTC)
        expires = token.expires_at if token else None
        if expires and expires.tzinfo is None:
            expires = expires.replace(tzinfo=UTC)
        if token is None or not token.active or expires is None or expires <= now:
            raise _not_found()
        patient = _patient_by_exact_phone(db, request.patient_phone)
        link = _link(db, patient.id, "queue_ticket_issued")
        patient_id, expected_chat = patient.id, int(link.chat_id)
        # QueueToken is a clinic/specialist-scoped registration token, not a
        # patient credential. Resolve the recipient exclusively via the linked
        # patient and never echo the bearer token in the HTTP response or logs.
        root = str(getattr(settings, "FRONTEND_URL", "") or "http://localhost:5173").rstrip("/")
        url = root + "/queue?" + urlencode({"token": token.token})
        message = "Ссылка для входа в очередь: " + escape(url)
        def verify_qr() -> None:
            _current_actor(db, current_user, {"registrar"})
            current_token = db.query(QueueToken).filter(QueueToken.token == raw_token).populate_existing().first()
            current_expires = current_token.expires_at if current_token else None
            if current_expires and current_expires.tzinfo is None:
                current_expires = current_expires.replace(tzinfo=UTC)
            if current_token is None or not current_token.active or current_expires is None or current_expires <= datetime.now(UTC):
                raise _not_found()
            if _patient_by_exact_phone(db, request.patient_phone).id != patient_id:
                raise _not_found()
            _link(db, patient_id, "queue_ticket_issued", expected_chat)

        await _send_verified_patient_message(db, link, message, "queue_ticket_issued", verify_qr)
        return {"success": True, "message": "QR код отправлен в Telegram"}

    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


# ===================== УПРАВЛЕНИЕ БОТОМ =====================


@router.get("/bot-status", response_model=dict[str, Any])
def get_bot_status(
    db: Session = Depends(get_db), current_user: User = Depends(require_roles("Admin"))
):
    """
    Получить статус Telegram бота
    """
    try:
        config = crud_telegram.get_telegram_config(db)

        # PR-2 (round 10): resolve BEFORE the no-config early return - a
        # deployment relying only on TELEGRAM_BOT_TOKEN (including
        # backend/.env) is configured even without a telegram_configs row.
        configured = resolve_patient_bot_token(db) is not None

        if not config:
            return {
                "configured": configured,
                "active": False,
                "message": (
                    "Telegram бот работает через переменную окружения"
                    if configured
                    else "Telegram бот не настроен"
                ),
            }

        telegram_service = (
            get_telegram_service()
        )  # noqa: F841  # manual-review: variable intentionally kept for debugging/future use

        return {
            # PR-2 (round 8): report through the same SSOT resolver the
            # polling/webhook/admin paths use - an undecryptable config row
            # with a live legacy/env fallback must not read as unconfigured.
            "configured": configured,
            "active": config.active,
            "bot_username": config.bot_username,
            "notifications_enabled": config.notifications_enabled,
            "supported_languages": config.supported_languages,
            "stats": {
                "total_users": len(
                    crud_telegram.get_telegram_users(db, active_only=False)
                ),
                "active_users": len(
                    crud_telegram.get_telegram_users(db, active_only=True)
                ),
                "templates": len(crud_telegram.get_telegram_templates(db)),
            },
        }

    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.get("/users", response_model=dict[str, Any])
def get_telegram_users(
    active_only: bool = True,
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin")),
):
    """
    Получить список пользователей Telegram
    """
    try:
        users = crud_telegram.get_telegram_users(
            db, active_only=active_only, limit=limit
        )

        users_data = []
        for user in users:
            users_data.append(
                {
                    "id": user.id,
                    "chat_id": user.chat_id,
                    "username": user.username,
                    "first_name": user.first_name,
                    "last_name": user.last_name,
                    "language_code": user.language_code,
                    "notifications_enabled": user.notifications_enabled,
                    "patient_linked": bool(user.patient_id),
                    "last_activity": (
                        user.last_activity.isoformat() if user.last_activity else None
                    ),
                    "active": user.active,
                }
            )

        return {"users": users_data, "total": len(users_data)}

    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


# ===================== БЫСТРЫЕ ДЕЙСТВИЯ =====================


@router.post("/quick/appointment-reminder", response_model=dict[str, Any], responses=_PATIENT_DELIVERY_RESPONSES)
async def quick_appointment_reminder(
    patient_phone: str,
    doctor_name: str,
    appointment_date: str,
    appointment_time: str,
    specialty: str = "Врач",
    cabinet: str = "Уточните в регистратуре",
    appointment_id: int | None = None,
    background_tasks: BackgroundTasks = BackgroundTasks(),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Registrar")),
):
    """
    Быстрая отправка напоминания о записи
    """
    appointment_data = {
        "appointment_id": appointment_id,
        "patient_name": "Пациент",  # Получать из БД по телефону
        "doctor_name": doctor_name,
        "specialty": specialty,
        "date": appointment_date,
        "time": appointment_time,
        "cabinet": cabinet,
    }

    return await send_appointment_reminder(
        SendAppointmentReminderIntegrationRequest(
            patient_phone=patient_phone, appointment_data=appointment_data
        ),
        background_tasks,
        db,
        current_user,
    )


@router.post("/quick/qr-notification", response_model=dict[str, Any], responses=_PATIENT_DELIVERY_RESPONSES)
async def quick_qr_notification(
    patient_phone: str,
    doctor_name: str,
    specialty: str,
    qr_token: str,
    date: str,
    time_window: str = "07:00-09:00",
    background_tasks: BackgroundTasks = BackgroundTasks(),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Registrar")),
):
    """
    Быстрая отправка QR кода
    """
    qr_data = {
        "doctor_name": doctor_name,
        "specialty": specialty,
        "token": qr_token,
        "date": date,
        "time_window": time_window,
    }

    return await send_qr_code(
        SendQrCodeRequest(patient_phone=patient_phone, qr_data=qr_data),
        background_tasks,
        db,
        current_user,
    )


# ===================== МОБИЛЬНЫЙ КОНТРАКТ (Android) =====================


class MobileTelegramSelfTestRequest(BaseModel):
    """Body of POST /api/v1/telegram-integration/send-notification as sent by
    the Android client. Every field is accepted for wire compatibility and
    deliberately IGNORED: the recipient chat is always the CURRENT user's own
    TelegramUser link and the text is a fixed server-side string, so the
    endpoint can never be used to relay arbitrary messages to arbitrary
    chats (no spam/phishing relay surface)."""

    chat_id: str | int | None = None
    message: str | None = None
    parse_mode: str | None = None

    model_config = {"extra": "ignore"}


def _resolve_own_telegram_link(db: Session, current_user: User) -> TelegramUser:
    """Resolve the CURRENT user's own ACTIVE TelegramUser link (never a
    client-supplied chat). Documented precedence: a direct user_id link
    ALWAYS wins over the patient-domain link, so a newer patient link can
    never steal the self-test delivery from the direct link. Inactive or
    blocked links are rejected the same way the canonical Mini App /
    notification paths treat them."""
    base_filters = (
        TelegramUser.active.is_(True),
        TelegramUser.blocked.is_(False),
    )
    # 1) Direct staff-style/user link — explicit ownership contract rank.
    link = (
        db.query(TelegramUser)
        .filter(TelegramUser.user_id == current_user.id, *base_filters)
        .order_by(TelegramUser.id.desc())
        .first()
    )
    if link and (link.patient_id is None or _is_private_telegram_chat_id(link.chat_id)):
        return link
    if link:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="telegram_not_linked")
    # 2) Patient-domain fallback (bot /start links patient rows).
    link = (
        db.query(TelegramUser)
        .filter(
            TelegramUser.patient_id.in_(
                select(Patient.id).where(Patient.user_id == current_user.id)
            ),
            *base_filters,
        )
        .order_by(TelegramUser.id.desc())
        .first()
    )
    if not link or not _is_private_telegram_chat_id(link.chat_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="telegram_not_linked",
        )
    return link


@mobile_router.post(
    "/send-notification",
    response_model=MobileTelegramSelfTestResponse,
)
@limiter.limit("3/minute")  # external send per call; keep the blast radius tiny
async def send_mobile_self_test_notification(
    request: Request,
    payload: MobileTelegramSelfTestRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Self-test Telegram delivery for the mobile client.

    Sends a fixed server-side test message to the CURRENT user's own linked
    chat. The chat is resolved server-side from the TelegramUser link; the
    client-supplied chat_id/message/parse_mode are parsed for wire
    compatibility and ignored (no arbitrary-recipient relay).
    """
    link = _resolve_own_telegram_link(db, current_user)
    chat_id = int(link.chat_id)

    # PR-2 SSOT freshness: re-initialize whenever the cached credential no
    # longer matches the canonical token; fail closed when the credential
    # state cannot be verified (same semantics as the webhook send path).
    service = await get_telegram_bot_service()
    try:
        canonical = resolve_patient_bot_token(db)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Telegram credential state is temporarily unverifiable",
        ) from exc
    if not service.active or service.bot_token != canonical:
        initialized = await service.initialize(db)
        if not initialized or not service.bot_token:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Telegram bot is not configured",
            )
    if not service.active:
        # initialize() can return True with a stored token while the bot is
        # administratively disabled (TelegramConfig.active = False); do not
        # send on a disabled bot.
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="telegram_bot_disabled",
        )
    # Admin disable-switch freshness: service.active may be STALE in
    # multi-worker deployments when TelegramConfig.active flips to False
    # without a token change (the cache predicate above then skips
    # initialize() entirely). Re-read the switch on every self-test.
    config = crud_telegram.get_telegram_config(db)
    if config is not None and not config.active:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="telegram_bot_disabled",
        )

    sent = await service.send_plain_message(chat_id, _MOBILE_SELF_TEST_TEXT)
    if not sent:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="telegram_send_failed",
        )

    return MobileTelegramSelfTestResponse(
        success=True,
        message="Тестовое уведомление отправлено в ваш Telegram-чат",
        chat_id=chat_id,
    )
