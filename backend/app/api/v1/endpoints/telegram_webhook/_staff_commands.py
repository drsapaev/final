"""
Split from telegram_webhook.py (5647 LOC → modular).
"""
from __future__ import annotations

import html
import logging
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from app.api.v1.endpoints.admin_telegram import (
    _normalize_staff_role,
    validate_staff_link_start_token,
)
from app.crud import telegram_config as crud_telegram
from app.models.lab import LabReportInstance
from app.models.online_queue import DailyQueue, OnlineQueueEntry
from app.models.patient import Patient
from app.models.payment import Payment, PaymentVisit
from app.models.telegram_config import TelegramMessage, TelegramUser
from app.models.visit import Visit

logger = logging.getLogger(__name__)
from app.api.v1.endpoints.telegram_webhook._helpers import *  # noqa: F401, F403

from app.api.v1.endpoints.telegram_webhook._helpers import (
    _extract_staff_link_start_payload,
    _extract_ticket_qr_start_payload,
    _localized_main_menu,
    _localized_notification_consent_menu,
    _localized_settings_menu,
    _localized_text,
    _normalize_patient_language,
    _patient_payment_entry_url,
    _telegram_chat_language,
    _telegram_chat_menu,
    _telegram_chat_text,
    _telegram_onboarding_entry_markup,
    _telegram_settings_message,
)  # noqa: F401
from app.api.v1.endpoints.telegram_webhook._patient_commands import (  # noqa: F401
    _create_staff_action_confirmation_request,
    _is_patient_settings_context_template,
    _latest_patient_bot_template_key,
    _linked_staff_for_chat,
    _normalize_staff_button_text,
    _record_staff_action_denied_audit,
    _record_staff_command_audit,
    _record_staff_link_audit,
    _send_patient_bot_reply,
    _staff_menu_for_role,
    _staff_menu_item_for_command,
    _staff_menu_item_for_text,
    _staff_menu_keyboard,
    _staff_menu_message,
    _staff_read_only_commands,
    _staff_read_only_domain_data_message,
    _staff_read_only_item_labels,
    _staff_state_change_operation_for_command,
    _upsert_staff_link_telegram_user,
    _upsert_ticket_qr_telegram_user,
)


from app.api.v1.endpoints.telegram_webhook._patient_commands import (  # noqa: F401
    _create_staff_action_confirmation_request,
    _is_patient_settings_context_template,
    _latest_patient_bot_template_key,
    _linked_staff_for_chat,
    _normalize_staff_button_text,
    _record_staff_action_denied_audit,
    _record_staff_command_audit,
    _record_staff_link_audit,
    _send_patient_bot_reply,
    _staff_menu_for_role,
    _staff_menu_item_for_command,
    _staff_menu_item_for_text,
    _staff_menu_keyboard,
    _staff_menu_message,
    _staff_read_only_commands,
    _staff_read_only_domain_data_message,
    _staff_read_only_item_labels,
    _staff_state_change_operation_for_command,
    _upsert_staff_link_telegram_user,
    _upsert_ticket_qr_telegram_user,
)

async def _handle_staff_read_only_menu(
    update: dict[str, Any], db: Session, bot_service
) -> bool:
    message = _message_from_update(update)
    if not message:
        return False

    chat_id = _message_chat_id(message)
    if chat_id is None:
        return False

    update_id = update.get("update_id")
    request_id = f"telegram-update:{update_id}" if update_id is not None else None
    text = _message_text(message)
    command = text.split(maxsplit=1)[0].split("@", 1)[0].lower() if text else ""
    normalized_text = _normalize_staff_button_text(text)
    read_only_commands = _staff_read_only_commands()
    state_change_operation = _staff_state_change_operation_for_command(command)
    staff_menu_requested = (
        command in read_only_commands
        or command == "/start"
        or command == "/menu"
        or state_change_operation is not None
        or normalized_text in _staff_read_only_item_labels()
    )
    if not staff_menu_requested:
        return False

    _telegram_user, user, role_menu = _linked_staff_for_chat(db, chat_id)
    if not user:
        if command == "/staff":
            _record_staff_command_audit(
                db,
                chat_id=chat_id,
                request_id=request_id,
                actor_user_id=None,
                telegram_user_id=getattr(_telegram_user, "id", None),
                role="unlinked",
                command_key=command,
                result="denied",
                reason="staff_not_linked",
            )
            db.commit()
            await bot_service._send_message(
                chat_id,
                TELEGRAM_STAFF_MENU_UNLINKED_MESSAGE,
                TELEGRAM_STAFF_LINK_REPLY_MARKUP,
            )
            return True
        return False

    if not role_menu:
        if user:
            _record_staff_command_audit(
                db,
                chat_id=chat_id,
                request_id=request_id,
                actor_user_id=int(user.id),
                telegram_user_id=getattr(_telegram_user, "id", None),
                role=_normalize_staff_role(getattr(user, "role", None)),
                command_key=command if command.startswith("/") else "staff_menu_item",
                result="denied",
                reason="role_not_allowed",
            )
            db.commit()
        await bot_service._send_message(
            chat_id,
            TELEGRAM_STAFF_MENU_FORBIDDEN_MESSAGE,
            TELEGRAM_STAFF_LINK_REPLY_MARKUP,
        )
        return True

    menu = _staff_menu_keyboard(role_menu)
    role = _normalize_staff_role(getattr(user, "role", None))
    if state_change_operation is not None:
        operation_key = str(state_change_operation.get("key") or "staff_action")
        allowed_roles = {
            _normalize_staff_role(role_key)
            for role_key in state_change_operation.get("roles", [])
        }
        if role in allowed_roles:
            try:
                confirmation_message = _create_staff_action_confirmation_request(
                    db,
                    chat_id=chat_id,
                    request_id=request_id,
                    actor_user_id=int(user.id),
                    telegram_user_id=getattr(_telegram_user, "id", None),
                    role=role,
                    operation=state_change_operation,
                    command_key=command,
                )
                db.commit()
            except Exception as exc:
                db.rollback()
                logger.warning(
                    "Staff action confirmation request failed operation_key=%s error_type=%s",
                    operation_key,
                    type(exc).__name__,
                )
                _record_staff_action_denied_audit(
                    db,
                    chat_id=chat_id,
                    request_id=request_id,
                    actor_user_id=int(user.id),
                    telegram_user_id=getattr(_telegram_user, "id", None),
                    role=role,
                    operation_key=operation_key,
                    command_key=command,
                    reason="confirmation_request_failed",
                )
                db.commit()
                await bot_service._send_message(
                    chat_id,
                    TELEGRAM_STAFF_ACTION_DENIED_MESSAGE,
                    menu,
                )
                return True

            await bot_service._send_message(chat_id, confirmation_message, menu)
            return True

        _record_staff_action_denied_audit(
            db,
            chat_id=chat_id,
            request_id=request_id,
            actor_user_id=int(user.id),
            telegram_user_id=getattr(_telegram_user, "id", None),
            role=role,
            operation_key=operation_key,
            command_key=command,
            reason="role_not_allowed",
        )
        db.commit()
        await bot_service._send_message(
            chat_id,
            TELEGRAM_STAFF_MENU_FORBIDDEN_MESSAGE,
            menu,
        )
        return True

    if command in {"/start", "/staff", "/help", "/menu"}:
        _record_staff_command_audit(
            db,
            chat_id=chat_id,
            request_id=request_id,
            actor_user_id=int(user.id),
            telegram_user_id=getattr(_telegram_user, "id", None),
            role=_normalize_staff_role(getattr(user, "role", None)),
            command_key=command,
            menu_item_key="staff_menu",
        )
        db.commit()
        await bot_service._send_message(
            chat_id,
            _staff_menu_message(user, role_menu),
            menu,
        )
        return True

    menu_item = _staff_menu_item_for_text(role_menu, text)
    if not menu_item and command in read_only_commands:
        menu_item = _staff_menu_item_for_command(role_menu, command)

    command_key = command if command in read_only_commands else "staff_menu_item"
    if command in read_only_commands and not menu_item:
        _record_staff_command_audit(
            db,
            chat_id=chat_id,
            request_id=request_id,
            actor_user_id=int(user.id),
            telegram_user_id=getattr(_telegram_user, "id", None),
            role=_normalize_staff_role(getattr(user, "role", None)),
            command_key=command_key,
            result="denied",
            reason="role_not_allowed",
        )
        db.commit()
        await bot_service._send_message(
            chat_id,
            TELEGRAM_STAFF_MENU_FORBIDDEN_MESSAGE,
            menu,
        )
        return True

    domain_data_message = _staff_read_only_domain_data_message(db, menu_item, user)
    _record_staff_command_audit(
        db,
        chat_id=chat_id,
        request_id=request_id,
        actor_user_id=int(user.id),
        telegram_user_id=getattr(_telegram_user, "id", None),
        role=_normalize_staff_role(getattr(user, "role", None)),
        command_key=command_key,
        menu_item_key=str(menu_item.get("key")) if menu_item else None,
    )
    db.commit()
    await bot_service._send_message(
        chat_id,
        domain_data_message or TELEGRAM_STAFF_MENU_PLACEHOLDER_MESSAGE,
        menu,
    )
    return True


async def _handle_ticket_qr_start(update: dict[str, Any], db: Session, bot_service) -> bool:
    extracted = _extract_ticket_qr_start_payload(update)
    if not extracted:
        return False

    token, message = extracted
    chat_id = (message.get("chat") or {}).get("id")
    visit = consume_telegram_ticket_start_token(db, token)
    if visit:
        if chat_id is None:
            db.rollback()
            return True

        try:
            existing_telegram_user = crud_telegram.get_telegram_user_by_chat_id(
                db, int(chat_id)
            )
            notifications_already_enabled = bool(
                getattr(existing_telegram_user, "notifications_enabled", False)
            )
            _upsert_ticket_qr_telegram_user(db, message, visit.patient_id)
            db.commit()
        except Exception as exc:
            db.rollback()
            logger.warning(
                "Telegram ticket QR user link failed error_type=%s",
                type(exc).__name__,
            )
            language = _normalize_patient_language(
                (message.get("from") or {}).get("language_code")
            )
            await bot_service._send_message(
                int(chat_id),
                _localized_text("ticket_qr_link_failed", language),
                _localized_main_menu(language),
            )
            return True

        language = _telegram_chat_language(db, int(chat_id))
        reply_text = _telegram_chat_text(db, int(chat_id), "ticket_qr_linked")
        reply_markup = _telegram_chat_menu(db, int(chat_id))
        if not notifications_already_enabled:
            reply_text = (
                f"{reply_text}\n\n{_localized_text('notification_consent', language)}"
            )
            reply_markup = _localized_notification_consent_menu(language)
        await bot_service._send_message(int(chat_id), reply_text, reply_markup)
    elif chat_id is not None:
        language = _telegram_chat_language(db, int(chat_id))
        await bot_service._send_message(
            int(chat_id),
            _localized_text("ticket_qr_expired", language),
            _localized_main_menu(language),
        )

    return True


async def _handle_staff_link_start(
    update: dict[str, Any], db: Session, bot_service
) -> bool:
    extracted = _extract_staff_link_start_payload(update)
    if not extracted:
        return False

    token, message = extracted
    chat_id = _message_chat_id(message)
    if chat_id is None:
        return True

    update_id = update.get("update_id")
    request_id = f"telegram-update:{update_id}" if update_id is not None else None

    try:
        validation = validate_staff_link_start_token(
            db, token, telegram_chat_id=chat_id
        )
        if not validation.get("valid"):
            logger.info(
                "Telegram staff link token rejected reason=%s",
                validation.get("reason"),
            )
            _record_staff_link_audit(
                db,
                action="staff_link_token_rejected",
                chat_id=chat_id,
                request_id=request_id,
                reason=str(validation.get("reason") or "invalid"),
            )
            db.commit()
            await bot_service._send_message(
                chat_id,
                TELEGRAM_STAFF_LINK_REJECTED_MESSAGE,
                TELEGRAM_STAFF_LINK_REPLY_MARKUP,
            )
            return True

        linked_user = _upsert_staff_link_telegram_user(
            db,
            message,
            linked_user_id=int(validation["user_id"]),
        )
        if not linked_user:
            logger.warning("Telegram staff link failed because chat row was missing")
            await bot_service._send_message(
                chat_id,
                TELEGRAM_STAFF_LINK_FAILED_MESSAGE,
                TELEGRAM_STAFF_LINK_REPLY_MARKUP,
            )
            return True

        role = validation.get("role") or "staff"
        _record_staff_link_audit(
            db,
            action="staff_link_created",
            chat_id=chat_id,
            request_id=request_id,
            actor_user_id=int(validation["user_id"]),
            telegram_user_id=getattr(linked_user, "id", None),
            role=str(role),
        )
        db.commit()
        logger.info("Telegram staff link created role=%s", role)
        role_menu = _staff_menu_for_role(role)
        reply_markup = (
            _staff_menu_keyboard(role_menu)
            if role_menu
            else TELEGRAM_STAFF_LINK_REPLY_MARKUP
        )
        await bot_service._send_message(
            chat_id,
            f"{TELEGRAM_STAFF_LINKED_MESSAGE}\nРоль: {role}",
            reply_markup,
        )
        return True
    except Exception as exc:
        db.rollback()
        logger.warning(
            "Telegram staff link handler failed error_type=%s",
            type(exc).__name__,
        )
        await bot_service._send_message(
            chat_id,
            TELEGRAM_STAFF_LINK_FAILED_MESSAGE,
            TELEGRAM_STAFF_LINK_REPLY_MARKUP,
        )
        return True

def _message_from_update(update: dict[str, Any]) -> dict[str, Any]:
    return update.get("message") or {}


def _message_chat_id(message: dict[str, Any]) -> int | None:
    chat_id = (message.get("chat") or {}).get("id")
    return int(chat_id) if chat_id is not None else None


def _message_text(message: dict[str, Any]) -> str:
    return str(message.get("text") or "").strip()


def _find_patient_by_phone(db: Session, phone: str) -> Patient | None:
    normalized_phone = normalize_phone_uz(phone)
    if not normalized_phone:
        return None

    patient_info = crud_telegram.find_patient_by_phone(db, normalized_phone)
    patient_id = patient_info.get("id") if patient_info else None
    if not patient_id:
        return None

    return db.query(Patient).filter(Patient.id == int(patient_id)).first()


def _patient_display_name(patient: Patient | None) -> str:
    if not patient:
        return "пациент"
    return patient.short_name()


def _recent_visit_summary(
    db: Session, patient_id: int, language_code: str = TELEGRAM_LANGUAGE_RU
) -> str:
    visit = (
        db.query(Visit)
        .filter(Visit.patient_id == patient_id)
        .order_by(Visit.created_at.desc(), Visit.id.desc())
        .first()
    )
    if not visit:
        return _localized_text("recent_visit_none", language_code)

    visit_date = (
        visit.visit_date.isoformat()
        if visit.visit_date
        else _localized_text("recent_visit_unknown_date", language_code)
    )
    return _localized_text("recent_visit_summary", language_code).format(
        visit_id=visit.id,
        visit_date=visit_date,
        status=visit.status,
    )


def _patient_recent_visits(
    db: Session, patient_id: int, limit: int = 3
) -> list[Visit]:
    return (
        db.query(Visit)
        .filter(Visit.patient_id == patient_id)
        .order_by(Visit.visit_date.desc(), Visit.created_at.desc(), Visit.id.desc())
        .limit(limit)
        .all()
    )


def _html_text(value: Any) -> str:
    return html.escape(str(value or ""), quote=False)


def _money_decimal(value: Any) -> Decimal:
    if value is None:
        return Decimal("0")
    try:
        return Decimal(str(value))
    except Exception:
        return Decimal("0")


def _format_money(value: Decimal) -> str:
    normalized = value.quantize(Decimal("0.01"))
    if normalized == normalized.to_integral_value():
        return f"{int(normalized):,}".replace(",", " ")
    return f"{normalized:,.2f}".replace(",", " ")


def _telegram_user_for_chat(db: Session, chat_id: int) -> TelegramUser | None:
    return crud_telegram.get_telegram_user_by_chat_id(db, chat_id)


def _patient_for_telegram_chat(
    db: Session, chat_id: int
) -> tuple[TelegramUser | None, Patient | None]:
    telegram_user = _telegram_user_for_chat(db, chat_id)
    if not telegram_user or not telegram_user.patient_id:
        return telegram_user, None
    patient = db.query(Patient).filter(Patient.id == telegram_user.patient_id).first()
    return telegram_user, patient


def _patient_today_queue_entries(db: Session, patient_id: int) -> list[OnlineQueueEntry]:
    return (
        db.query(OnlineQueueEntry)
        .join(DailyQueue, OnlineQueueEntry.queue_id == DailyQueue.id)
        .filter(
            OnlineQueueEntry.patient_id == patient_id,
            DailyQueue.day == date.today(),
            ~OnlineQueueEntry.status.in_(QUEUE_TERMINAL_STATUSES),
        )
        .order_by(OnlineQueueEntry.queue_time.asc(), OnlineQueueEntry.id.asc())
        .all()
    )


def _queue_entry_position(db: Session, entry: OnlineQueueEntry) -> int | None:
    if entry.status not in QUEUE_WAITING_STATUSES:
        return None

    waiting_entries = (
        db.query(OnlineQueueEntry)
        .filter(
            OnlineQueueEntry.queue_id == entry.queue_id,
            OnlineQueueEntry.status.in_(QUEUE_WAITING_STATUSES),
        )
        .order_by(
            OnlineQueueEntry.priority.desc(),
            OnlineQueueEntry.queue_time.asc(),
            OnlineQueueEntry.id.asc(),
        )
        .all()
    )
    for position, waiting_entry in enumerate(waiting_entries, start=1):
        if waiting_entry.id == entry.id:
            return position
    return None


def _queue_entry_name(
    entry: OnlineQueueEntry, language_code: str = TELEGRAM_LANGUAGE_RU
) -> str:
    queue = getattr(entry, "queue", None)
    queue_tag = getattr(queue, "queue_tag", None)
    if queue_tag:
        language = _normalize_patient_language(language_code)
        labels = QUEUE_TAG_LABELS_BY_LANGUAGE.get(language, QUEUE_TAG_LABELS)
        return labels.get(queue_tag) or QUEUE_TAG_LABELS.get(queue_tag, queue_tag)

    services = entry.services or []
    if services:
        first_service = services[0] or {}
        return str(
            first_service.get("name")
            or first_service.get("title")
            or _localized_text("queue_default_name", language_code)
        )
    return _localized_text("queue_default_name", language_code)


def _queue_status_label(status: str, language_code: str = TELEGRAM_LANGUAGE_RU) -> str:
    language = _normalize_patient_language(language_code)
    labels = QUEUE_STATUS_LABELS_BY_LANGUAGE.get(language, QUEUE_STATUS_LABELS)
    return labels.get(status) or QUEUE_STATUS_LABELS.get(status, status)


def _queue_entry_cabinet(
    entry: OnlineQueueEntry, language_code: str = TELEGRAM_LANGUAGE_RU
) -> str | None:
    queue = getattr(entry, "queue", None)
    cabinet_number = getattr(queue, "cabinet_number", None)
    if not cabinet_number:
        return None
    return _localized_text("queue_cabinet", language_code).format(
        cabinet=_html_text(cabinet_number)
    )


def _clinic_queue_message(db: Session, chat_id: int) -> str:
    telegram_user, patient = _patient_for_telegram_chat(db, chat_id)
    if not telegram_user or not telegram_user.patient_id:
        return _telegram_chat_text(db, chat_id, "unlinked_protected_action")

    language = _telegram_chat_language(db, chat_id)
    patient_name = _html_text(_patient_display_name(patient))
    entries = _patient_today_queue_entries(db, telegram_user.patient_id)
    open_hint = _localized_text("queue_open_hint", language)
    if not entries:
        queue_empty = _localized_text("queue_empty", language).format(
            patient=patient_name,
            visit_summary=_html_text(
                _recent_visit_summary(db, telegram_user.patient_id, language)
            ),
        )
        return f"{queue_empty}\n\n{open_hint}"

    lines = [
        _localized_text("queue_patient", language).format(patient=patient_name),
        _localized_text("queue_title", language),
    ]
    for entry in entries[:5]:
        status_label = _queue_status_label(entry.status, language)
        position = _queue_entry_position(db, entry)
        cabinet = _queue_entry_cabinet(entry, language)
        details = [
            f"№{entry.number}",
            _html_text(_queue_entry_name(entry, language)),
            _localized_text("queue_status", language).format(
                status=_html_text(status_label)
            ),
        ]
        if position:
            details.append(
                _localized_text("queue_position", language).format(position=position)
            )
        if cabinet:
            details.append(cabinet)
        lines.append(" • ".join(details))

    if len(entries) > 5:
        lines.append(
            _localized_text("queue_more", language).format(count=len(entries) - 5)
        )
    lines.extend(["", open_hint])
    return "\n".join(lines)


def _clinic_visits_message(db: Session, chat_id: int) -> str:
    telegram_user, patient = _patient_for_telegram_chat(db, chat_id)
    if not telegram_user or not telegram_user.patient_id:
        return _telegram_chat_text(db, chat_id, "unlinked_protected_action")

    language = _telegram_chat_language(db, chat_id)
    patient_name = _html_text(_patient_display_name(patient))
    visits = _patient_recent_visits(db, telegram_user.patient_id)
    open_hint = _localized_text("visits_open_hint", language)
    if not visits:
        visits_empty = _localized_text("visits_empty", language).format(
            patient=patient_name
        )
        return f"{visits_empty}\n\n{open_hint}"

    lines = [
        _localized_text("visits_patient", language).format(patient=patient_name),
        _localized_text("visits_title", language),
    ]
    for index, visit in enumerate(visits, start=1):
        visit_date = (
            visit.visit_date.isoformat()
            if visit.visit_date
            else _localized_text("recent_visit_unknown_date", language)
        )
        lines.append(
            _localized_text("visits_line", language).format(
                index=index,
                visit_id=visit.id,
                visit_date=_html_text(visit_date),
                status=_html_text(visit.status),
            )
        )
    lines.extend([_localized_text("visits_privacy_note", language), "", open_hint])
    return "\n".join(lines)


def _visit_services_total(visit: Visit) -> Decimal:
    total = Decimal("0")
    for service in getattr(visit, "services", []) or []:
        total += _money_decimal(getattr(service, "price", None)) * _money_decimal(
            getattr(service, "qty", 1) or 1
        )
    return total


def _patient_relevant_visits(
    db: Session, patient_id: int, entries: list[OnlineQueueEntry]
) -> list[Visit]:
    visit_ids = sorted({int(entry.visit_id) for entry in entries if entry.visit_id})
    if visit_ids:
        return (
            db.query(Visit)
            .filter(Visit.patient_id == patient_id, Visit.id.in_(visit_ids))
            .order_by(Visit.created_at.desc(), Visit.id.desc())
            .all()
        )

    visits = (
        db.query(Visit)
        .filter(Visit.patient_id == patient_id, Visit.visit_date == date.today())
        .order_by(Visit.created_at.desc(), Visit.id.desc())
        .limit(3)
        .all()
    )
    if visits:
        return visits

    return (
        db.query(Visit)
        .filter(Visit.patient_id == patient_id, Visit.status == "open")
        .order_by(Visit.created_at.desc(), Visit.id.desc())
        .limit(3)
        .all()
    )


def _payment_total_for_visits(
    db: Session, visit_ids: list[int], statuses: set[str]
) -> Decimal:
    if not visit_ids:
        return Decimal("0")

    total = Decimal("0")
    status_values = tuple(statuses)
    junction_visit_ids: set[int] = set()
    junction_rows = (
        db.query(PaymentVisit.visit_id, PaymentVisit.amount)
        .join(Payment, Payment.id == PaymentVisit.payment_id)
        .filter(
            PaymentVisit.visit_id.in_(visit_ids),
            Payment.status.in_(status_values),
        )
        .all()
    )
    for visit_id, amount in junction_rows:
        junction_visit_ids.add(int(visit_id))
        total += _money_decimal(amount)

    direct_payments = (
        db.query(Payment)
        .filter(Payment.visit_id.in_(visit_ids), Payment.status.in_(status_values))
        .all()
    )
    for payment in direct_payments:
        if int(payment.visit_id) in junction_visit_ids:
            continue
        total += _money_decimal(payment.amount)

    return total


def _billing_totals(
    db: Session, patient_id: int
) -> tuple[list[OnlineQueueEntry], list[Visit], Decimal, Decimal, Decimal, Decimal]:
    entries = _patient_today_queue_entries(db, patient_id)
    visits = _patient_relevant_visits(db, patient_id, entries)
    visits_by_id = {visit.id: visit for visit in visits}
    entry_total_by_visit: dict[int, Decimal] = {}
    unlinked_entry_total = Decimal("0")

    for entry in entries:
        entry_total = _money_decimal(entry.total_amount)
        if entry.visit_id:
            current = entry_total_by_visit.get(int(entry.visit_id), Decimal("0"))
            entry_total_by_visit[int(entry.visit_id)] = max(current, entry_total)
        else:
            unlinked_entry_total += entry_total

    expected_total = unlinked_entry_total
    for visit in visits:
        queue_total = entry_total_by_visit.get(visit.id, Decimal("0"))
        expected_total += queue_total if queue_total > 0 else _visit_services_total(visit)

    visit_ids = sorted(visits_by_id)
    paid_total = _payment_total_for_visits(db, visit_ids, PAYMENT_PAID_STATUSES)
    pending_total = _payment_total_for_visits(db, visit_ids, PAYMENT_PENDING_STATUSES)
    debt_total = max(expected_total - paid_total, Decimal("0"))
    return entries, visits, expected_total, paid_total, pending_total, debt_total


def _clinic_payments_message(db: Session, chat_id: int) -> str:
    telegram_user, patient = _patient_for_telegram_chat(db, chat_id)
    if not telegram_user or not telegram_user.patient_id:
        return _telegram_chat_text(db, chat_id, "unlinked_protected_action")

    language = _telegram_chat_language(db, chat_id)
    patient_name = _html_text(_patient_display_name(patient))
    entries, visits, expected_total, paid_total, pending_total, debt_total = _billing_totals(
        db, telegram_user.patient_id
    )
    if not entries and not visits and expected_total <= 0 and paid_total <= 0:
        return _localized_text("payments_empty", language).format(patient=patient_name)

    lines = [
        _localized_text("payments_patient", language).format(patient=patient_name),
        _localized_text("payments_title", language),
        _localized_text("payments_billed", language).format(
            amount=_format_money(expected_total)
        ),
        _localized_text("payments_paid", language).format(
            amount=_format_money(paid_total)
        ),
        _localized_text("payments_debt", language).format(
            amount=_format_money(debt_total)
        ),
    ]
    if pending_total > 0:
        lines.append(
            _localized_text("payments_pending", language).format(
                amount=_format_money(pending_total)
            )
        )
    if visits:
        lines.append(
            _localized_text("payments_visits", language).format(count=len(visits))
        )
    if _patient_payment_entry_url():
        lines.append(_localized_text("payments_protected_entry", language))
    else:
        lines.append(_localized_text("payments_online_unavailable", language))
    return "\n".join(lines)


def _latest_ready_lab_report_instances(
    db: Session, patient_id: int, limit: int = MAX_TELEGRAM_LAB_REPORTS
) -> list[LabReportInstance]:
    return (
        db.query(LabReportInstance)
        .filter(
            LabReportInstance.patient_id == patient_id,
            LabReportInstance.status.in_(LAB_REPORT_READY_STATUSES),
        )
        .order_by(LabReportInstance.created_at.desc(), LabReportInstance.id.desc())
        .limit(limit)
        .all()
    )


def _lab_report_document_caption(
    instance: LabReportInstance,
    report_date: datetime,
    language_code: str = TELEGRAM_LANGUAGE_RU,
) -> str:
    caption = _localized_text("lab_result_document_caption", language_code).format(
        template_name=_html_text(instance.template.name),
        report_id=instance.id,
        report_date=report_date.strftime("%d.%m.%Y"),
    )
    if len(caption) > 1000:
        return f"{caption[:997]}..."
    return caption


def _build_lab_report_pdf(db: Session, instance: LabReportInstance) -> tuple[str, bytes, str]:
    service = LabReportingService(db)
    materialized_sections = service.materialize_instance(instance)
    critical_findings = service.summarize_critical_findings(materialized_sections)
    report_date = instance.finalized_at or instance.created_at or datetime.now(UTC)
    pdf_bytes = lab_report_pdf_service.render_report(
        {
            "template_name": instance.template.name,
            "layout_preset": instance.template_version.layout_preset,
            "page_settings": instance.template_version.page_settings or {},
            "branding": instance.branding_snapshot or {},
            "patient": instance.patient_snapshot or {},
            "signers": instance.signer_snapshot or {},
            "sections": materialized_sections,
            "critical_findings": critical_findings,
            "footer_notes": instance.template_version.footer_notes,
            "report_date": report_date.strftime("%d.%m.%Y"),
        }
    )
    filename = f"kosmed-lab-report-{instance.id}.pdf"
    caption = _lab_report_document_caption(
        instance, report_date, TELEGRAM_LANGUAGE_RU
    )
    return filename, pdf_bytes, caption


def _log_lab_report_document_send(
    db: Session,
    chat_id: int,
    instance_id: int,
    caption: str,
    status_value: str,
    message_id: int | None = None,
    error_message: str | None = None,
) -> None:
    try:
        db.add(
            TelegramMessage(
                chat_id=chat_id,
                message_id=message_id,
                message_type="lab_result_pdf",
                template_key="telegram_lab_result_pdf",
                message_text=caption,
                status=status_value,
                error_message=error_message,
                related_entity_type="lab_report_instance",
                related_entity_id=instance_id,
                sent_at=datetime.now(UTC) if status_value == "sent" else None,
            )
        )
        db.commit()
    except Exception as exc:
        db.rollback()
        logger.warning(
            "Telegram lab report document log failed error_type=%s",
            type(exc).__name__,
        )


async def _send_clinic_lab_results(db: Session, bot_service, chat_id: int) -> None:
    telegram_user, _patient = _patient_for_telegram_chat(db, chat_id)
    language = _telegram_chat_language(db, chat_id)
    if not telegram_user or not telegram_user.patient_id:
        await _send_patient_bot_reply(
            db,
            bot_service,
            chat_id,
            _telegram_chat_text(db, chat_id, "unlinked_protected_action"),
            _telegram_onboarding_entry_markup(db, chat_id) or _telegram_chat_menu(db, chat_id),
            "telegram_patient_results_needs_link",
        )
        return

    instances = _latest_ready_lab_report_instances(db, telegram_user.patient_id)
    if not instances:
        await _send_patient_bot_reply(
            db,
            bot_service,
            chat_id,
            _localized_text("lab_results_empty", language),
            _telegram_chat_menu(db, chat_id),
            "telegram_patient_lab_results_empty",
        )
        return

    await _send_patient_bot_reply(
        db,
        bot_service,
        chat_id,
        _localized_text("lab_results_found", language).format(count=len(instances)),
        _telegram_chat_menu(db, chat_id),
        "telegram_patient_lab_results_found",
    )
    sent_count = 0
    for instance in instances:
        try:
            filename, pdf_bytes, caption = _build_lab_report_pdf(db, instance)
            if language == TELEGRAM_LANGUAGE_UZ:
                report_date = (
                    instance.finalized_at or instance.created_at or datetime.now(UTC)
                )
                caption = _lab_report_document_caption(instance, report_date, language)
            send_document = getattr(bot_service, "_send_document", None)
            if callable(send_document):
                ok, message_id, error_message = await send_document(
                    chat_id,
                    filename,
                    pdf_bytes,
                    caption,
                )
            else:
                logger.error("Telegram bot service does not support document send")
                ok, message_id, error_message = False, None, "send_document_not_supported"
            _log_lab_report_document_send(
                db,
                chat_id,
                instance.id,
                caption,
                "sent" if ok else "failed",
                message_id=message_id,
                error_message=error_message,
            )
            if ok:
                sent_count += 1
        except Exception as exc:
            logger.warning(
                "Telegram lab report PDF send failed instance_id=%s error_type=%s",
                instance.id,
                type(exc).__name__,
            )
            _log_lab_report_document_send(
                db,
                chat_id,
                instance.id,
                _localized_text(
                    "lab_result_document_failed_caption", language
                ).format(report_id=instance.id),
                "failed",
                error_message=type(exc).__name__,
            )

    if sent_count == 0:
        await _send_patient_bot_reply(
            db,
            bot_service,
            chat_id,
            _localized_text("lab_results_send_failed", language),
            _telegram_chat_menu(db, chat_id),
            "telegram_patient_lab_results_send_failed",
        )


def _clinic_status_message(db: Session, chat_id: int) -> str:
    telegram_user, patient = _patient_for_telegram_chat(db, chat_id)
    if not telegram_user or not telegram_user.patient_id:
        return _telegram_chat_text(db, chat_id, "unlinked_protected_action")

    language = _telegram_chat_language(db, chat_id)
    return _localized_text("profile_linked", language).format(
        patient=_html_text(_patient_display_name(patient)),
        visit_summary=_html_text(
            _recent_visit_summary(db, telegram_user.patient_id, language)
        ),
    )


def _clinic_results_message(db: Session, chat_id: int) -> str:
    telegram_user = crud_telegram.get_telegram_user_by_chat_id(db, chat_id)
    if not telegram_user or not telegram_user.patient_id:
        return _telegram_chat_text(db, chat_id, "unlinked_protected_action")

    return _telegram_chat_text(db, chat_id, "results_hint")


async def _send_language_choice(db: Session, bot_service, chat_id: int) -> None:
    await _send_patient_bot_reply(
        db,
        bot_service,
        chat_id,
        _localized_text("language_prompt", TELEGRAM_LANGUAGE_RU),
        TELEGRAM_LANGUAGE_MENU,
        "telegram_patient_language_prompt",
    )


async def _send_clinic_welcome(
    db: Session,
    bot_service,
    chat_id: int,
    language_code: str = TELEGRAM_LANGUAGE_RU,
) -> None:
    await _send_patient_bot_reply(
        db,
        bot_service,
        chat_id,
        _localized_text("welcome", language_code),
        _localized_main_menu(language_code),
        "telegram_patient_welcome",
    )


async def _send_notification_consent(
    db: Session,
    bot_service,
    chat_id: int,
    language_code: str = TELEGRAM_LANGUAGE_RU,
) -> None:
    await _send_patient_bot_reply(
        db,
        bot_service,
        chat_id,
        _localized_text("notification_consent", language_code),
        _localized_notification_consent_menu(language_code),
        "telegram_patient_notification_consent",
    )


def _patient_contact_linked_text(
    language_code: str,
    patient_label: str,
    patient_name: str,
    include_notification_consent: bool,
) -> str:
    text = (
        f"{_localized_text('contact_linked', language_code)}\n"
        f"{patient_label}: {patient_name}"
    )
    if include_notification_consent:
        return f"{text}\n\n{_localized_text('notification_consent', language_code)}"
    return text


async def _set_notification_consent(
    db: Session, bot_service, chat_id: int, enabled: bool
) -> None:
    telegram_user = crud_telegram.get_telegram_user_by_chat_id(db, chat_id)
    language = _normalize_patient_language(getattr(telegram_user, "language_code", None))
    previous_template_key = _latest_patient_bot_template_key(db, chat_id)
    if telegram_user:
        telegram_user.notifications_enabled = enabled
        telegram_user.appointment_reminders = enabled
        telegram_user.lab_notifications = enabled
        telegram_user.last_activity = datetime.now(UTC)
        db.commit()

    result_key = "notifications_enabled" if enabled else "notifications_disabled"
    settings_context = _is_patient_settings_context_template(previous_template_key)
    reply_text = _localized_text(result_key, language)
    reply_markup = _localized_main_menu(language)
    template_key = f"telegram_patient_{result_key}"
    if settings_context:
        reply_text = f"{reply_text}\n\n{_telegram_settings_message(db, chat_id)}"
        reply_markup = _localized_settings_menu(language)
        template_key = f"telegram_patient_settings_{result_key}"
    await _send_patient_bot_reply(
        db,
        bot_service,
        chat_id,
        reply_text,
        reply_markup,
        template_key,
    )


async def _handle_contact_link(
    message: dict[str, Any], db: Session, bot_service
) -> bool:
    contact = message.get("contact")
    if not contact:
        return False

    chat_id = _message_chat_id(message)
    from_user_id = (message.get("from") or {}).get("id")
    contact_user_id = contact.get("user_id")
    if chat_id is None:
        return True

    if from_user_id is None or contact_user_id != from_user_id:
        await _send_patient_bot_reply(
            db,
            bot_service,
            chat_id,
            _telegram_chat_text(db, chat_id, "contact_rejected"),
            _telegram_chat_menu(db, chat_id),
            "telegram_patient_contact_rejected",
        )
        return True

    patient = _find_patient_by_phone(db, str(contact.get("phone_number") or ""))
    if not patient:
        existing_telegram_user = crud_telegram.get_telegram_user_by_chat_id(
            db, int(chat_id)
        )
        _upsert_ticket_qr_telegram_user(
            db,
            message,
            notifications_enabled=False if existing_telegram_user is None else None,
        )
        db.commit()
        await _send_patient_bot_reply(
            db,
            bot_service,
            chat_id,
            _telegram_chat_text(db, chat_id, "patient_not_found"),
            _telegram_onboarding_entry_markup(db, chat_id) or _telegram_chat_menu(db, chat_id),
            "telegram_patient_not_found",
        )
        return True

    try:
        existing_telegram_user = crud_telegram.get_telegram_user_by_chat_id(
            db, int(chat_id)
        )
        notifications_already_enabled = bool(
            getattr(existing_telegram_user, "notifications_enabled", False)
        )
        _upsert_ticket_qr_telegram_user(db, message, patient.id)
        db.commit()
    except Exception as exc:
        db.rollback()
        logger.warning(
            "Telegram contact link failed error_type=%s",
            type(exc).__name__,
        )
        await _send_patient_bot_reply(
            db,
            bot_service,
            chat_id,
            _telegram_chat_text(db, chat_id, "ticket_qr_link_failed"),
            _telegram_chat_menu(db, chat_id),
            "telegram_patient_ticket_qr_link_failed",
        )
        return True

    language = _telegram_chat_language(db, chat_id)
    reply_markup = _localized_main_menu(language)
    if not notifications_already_enabled:
        reply_markup = _localized_notification_consent_menu(language)
    patient_label = "Bemor" if language == TELEGRAM_LANGUAGE_UZ else "Пациент"
    await _send_patient_bot_reply(
        db,
        bot_service,
        chat_id,
        _patient_contact_linked_text(
            language,
            patient_label,
            _patient_display_name(patient),
            not notifications_already_enabled,
        ),
        reply_markup,
        "telegram_patient_contact_linked",
    )
    return True

