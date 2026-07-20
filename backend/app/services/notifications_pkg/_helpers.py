"""Module-level helper functions from notifications.py.

Split from notifications.py — these functions are used by the
NotificationSenderService but are not methods.
"""
from __future__ import annotations

import logging  # noqa: F401
import smtplib  # noqa: F401
from datetime import UTC, datetime  # noqa: F401
from email.mime.multipart import MIMEMultipart  # noqa: F401
from email.mime.text import MIMEText  # noqa: F401
from html import escape  # noqa: F401
from typing import Any  # noqa: F401

import httpx  # noqa: F401
from jinja2 import Environment, select_autoescape  # noqa: F401

# NOTIF-REAUDIT-28 P1-1: autoescape для защиты от SSTI/XSS.
# Раньше Template(template_text) использовался без autoescape —
# admin-controlled templates могли выполнять произвольный Python (SSTI),
# а user data с HTML попадала в email body unescaped.
_jinja_env = Environment(autoescape=True)
from sqlalchemy.orm import Session  # noqa: F401

from app.core.config import settings  # noqa: F401
from app.crud.notification import (  # noqa: F401
    crud_notification_history,
    crud_notification_template,
)
from app.crud.user_management import (  # noqa: F401
    user_notification_settings as crud_user_notification_settings,
)
from app.models.notification import NotificationHistory  # noqa: F401
from app.models.user import User  # noqa: F401
from app.schemas.notification import NotificationHistoryCreate  # noqa: F401
from app.services.fcm_service import get_fcm_service  # noqa: F401
from app.services.notification_platform_service import (
    get_notification_platform_service,  # noqa: F401
)
from app.services.notification_websocket import (
    get_notification_ws_manager,  # noqa: F401
)
from app.services.telegram.bot import telegram_bot  # noqa: F401

logger = logging.getLogger(__name__)


def _fresh_db():
    """NOTIF-REAUDIT-28 P0-5: create a fresh DB session for background tasks.

    FastAPI закрывает request-scoped сессию после ответа. Background tasks,
    которым передали `db=db`, работают с закрытой сессией → DetachedInstanceError.
    Использование: `with _fresh_db() as db: sender.send(db, ...)`
    """
    from contextlib import contextmanager

    from app.db.session import SessionLocal

    @contextmanager
    def _session():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    return _session()


NOTIFICATION_EVENT_TYPE_ALIASES = {
    "queue_changed": "queue_update",
    "diagnostics_return": "diagnostics_return_needed",
    "queue_status": "queue_status_changed",
    "payment_update": "payment_notification",
    "payment_success": "payment_notification",
    "paymentcreated": "payment_created",
    "paymentpaid": "payment_paid",
    "result_ready": "lab_results",
    "lab_result_ready": "lab_results",
    "labresultready": "lab_results",
    "appointment_rescheduled": "schedule_change",
    "appointment_cancelled": "schedule_change",
    "visitcreated": "visit_created",
    "queueticketissued": "queue_ticket_issued",
    "queuestatuschanged": "queue_status_changed",
    "patientcalled": "patient_called",
    "all_free_pending": "all_free_requested",
    "all_free_declined": "all_free_rejected",
    "allfree_requested": "all_free_requested",
    "allfree_approved": "all_free_approved",
    "allfree_rejected": "all_free_rejected",
    "notification_message_received": "message_received",
    "lab_critical": "lab_critical_result",
    "lab_new_assignment": "lab_new_study",
    "lab_result_sent": "lab_result_sent_confirmation",
    "registrar_alert": "registrar_system_alert",
    "security_warning": "security_alert",
    "billing_warning": "billing_alert",
    "patient_create": "patient_registered",
}

LAB_NOTIFICATION_EVENT_TYPES = {
    "lab_results",
    "lab_critical_result",
    "lab_new_study",
    "lab_critical_finding",
    "lab_result_sent_confirmation",
    "diagnostics_return_needed",
}

REGISTRAR_NOTIFICATION_EVENT_TYPES = {
    "new_appointment",
    "price_change",
    "queue_status_changed",
    "system_alert",
    "registrar_system_alert",
    "security_alert",
    "billing_alert",
    "all_free_requested",
    "all_free_approved",
    "all_free_rejected",
    "patient_registered",
}

QUEUE_NOTIFICATION_EVENT_TYPES = {
    "patient_called",
    "queue_call",
    "queue_status_changed",
    "queue_position",
    "queue_reminder",
    "queue_ticket_issued",
    "diagnostics_return_needed",
    "queue_update",
}

PATIENT_TELEGRAM_EVENT_PREFERENCES = {
    "appointment_reminder": "appointment_reminders",
    "visit_created": "appointment_reminders",
    "queue_ticket_issued": "appointment_reminders",
    "queue_status_changed": "appointment_reminders",
    "patient_called": "appointment_reminders",
    "payment_created": "notifications_enabled",
    "payment_notification": "notifications_enabled",
    "payment_paid": "notifications_enabled",
    "lab_results": "lab_notifications",
}

PATIENT_TELEGRAM_EVENT_MESSAGES = {
    "appointment_reminder": {
        "ru": "Напоминание о записи. Дата: {date}. Врач: {doctor}.",
        "uz-Latn": "Qabul eslatmasi. Sana: {date}. Shifokor: {doctor}.",
    },
    "visit_created": {
        "ru": "Запись создана. Дата: {date}. Врач: {doctor}.",
        "uz-Latn": "Qabul yaratildi. Sana: {date}. Shifokor: {doctor}.",
    },
    "queue_ticket_issued": {
        "ru": "Талон очереди готов. Номер: {queue_number}. Кабинет: {cabinet}.",
        "uz-Latn": "Navbat taloni tayyor. Raqam: {queue_number}. Xona: {cabinet}.",
    },
    "queue_status_changed": {
        "ru": "Статус очереди обновлен. Номер: {queue_number}. Статус: {status}.",
        "uz-Latn": "Navbat holati yangilandi. Raqam: {queue_number}. Holat: {status}.",
    },
    "patient_called": {
        "ru": "Вас приглашают. Номер: {queue_number}. Кабинет: {cabinet}.",
        "uz-Latn": "Sizni chaqirishmoqda. Raqam: {queue_number}. Xona: {cabinet}.",
    },
    "payment_created": {
        "ru": "Сформирована оплата. Сумма: {amount} {currency}.",
        "uz-Latn": "To'lov yaratildi. Summa: {amount} {currency}.",
    },
    "payment_notification": {
        "ru": "Статус оплаты обновлен. Сумма: {amount} {currency}.",
        "uz-Latn": "To'lov holati yangilandi. Summa: {amount} {currency}.",
    },
    "payment_paid": {
        "ru": "Оплата получена. Квитанция доступна в защищенном кабинете.",
        "uz-Latn": "To'lov qabul qilindi. Kvitansiya himoyalangan kabinetda mavjud.",
    },
    "lab_results": {
        "ru": "Результаты готовы. Откройте защищенный кабинет.",
        "uz-Latn": "Natijalar tayyor. Himoyalangan kabinetni oching.",
    },
}


def _normalize_notification_event_type(
    event_type: str | None,
    *,
    fallback: str = "",
) -> str:
    normalized = str(event_type or "").strip().lower()
    if not normalized:
        return fallback
    return NOTIFICATION_EVENT_TYPE_ALIASES.get(normalized, normalized)


def _normalize_patient_telegram_language(language_code: Any) -> str:
    value = str(language_code or "").strip().lower().replace("_", "-")
    if value in {"uz", "uz-latn", "uzbek", "o'zbekcha"}:
        return "uz-Latn"
    return "ru"


def _safe_patient_telegram_value(value: Any, fallback: str) -> str:
    text = str(value or "").strip()
    if not text:
        text = fallback
    return escape(text[:80])


def _patient_telegram_event_message(
    event_type: str,
    language_code: Any,
    metadata: dict[str, Any] | None = None,
) -> str | None:
    templates = PATIENT_TELEGRAM_EVENT_MESSAGES.get(event_type)
    if not templates:
        return None

    language = _normalize_patient_telegram_language(language_code)
    template = templates.get(language) or templates["ru"]
    data = metadata or {}
    safe_data = {
        "date": _safe_patient_telegram_value(
            data.get("date") or data.get("visit_date") or data.get("appointment_date"),
            "-" if language == "ru" else "-",
        ),
        "doctor": _safe_patient_telegram_value(
            data.get("doctor") or data.get("doctor_name"),
            "уточняется" if language == "ru" else "aniqlanmoqda",
        ),
        "queue_number": _safe_patient_telegram_value(
            data.get("queue_number") or data.get("number"),
            "-" if language == "ru" else "-",
        ),
        "cabinet": _safe_patient_telegram_value(
            data.get("cabinet") or data.get("cabinet_number"),
            "уточняется" if language == "ru" else "aniqlanmoqda",
        ),
        "status": _safe_patient_telegram_value(
            data.get("status"),
            "обновлен" if language == "ru" else "yangilandi",
        ),
        "amount": _safe_patient_telegram_value(data.get("amount"), "0"),
        "currency": _safe_patient_telegram_value(data.get("currency"), "UZS"),
    }
    return template.format(**safe_data)


