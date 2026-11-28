"""
Split from telegram_webhook.py (5647 LOC → modular).
"""

from __future__ import annotations

import hmac
import logging
from datetime import date, datetime
from functools import partial
from typing import Any, NoReturn

from fastapi import HTTPException, Request, Response, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.api.v1.endpoints.admin_telegram import (
    _get_configured_bot_token,
)
from app.crud import telegram_config as crud_telegram
from app.crud.clinic import clinic_today
from app.models.appointment import Appointment
from app.models.clinic import Doctor
from app.models.department import Department
from app.models.lab import LabReportInstance
from app.models.patient import Patient
from app.models.telegram_config import TelegramUser
from app.services.appointment_booking_routing import (
    resolve_booking_department,
    resolve_doctor_routing_department,
)
from app.services.appointment_duration_snapshot import (
    InvalidServiceSelection,
    resolve_exact_service_selection,
)
from app.services.appointment_eligibility import ensure_doctor_eligible_for_appointment
from app.services.patient_onboarding_service import PatientOnboardingService
from app.services.public_booking_settings import (
    PublicBookingSettingsError,
    PublicBookingSettingsService,
)
from app.services.telegram_bot import dispatch_patient_bot_update

logger = logging.getLogger(__name__)
from app.api.v1.endpoints.telegram_webhook._helpers import *  # noqa: F401, F403
from app.api.v1.endpoints.telegram_webhook._helpers import (
    _localized_services_menu,
    _localized_settings_menu,
    _localized_text,
    _normalize_patient_language,
    _parse_patient_mini_app_entry_token,
    _parse_patient_onboarding_entry_token,
    _patient_text_handler_aliases,
    _telegram_chat_language,
    _telegram_chat_menu,
    _telegram_chat_text,
    _telegram_clinic_message,
    _telegram_has_pending_onboarding,
    _telegram_onboarding_entry_markup,
    _telegram_patient_access,
    _telegram_service_entry_markup,
    _telegram_settings_message,
)  # noqa: F401
from app.api.v1.endpoints.telegram_webhook._patient_commands import (  # noqa: F401  # noqa: F401
    _has_patient_language_selection,
    _is_patient_settings_context_template,
    _latest_patient_bot_template_key,
    _send_patient_bot_reply,
    _upsert_ticket_qr_telegram_user,
)
from app.api.v1.endpoints.telegram_webhook._staff_commands import (  # noqa: F401  # noqa: F401
    _billing_totals,
    _build_lab_report_pdf,
    _format_money,
    _handle_contact_link,
    _handle_staff_link_start,
    _handle_staff_read_only_menu,
    _handle_ticket_qr_start,
    _latest_ready_lab_report_instances,
    _message_from_update,
    _patient_display_name,
    _patient_recent_visits,
    _patient_today_queue_entries,
    _send_language_choice,
    _set_notification_consent,
)


async def _dispatch_clinic_bot_update(
    update: dict[str, Any],
    db: Session,
    bot_service,
    start_handler,
    command_handlers: dict,
    text_handlers: dict,
) -> bool:
    """Use the same patient dispatch for the service and its fallback."""
    handlers = {
        "staff_start_handler": _handle_staff_link_start,
        "staff_menu_handler": _handle_staff_read_only_menu,
        "ticket_start_handler": _handle_ticket_qr_start,
        "contact_handler": _handle_contact_link,
        "start_handler": start_handler,
        "command_handlers": command_handlers,
        "text_handlers": text_handlers,
    }
    dispatch = getattr(bot_service, "process_patient_bot_update", None)
    if callable(dispatch):
        return await dispatch(update, db, **handlers)
    return await dispatch_patient_bot_update(bot_service, update, db, **handlers)


async def _handle_clinic_bot_update(
    update: dict[str, Any], db: Session, bot_service
) -> bool:
    async def reply(chat_id: int, text_key: str, template: str, markup=None) -> None:
        await _send_patient_bot_reply(
            db,
            bot_service,
            chat_id,
            _telegram_chat_text(db, chat_id, text_key),
            markup or _telegram_chat_menu(db, chat_id),
            template,
        )

    async def clinic_handler(chat_id: int, *, unavailable: bool = False) -> None:
        language = _telegram_chat_language(db, chat_id)
        text = _telegram_clinic_message(db, chat_id)
        if unavailable:
            text = f"{_localized_text('patient_link_unavailable', language)}\n\n{text}"
            markup = _telegram_chat_menu(db, chat_id)
        else:
            back = (
                "⬅️ Asosiy menyu"
                if language == TELEGRAM_LANGUAGE_UZ
                else "⬅️ Главное меню"
            )
            markup = {"keyboard": [[{"text": back}]], "resize_keyboard": True}
        await _send_patient_bot_reply(
            db, bot_service, chat_id, text, markup, "telegram_patient_support"
        )

    def ensure_profile(chat_id: int, message: dict[str, Any]) -> None:
        if crud_telegram.get_telegram_user_by_chat_id(db, chat_id) is None:
            _upsert_ticket_qr_telegram_user(db, message, notifications_enabled=False)
            db.commit()

    async def start_handler(chat_id: int, message: dict[str, Any]) -> None:
        ensure_profile(chat_id, message)
        telegram_user, access = _telegram_patient_access(db, chat_id)
        if access == "unavailable":
            await clinic_handler(chat_id, unavailable=True)
        elif access == "linked" or _telegram_has_pending_onboarding(db, telegram_user):
            text_key = (
                "patient_menu_intro"
                if access == "linked"
                else "patient_open_request_status"
            )
            await reply(chat_id, text_key, "telegram_patient_start_menu")
        elif _has_patient_language_selection(db, chat_id):
            await reply(chat_id, "share_contact", "telegram_patient_start_menu")
        else:
            await _send_language_choice(db, bot_service, chat_id)

    async def language_handler(chat_id: int, language_code: str) -> None:
        previous_template_key = _latest_patient_bot_template_key(db, chat_id)
        _upsert_ticket_qr_telegram_user(
            db, _message_from_update(update), language_code=language_code
        )
        db.commit()
        language = _normalize_patient_language(language_code)
        logger.info(
            "Telegram patient bot language selected",
            extra={"language_code": language},
        )
        settings_context = _is_patient_settings_context_template(previous_template_key)
        reply_text = _localized_text("language_selected", language)
        reply_markup = _telegram_chat_menu(db, chat_id)
        template_key = "telegram_patient_language_selected"
        telegram_user, access = _telegram_patient_access(db, chat_id)
        if settings_context:
            reply_text = f"{reply_text}\n\n{_telegram_settings_message(db, chat_id)}"
            reply_markup = _localized_settings_menu(
                language, navigation_menu=_telegram_chat_menu(db, chat_id)
            )
            template_key = "telegram_patient_settings_language_selected"
        elif access == "onboarding":
            prompt = (
                "patient_open_request_status"
                if _telegram_has_pending_onboarding(db, telegram_user)
                else "share_contact"
            )
            reply_text = f"{reply_text}\n\n{_localized_text(prompt, language)}"
            template_key = "telegram_patient_language_selected_needs_contact"
        await _send_patient_bot_reply(
            db, bot_service, chat_id, reply_text, reply_markup, template_key
        )

    async def help_handler(chat_id: int) -> None:
        await reply(chat_id, "help", "telegram_patient_help")

    async def menu_handler(chat_id: int) -> None:
        await reply(
            chat_id, "main_menu_refreshed", "telegram_patient_main_menu_refreshed"
        )

    async def services_handler(chat_id: int) -> None:
        _, access = _telegram_patient_access(db, chat_id)
        if access == "linked":
            language = _telegram_chat_language(db, chat_id)
            await reply(
                chat_id,
                "services_menu",
                "telegram_patient_services_menu",
                _localized_services_menu(language),
            )
        else:
            await entry_handler(
                chat_id,
                "booking",
                "patient_open_booking",
                "booking_entry_button",
                "telegram_patient_book",
            )

    async def settings_handler(chat_id: int) -> None:
        language = _telegram_chat_language(db, chat_id)
        await _send_patient_bot_reply(
            db,
            bot_service,
            chat_id,
            _telegram_settings_message(db, chat_id),
            _localized_settings_menu(
                language, navigation_menu=_telegram_chat_menu(db, chat_id)
            ),
            "telegram_patient_settings",
        )

    async def entry_handler(
        chat_id: int, section: str, text_key: str, button_key: str, template: str
    ) -> None:
        telegram_user, access = _telegram_patient_access(db, chat_id)
        if access == "unavailable":
            await clinic_handler(chat_id, unavailable=True)
            return
        if access == "linked":
            markup = _telegram_service_entry_markup(db, chat_id, section, button_key)
        elif _telegram_has_pending_onboarding(db, telegram_user):
            text_key = "patient_open_request_status"
            markup = _telegram_onboarding_entry_markup(
                db, chat_id, "request_status_entry_button"
            )
        else:
            text_key = (
                "patient_open_onboarding"
                if section == "booking"
                else "patient_link_prompt"
            )
            markup = _telegram_onboarding_entry_markup(db, chat_id)
        await reply(
            chat_id, text_key if markup else "patient_app_unavailable", template, markup
        )

    book_handler = partial(
        entry_handler,
        section="booking",
        text_key="patient_open_booking",
        button_key="booking_entry_button",
        template="telegram_patient_book",
    )
    cabinet_handler = partial(
        entry_handler,
        section="cabinet",
        text_key="patient_open_cabinet",
        button_key="patient_cabinet_entry_button",
        template="telegram_patient_cabinet",
    )
    queue_handler = partial(
        entry_handler,
        section="queue",
        text_key="patient_open_queue",
        button_key="queue_entry_button",
        template="telegram_patient_queue",
    )
    visits_handler = partial(
        entry_handler,
        section="visits",
        text_key="patient_open_visits",
        button_key="visits_entry_button",
        template="telegram_patient_visits",
    )
    payments_handler = partial(
        entry_handler,
        section="payments",
        text_key="patient_open_payments",
        button_key="payments_entry_button",
        template="telegram_patient_payments",
    )
    results_handler = partial(
        entry_handler,
        section="results",
        text_key="patient_open_results",
        button_key="results_entry_button",
        template="telegram_patient_results",
    )
    forms_handler = partial(
        entry_handler,
        section="forms",
        text_key="patient_forms",
        button_key="patient_forms_entry_button",
        template="telegram_patient_forms",
    )

    async def share_contact_handler(chat_id: int) -> None:
        await reply(chat_id, "share_contact", "telegram_patient_share_contact")

    async def staff_entry_handler(chat_id: int) -> None:
        await reply(chat_id, "staff_entry", "telegram_patient_staff_entry_placeholder")

    async def enable_notifications_handler(chat_id: int) -> None:
        await _set_notification_consent(db, bot_service, chat_id, True)

    async def disable_notifications_handler(chat_id: int) -> None:
        await _set_notification_consent(db, bot_service, chat_id, False)

    russian_language_handler = partial(
        language_handler, language_code=TELEGRAM_LANGUAGE_RU
    )
    uzbek_language_handler = partial(
        language_handler, language_code=TELEGRAM_LANGUAGE_UZ
    )

    command_handlers = {
        "/help": help_handler,
        "/menu": menu_handler,
        "/book": book_handler,
        "/queue": queue_handler,
        "/visits": visits_handler,
        "/appointments": visits_handler,
        "/payments": payments_handler,
        "/profile": cabinet_handler,
        "/results": results_handler,
        "/services": services_handler,
        "/forms": forms_handler,
        "/documents": results_handler,
        "/doctors": book_handler,
        "/cabinet": cabinet_handler,
        "/settings": settings_handler,
        "/support": clinic_handler,
    }
    text_handlers = _patient_text_handler_aliases(
        [
            ("🏥 Записаться на приём", book_handler),
            ("🏥 Записаться", book_handler),
            ("❓ Помощь", help_handler),
            ("⚙️ Настройки", settings_handler),
            ("🎫 Моя очередь", queue_handler),
            ("📅 Мои визиты", visits_handler),
            ("💳 Оплаты и долг", payments_handler),
            ("👤 Мой статус", cabinet_handler),
            ("📄 Результаты", results_handler),
            ("📱 Поделиться номером", share_contact_handler),
            ("📲 Онлайн-сервисы", services_handler),
            ("📋 Анкеты пациента", forms_handler),
            ("🧾 Документы и чеки", results_handler),
            ("🧑‍⚕️ Врачи и расписание", book_handler),
            ("📲 Кабинет пациента", cabinet_handler),
            ("📲 Мой кабинет", cabinet_handler),
            ("📅 Записи", visits_handler),
            ("📋 Статус заявки", cabinet_handler),
            ("👥 Режим сотрудника", staff_entry_handler),
            ("⬅️ Главное меню", menu_handler),
            ("☎️ Связаться с клиникой", clinic_handler),
            ("☎️ Клиника", clinic_handler),
            ("меню", menu_handler),
            ("menu", menu_handler),
            ("menyu", menu_handler),
            ("staff", staff_entry_handler),
            ("сотрудник", staff_entry_handler),
            ("🇷🇺 Русский", russian_language_handler),
            ("🇺🇿 O'zbekcha", uzbek_language_handler),
            ("ozbekcha", uzbek_language_handler),
            ("uzbekcha", uzbek_language_handler),
            ("🔔 Разрешить уведомления", enable_notifications_handler),
            ("🔕 Без уведомлений", disable_notifications_handler),
            ("🔔 Xabarnomalarga roziman", enable_notifications_handler),
            ("🔕 Xabarnomasiz", disable_notifications_handler),
            ("🏥 Qabulga yozilish", book_handler),
            ("❓ Yordam", help_handler),
            ("⚙️ Sozlamalar", settings_handler),
            ("🎫 Mening navbatim", queue_handler),
            ("📅 Mening tashriflarim", visits_handler),
            ("💳 To'lovlar va qarz", payments_handler),
            ("👤 Mening holatim", cabinet_handler),
            ("📄 Natijalar", results_handler),
            ("📱 Telefon raqamni ulashish", share_contact_handler),
            ("📲 Onlayn xizmatlar", services_handler),
            ("📋 Bemor anketalari", forms_handler),
            ("🧾 Hujjatlar va cheklar", results_handler),
            ("🧑‍⚕️ Shifokorlar jadvali", book_handler),
            ("📲 Bemor kabineti", cabinet_handler),
            ("📲 Mening kabinetim", cabinet_handler),
            ("📋 Ariza holati", cabinet_handler),
            ("👥 Xodim rejimi", staff_entry_handler),
            ("⬅️ Asosiy menyu", menu_handler),
            ("☎️ Klinikaga bog'lanish", clinic_handler),
            ("☎️ Klinika", clinic_handler),
            ("Menyu", menu_handler),
            ("Asosiy menyu", menu_handler),
            ("xodim", staff_entry_handler),
        ]
    )

    async def handle_patient_action(chat_id: int, handler) -> None:
        ensure_profile(chat_id, _message_from_update(update))
        _, access = _telegram_patient_access(db, chat_id)
        if access == "unavailable":
            await clinic_handler(chat_id, unavailable=True)
            return
        await handler(chat_id)

    return await _dispatch_clinic_bot_update(
        update=update,
        db=db,
        bot_service=bot_service,
        start_handler=start_handler,
        command_handlers={
            key: partial(handle_patient_action, handler=handler)
            for key, handler in command_handlers.items()
        },
        text_handlers={
            key: partial(handle_patient_action, handler=handler)
            for key, handler in text_handlers.items()
        },
    )


class TelegramMiniAppAppointmentPreviewRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    init_data: str | None = Field(default=None, alias="initData")
    entry_token: str | None = Field(default=None, alias="entryToken")
    patient_id: int | None = Field(default=None, alias="patientId")
    section: str | None = None
    appointment_date: date = Field(..., alias="appointmentDate")
    appointment_time: str | None = Field(default=None, alias="appointmentTime")
    doctor_id: int | None = Field(default=None, alias="doctorId")
    department: str | None = None
    notes: str | None = None
    services: list[str] | None = None
    service_ids: list[int] | None = Field(default=None, alias="serviceIds")


class TelegramMiniAppPatientManifestRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    init_data: str | None = Field(default=None, alias="initData")
    entry_token: str | None = Field(default=None, alias="entryToken")
    section: str | None = None


class TelegramMiniAppBookingDepartmentsRequest(BaseModel):
    """Round-12 (owner P1, PR #3386 review): auth shape for the booking
    departments reference endpoint.

    The Mini App booking form no longer free-types a department name (a
    localized label like "Кардиология" is NOT the canonical `Department.key`
    the routing contract resolves); it picks from THIS endpoint's list, so
    the submitted value is always a canonical key. Same identity contract
    as the booking endpoints themselves (initData primary, entry token
    allowed) — the reference data rides the SAME authenticated surface it
    feeds, and the error reasons match the booking scope contract.
    """

    model_config = ConfigDict(populate_by_name=True)

    init_data: str | None = Field(default=None, alias="initData")
    entry_token: str | None = Field(default=None, alias="entryToken")
    section: str | None = None


class TelegramMiniAppBookingServicesRequest(BaseModel):
    """Authenticated reference read for Admin-approved booking service IDs."""

    model_config = ConfigDict(populate_by_name=True)

    init_data: str | None = Field(default=None, alias="initData")
    entry_token: str | None = Field(default=None, alias="entryToken")
    section: str | None = None


class TelegramMiniAppPatientFormsPreviewRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    init_data: str | None = Field(default=None, alias="initData")
    entry_token: str | None = Field(default=None, alias="entryToken")
    patient_id: int | None = Field(default=None, alias="patientId")
    section: str | None = None


class TelegramMiniAppPatientCabinetSummaryRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    init_data: str | None = Field(default=None, alias="initData")
    entry_token: str | None = Field(default=None, alias="entryToken")
    patient_id: int | None = Field(default=None, alias="patientId")
    section: str | None = None


class TelegramMiniAppPatientReportDownloadRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    init_data: str | None = Field(default=None, alias="initData")
    entry_token: str | None = Field(default=None, alias="entryToken")
    patient_id: int | None = Field(default=None, alias="patientId")
    section: str | None = None
    report_id: int = Field(..., alias="reportId", ge=1)


class TelegramMiniAppPatientFormSubmissionRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    init_data: str | None = Field(default=None, alias="initData")
    entry_token: str | None = Field(default=None, alias="entryToken")
    patient_id: int | None = Field(default=None, alias="patientId")
    section: str | None = None
    form_id: str = Field(..., alias="formId", min_length=1, max_length=64)
    answers: dict[str, Any] = Field(default_factory=dict)
    status: str = Field(default="submitted")


def _validate_webhook_secret(request: Request, db: Session):
    """Validate the secret AND return the config row it authenticated.

    PR-3 (round 31): the caller derives the dedup identity from THIS row's
    credential — one snapshot read binds the secret validation and the
    identity, so an admin replacing the bot between the two reads can no
    longer claim an old-bot update under the replacement bot's identity.
    """
    config = crud_telegram.get_telegram_config(db)
    expected_secret = getattr(config, "webhook_secret", None)
    if not expected_secret:
        logger.error(
            "Telegram webhook rejected because webhook secret is not configured"
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Telegram webhook secret is not configured",
        )

    received_secret = request.headers.get(WEBHOOK_SECRET_HEADER)
    if not hmac.compare_digest(received_secret or "", expected_secret or ""):
        logger.warning("Telegram webhook rejected due to invalid secret token")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid Telegram webhook secret",
        )
    return config


# TG-AUDIT-28 P0-8: webhook должен возвращать 200 даже при ошибке,
# чтобы Telegram не retry'ил (дублирующая обработка). Ошибка логируется.
def _acknowledge_webhook_error(operation: str, exc: Exception) -> JSONResponse:
    logger.error(
        "Telegram webhook error operation=%s error_type=%s: %s",
        operation,
        type(exc).__name__,
        exc,
    )
    return JSONResponse(
        status_code=200, content={"status": "error", "message": "Internal error logged"}
    )


def _raise_telegram_webhook_internal_error(
    operation: str, public_detail: str, exc: Exception
) -> NoReturn:
    logger.warning(
        "Telegram webhook endpoint failed operation=%s error_type=%s",
        operation,
        type(exc).__name__,
    )
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail=public_detail,
    ) from exc


def _telegram_bot_info_failure(exc: Exception) -> dict[str, Any]:
    logger.warning(
        "Telegram webhook endpoint failed operation=get_bot_info error_type=%s",
        type(exc).__name__,
    )
    return {"active": False, "message": TELEGRAM_BOT_INFO_PUBLIC_MESSAGE}


def _mini_app_booking_scope_status_code(reason: str) -> int:
    if reason in MINI_APP_BOOKING_REQUEST_ERROR_REASONS:
        return status.HTTP_400_BAD_REQUEST
    return status.HTTP_403_FORBIDDEN


def _mini_app_forms_scope_status_code(reason: str) -> int:
    if reason in MINI_APP_FORMS_REQUEST_ERROR_REASONS:
        return status.HTTP_400_BAD_REQUEST
    return status.HTTP_403_FORBIDDEN


def _mini_app_booking_deny_reason(detail: Any) -> str:
    """Extract the machine-readable failure reason from an HTTPException
    (SSOT parity with the portal's `_deny_reason` audit trail rows)."""
    if isinstance(detail, dict):
        reason = detail.get("reason")
        if isinstance(reason, str):
            return reason
        message = detail.get("message")
        if isinstance(message, str):
            return message
    if isinstance(detail, str):
        return detail
    return "mini_app_error"


def _mini_app_booking_departments_payload(db: Session) -> dict[str, Any]:
    """Round-12 (owner P1, PR #3386 review): ACTIVE departments for the
    Mini App booking form's department selector.

    The selector submits the canonical `Department.key` — the exact value
    `resolve_booking_department` resolves — so a normal user can no longer
    send a localized label ("Кардиология") and receive 400
    `department_unknown`. Only ACTIVE rows are listed (an inactive
    department in the list would guarantee a 400 on submit), and the
    display name is the clinic's own `name_ru` — the Mini App booking
    surface is Russian-first (same choice as every other patient-facing
    string there).

    Round-15 (owner P2): the clinic's `name_uz` rides along so the
    uz-Latn shell renders the selector in the same language as the rest
    of the form; RU display keeps using `name`.
    """
    department_rows = (
        db.query(Department)
        .filter(Department.active == True)  # noqa: E712 - SQLAlchemy filter
        .order_by(Department.name_ru.asc(), Department.key.asc())
        .all()
    )
    return {
        "departments": [
            {
                "key": row.key,
                "name": row.name_ru,
                "name_uz": row.name_uz,
            }
            for row in department_rows
        ]
    }


def _build_mini_app_appointment_booking_preview_from_request(
    request_body: TelegramMiniAppAppointmentPreviewRequest,
    db: Session,
    *,
    allow_entry_token: bool = False,
    request: Request | None = None,  # M4-P0-1: for audit logging
    resolve_routing: bool = True,
    audit_action: str = "preview",
):
    from app.services.patient_access_audit import log_patient_access

    try:
        if allow_entry_token:
            scope, _auth_source = _resolve_mini_app_patient_scope_from_auth(
                db,
                init_data_payload=request_body.init_data,
                entry_token=request_body.entry_token,
                expected_section=request_body.section or "appointments",
            )
        else:
            if not request_body.init_data:
                raise TelegramMiniAppInitDataError("init_data_required")
            scope = _resolve_mini_app_patient_scope_from_init_data(
                db,
                request_body.init_data,
            )

        try:
            PublicBookingSettingsService(db).validate_patient_booking_service_selection(
                service_ids=request_body.service_ids,
                services=request_body.services,
            )
        except PublicBookingSettingsError as exc:
            log_patient_access(
                db=db,
                scope=scope,
                resource_type="appointment",
                action=audit_action,
                outcome="denied",
                request=request,
                extra_data={"reason": exc.code},
            )
            raise HTTPException(
                status_code=exc.status_code,
                detail={"reason": exc.code},
            ) from exc

        preview = build_telegram_mini_app_appointment_booking_preview(
            scope,
            patient_id=request_body.patient_id,
            appointment_date=request_body.appointment_date,
            appointment_time=request_body.appointment_time,
            doctor_id=request_body.doctor_id,
            department=request_body.department,
            notes=request_body.notes,
            services=request_body.services,
            service_ids=request_body.service_ids,
            # Round-11 (owner P2 parity, PR #3340): the past-day check
            # follows the CLINIC's calendar (Asia/Tashkent queue-settings
            # SSOT `clinic_today`), not the UTC host's `date.today()` — the
            # portal booking surface got this in round-9; both Mini App
            # booking endpoints share THIS helper, so preview and create
            # validate against the same clinic-local day.
            today=clinic_today(db),
        )
    except TelegramMiniAppInitDataError as exc:
        # M4-P0-1: Log auth failure
        log_patient_access(
            db=db,
            subject_patient_id=request_body.patient_id,
            resource_type="appointment",
            action=audit_action,
            outcome="denied",
            request=request,
            extra_data={"reason": exc.reason},
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"reason": exc.reason},
        ) from exc
    except TelegramMiniAppSessionScopeError as exc:
        # M4-P0-1: Log scope failure
        log_patient_access(
            db=db,
            subject_patient_id=request_body.patient_id,
            resource_type="appointment",
            action=audit_action,
            outcome="denied",
            request=request,
            extra_data={"reason": exc.reason},
        )
        raise HTTPException(
            status_code=_mini_app_booking_scope_status_code(exc.reason),
            detail={"reason": exc.reason},
        ) from exc

    # Round-11 (owner P1 parity, PR #3340): BOTH Mini App booking endpoints
    # (preview and create run through this helper) resolve the SAME
    # canonical routing context the create will persist — the submitted
    # department must resolve to an ACTIVE row, and a doctor-booking's
    # routing department is the doctor's CANONICAL department (controlled
    # 400s for unknown/inactive/missing/mismatched departments BEFORE any
    # mutation). A missing Doctor row keeps the pre-round-11 preview shape;
    # create's eligibility gate still answers 404 for it.
    #
    # Round-12 (owner P1/P2, PR #3386 review): the CREATE endpoint passes
    # ``resolve_routing=False`` — its routing context is resolved AFTER the
    # established doctor_not_eligible gate (the eligibility contract keeps
    # precedence over request-shaped routing 400s) and re-validated under
    # FOR UPDATE next to the INSERT (lock_department_for_booking). Only the
    # non-mutating preview keeps the early resolution here.
    department_row: Department | None = None
    doctor_row: Doctor | None = None
    if resolve_routing:
        try:
            department_row = resolve_booking_department(db, preview.draft.department)
            if preview.draft.doctor_id is not None:
                doctor_row = (
                    db.query(Doctor)
                    .filter(Doctor.id == preview.draft.doctor_id)
                    .first()
                )
                if doctor_row is not None:
                    department_row = resolve_doctor_routing_department(
                        doctor_row, department_row
                    )
        except HTTPException as exc:
            # SSOT parity (portal round-3): a routing denial leaves an audit
            # trail row too.
            log_patient_access(
                db=db,
                scope=scope,
                resource_type="appointment",
                action=audit_action,
                outcome="denied",
                request=request,
                extra_data={"reason": _mini_app_booking_deny_reason(exc.detail)},
            )
            raise
        # Use the same exact-ID doctor/department compatibility policy as
        # Create, after resolving the identical canonical department. The
        # existing Mini App contract keeps lifecycle failures (missing or
        # ineligible doctor) ahead of service compatibility in Create.
        validate_service_compatibility = preview.draft.doctor_id is None
        if preview.draft.doctor_id is not None and doctor_row is not None:
            try:
                ensure_doctor_eligible_for_appointment(db, preview.draft.doctor_id)
            except HTTPException as exc:
                if exc.status_code not in {
                    status.HTTP_404_NOT_FOUND,
                    status.HTTP_409_CONFLICT,
                }:
                    raise
            else:
                validate_service_compatibility = True
        if validate_service_compatibility:
            try:
                resolve_exact_service_selection(
                    db,
                    preview.draft.service_ids,
                    doctor_id=preview.draft.doctor_id,
                    department_id=(
                        int(department_row.id) if department_row is not None else None
                    ),
                )
            except InvalidServiceSelection as exc:
                log_patient_access(
                    db=db,
                    scope=scope,
                    resource_type="appointment",
                    action=audit_action,
                    outcome="denied",
                    request=request,
                    extra_data={"reason": str(exc)},
                )
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail={"code": str(exc), "field": "service_ids"},
                ) from exc
    # M4-P0-1: Log successful appointment preview access
    # (audit for actual creation happens in _routes.py create_mini_app_appointment_booking)
    log_patient_access(
        db=db,
        scope=scope,
        resource_type="appointment",
        action="preview",
        outcome="success",
        request=request,
        extra_data={
            "appointment_date": str(preview.draft.appointment_date),
            "appointment_time": preview.draft.appointment_time,
            "department": preview.draft.department,
            "department_id": int(department_row.id) if department_row else None,
        },
    )

    return preview, department_row


def _resolve_mini_app_patient_scope_from_init_data(
    db: Session,
    init_data_payload: str,
):
    bot_token = _get_configured_bot_token(db)
    if not bot_token:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"reason": "bot_token_required"},
        )

    init_data = validate_telegram_mini_app_init_data(
        init_data_payload,
        bot_token=bot_token,
        # M4-P0-2: Legacy mode for per-request initData callers.
        # max_age=24h (backward compat), replay_check=False (same initData
        # is sent with every request). New /auth/exchange endpoint uses
        # the secure defaults: max_age=5min, replay_check=True.
        max_age_seconds=LEGACY_MAX_AUTH_AGE_SECONDS,
        replay_check=False,
    )
    return resolve_telegram_mini_app_session_scope(
        db,
        init_data,
        expected_scope="patient",
    )


def _resolve_mini_app_patient_scope_from_entry_token(
    db: Session,
    entry_token: str,
    *,
    expected_section: str | None = None,
) -> TelegramMiniAppSessionScope:
    parsed = _parse_patient_mini_app_entry_token(
        entry_token,
        expected_section=expected_section,
    )
    if not parsed:
        raise TelegramMiniAppSessionScopeError("entry_token_invalid")

    telegram_user = crud_telegram.get_telegram_user_by_chat_id(
        db,
        int(parsed["chat_id"]),
    )
    if not telegram_user:
        raise TelegramMiniAppSessionScopeError("telegram_link_required")
    if not getattr(telegram_user, "active", False):
        raise TelegramMiniAppSessionScopeError("telegram_link_inactive")
    if getattr(telegram_user, "blocked", False):
        raise TelegramMiniAppSessionScopeError("telegram_link_blocked")
    if not getattr(telegram_user, "patient_id", None):
        raise TelegramMiniAppSessionScopeError("patient_scope_required")

    return TelegramMiniAppSessionScope(
        scope_type="patient",
        telegram_user_id=int(telegram_user.id),
        telegram_chat_id=int(telegram_user.chat_id),
        patient_id=int(telegram_user.patient_id),
    )


def _resolve_mini_app_patient_scope_from_auth(
    db: Session,
    *,
    init_data_payload: str | None = None,
    entry_token: str | None = None,
    expected_section: str | None = None,
) -> tuple[TelegramMiniAppSessionScope, str]:
    normalized_init_data = str(init_data_payload or "").strip()
    if normalized_init_data:
        return (
            _resolve_mini_app_patient_scope_from_init_data(
                db,
                normalized_init_data,
            ),
            "init_data",
        )

    normalized_entry_token = str(entry_token or "").strip()
    if normalized_entry_token:
        return (
            _resolve_mini_app_patient_scope_from_entry_token(
                db,
                normalized_entry_token,
                expected_section=expected_section,
            ),
            "entry_token",
        )

    raise TelegramMiniAppInitDataError("init_data_required")


def _telegram_user_from_mini_app_init_data(
    db: Session,
    init_data_payload: str,
) -> TelegramUser:
    bot_token = _get_configured_bot_token(db)
    if not bot_token:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"reason": "bot_token_required"},
        )

    init_data = validate_telegram_mini_app_init_data(
        init_data_payload,
        bot_token=bot_token,
        # M4-P0-2: Legacy mode (see comment above).
        max_age_seconds=LEGACY_MAX_AUTH_AGE_SECONDS,
        replay_check=False,
    )
    user = init_data.user if isinstance(init_data.user, dict) else {}
    try:
        chat_id = int(user.get("id"))
    except (TypeError, ValueError) as exc:
        raise TelegramMiniAppSessionScopeError("telegram_user_id_required") from exc

    telegram_user = crud_telegram.get_telegram_user_by_chat_id(db, chat_id)
    if not telegram_user:
        raise TelegramMiniAppSessionScopeError("telegram_link_required")
    if not getattr(telegram_user, "active", False):
        raise TelegramMiniAppSessionScopeError("telegram_link_inactive")
    if getattr(telegram_user, "blocked", False):
        raise TelegramMiniAppSessionScopeError("telegram_link_blocked")
    return telegram_user


def _onboarding_scope_for_telegram_user(
    telegram_user: TelegramUser,
) -> TelegramMiniAppSessionScope:
    return TelegramMiniAppSessionScope(
        scope_type="onboarding",  # type: ignore[arg-type]
        telegram_user_id=int(telegram_user.id),
        telegram_chat_id=int(telegram_user.chat_id),
        patient_id=None,
    )


def _resolve_mini_app_onboarding_scope_from_init_data(
    db: Session,
    init_data_payload: str,
) -> TelegramMiniAppSessionScope:
    telegram_user = _telegram_user_from_mini_app_init_data(db, init_data_payload)
    return _onboarding_scope_for_telegram_user(telegram_user)


def _resolve_mini_app_onboarding_scope_from_entry_token(
    db: Session,
    entry_token: str,
    *,
    expected_section: str | None = None,
) -> TelegramMiniAppSessionScope:
    parsed = _parse_patient_onboarding_entry_token(
        entry_token,
        expected_section=expected_section,
    )
    if not parsed:
        raise TelegramMiniAppSessionScopeError("entry_token_invalid")

    telegram_user = crud_telegram.get_telegram_user_by_chat_id(
        db,
        int(parsed["chat_id"]),
    )
    if not telegram_user:
        raise TelegramMiniAppSessionScopeError("telegram_link_required")
    if not getattr(telegram_user, "active", False):
        raise TelegramMiniAppSessionScopeError("telegram_link_inactive")
    if getattr(telegram_user, "blocked", False):
        raise TelegramMiniAppSessionScopeError("telegram_link_blocked")
    return _onboarding_scope_for_telegram_user(telegram_user)


def _resolve_mini_app_onboarding_scope_from_auth(
    db: Session,
    *,
    init_data_payload: str | None = None,
    entry_token: str | None = None,
    expected_section: str | None = None,
) -> tuple[TelegramMiniAppSessionScope, str]:
    normalized_init_data = str(init_data_payload or "").strip()
    if normalized_init_data:
        return (
            _resolve_mini_app_onboarding_scope_from_init_data(
                db,
                normalized_init_data,
            ),
            "init_data",
        )

    normalized_entry_token = str(entry_token or "").strip()
    if normalized_entry_token:
        return (
            _resolve_mini_app_onboarding_scope_from_entry_token(
                db,
                normalized_entry_token,
                expected_section=expected_section,
            ),
            "entry_token",
        )

    raise TelegramMiniAppInitDataError("init_data_required")


def _mini_app_patient_manifest_payload(
    db: Session,
    scope: TelegramMiniAppSessionScope,
    *,
    auth_source: str,
) -> dict[str, Any]:
    patient = db.query(Patient).filter(Patient.id == int(scope.patient_id)).first()
    telegram_user = (
        db.query(TelegramUser)
        .filter(TelegramUser.id == int(scope.telegram_user_id))
        .first()
    )
    language_code = _normalize_patient_language(
        getattr(telegram_user, "language_code", None)
    )
    return {
        "scope": {
            "type": scope.scope_type,
        },
        "auth": {
            "source": auth_source,
            "entry_token_fallback": auth_source == "entry_token",
        },
        "language": {
            "code": language_code,
            "label": (
                "O'zbekcha" if language_code == TELEGRAM_LANGUAGE_UZ else "Русский"
            ),
        },
        "patient": {
            "linked": True,
            "name": _patient_display_name(patient),
        },
        "capabilities": {
            "appointments": {
                "status": "preview_enabled",
                "preview_enabled": True,
                "create_enabled": False,
            },
            "forms": {
                "status": "preview_enabled",
                "preview_enabled": True,
                "capture_enabled": True,
            },
            "cabinet": {
                "status": "summary_enabled",
                "read_enabled": True,
            },
            "visits": {
                "status": "summary_enabled",
                "read_enabled": True,
            },
            "queue": {
                "status": "summary_enabled",
                "read_enabled": True,
            },
            "payments": {
                "status": "summary_enabled",
                "view_enabled": True,
                "payment_capture_enabled": False,
            },
            "results": {
                "status": "ready_pdf_list_enabled",
                "read_enabled": True,
            },
        },
        "policy": {
            "plain_telegram_chat_allowed": False,
            "medical_details_in_chat": False,
            "entry_token_ttl_seconds": PATIENT_MINI_APP_ENTRY_TOKEN_TTL_SECONDS,
        },
    }


def _mini_app_patient_onboarding_manifest_payload(
    db: Session,
    scope: TelegramMiniAppSessionScope,
    *,
    auth_source: str,
) -> dict[str, Any]:
    telegram_user = (
        db.query(TelegramUser)
        .filter(TelegramUser.id == int(scope.telegram_user_id))
        .first()
    )
    language_code = _normalize_patient_language(
        getattr(telegram_user, "language_code", None)
    )
    onboarding_status = (
        PatientOnboardingService(db).own_status_response(telegram_user)
        if telegram_user is not None
        else {
            "request": None,
            "messageKey": "patient_onboarding_not_found",
            "safeNextAction": "submit_onboarding_request",
        }
    )
    return {
        "scope": {
            "type": "onboarding",
        },
        "auth": {
            "source": auth_source,
            "entry_token_fallback": auth_source == "entry_token",
        },
        "language": {
            "code": language_code,
            "label": (
                "O'zbekcha" if language_code == TELEGRAM_LANGUAGE_UZ else "Русский"
            ),
        },
        "patient": {
            "linked": False,
            "name": None,
        },
        "onboarding": onboarding_status,
        "capabilities": {
            "appointments": {
                "status": "request_review_enabled",
                "preview_enabled": False,
                "create_enabled": False,
                "onboarding_request_enabled": True,
            },
            "forms": {"status": "staff_approval_required", "read_enabled": False},
            "cabinet": {"status": "staff_approval_required", "read_enabled": False},
            "visits": {"status": "staff_approval_required", "read_enabled": False},
            "queue": {"status": "staff_approval_required", "read_enabled": False},
            "payments": {"status": "staff_approval_required", "view_enabled": False},
            "results": {"status": "staff_approval_required", "read_enabled": False},
            "documents": {"status": "staff_approval_required", "read_enabled": False},
        },
        "policy": {
            "plain_telegram_chat_allowed": False,
            "medical_details_in_chat": False,
            "entry_token_ttl_seconds": PATIENT_MINI_APP_ENTRY_TOKEN_TTL_SECONDS,
            "patient_auto_create_allowed": False,
            "confirmed_appointment_create_allowed": False,
        },
    }


def _build_mini_app_patient_manifest_from_request(
    request_body: TelegramMiniAppPatientManifestRequest,
    db: Session,
    *,
    request: Request | None = None,  # M4-P0-1: for audit logging
) -> dict[str, Any]:
    from app.services.patient_access_audit import log_patient_access

    try:
        scope, auth_source = _resolve_mini_app_patient_scope_from_auth(
            db,
            init_data_payload=request_body.init_data,
            entry_token=request_body.entry_token,
            expected_section=request_body.section,
        )
        # M4-P0-1: Log successful manifest access
        log_patient_access(
            db=db,
            scope=scope,
            resource_type="manifest",
            action="view",
            outcome="success",
            request=request,
        )
        return _mini_app_patient_manifest_payload(db, scope, auth_source=auth_source)
    except (TelegramMiniAppInitDataError, TelegramMiniAppSessionScopeError):
        try:
            onboarding_scope, onboarding_auth_source = (
                _resolve_mini_app_onboarding_scope_from_auth(
                    db,
                    init_data_payload=request_body.init_data,
                    entry_token=request_body.entry_token,
                    expected_section=request_body.section,
                )
            )
        except TelegramMiniAppInitDataError as exc:
            # M4-P0-1: Log auth failure
            log_patient_access(
                db=db,
                resource_type="manifest",
                action="view",
                outcome="denied",
                request=request,
                extra_data={"reason": exc.reason},
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"reason": exc.reason},
            ) from exc
        except TelegramMiniAppSessionScopeError as exc:
            # M4-P0-1: Log scope failure
            log_patient_access(
                db=db,
                resource_type="manifest",
                action="view",
                outcome="denied",
                request=request,
                extra_data={"reason": exc.reason},
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"reason": exc.reason},
            ) from exc
        return _mini_app_patient_onboarding_manifest_payload(
            db,
            onboarding_scope,
            auth_source=onboarding_auth_source,
        )


def _iso_date_value(value: date | datetime | None) -> str | None:
    if value is None:
        return None
    return (
        value.date().isoformat() if isinstance(value, datetime) else value.isoformat()
    )


def _iso_datetime_value(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.isoformat()


def _mini_app_patient_appointments(
    db: Session,
    patient_id: int,
    *,
    limit: int = 3,
) -> list[Appointment]:
    return (
        db.query(Appointment)
        .filter(Appointment.patient_id == patient_id)
        .order_by(
            Appointment.appointment_date.desc(),
            Appointment.created_at.desc(),
            Appointment.id.desc(),
        )
        .limit(limit)
        .all()
    )


def _appointment_department_label(appointment: Appointment) -> str | None:
    # Round-4 (owner P2, PR #3340): `Department` has NO `name` column — only
    # `key` / `name_ru` / `name_uz` — so the previous
    # `getattr(department, "name", None)` silently returned None for every
    # row with a persisted department (the portal booking now guarantees
    # one). Display the localized Russian name with the canonical key as
    # the fallback; the shared builder serves both Mini App and JWT portal.
    department = getattr(appointment, "department", None)
    return getattr(department, "name_ru", None) or getattr(department, "key", None)


def _mini_app_patient_cabinet_summary_payload(
    db: Session,
    scope,
) -> dict[str, Any]:
    patient_id = int(scope.patient_id)
    patient = db.query(Patient).filter(Patient.id == patient_id).first()
    appointments = _mini_app_patient_appointments(db, patient_id)
    recent_visits = _patient_recent_visits(db, patient_id)
    queue_entries = _patient_today_queue_entries(db, patient_id)
    (
        entries,
        visits_for_billing,
        expected_total,
        paid_total,
        pending_total,
        debt_total,
    ) = _billing_totals(db, patient_id)
    reports = _latest_ready_lab_report_instances(db, patient_id)

    return {
        "scope": {
            "type": scope.scope_type,
            "patient_id": patient_id,
        },
        "patient": {
            "name": _patient_display_name(patient),
        },
        "appointments": [
            {
                "id": int(appointment.id),
                "date": _iso_date_value(appointment.appointment_date),
                "time": appointment.appointment_time,
                "status": appointment.status,
                "department": _appointment_department_label(appointment),
            }
            for appointment in appointments
        ],
        "visits": [
            {
                "id": int(visit.id),
                "date": _iso_date_value(visit.visit_date),
                "status": visit.status,
            }
            for visit in recent_visits
        ],
        "queue": [
            {
                "number": entry.number,
                "status": entry.status,
                "cabinet": getattr(
                    getattr(entry, "queue", None), "cabinet_number", None
                ),
            }
            for entry in queue_entries[:5]
        ],
        "payments": {
            "billed": _format_money(expected_total),
            "paid": _format_money(paid_total),
            "pending": _format_money(pending_total),
            "debt": _format_money(debt_total),
            "linked_visit_count": len(visits_for_billing),
            "active_queue_count": len(entries),
        },
        "reports": [
            {
                "id": int(report.id),
                "name": getattr(
                    getattr(report, "template", None), "name", "Lab report"
                ),
                "ready_at": _iso_datetime_value(
                    report.finalized_at or report.created_at
                ),
                "status": report.status,
            }
            for report in reports
        ],
        "policy": {
            "plain_telegram_chat_allowed": False,
            "medical_details_in_chat": False,
            "pdf_included": False,
        },
    }


def _build_mini_app_patient_cabinet_summary_from_request(
    request_body: TelegramMiniAppPatientCabinetSummaryRequest,
    db: Session,
    *,
    request: Request | None = None,  # M4-P0-1: for audit logging
) -> dict[str, Any]:
    # M4-P1-1: Centralized ABAC authorization
    from app.services.authorization import can_access_phi
    from app.services.patient_access_audit import log_patient_access

    try:
        scope, _auth_source = _resolve_mini_app_patient_scope_from_auth(
            db,
            init_data_payload=request_body.init_data,
            entry_token=request_body.entry_token,
            expected_section=request_body.section or "cabinet",
        )
        # M4-P1-1: Use centralized authorization instead of inline patient_id check
        subject_patient_id = (
            request_body.patient_id
            if request_body.patient_id is not None
            else scope.patient_id
        )
        if not can_access_phi(
            scope,
            subject_patient_id=subject_patient_id,
            resource_type="cabinet_summary",
            action="view",
        ):
            # M4-P0-1: Log denied access attempt
            log_patient_access(
                db=db,
                scope=scope,
                subject_patient_id=subject_patient_id,
                resource_type="cabinet_summary",
                action="view",
                outcome="denied",
                request=request,
                extra_data={"reason": "authorization_denied"},
            )
            raise TelegramMiniAppSessionScopeError("patient_scope_mismatch")
    except TelegramMiniAppInitDataError as exc:
        # M4-P0-1: Log auth failure (cannot identify subject, but log attempt)
        log_patient_access(
            db=db,
            subject_patient_id=request_body.patient_id,
            resource_type="cabinet_summary",
            action="view",
            outcome="denied",
            request=request,
            extra_data={"reason": exc.reason},
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"reason": exc.reason},
        ) from exc
    except TelegramMiniAppSessionScopeError as exc:
        # M4-P0-1: Log scope failure
        log_patient_access(
            db=db,
            subject_patient_id=request_body.patient_id,
            resource_type="cabinet_summary",
            action="view",
            outcome="denied",
            request=request,
            extra_data={"reason": exc.reason},
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"reason": exc.reason},
        ) from exc

    # M4-P0-1: Log successful cabinet summary access
    log_patient_access(
        db=db,
        scope=scope,
        resource_type="cabinet_summary",
        action="view",
        outcome="success",
        request=request,
    )

    return _mini_app_patient_cabinet_summary_payload(db, scope)


def _resolve_mini_app_patient_scope_for_optional_patient(
    db: Session,
    init_data_payload: str | None,
    entry_token: str | None,
    patient_id: int | None,
    *,
    expected_section: str | None = None,
):
    scope, _auth_source = _resolve_mini_app_patient_scope_from_auth(
        db,
        init_data_payload=init_data_payload,
        entry_token=entry_token,
        expected_section=expected_section,
    )
    if patient_id is not None and int(scope.patient_id) != int(patient_id):
        raise TelegramMiniAppSessionScopeError("patient_scope_mismatch")
    return scope


def _build_mini_app_patient_report_download_response(
    request_body: TelegramMiniAppPatientReportDownloadRequest,
    db: Session,
    *,
    request: Request | None = None,  # M4-P0-1: for audit logging
) -> Response:
    # M4-P1-1: Centralized ABAC authorization
    from app.services.authorization import can_access_phi
    from app.services.patient_access_audit import log_patient_access

    try:
        scope = _resolve_mini_app_patient_scope_for_optional_patient(
            db,
            request_body.init_data,
            request_body.entry_token,
            request_body.patient_id,
            expected_section=request_body.section or "results",
        )
        # M4-P1-1: Use centralized authorization
        subject_patient_id = (
            request_body.patient_id
            if request_body.patient_id is not None
            else scope.patient_id
        )
        if not can_access_phi(
            scope,
            subject_patient_id=subject_patient_id,
            resource_type="lab_report",
            action="download",
            resource_id=str(request_body.report_id),
        ):
            log_patient_access(
                db=db,
                scope=scope,
                subject_patient_id=subject_patient_id,
                resource_type="lab_report",
                resource_id=str(request_body.report_id),
                action="download",
                outcome="denied",
                request=request,
                extra_data={"reason": "authorization_denied"},
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"reason": "authorization_denied"},
            )
    except TelegramMiniAppInitDataError as exc:
        # M4-P0-1: Log auth failure
        log_patient_access(
            db=db,
            subject_patient_id=request_body.patient_id,
            resource_type="lab_report",
            resource_id=str(request_body.report_id),
            action="download",
            outcome="denied",
            request=request,
            extra_data={"reason": exc.reason},
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"reason": exc.reason},
        ) from exc
    except TelegramMiniAppSessionScopeError as exc:
        # M4-P0-1: Log scope failure
        log_patient_access(
            db=db,
            subject_patient_id=request_body.patient_id,
            resource_type="lab_report",
            resource_id=str(request_body.report_id),
            action="download",
            outcome="denied",
            request=request,
            extra_data={"reason": exc.reason},
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"reason": exc.reason},
        ) from exc

    report = (
        db.query(LabReportInstance)
        .filter(
            LabReportInstance.id == int(request_body.report_id),
            LabReportInstance.patient_id == int(scope.patient_id),
            LabReportInstance.status.in_(LAB_REPORT_READY_STATUSES),
        )
        .first()
    )
    if report is None:
        # M4-P0-1: Log not-found / not-ready attempt (denied)
        log_patient_access(
            db=db,
            scope=scope,
            resource_type="lab_report",
            resource_id=str(request_body.report_id),
            action="download",
            outcome="denied",
            request=request,
            extra_data={"reason": "report_not_ready_or_not_found"},
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"reason": "report_not_ready_or_not_found"},
        )

    try:
        from app.api.v1.endpoints import telegram_webhook

        filename, pdf_bytes, _caption = telegram_webhook._build_lab_report_pdf(
            db, report
        )
    except Exception as exc:
        # M4-P0-1: Log generation error
        log_patient_access(
            db=db,
            scope=scope,
            resource_type="lab_report",
            resource_id=str(request_body.report_id),
            action="download",
            outcome="error",
            request=request,
            extra_data={"reason": "pdf_generation_failed"},
        )
        _raise_telegram_webhook_internal_error(
            "mini_app_patient_report_download",
            "Protected report could not be generated",
            exc,
        )

    # M4-P0-1: Log successful report download
    log_patient_access(
        db=db,
        scope=scope,
        resource_type="lab_report",
        resource_id=str(report.id),
        action="download",
        outcome="success",
        request=request,
        extra_data={"report_status": report.status, "filename": filename},
    )

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _build_mini_app_patient_forms_preview_from_request(
    request_body: TelegramMiniAppPatientFormsPreviewRequest,
    db: Session,
    *,
    request: Request | None = None,  # M4-P0-1: for audit logging
):
    from app.services.patient_access_audit import log_patient_access

    try:
        scope, _auth_source = _resolve_mini_app_patient_scope_from_auth(
            db,
            init_data_payload=request_body.init_data,
            entry_token=request_body.entry_token,
            expected_section=request_body.section or "forms",
        )
        preview = build_telegram_mini_app_patient_forms_preview(
            db,
            scope,
            patient_id=request_body.patient_id,
        )
    except TelegramMiniAppInitDataError as exc:
        # M4-P0-1: Log auth failure
        log_patient_access(
            db=db,
            subject_patient_id=request_body.patient_id,
            resource_type="forms_preview",
            action="view",
            outcome="denied",
            request=request,
            extra_data={"reason": exc.reason},
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"reason": exc.reason},
        ) from exc
    except TelegramMiniAppSessionScopeError as exc:
        # M4-P0-1: Log scope failure
        log_patient_access(
            db=db,
            subject_patient_id=request_body.patient_id,
            resource_type="forms_preview",
            action="view",
            outcome="denied",
            request=request,
            extra_data={"reason": exc.reason},
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"reason": exc.reason},
        ) from exc

    # M4-P0-1: Log successful forms preview access
    log_patient_access(
        db=db,
        scope=scope,
        resource_type="forms_preview",
        action="view",
        outcome="success",
        request=request,
        extra_data={"forms_count": len(preview.forms)},
    )

    return preview


def _save_mini_app_patient_form_submission_from_request(
    request_body: TelegramMiniAppPatientFormSubmissionRequest,
    db: Session,
    *,
    request: Request | None = None,  # M4-P0-1: for audit logging
):
    from app.services.patient_access_audit import log_patient_access

    try:
        scope, _auth_source = _resolve_mini_app_patient_scope_from_auth(
            db,
            init_data_payload=request_body.init_data,
            entry_token=request_body.entry_token,
            expected_section=request_body.section or "forms",
        )
        result = save_telegram_mini_app_patient_form_submission(
            db,
            scope,
            patient_id=request_body.patient_id,
            form_id=request_body.form_id,
            answers=request_body.answers,
            status=request_body.status,
        )
    except TelegramMiniAppInitDataError as exc:
        # M4-P0-1: Log auth failure
        log_patient_access(
            db=db,
            subject_patient_id=request_body.patient_id,
            resource_type="form_submission",
            resource_id=str(request_body.form_id),
            action="submit",
            outcome="denied",
            request=request,
            extra_data={"reason": exc.reason},
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"reason": exc.reason},
        ) from exc
    except TelegramMiniAppSessionScopeError as exc:
        # M4-P0-1: Log scope failure
        log_patient_access(
            db=db,
            subject_patient_id=request_body.patient_id,
            resource_type="form_submission",
            resource_id=str(request_body.form_id),
            action="submit",
            outcome="denied",
            request=request,
            extra_data={"reason": exc.reason},
        )
        raise HTTPException(
            status_code=_mini_app_forms_scope_status_code(exc.reason),
            detail={"reason": exc.reason},
        ) from exc

    # M4-P0-1: Log successful form submission
    log_patient_access(
        db=db,
        scope=scope,
        resource_type="form_submission",
        resource_id=str(request_body.form_id),
        action="submit",
        outcome="success",
        request=request,
        extra_data={
            "form_status": request_body.status,
            "submission_id": result.submission.id if result.submission else None,
        },
    )

    return result


def _telegram_user_from_onboarding_request_auth(
    db: Session,
    request_body: PatientOnboardingAuthRequest,
) -> TelegramUser:
    try:
        scope, _auth_source = _resolve_mini_app_onboarding_scope_from_auth(
            db,
            init_data_payload=request_body.init_data,
            entry_token=request_body.entry_token,
            expected_section=request_body.section or "appointments",
        )
    except TelegramMiniAppInitDataError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"reason": exc.reason},
        ) from exc
    except TelegramMiniAppSessionScopeError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"reason": exc.reason},
        ) from exc

    telegram_user = (
        db.query(TelegramUser)
        .filter(TelegramUser.id == int(scope.telegram_user_id))
        .first()
    )
    if telegram_user is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"reason": "telegram_link_required"},
        )
    return telegram_user
