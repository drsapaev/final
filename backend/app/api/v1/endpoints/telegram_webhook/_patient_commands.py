"""
Split from telegram_webhook.py (5647 LOC → modular).
"""
from __future__ import annotations

import hashlib
import logging
import secrets
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.v1.endpoints.admin_telegram import (
    STAFF_BOT_COMMAND_REGISTRATION_CONTRACT,
    STAFF_BOT_CONFIRMATION_CONTRACT,
    STAFF_BOT_READ_ONLY_DOMAIN_DATA_COMMAND_KEYS,
    STAFF_BOT_READ_ONLY_MENU_CONTRACT,
    _build_staff_bot_status,
    _get_configured_bot_token,
    _get_staff_bot_token_runtime_status,
    _normalize_staff_role,
)
from app.crud import audit as crud_audit
from app.crud import telegram_config as crud_telegram
from app.models.clinic import Doctor
from app.models.lab import LabReportInstance
from app.models.notification import NotificationDelivery, NotificationEvent
from app.models.online_queue import DailyQueue, OnlineQueueEntry
from app.models.payment import Payment
from app.models.payment_invoice import PaymentInvoice
from app.models.payment_webhook import PaymentWebhook
from app.models.telegram_config import TelegramMessage, TelegramUser
from app.models.user import User
from app.models.visit import Visit

logger = logging.getLogger(__name__)
from app.api.v1.endpoints.telegram_webhook._helpers import *  # noqa: F401, F403


async def _send_patient_bot_reply(
    db: Session,
    bot_service,
    chat_id: int,
    text: str,
    reply_markup: dict[str, Any],
    template_key: str,
) -> bool:
    corruption_reason = telegram_text_corruption_reason(text)
    if corruption_reason:
        try:
            db.add(
                TelegramMessage(
                    chat_id=chat_id,
                    message_type="patient_bot_reply",
                    template_key=template_key,
                    message_text="[blocked_corrupted_text]",
                    status="failed",
                    error_message=f"blocked_corrupted_text:{corruption_reason}",
                )
            )
            db.commit()
            logger.warning(
                "Telegram patient bot reply blocked template_key=%s reason=%s",
                template_key,
                corruption_reason,
            )
        except Exception as exc:
            db.rollback()
            logger.warning(
                "Telegram patient bot reply block log failed template_key=%s error_type=%s",
                template_key,
                type(exc).__name__,
            )
        return False

    sent = bool(await bot_service._send_message(chat_id, text, reply_markup))
    try:
        db.add(
            TelegramMessage(
                chat_id=chat_id,
                message_type="patient_bot_reply",
                template_key=template_key,
                message_text=str(text or ""),
                status="sent" if sent else "failed",
                sent_at=datetime.now(UTC) if sent else None,
            )
        )
        db.commit()
        logger.info(
            "Telegram patient bot reply recorded template_key=%s status=%s",
            template_key,
            "sent" if sent else "failed",
        )
    except Exception as exc:
        db.rollback()
        logger.warning(
            "Telegram patient bot reply log failed template_key=%s error_type=%s",
            template_key,
            type(exc).__name__,
        )
    return sent


def _latest_patient_bot_template_key(db: Session, chat_id: int) -> str | None:
    row = (
        db.query(TelegramMessage.template_key)
        .filter(
            TelegramMessage.chat_id == chat_id,
            TelegramMessage.message_type == "patient_bot_reply",
        )
        .order_by(TelegramMessage.id.desc())
        .first()
    )
    return str(row[0]) if row and row[0] else None


def _is_patient_settings_context_template(template_key: str | None) -> bool:
    return template_key in {
        "telegram_patient_settings",
        "telegram_patient_settings_language_selected",
        "telegram_patient_settings_notifications_enabled",
        "telegram_patient_settings_notifications_disabled",
    }


def _upsert_ticket_qr_telegram_user(
    db: Session,
    message: dict[str, Any],
    patient_id: int | None = None,
    language_code: str | None = None,
    notifications_enabled: bool | None = None,
) -> None:
    chat = message.get("chat") or {}
    from_user = message.get("from") or {}
    chat_id = chat.get("id")
    if chat_id is None:
        return

    telegram_user = crud_telegram.get_telegram_user_by_chat_id(db, int(chat_id))
    payload = {
        "username": from_user.get("username"),
        "first_name": from_user.get("first_name"),
        "last_name": from_user.get("last_name"),
        "active": True,
        "blocked": False,
        "last_activity": datetime.now(UTC),
    }
    if language_code is not None:
        payload["language_code"] = _normalize_patient_language(language_code)
    elif not telegram_user:
        payload["language_code"] = _normalize_patient_language(
            from_user.get("language_code") or TELEGRAM_LANGUAGE_RU
        )
    if patient_id is not None:
        payload["patient_id"] = patient_id
    if notifications_enabled is not None:
        payload["notifications_enabled"] = notifications_enabled
        payload["appointment_reminders"] = notifications_enabled
        payload["lab_notifications"] = notifications_enabled

    if telegram_user:
        for field, value in payload.items():
            if hasattr(telegram_user, field):
                setattr(telegram_user, field, value)
        db.flush()
        return

    create_notifications_enabled = payload.pop("notifications_enabled", False)
    create_appointment_reminders = payload.pop("appointment_reminders", False)
    create_lab_notifications = payload.pop("lab_notifications", False)
    db.add(
        TelegramUser(
            **payload,
            chat_id=int(chat_id),
            notifications_enabled=create_notifications_enabled,
            appointment_reminders=create_appointment_reminders,
            lab_notifications=create_lab_notifications,
        )
    )
    db.flush()


def _staff_telegram_reference_hash(chat_id: int) -> str:
    digest = hashlib.sha256(f"staff-telegram-chat:{chat_id}".encode()).hexdigest()
    return f"telegram_chat:{digest[:24]}"


def _upsert_staff_link_telegram_user(
    db: Session,
    message: dict[str, Any],
    *,
    linked_user_id: int,
) -> TelegramUser | None:
    chat = message.get("chat") or {}
    from_user = message.get("from") or {}
    chat_id = chat.get("id")
    if chat_id is None:
        return None

    telegram_user = crud_telegram.get_telegram_user_by_chat_id(db, int(chat_id))
    payload = {
        "user_id": linked_user_id,
        "username": from_user.get("username"),
        "first_name": from_user.get("first_name"),
        "last_name": from_user.get("last_name"),
        "active": True,
        "blocked": False,
        "last_activity": datetime.now(UTC),
    }

    if telegram_user:
        for field, value in payload.items():
            if hasattr(telegram_user, field):
                setattr(telegram_user, field, value)
        db.flush()
        return telegram_user

    telegram_user = TelegramUser(
        **payload,
        chat_id=int(chat_id),
        language_code=_normalize_patient_language(
            from_user.get("language_code") or TELEGRAM_LANGUAGE_RU
        ),
        notifications_enabled=False,
        appointment_reminders=False,
        lab_notifications=False,
    )
    db.add(telegram_user)
    db.flush()
    return telegram_user


def _record_staff_link_audit(
    db: Session,
    *,
    action: str,
    chat_id: int,
    request_id: str | None,
    actor_user_id: int | None = None,
    telegram_user_id: int | None = None,
    role: str | None = None,
    reason: str | None = None,
) -> None:
    result = "success" if action == "staff_link_created" else "rejected"
    payload = {
        "actor_role": role,
        "telegram_user_id_hash": _staff_telegram_reference_hash(chat_id),
        "action_key": action,
        "target_type": "telegram_user",
        "target_reference_hash": _staff_telegram_reference_hash(chat_id),
        "result": result,
        "timestamp": datetime.now(UTC).isoformat(),
        "request_id": request_id,
    }
    if reason:
        payload["reason"] = reason

    crud_audit.log(
        db,
        action=action,
        entity_type="telegram_user",
        entity_id=telegram_user_id,
        actor_user_id=actor_user_id,
        payload=payload,
    )


def _record_staff_command_audit(
    db: Session,
    *,
    chat_id: int,
    request_id: str | None,
    actor_user_id: int | None,
    telegram_user_id: int | None,
    role: str,
    command_key: str,
    menu_item_key: str | None = None,
    result: str = "handled",
    reason: str | None = None,
) -> None:
    payload = {
        "actor_role": role,
        "telegram_user_id_hash": _staff_telegram_reference_hash(chat_id),
        "action_key": "staff_command_received",
        "target_type": "telegram_user",
        "target_reference_hash": _staff_telegram_reference_hash(chat_id),
        "result": result,
        "timestamp": datetime.now(UTC).isoformat(),
        "request_id": request_id,
        "command_key": command_key,
        "read_only": True,
        "state_changing_action": False,
        "redacted": True,
    }
    if menu_item_key:
        payload["menu_item_key"] = menu_item_key
    if reason:
        payload["reason"] = reason

    crud_audit.log(
        db,
        action="staff_command_received",
        entity_type="telegram_user",
        entity_id=telegram_user_id,
        actor_user_id=actor_user_id,
        payload=payload,
    )


def _staff_action_reference_hash(operation_key: str) -> str:
    digest = hashlib.sha256(f"staff_action:{operation_key}".encode()).hexdigest()
    return f"staff_action:{digest[:24]}"


def _staff_confirmation_token_hash(raw_token: str) -> str:
    digest = hashlib.sha256(raw_token.encode()).hexdigest()
    return f"staff_confirmation_token:{digest}"


def _staff_action_payload_hash(
    *, operation_key: str, command_key: str, role: str
) -> str:
    digest = hashlib.sha256(
        f"{operation_key}|{command_key}|{role}".encode()
    ).hexdigest()
    return f"staff_action_payload:{digest}"


def _staff_action_idempotency_key_hash(
    *,
    token_hash: str,
    action_payload_hash: str,
    target_reference_hash: str,
    request_id: str | None,
) -> str:
    material = "|".join(
        [
            token_hash,
            action_payload_hash,
            target_reference_hash,
            str(request_id or ""),
        ]
    )
    digest = hashlib.sha256(material.encode()).hexdigest()
    return f"staff_action_idempotency:{digest}"


def _record_staff_action_denied_audit(
    db: Session,
    *,
    chat_id: int,
    request_id: str | None,
    actor_user_id: int,
    telegram_user_id: int | None,
    role: str,
    operation_key: str,
    command_key: str,
    reason: str,
) -> None:
    payload = {
        "actor_role": role,
        "telegram_user_id_hash": _staff_telegram_reference_hash(chat_id),
        "action_key": "staff_action_denied",
        "target_type": "telegram_staff_action",
        "target_reference_hash": _staff_action_reference_hash(operation_key),
        "result": "denied",
        "timestamp": datetime.now(UTC).isoformat(),
        "request_id": request_id,
        "operation_key": operation_key,
        "command_key": command_key,
        "confirmation_required": True,
        "telegram_execution_enabled": False,
        "domain_mutation": False,
        "state_changing_action": True,
        "redacted": True,
        "reason": reason,
    }
    crud_audit.log(
        db,
        action="staff_action_denied",
        entity_type="telegram_user",
        entity_id=telegram_user_id,
        actor_user_id=actor_user_id,
        payload=payload,
    )


def _record_staff_action_confirmation_requested_audit(
    db: Session,
    *,
    chat_id: int,
    request_id: str | None,
    actor_user_id: int,
    telegram_user_id: int | None,
    role: str,
    operation_key: str,
    command_key: str,
    target_reference_hash: str,
    expires_at: datetime,
    confirmation_window_seconds: int,
) -> None:
    payload = {
        "actor_role": role,
        "telegram_user_id_hash": _staff_telegram_reference_hash(chat_id),
        "action_key": "staff_action_confirmation_requested",
        "target_type": "telegram_staff_action",
        "target_reference_hash": target_reference_hash,
        "result": "confirmation_requested",
        "timestamp": datetime.now(UTC).isoformat(),
        "request_id": request_id,
        "operation_key": operation_key,
        "command_key": command_key,
        "confirmation_required": True,
        "confirmation_token_hash_stored": True,
        "confirmation_token_returned_to_telegram": False,
        "confirmation_expires_at": expires_at.isoformat(),
        "confirmation_window_seconds": confirmation_window_seconds,
        "idempotency_key_present": True,
        "idempotency_key_hash_stored": True,
        "idempotency_key_returned_to_telegram": False,
        "telegram_execution_enabled": False,
        "domain_mutation": False,
        "state_changing_action": True,
        "redacted": True,
    }
    crud_audit.log(
        db,
        action="staff_action_confirmation_requested",
        entity_type="telegram_user",
        entity_id=telegram_user_id,
        actor_user_id=actor_user_id,
        payload=payload,
    )


def _create_staff_action_confirmation_request(
    db: Session,
    *,
    chat_id: int,
    request_id: str | None,
    actor_user_id: int,
    telegram_user_id: int | None,
    role: str,
    operation: dict[str, Any],
    command_key: str,
) -> str:
    operation_key = str(operation.get("key") or "staff_action").strip()
    confirmation_window_seconds = int(
        STAFF_BOT_CONFIRMATION_CONTRACT.get("confirmation_window_seconds") or 120
    )
    expires_at = datetime.now(UTC) + timedelta(
        seconds=confirmation_window_seconds
    )
    target_reference_hash = _staff_action_reference_hash(operation_key)
    action_payload_hash = _staff_action_payload_hash(
        operation_key=operation_key,
        command_key=command_key,
        role=role,
    )
    raw_token = secrets.token_urlsafe(32)
    token_hash = _staff_confirmation_token_hash(raw_token)
    idempotency_key_hash = _staff_action_idempotency_key_hash(
        token_hash=token_hash,
        action_payload_hash=action_payload_hash,
        target_reference_hash=target_reference_hash,
        request_id=request_id,
    )

    _record_staff_action_confirmation_requested_audit(
        db,
        chat_id=chat_id,
        request_id=request_id,
        actor_user_id=actor_user_id,
        telegram_user_id=telegram_user_id,
        role=role,
        operation_key=operation_key,
        command_key=command_key,
        target_reference_hash=target_reference_hash,
        expires_at=expires_at,
        confirmation_window_seconds=confirmation_window_seconds,
    )
    TelegramStaffConfirmationTokenService(db).issue_token(
        token_hash=token_hash,
        staff_user_id=actor_user_id,
        telegram_chat_id=chat_id,
        operation_key=operation_key,
        command_key=command_key,
        action_payload_hash=action_payload_hash,
        target_type="telegram_staff_action",
        target_reference_hash=target_reference_hash,
        idempotency_key_hash=idempotency_key_hash,
        expires_at=expires_at,
        request_id=request_id,
    )

    operation_label = str(operation.get("label") or operation_key).strip()
    domain = str(operation.get("domain_service_required") or "domain").strip()
    return "\n".join(
        [
            TELEGRAM_STAFF_ACTION_CONFIRMATION_REQUESTED_MESSAGE,
            f"Action: {operation_label}",
            f"Domain: {domain}",
            f"Expires in: {confirmation_window_seconds} seconds",
            "Status: awaiting confirmation in the protected clinic app",
            "Telegram execution: disabled",
            "Domain mutation: not performed",
        ]
    )


def _staff_read_only_commands() -> set[str]:
    return {
        str(item.get("command") or "").lower()
        for item in STAFF_BOT_COMMAND_REGISTRATION_CONTRACT.get("commands", [])
        if item.get("intent") == "read_only" and item.get("command")
    }


def _staff_menu_for_role(role: Any) -> dict[str, Any] | None:
    role_key = _normalize_staff_role(role)
    for role_menu in STAFF_BOT_READ_ONLY_MENU_CONTRACT:
        if role_menu.get("role") == role_key:
            return role_menu
    return None


STAFF_MENU_ITEM_ICONS = {
    "queue_overview": "📋",
    "next_patient": "➡️",
    "payment_status": "💳",
    "today_schedule": "📅",
    "emr_reminders": "🩺",
    "unpaid_invoices": "🧾",
    "paid_invoices": "✅",
    "reconciliation_alerts": "🔁",
    "ready_reports": "📄",
    "pending_reports": "⏳",
    "delivery_status": "📬",
    "daily_summary": "📊",
    "integration_errors": "⚠️",
    "staff_readiness": "🛠️",
    "revenue_summary": "💰",
}

STAFF_MENU_BUTTON_ICON_PREFIXES = tuple(
    dict.fromkeys(
        [
            *STAFF_MENU_ITEM_ICONS.values(),
            "🏠",
            "❓",
        ]
    )
)


def _staff_menu_item_label(item: dict[str, Any]) -> str:
    key = str(item.get("key") or "").strip()
    label = str(item.get("label") or key).strip()
    icon = STAFF_MENU_ITEM_ICONS.get(key)
    return f"{icon} {label}" if icon else label


def _normalize_staff_button_text(text: Any) -> str:
    value = " ".join(str(text or "").strip().lower().split())
    value = value.replace("\ufe0f", "").strip()
    for prefix in STAFF_MENU_BUTTON_ICON_PREFIXES:
        normalized_prefix = prefix.replace("\ufe0f", "").strip().lower()
        if normalized_prefix and value.startswith(normalized_prefix):
            value = value[len(normalized_prefix):].strip()
            break
    return value


def _staff_menu_keyboard(role_menu: dict[str, Any]) -> dict[str, Any]:
    rows = [
        [{"text": _staff_menu_item_label(item)}]
        for item in role_menu.get("items", [])
        if item.get("intent") == "read_only"
    ]
    rows.append([{"text": "/staff"}, {"text": "/help"}])
    return {
        "keyboard": rows,
        "resize_keyboard": True,
        "one_time_keyboard": False,
    }


def _staff_menu_message(user: User, role_menu: dict[str, Any]) -> str:
    items = [
        _staff_menu_item_label(item)
        for item in role_menu.get("items", [])
        if item.get("intent") == "read_only"
    ]
    role_key = _normalize_staff_role(getattr(user, "role", None))
    role_label = str(role_menu.get("label") or role_key).strip()
    lines = [
        "👥 Меню сотрудника (только просмотр)",
        "Staff read-only menu",
        f"Роль: {role_label} ({role_key})",
        f"Role: {role_key}",
        "",
        "Что можно смотреть в Telegram:",
    ]
    lines.extend(f"- {item}" for item in items)
    lines.extend(
        [
            "",
            "Команды:",
            "/staff или /help - открыть это меню",
            "/queue - очередь по роли",
            "/schedule - расписание",
            "/payments - статусы оплат",
            "/reports - готовность результатов",
            "/summary - операционная сводка",
            "",
            "Действия, которые меняют данные, в Telegram отключены.",
            "State-changing actions are disabled in Telegram.",
            "Для вызова пациента, изменения очереди, оплаты или EMR откройте приложение клиники.",
            "No patient names, phone numbers, diagnoses, or full EMR content are shown here.",
        ]
    )
    return "\n".join(lines)


def _staff_read_only_item_labels() -> set[str]:
    labels: set[str] = set()
    for role_menu in STAFF_BOT_READ_ONLY_MENU_CONTRACT:
        for item in role_menu.get("items", []):
            label = str(item.get("label") or "").strip().lower()
            if label:
                labels.add(label)
                labels.add(_normalize_staff_button_text(label))
            key = str(item.get("key") or "").strip().lower()
            if key:
                labels.add(key)
            display_label = _staff_menu_item_label(item)
            if display_label:
                labels.add(_normalize_staff_button_text(display_label))
    return labels


def _staff_menu_item_for_text(
    role_menu: dict[str, Any], text: str
) -> dict[str, Any] | None:
    normalized_text = _normalize_staff_button_text(text)
    for item in role_menu.get("items", []):
        label = str(item.get("label") or "").strip().lower()
        key = str(item.get("key") or "").strip().lower()
        display_label = _normalize_staff_button_text(_staff_menu_item_label(item))
        if normalized_text in {label, key, display_label}:
            return item
    return None


def _staff_menu_item_for_command(
    role_menu: dict[str, Any], command: str
) -> dict[str, Any] | None:
    allowed_keys = set(STAFF_COMMAND_DOMAIN_ITEM_KEYS.get(command, ()))
    if not allowed_keys:
        return None
    for item in role_menu.get("items", []):
        if str(item.get("key") or "").strip().lower() in allowed_keys:
            return item
    return None


def _today_start() -> datetime:
    return datetime.combine(date.today(), datetime.min.time())


def _status_counts(rows: list[tuple[Any, Any]]) -> dict[str, int]:
    return {str(status or "unknown"): int(count or 0) for status, count in rows}


def _format_money(amount: Any) -> str:
    value = amount if isinstance(amount, Decimal) else Decimal(str(amount or 0))
    return f"{value.quantize(Decimal('0.01'))} UZS"


def _queue_status_counts(db: Session) -> dict[str, int]:
    rows = (
        db.query(OnlineQueueEntry.status, func.count(OnlineQueueEntry.id))
        .join(DailyQueue, OnlineQueueEntry.queue_id == DailyQueue.id)
        .filter(DailyQueue.day == date.today())
        .group_by(OnlineQueueEntry.status)
        .all()
    )
    return _status_counts(rows)


def _payment_status_rows(db: Session) -> list[tuple[str, int, Decimal]]:
    return [
        (str(status or "unknown"), int(count or 0), amount or Decimal("0"))
        for status, count, amount in (
            db.query(
                Payment.status,
                func.count(Payment.id),
                func.coalesce(func.sum(Payment.amount), 0),
            )
            .filter(Payment.created_at >= _today_start())
            .group_by(Payment.status)
            .all()
        )
    ]


def _payment_invoice_status_rows(db: Session) -> list[tuple[str, int, Decimal]]:
    return [
        (str(status or "unknown"), int(count or 0), amount or Decimal("0"))
        for status, count, amount in (
            db.query(
                PaymentInvoice.status,
                func.count(PaymentInvoice.id),
                func.coalesce(func.sum(PaymentInvoice.total_amount), 0),
            )
            .filter(PaymentInvoice.created_at >= _today_start())
            .group_by(PaymentInvoice.status)
            .all()
        )
    ]


def _lab_status_counts(db: Session) -> dict[str, int]:
    rows = (
        db.query(LabReportInstance.status, func.count(LabReportInstance.id))
        .filter(LabReportInstance.created_at >= _today_start())
        .group_by(LabReportInstance.status)
        .all()
    )
    return _status_counts(rows)


def _lab_delivery_status_counts(db: Session) -> dict[str, int]:
    rows = (
        db.query(
            NotificationDelivery.delivery_status,
            func.count(NotificationDelivery.id),
        )
        .join(NotificationEvent, NotificationEvent.id == NotificationDelivery.event_id)
        .filter(
            NotificationDelivery.created_at >= _today_start(),
            NotificationDelivery.channel == "telegram",
            NotificationEvent.event_type.in_(LAB_RESULT_DELIVERY_EVENT_TYPES),
        )
        .group_by(NotificationDelivery.delivery_status)
        .all()
    )
    return _status_counts(rows)


def _integration_error_counts(db: Session) -> dict[str, int]:
    failed_webhook_calls_today = (
        db.query(func.count(WebhookCall.id))
        .filter(
            WebhookCall.created_at >= _today_start(),
            WebhookCall.status == WebhookCallStatus.FAILED,
        )
        .scalar()
        or 0
    )
    retrying_webhook_calls = (
        db.query(func.count(WebhookCall.id))
        .filter(WebhookCall.status == WebhookCallStatus.RETRYING)
        .scalar()
        or 0
    )
    unprocessed_webhook_events = (
        db.query(func.count(WebhookEvent.id))
        .filter(WebhookEvent.processed.is_(False))
        .scalar()
        or 0
    )
    failed_payment_webhooks_today = (
        db.query(func.count(PaymentWebhook.id))
        .filter(
            PaymentWebhook.created_at >= _today_start(),
            PaymentWebhook.status == "failed",
        )
        .scalar()
        or 0
    )
    return {
        "failed_webhook_calls_today": int(failed_webhook_calls_today),
        "retrying_webhook_calls": int(retrying_webhook_calls),
        "unprocessed_webhook_events": int(unprocessed_webhook_events),
        "failed_payment_webhooks_today": int(failed_payment_webhooks_today),
    }


def _visit_status_counts(db: Session, user: User | None = None) -> dict[str, int]:
    query = db.query(Visit.status, func.count(Visit.id)).filter(
        Visit.visit_date == date.today()
    )
    if _normalize_staff_role(getattr(user, "role", None)) == "doctor":
        doctor = (
            db.query(Doctor)
            .filter(
                Doctor.user_id == getattr(user, "id", None),
                Doctor.active.is_(True),
            )
            .first()
        )
        if not doctor:
            return {}
        query = query.filter(Visit.doctor_id == doctor.id)
    rows = query.group_by(Visit.status).all()
    return _status_counts(rows)


def _staff_queue_overview_message(db: Session) -> str:
    counts = _queue_status_counts(db)
    total = sum(counts.values())
    active = sum(
        count for status, count in counts.items() if status not in QUEUE_TERMINAL_STATUSES
    )
    in_progress = sum(
        counts.get(status, 0) for status in ("called", "in_service", "diagnostics")
    )
    return "\n".join(
        [
            "Queue overview",
            f"Date: {date.today().isoformat()}",
            f"Total entries: {total}",
            f"Active entries: {active}",
            f"Waiting: {counts.get('waiting', 0)}",
            f"Called/in service: {in_progress}",
            "Mode: read-only aggregate snapshot",
        ]
    )


def _staff_next_patient_entry(db: Session) -> OnlineQueueEntry | None:
    return (
        db.query(OnlineQueueEntry)
        .join(DailyQueue, OnlineQueueEntry.queue_id == DailyQueue.id)
        .filter(
            DailyQueue.day == date.today(),
            DailyQueue.active.is_(True),
            OnlineQueueEntry.status.in_(QUEUE_WAITING_STATUSES),
        )
        .order_by(
            OnlineQueueEntry.priority.desc(),
            func.coalesce(
                OnlineQueueEntry.queue_time, OnlineQueueEntry.created_at
            ).asc(),
            OnlineQueueEntry.id.asc(),
        )
        .first()
    )


def _staff_next_patient_message(db: Session) -> str:
    entry = _staff_next_patient_entry(db)
    if not entry:
        return "\n".join(
            [
                "Next patient",
                f"Date: {date.today().isoformat()}",
                "Waiting patients: 0",
                "Mode: read-only queue snapshot",
            ]
        )

    queue_name = _queue_entry_name(entry)
    position = _queue_entry_position(db, entry)
    details = [
        "Next patient",
        f"Date: {date.today().isoformat()}",
        f"Queue: {queue_name}",
        f"Queue number: {entry.number}",
        f"Status: {entry.status}",
    ]
    if position:
        details.append(f"Position: {position}")
    details.append("Mode: read-only queue snapshot")
    return "\n".join(details)


def _staff_today_schedule_message(db: Session, user: User | None = None) -> str:
    counts = _visit_status_counts(db, user)
    normalized_counts = {
        str(status or "unknown").lower(): count for status, count in counts.items()
    }
    total = sum(counts.values())
    in_progress = sum(
        normalized_counts.get(status, 0)
        for status in ("in_progress", "in_visit", "called")
    )
    completed = sum(
        normalized_counts.get(status, 0)
        for status in ("completed", "served", "done")
    )
    cancelled = sum(
        normalized_counts.get(status, 0)
        for status in ("cancelled", "canceled", "no_show")
    )
    open_visits = max(total - in_progress - completed - cancelled, 0)
    return "\n".join(
        [
            "Today's schedule",
            f"Date: {date.today().isoformat()}",
            f"Visits today: {total}",
            f"Open visits: {open_visits}",
            f"In progress: {in_progress}",
            f"Completed/cancelled: {completed + cancelled}",
            "Mode: read-only schedule snapshot",
        ]
    )


def _staff_emr_reminders_message(db: Session, user: User | None = None) -> str:
    counts = _visit_status_counts(db, user)
    normalized_counts = {
        str(status or "unknown").lower(): count for status, count in counts.items()
    }
    total = sum(counts.values())
    closed = sum(
        normalized_counts.get(status, 0) for status in EMR_CLOSED_VISIT_STATUSES
    )
    needs_closure = max(total - closed, 0)
    in_progress = sum(
        normalized_counts.get(status, 0)
        for status in ("in_progress", "in_visit", "called")
    )
    open_visits = max(needs_closure - in_progress, 0)
    return "\n".join(
        [
            "EMR reminders",
            f"Date: {date.today().isoformat()}",
            f"Visits needing EMR closure: {needs_closure}",
            f"Open visits: {open_visits}",
            f"In progress: {in_progress}",
            f"Closed/cancelled: {closed}",
            "Mode: read-only EMR reminder snapshot",
        ]
    )


def _staff_unpaid_invoices_message(db: Session) -> str:
    rows = _payment_invoice_status_rows(db)
    total_count = sum(count for _status, count, _amount in rows)
    unpaid_count = sum(
        count for status, count, _amount in rows if status in UNPAID_INVOICE_STATUSES
    )
    unpaid_total = sum(
        (amount for status, _count, amount in rows if status in UNPAID_INVOICE_STATUSES),
        Decimal("0"),
    )
    return "\n".join(
        [
            "Unpaid invoices",
            f"Date: {date.today().isoformat()}",
            f"Invoices today: {total_count}",
            f"Unpaid invoices: {unpaid_count}",
            f"Unpaid total: {_format_money(unpaid_total)}",
            "Mode: read-only invoice aggregate snapshot",
        ]
    )


def _staff_paid_invoices_message(db: Session) -> str:
    rows = _payment_invoice_status_rows(db)
    total_count = sum(count for _status, count, _amount in rows)
    paid_count = sum(
        count for status, count, _amount in rows if status in PAID_INVOICE_STATUSES
    )
    paid_total = sum(
        (amount for status, _count, amount in rows if status in PAID_INVOICE_STATUSES),
        Decimal("0"),
    )
    return "\n".join(
        [
            "Paid invoices",
            f"Date: {date.today().isoformat()}",
            f"Invoices today: {total_count}",
            f"Paid invoices: {paid_count}",
            f"Paid total: {_format_money(paid_total)}",
            "Mode: read-only invoice aggregate snapshot",
        ]
    )


def _staff_reconciliation_alerts_message(db: Session) -> str:
    result = PaymentReconciliationApiService(db).get_reconciliation_alerts(
        threshold=float(RECONCILIATION_ALERT_THRESHOLD)
    )
    alerts = result.get("alerts") or []
    severity_counts = {
        "error": sum(1 for alert in alerts if alert.get("severity") == "error"),
        "high": int(
            result.get("high_severity_count")
            or sum(1 for alert in alerts if alert.get("severity") == "high")
        ),
        "medium": sum(1 for alert in alerts if alert.get("severity") == "medium"),
    }
    providers = sorted(
        {
            str(alert.get("provider") or "unknown")
            for alert in alerts
            if alert.get("provider")
        }
    )
    provider_summary = ", ".join(providers[:3]) if providers else "none"
    if len(providers) > 3:
        provider_summary = f"{provider_summary} +{len(providers) - 3}"
    return "\n".join(
        [
            "Reconciliation alerts",
            f"Date: {date.today().isoformat()}",
            f"Alerts: {int(result.get('alert_count') or len(alerts))}",
            f"High severity: {severity_counts['high']}",
            f"Medium severity: {severity_counts['medium']}",
            f"Error severity: {severity_counts['error']}",
            f"Providers: {provider_summary}",
            "Mode: read-only reconciliation aggregate snapshot",
        ]
    )


def _staff_payment_status_message(db: Session) -> str:
    rows = _payment_status_rows(db)
    total_count = sum(count for _status, count, _amount in rows)
    paid_total = sum(
        (amount for status, _count, amount in rows if status in PAYMENT_PAID_STATUSES),
        Decimal("0"),
    )
    pending_total = sum(
        (amount for status, _count, amount in rows if status in PAYMENT_PENDING_STATUSES),
        Decimal("0"),
    )
    pending_count = sum(
        count for status, count, _amount in rows if status in PAYMENT_PENDING_STATUSES
    )
    return "\n".join(
        [
            "Payment status",
            f"Date: {date.today().isoformat()}",
            f"Payments today: {total_count}",
            f"Pending payments: {pending_count}",
            f"Paid total: {_format_money(paid_total)}",
            f"Pending total: {_format_money(pending_total)}",
            "Mode: read-only aggregate snapshot",
        ]
    )


def _staff_revenue_summary_message(db: Session) -> str:
    rows = _payment_invoice_status_rows(db)
    invoice_count = sum(count for _status, count, _amount in rows)
    gross_total = sum((amount for _status, _count, amount in rows), Decimal("0"))
    collected_total = sum(
        (amount for status, _count, amount in rows if status in PAID_INVOICE_STATUSES),
        Decimal("0"),
    )
    pending_total = sum(
        (amount for status, _count, amount in rows if status in UNPAID_INVOICE_STATUSES),
        Decimal("0"),
    )
    other_total = max(gross_total - collected_total - pending_total, Decimal("0"))
    return "\n".join(
        [
            "Revenue summary",
            f"Date: {date.today().isoformat()}",
            f"Invoices today: {invoice_count}",
            f"Gross invoiced: {_format_money(gross_total)}",
            f"Collected revenue: {_format_money(collected_total)}",
            f"Pending revenue: {_format_money(pending_total)}",
            f"Other invoice total: {_format_money(other_total)}",
            "Mode: read-only revenue aggregate snapshot",
        ]
    )


def _staff_lab_reports_message(db: Session) -> str:
    counts = _lab_status_counts(db)
    ready = sum(
        counts.get(status, 0)
        for status in {"READY", "FINALIZED", "PRINTED"} | LAB_REPORT_READY_STATUSES
    )
    total = sum(counts.values())
    return "\n".join(
        [
            "Lab report status",
            f"Date: {date.today().isoformat()}",
            f"Reports today: {total}",
            f"Ready reports: {ready}",
            f"Pending reports: {max(total - ready, 0)}",
            "Mode: read-only aggregate snapshot",
        ]
    )


def _staff_pending_lab_reports_message(db: Session) -> str:
    counts = _lab_status_counts(db)
    pending = sum(
        counts.get(status, 0) for status in LAB_REPORT_PENDING_STATUSES
    )
    draft = counts.get("DRAFT", 0)
    in_progress = counts.get("IN_PROGRESS", 0)
    ready_or_done = sum(
        counts.get(status, 0)
        for status in {"READY", "FINALIZED", "PRINTED"} | LAB_REPORT_READY_STATUSES
    )
    total = sum(counts.values())
    return "\n".join(
        [
            "Pending lab reports",
            f"Date: {date.today().isoformat()}",
            f"Reports today: {total}",
            f"Pending reports: {pending}",
            f"Draft reports: {draft}",
            f"In progress: {in_progress}",
            f"Ready/final: {ready_or_done}",
            "Mode: read-only lab aggregate snapshot",
        ]
    )


def _staff_lab_delivery_status_message(db: Session) -> str:
    counts = _lab_delivery_status_counts(db)
    total = sum(counts.values())
    successful = sum(
        counts.get(status, 0) for status in SUCCESSFUL_DELIVERY_STATUSES
    )
    pending = sum(counts.get(status, 0) for status in PENDING_DELIVERY_STATUSES)
    failed = counts.get("failed", 0)
    other = max(total - successful - pending - failed, 0)
    return "\n".join(
        [
            "Lab result delivery status",
            f"Date: {date.today().isoformat()}",
            f"Telegram deliveries today: {total}",
            f"Delivered/seen/read: {successful}",
            f"Pending/dispatched: {pending}",
            f"Failed: {failed}",
            f"Other: {other}",
            "Mode: read-only delivery aggregate snapshot",
        ]
    )


def _staff_integration_errors_message(db: Session) -> str:
    counts = _integration_error_counts(db)
    total = sum(counts.values())
    return "\n".join(
        [
            "Integration errors",
            f"Date: {date.today().isoformat()}",
            f"Total attention items: {total}",
            f"Failed webhook calls today: {counts['failed_webhook_calls_today']}",
            f"Retrying webhook calls: {counts['retrying_webhook_calls']}",
            f"Unprocessed webhook events: {counts['unprocessed_webhook_events']}",
            f"Failed payment webhooks today: {counts['failed_payment_webhooks_today']}",
            "Mode: read-only integration aggregate snapshot",
        ]
    )


def _staff_daily_summary_message(db: Session) -> str:
    queue_counts = _queue_status_counts(db)
    payment_rows = _payment_status_rows(db)
    lab_counts = _lab_status_counts(db)
    visits_today = (
        db.query(func.count(Visit.id))
        .filter(Visit.visit_date == date.today())
        .scalar()
        or 0
    )
    paid_total = sum(
        (
            amount
            for status, _count, amount in payment_rows
            if status in PAYMENT_PAID_STATUSES
        ),
        Decimal("0"),
    )
    ready_reports = sum(
        lab_counts.get(status, 0)
        for status in {"READY", "FINALIZED", "PRINTED"} | LAB_REPORT_READY_STATUSES
    )
    return "\n".join(
        [
            "Daily clinic summary",
            f"Date: {date.today().isoformat()}",
            f"Visits scheduled: {int(visits_today)}",
            f"Queue entries: {sum(queue_counts.values())}",
            f"Paid today: {_format_money(paid_total)}",
            f"Ready lab reports: {ready_reports}",
            "Mode: read-only aggregate snapshot",
        ]
    )


def _staff_readiness_message(db: Session) -> str:
    patient_bot_token = _get_configured_bot_token(db)
    token_status = _get_staff_bot_token_runtime_status(
        db, patient_bot_token=patient_bot_token
    )
    staff_status = _build_staff_bot_status(
        webhook_set=False,
        staff_bot_token_status=token_status,
    )
    readiness = staff_status.get("readiness", [])
    ready_count = sum(1 for item in readiness if item.get("ready"))
    command_contract = staff_status.get("command_registration_contract", {})
    token_contract = staff_status.get("token_contract", {})
    return "\n".join(
        [
            "Staff bot readiness",
            f"Ready gates: {ready_count}/{len(readiness)}",
            f"Dedicated token: {'ready' if token_contract.get('ready') else 'required'}",
            "Read-only menu: enabled",
            (
                "Read-only commands: ready"
                if command_contract.get("registration_enabled")
                else "Read-only commands: blocked"
            ),
            "Live data: limited read-only aggregates",
            "State-changing actions: disabled",
        ]
    )


def _staff_read_only_domain_data_message(
    db: Session, menu_item: dict[str, Any] | None, user: User | None = None
) -> str | None:
    item_key = str((menu_item or {}).get("key") or "").strip()
    if item_key not in STAFF_BOT_READ_ONLY_DOMAIN_DATA_COMMAND_KEYS:
        return None
    if item_key == "staff_readiness":
        return _staff_readiness_message(db)
    if item_key == "queue_overview":
        return _staff_queue_overview_message(db)
    if item_key == "next_patient":
        return _staff_next_patient_message(db)
    if item_key == "today_schedule":
        return _staff_today_schedule_message(db, user)
    if item_key == "emr_reminders":
        return _staff_emr_reminders_message(db, user)
    if item_key == "unpaid_invoices":
        return _staff_unpaid_invoices_message(db)
    if item_key == "paid_invoices":
        return _staff_paid_invoices_message(db)
    if item_key == "reconciliation_alerts":
        return _staff_reconciliation_alerts_message(db)
    if item_key == "payment_status":
        return _staff_payment_status_message(db)
    if item_key == "ready_reports":
        return _staff_lab_reports_message(db)
    if item_key == "pending_reports":
        return _staff_pending_lab_reports_message(db)
    if item_key == "delivery_status":
        return _staff_lab_delivery_status_message(db)
    if item_key == "integration_errors":
        return _staff_integration_errors_message(db)
    if item_key == "revenue_summary":
        return _staff_revenue_summary_message(db)
    if item_key == "daily_summary":
        return _staff_daily_summary_message(db)
    return None


def _staff_state_change_operations_by_command() -> dict[str, dict[str, Any]]:
    operations: dict[str, dict[str, Any]] = {}
    for operation in STAFF_BOT_CONFIRMATION_CONTRACT.get("operations", []):
        for command in operation.get("telegram_commands", []):
            command_key = str(command or "").strip().lower()
            if command_key:
                operations[command_key] = operation
    return operations


def _staff_state_change_operation_for_command(
    command: str,
) -> dict[str, Any] | None:
    return _staff_state_change_operations_by_command().get(command)


def _linked_staff_for_chat(
    db: Session, chat_id: int
) -> tuple[TelegramUser | None, User | None, dict[str, Any] | None]:
    telegram_user = crud_telegram.get_telegram_user_by_chat_id(db, chat_id)
    if not telegram_user or not telegram_user.user_id:
        return telegram_user, None, None

    user = db.query(User).filter(User.id == telegram_user.user_id).first()
    if not user or not getattr(user, "is_active", True):
        return telegram_user, user, None

    return telegram_user, user, _staff_menu_for_role(getattr(user, "role", None))

