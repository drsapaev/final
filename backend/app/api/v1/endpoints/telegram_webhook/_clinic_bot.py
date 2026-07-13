"""
Split from telegram_webhook.py (5647 LOC → modular).
"""
from __future__ import annotations

import hmac
import logging
from datetime import date, datetime
from typing import Any, NoReturn

from fastapi import HTTPException, Request, Response, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.api.v1.endpoints.admin_telegram import (
    _get_configured_bot_token,
)
from app.crud import telegram_config as crud_telegram
from app.models.appointment import Appointment
from app.models.lab import LabReportInstance
from app.models.patient import Patient
from app.models.telegram_config import TelegramUser
from app.services.patient_onboarding_service import PatientOnboardingService

logger = logging.getLogger(__name__)
from app.api.v1.endpoints.telegram_webhook._helpers import *  # noqa: F401, F403
from app.api.v1.endpoints.telegram_webhook._helpers import (
    _localized_main_menu,
    _localized_services_menu,
    _localized_settings_menu,
    _localized_text,
    _normalize_patient_button_text,
    _normalize_patient_language,
    _parse_patient_mini_app_entry_token,
    _parse_patient_onboarding_entry_token,
    _patient_text_handler_aliases,
    _telegram_booking_entry_markup,
    _telegram_chat_language,
    _telegram_chat_menu,
    _telegram_chat_text,
    _telegram_patient_cabinet_entry_markup,
    _telegram_patient_doctors_entry_markup,
    _telegram_patient_documents_entry_markup,
    _telegram_patient_forms_entry_markup,
    _telegram_payment_entry_markup,
    _telegram_queue_entry_markup,
    _telegram_settings_message,
    _telegram_visits_entry_markup,
)  # noqa: F401
from app.api.v1.endpoints.telegram_webhook._patient_commands import (  # noqa: F401  # noqa: F401
    _is_patient_settings_context_template,
    _latest_patient_bot_template_key,
    _send_patient_bot_reply,
    _upsert_ticket_qr_telegram_user,
)
from app.api.v1.endpoints.telegram_webhook._staff_commands import (  # noqa: F401  # noqa: F401
    _billing_totals,
    _build_lab_report_pdf,
    _clinic_payments_message,
    _clinic_queue_message,
    _clinic_status_message,
    _clinic_visits_message,
    _format_money,
    _handle_contact_link,
    _handle_staff_link_start,
    _handle_staff_read_only_menu,
    _handle_ticket_qr_start,
    _latest_ready_lab_report_instances,
    _message_chat_id,
    _message_from_update,
    _message_text,
    _patient_display_name,
    _patient_for_telegram_chat,
    _patient_recent_visits,
    _patient_today_queue_entries,
    _send_clinic_lab_results,
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
    """Dispatch a clinic bot update to the appropriate handler."""
    dispatch = getattr(bot_service, "process_patient_bot_update", None)
    if callable(dispatch):
        return await dispatch(
            update,
            db,
            staff_start_handler=_handle_staff_link_start,
            staff_menu_handler=_handle_staff_read_only_menu,
            ticket_start_handler=_handle_ticket_qr_start,
            contact_handler=_handle_contact_link,
            start_handler=start_handler,
            command_handlers=command_handlers,
            text_handlers=text_handlers,
        )

    if await _handle_staff_link_start(update, db, bot_service):
        return True

    if await _handle_staff_read_only_menu(update, db, bot_service):
        return True

    if await _handle_ticket_qr_start(update, db, bot_service):
        return True

    message = _message_from_update(update)
    if not message:
        return False

    chat_id = _message_chat_id(message)
    if chat_id is None:
        return False

    if await _handle_contact_link(message, db, bot_service):
        return True

    existing_telegram_user = crud_telegram.get_telegram_user_by_chat_id(db, chat_id)
    if existing_telegram_user is None:
        _upsert_ticket_qr_telegram_user(db, message, notifications_enabled=False)
        db.commit()

    text = _message_text(message)
    command = text.split(maxsplit=1)[0].split("@", 1)[0].lower() if text else ""
    handler = command_handlers.get(command) or text_handlers.get(
        _normalize_patient_button_text(text)
    )
    if command == "/start":
        await start_handler(chat_id, message)
        return True
    if handler:
        await handler(chat_id)
        return True
    return False


async def _handle_clinic_bot_update(
    update: dict[str, Any], db: Session, bot_service
) -> bool:
    async def start_handler(chat_id: int, message: dict[str, Any]) -> None:
        _upsert_ticket_qr_telegram_user(db, message, notifications_enabled=False)
        db.commit()
        await _send_language_choice(db, bot_service, chat_id)

    async def language_handler(chat_id: int, language_code: str) -> None:
        message = _message_from_update(update)
        telegram_user = crud_telegram.get_telegram_user_by_chat_id(db, chat_id)
        previous_template_key = _latest_patient_bot_template_key(db, chat_id)
        _upsert_ticket_qr_telegram_user(
            db,
            message,
            language_code=language_code,
            notifications_enabled=False if telegram_user is None else None,
        )
        db.commit()
        language = _normalize_patient_language(language_code)
        logger.info(
            "Telegram patient bot language selected",
            extra={"language_code": language},
        )
        settings_context = _is_patient_settings_context_template(previous_template_key)
        reply_text = _localized_text("language_selected", language)
        reply_markup = _localized_main_menu(language)
        template_key = "telegram_patient_language_selected"
        linked_telegram_user = crud_telegram.get_telegram_user_by_chat_id(db, chat_id)
        if not settings_context and not getattr(linked_telegram_user, "patient_id", None):
            reply_text = f"{reply_text}\n\n{_localized_text('share_contact', language)}"
            template_key = "telegram_patient_language_selected_needs_contact"
        if settings_context:
            reply_text = f"{reply_text}\n\n{_telegram_settings_message(db, chat_id)}"
            reply_markup = _localized_settings_menu(language)
            template_key = "telegram_patient_settings_language_selected"
        await _send_patient_bot_reply(
            db,
            bot_service,
            chat_id,
            reply_text,
            reply_markup,
            template_key,
        )

    async def help_handler(chat_id: int) -> None:
        language = _telegram_chat_language(db, chat_id)
        await _send_patient_bot_reply(
            db,
            bot_service,
            chat_id,
            _localized_text("help", language),
            _localized_main_menu(language),
            "telegram_patient_help",
        )

    async def menu_handler(chat_id: int) -> None:
        language = _telegram_chat_language(db, chat_id)
        await _send_patient_bot_reply(
            db,
            bot_service,
            chat_id,
            _localized_text("main_menu_refreshed", language),
            _localized_main_menu(language),
            "telegram_patient_main_menu_refreshed",
        )

    async def services_handler(chat_id: int) -> None:
        language = _telegram_chat_language(db, chat_id)
        await _send_patient_bot_reply(
            db,
            bot_service,
            chat_id,
            _localized_text("services_menu", language),
            _localized_services_menu(language),
            "telegram_patient_services_menu",
        )

    async def settings_handler(chat_id: int) -> None:
        language = _telegram_chat_language(db, chat_id)
        await _send_patient_bot_reply(
            db,
            bot_service,
            chat_id,
            _telegram_settings_message(db, chat_id),
            _localized_settings_menu(language),
            "telegram_patient_settings",
        )

    async def queue_handler(chat_id: int) -> None:
        await _send_patient_bot_reply(
            db,
            bot_service,
            chat_id,
            _clinic_queue_message(db, chat_id),
            _telegram_queue_entry_markup(db, chat_id)
            or _telegram_chat_menu(db, chat_id),
            "telegram_patient_queue",
        )

    async def visits_handler(chat_id: int) -> None:
        await _send_patient_bot_reply(
            db,
            bot_service,
            chat_id,
            _clinic_visits_message(db, chat_id),
            _telegram_visits_entry_markup(db, chat_id)
            or _telegram_chat_menu(db, chat_id),
            "telegram_patient_visits",
        )

    async def payments_handler(chat_id: int) -> None:
        await _send_patient_bot_reply(
            db,
            bot_service,
            chat_id,
            _clinic_payments_message(db, chat_id),
            _telegram_payment_entry_markup(db, chat_id)
            or _telegram_chat_menu(db, chat_id),
            "telegram_patient_payments",
        )

    async def profile_handler(chat_id: int) -> None:
        await _send_patient_bot_reply(
            db,
            bot_service,
            chat_id,
            _clinic_status_message(db, chat_id),
            _telegram_chat_menu(db, chat_id),
            "telegram_patient_profile",
        )

    async def results_handler(chat_id: int) -> None:
        await _send_clinic_lab_results(db, bot_service, chat_id)

    async def share_contact_handler(chat_id: int) -> None:
        await _send_patient_bot_reply(
            db,
            bot_service,
            chat_id,
            _telegram_chat_text(db, chat_id, "share_contact"),
            _telegram_chat_menu(db, chat_id),
            "telegram_patient_share_contact",
        )

    async def book_handler(chat_id: int) -> None:
        language = _telegram_chat_language(db, chat_id)
        reply_markup = _telegram_booking_entry_markup(db, chat_id) or _localized_main_menu(language)
        await _send_patient_bot_reply(
            db,
            bot_service,
            chat_id,
            _localized_text("book", language),
            reply_markup,
            "telegram_patient_book",
        )

    async def patient_forms_handler(chat_id: int) -> None:
        language = _telegram_chat_language(db, chat_id)
        telegram_user, _patient = _patient_for_telegram_chat(db, chat_id)
        reply_text = (
            _localized_text("patient_forms", language)
            if telegram_user and telegram_user.patient_id
            else _localized_text("unlinked_protected_action", language)
        )
        reply_markup = (
            _telegram_patient_forms_entry_markup(db, chat_id)
            or _localized_services_menu(language)
        )
        await _send_patient_bot_reply(
            db,
            bot_service,
            chat_id,
            reply_text,
            reply_markup,
            "telegram_patient_forms_placeholder",
        )

    async def patient_documents_handler(chat_id: int) -> None:
        language = _telegram_chat_language(db, chat_id)
        telegram_user, _patient = _patient_for_telegram_chat(db, chat_id)
        reply_text = (
            _localized_text("patient_documents", language)
            if telegram_user and telegram_user.patient_id
            else _localized_text("unlinked_protected_action", language)
        )
        reply_markup = (
            _telegram_patient_documents_entry_markup(db, chat_id)
            or _localized_services_menu(language)
        )
        await _send_patient_bot_reply(
            db,
            bot_service,
            chat_id,
            reply_text,
            reply_markup,
            "telegram_patient_documents_placeholder",
        )

    async def doctor_schedule_handler(chat_id: int) -> None:
        language = _telegram_chat_language(db, chat_id)
        reply_markup = (
            _telegram_patient_doctors_entry_markup(db, chat_id)
            or _localized_services_menu(language)
        )
        await _send_patient_bot_reply(
            db,
            bot_service,
            chat_id,
            _localized_text("doctor_schedule", language),
            reply_markup,
            "telegram_patient_doctor_schedule_placeholder",
        )

    async def patient_cabinet_handler(chat_id: int) -> None:
        language = _telegram_chat_language(db, chat_id)
        telegram_user, _patient = _patient_for_telegram_chat(db, chat_id)
        reply_text = (
            _localized_text("patient_cabinet", language)
            if telegram_user and telegram_user.patient_id
            else _localized_text("unlinked_protected_action", language)
        )
        reply_markup = (
            _telegram_patient_cabinet_entry_markup(db, chat_id)
            or _localized_services_menu(language)
        )
        await _send_patient_bot_reply(
            db,
            bot_service,
            chat_id,
            reply_text,
            reply_markup,
            "telegram_patient_cabinet_placeholder",
        )

    async def staff_entry_handler(chat_id: int) -> None:
        language = _telegram_chat_language(db, chat_id)
        await _send_patient_bot_reply(
            db,
            bot_service,
            chat_id,
            _localized_text("staff_entry", language),
            _localized_main_menu(language),
            "telegram_patient_staff_entry_placeholder",
        )

    async def support_handler(chat_id: int) -> None:
        language = _telegram_chat_language(db, chat_id)
        await _send_patient_bot_reply(
            db,
            bot_service,
            chat_id,
            _localized_text("support", language),
            _localized_main_menu(language),
            "telegram_patient_support",
        )

    async def enable_notifications_handler(chat_id: int) -> None:
        await _set_notification_consent(db, bot_service, chat_id, True)

    async def disable_notifications_handler(chat_id: int) -> None:
        await _set_notification_consent(db, bot_service, chat_id, False)

    async def russian_language_handler(chat_id: int) -> None:
        await language_handler(chat_id, TELEGRAM_LANGUAGE_RU)

    async def uzbek_language_handler(chat_id: int) -> None:
        await language_handler(chat_id, TELEGRAM_LANGUAGE_UZ)

    command_handlers = {
        "/help": help_handler,
        "/menu": menu_handler,
        "/book": book_handler,
        "/queue": queue_handler,
        "/visits": visits_handler,
        "/payments": payments_handler,
        "/profile": profile_handler,
        "/results": results_handler,
        "/services": services_handler,
        "/forms": patient_forms_handler,
        "/documents": patient_documents_handler,
        "/doctors": doctor_schedule_handler,
        "/cabinet": patient_cabinet_handler,
        "/settings": settings_handler,
        "/support": support_handler,
    }
    text_handlers = _patient_text_handler_aliases(
        [
            ("🏥 Записаться на приём", book_handler),
            ("❓ Помощь", help_handler),
            ("⚙️ Настройки", settings_handler),
            ("🎫 Моя очередь", queue_handler),
            ("📅 Мои визиты", visits_handler),
            ("💳 Оплаты и долг", payments_handler),
            ("👤 Мой статус", profile_handler),
            ("📄 Результаты", results_handler),
            ("📱 Поделиться номером", share_contact_handler),
            ("📲 Онлайн-сервисы", services_handler),
            ("📋 Анкеты пациента", patient_forms_handler),
            ("🧾 Документы и чеки", patient_documents_handler),
            ("🧑‍⚕️ Врачи и расписание", doctor_schedule_handler),
            ("📲 Кабинет пациента", patient_cabinet_handler),
            ("👥 Режим сотрудника", staff_entry_handler),
            ("⬅️ Главное меню", menu_handler),
            ("☎️ Связаться с клиникой", support_handler),
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
            ("👤 Mening holatim", profile_handler),
            ("📄 Natijalar", results_handler),
            ("📱 Telefon raqamni ulashish", share_contact_handler),
            ("📲 Onlayn xizmatlar", services_handler),
            ("📋 Bemor anketalari", patient_forms_handler),
            ("🧾 Hujjatlar va cheklar", patient_documents_handler),
            ("🧑‍⚕️ Shifokorlar jadvali", doctor_schedule_handler),
            ("📲 Bemor kabineti", patient_cabinet_handler),
            ("👥 Xodim rejimi", staff_entry_handler),
            ("⬅️ Asosiy menyu", menu_handler),
            ("☎️ Klinikaga bog'lanish", support_handler),
            ("Menyu", menu_handler),
            ("Asosiy menyu", menu_handler),
            ("xodim", staff_entry_handler),
        ]
    )

    # Dispatch the update to the appropriate handler
    return await _dispatch_clinic_bot_update(
        update=update,
        db=db,
        bot_service=bot_service,
        start_handler=start_handler,
        command_handlers=command_handlers,
        text_handlers=text_handlers,
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


class TelegramMiniAppPatientManifestRequest(BaseModel):
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


def _validate_webhook_secret(request: Request, db: Session) -> None:
    config = crud_telegram.get_telegram_config(db)
    expected_secret = getattr(config, "webhook_secret", None)
    if not expected_secret:
        logger.error("Telegram webhook rejected because webhook secret is not configured")
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


# TG-AUDIT-28 P0-8: webhook должен возвращать 200 даже при ошибке,
# чтобы Telegram не retry'ил (дублирующая обработка). Ошибка логируется.
def _acknowledge_webhook_error(operation: str, exc: Exception) -> JSONResponse:
    logger.error(
        "Telegram webhook error operation=%s error_type=%s: %s",
        operation, type(exc).__name__, exc,
    )
    return JSONResponse(status_code=200, content={"status": "error", "message": "Internal error logged"})


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


def _build_mini_app_appointment_booking_preview_from_request(
    request_body: TelegramMiniAppAppointmentPreviewRequest,
    db: Session,
    *,
    allow_entry_token: bool = False,
):
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

        preview = build_telegram_mini_app_appointment_booking_preview(
            scope,
            patient_id=request_body.patient_id,
            appointment_date=request_body.appointment_date,
            appointment_time=request_body.appointment_time,
            doctor_id=request_body.doctor_id,
            department=request_body.department,
            notes=request_body.notes,
            services=request_body.services,
        )
    except TelegramMiniAppInitDataError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"reason": exc.reason},
        ) from exc
    except TelegramMiniAppSessionScopeError as exc:
        raise HTTPException(
            status_code=_mini_app_booking_scope_status_code(exc.reason),
            detail={"reason": exc.reason},
        ) from exc

    return preview


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
        return _resolve_mini_app_patient_scope_from_init_data(
            db,
            normalized_init_data,
        ), "init_data"

    normalized_entry_token = str(entry_token or "").strip()
    if normalized_entry_token:
        return _resolve_mini_app_patient_scope_from_entry_token(
            db,
            normalized_entry_token,
            expected_section=expected_section,
        ), "entry_token"

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
        return _resolve_mini_app_onboarding_scope_from_init_data(
            db,
            normalized_init_data,
        ), "init_data"

    normalized_entry_token = str(entry_token or "").strip()
    if normalized_entry_token:
        return _resolve_mini_app_onboarding_scope_from_entry_token(
            db,
            normalized_entry_token,
            expected_section=expected_section,
        ), "entry_token"

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
            "label": "O'zbekcha"
            if language_code == TELEGRAM_LANGUAGE_UZ
            else "Русский",
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
            "label": "O'zbekcha"
            if language_code == TELEGRAM_LANGUAGE_UZ
            else "Русский",
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
) -> dict[str, Any]:
    try:
        scope, auth_source = _resolve_mini_app_patient_scope_from_auth(
            db,
            init_data_payload=request_body.init_data,
            entry_token=request_body.entry_token,
            expected_section=request_body.section,
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
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"reason": exc.reason},
            ) from exc
        except TelegramMiniAppSessionScopeError as exc:
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
    return value.date().isoformat() if isinstance(value, datetime) else value.isoformat()


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
    department = getattr(appointment, "department", None)
    return getattr(department, "name", None)


def _mini_app_patient_cabinet_summary_payload(
    db: Session,
    scope,
) -> dict[str, Any]:
    patient_id = int(scope.patient_id)
    patient = db.query(Patient).filter(Patient.id == patient_id).first()
    appointments = _mini_app_patient_appointments(db, patient_id)
    recent_visits = _patient_recent_visits(db, patient_id)
    queue_entries = _patient_today_queue_entries(db, patient_id)
    entries, visits_for_billing, expected_total, paid_total, pending_total, debt_total = (
        _billing_totals(db, patient_id)
    )
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
                "cabinet": getattr(getattr(entry, "queue", None), "cabinet_number", None),
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
                "name": getattr(getattr(report, "template", None), "name", "Lab report"),
                "ready_at": _iso_datetime_value(report.finalized_at or report.created_at),
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
) -> dict[str, Any]:
    try:
        scope, _auth_source = _resolve_mini_app_patient_scope_from_auth(
            db,
            init_data_payload=request_body.init_data,
            entry_token=request_body.entry_token,
            expected_section=request_body.section or "cabinet",
        )
        if request_body.patient_id is not None:
            if int(scope.patient_id) != int(request_body.patient_id):
                raise TelegramMiniAppSessionScopeError("patient_scope_mismatch")
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
) -> Response:
    try:
        scope = _resolve_mini_app_patient_scope_for_optional_patient(
            db,
            request_body.init_data,
            request_body.entry_token,
            request_body.patient_id,
            expected_section=request_body.section or "results",
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
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"reason": "report_not_ready_or_not_found"},
        )

    try:
        from app.api.v1.endpoints import telegram_webhook

        filename, pdf_bytes, _caption = telegram_webhook._build_lab_report_pdf(db, report)
    except Exception as exc:
        _raise_telegram_webhook_internal_error(
            "mini_app_patient_report_download",
            "Protected report could not be generated",
            exc,
        )

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _build_mini_app_patient_forms_preview_from_request(
    request_body: TelegramMiniAppPatientFormsPreviewRequest,
    db: Session,
):
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
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"reason": exc.reason},
        ) from exc
    except TelegramMiniAppSessionScopeError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"reason": exc.reason},
        ) from exc

    return preview


def _save_mini_app_patient_form_submission_from_request(
    request_body: TelegramMiniAppPatientFormSubmissionRequest,
    db: Session,
):
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
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"reason": exc.reason},
        ) from exc
    except TelegramMiniAppSessionScopeError as exc:
        raise HTTPException(
            status_code=_mini_app_forms_scope_status_code(exc.reason),
            detail={"reason": exc.reason},
        ) from exc

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

