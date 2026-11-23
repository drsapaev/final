"""Patient RSVP decisions for a single, versioned appointment occurrence.

Only a callback received from Telegram's authenticated private-chat ingress may
call this service.  A patient's RSVP never represents payment.
"""

from __future__ import annotations

import hashlib
import hmac
import re
import secrets
from datetime import UTC, datetime, time
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.appointment import Appointment
from app.models.enums import AppointmentStatus, can_transition_status
from app.models.telegram_config import TelegramUser

_CALLBACK = re.compile(r"^ar:([vcx]):([0-9a-z]{1,13}):([0-9a-z]{1,7}):([0-9a-z]{1,13}):([0-9a-f]{20})$")
_DIGITS = "0123456789abcdefghijklmnopqrstuvwxyz"


def _base36(value: int) -> str:
    if value == 0:
        return "0"
    result = ""
    while value:
        value, digit = divmod(value, 36)
        result = _DIGITS[digit] + result
    return result


def _mac(action: str, appointment_id: int, revision: int, chat_id: int,
         link_id: int, link_epoch: int, nonce: int) -> str:
    value = f"appointment-rsvp-v3:{action}:{appointment_id}:{revision}:{chat_id}:{link_id}:{link_epoch}:{nonce}".encode()
    return hmac.new(settings.SECRET_KEY.encode(), value, hashlib.sha256).hexdigest()[:20]


def _masks(chat_id: int, link_id: int, link_epoch: int, nonce: int) -> tuple[int, int]:
    """One-time masks hide record identifiers and occurrence metadata."""
    value = f"appointment-rsvp-mask-v3:{chat_id}:{link_id}:{link_epoch}:{nonce}".encode()
    digest = hmac.new(settings.SECRET_KEY.encode(), value, hashlib.sha256).digest()
    return int.from_bytes(digest[:4], "big") & (2**31 - 1), int.from_bytes(digest[4:12], "big") & (2**63 - 1)


def make_appointment_callback(action: str, appointment_id: int, revision: int, chat_id: int,
                              link_id: int, link_epoch: int) -> str:
    """Return a short authenticated callback bound to chat and occurrence."""
    if action not in {"v", "c", "x"} or any(
        isinstance(value, bool) or not isinstance(value, int)
        for value in (appointment_id, revision, chat_id, link_id, link_epoch)
    ) or not 0 < appointment_id < 2**31 or not 0 <= revision < 2**63 or chat_id <= 0 or link_id <= 0 or not 0 <= link_epoch < 2**63:
        raise ValueError("Invalid appointment callback input")
    nonce = secrets.randbits(64)
    id_mask, revision_mask = _masks(chat_id, link_id, link_epoch, nonce)
    signature = _mac(action, appointment_id, revision, chat_id, link_id, link_epoch, nonce)
    payload = f"ar:{action}:{_base36(nonce)}:{_base36(appointment_id ^ id_mask)}:{_base36(revision ^ revision_mask)}:{signature}"
    if len(payload.encode()) > 64 or not _CALLBACK.fullmatch(payload):
        raise ValueError("Appointment callback exceeds supported range")
    return payload


def parse_appointment_callback(data: str) -> tuple[str, int, int, int, str] | None:
    """Parse only; the MAC is verified after locking the active link."""
    match = _CALLBACK.fullmatch(data)
    if not match:
        return None
    action, encoded_nonce, encoded_id, encoded_revision, supplied = match.groups()
    try:
        nonce, masked_id, masked_revision = (int(v, 36) for v in (encoded_nonce, encoded_id, encoded_revision))
    except ValueError:
        return None
    if (
        nonce >= 2**64 or masked_id >= 2**31 or masked_revision >= 2**63
        or any(_base36(value) != encoded for value, encoded in (
            (nonce, encoded_nonce), (masked_id, encoded_id), (masked_revision, encoded_revision)
        ))
    ):
        return None
    return action, nonce, masked_id, masked_revision, supplied


def _appointment_start(appointment: Appointment) -> datetime | None:
    """Interpret booked local time using the clinic's configured timezone."""
    if not appointment.appointment_date:
        return None
    try:
        # Match the existing patient appointment policy for an unset time.
        parsed_time = time.fromisoformat(appointment.appointment_time or "09:00")
        if parsed_time.tzinfo is not None:
            return None
        return datetime.combine(
            appointment.appointment_date, parsed_time, tzinfo=ZoneInfo(settings.TIMEZONE)
        )
    except (TypeError, ValueError, KeyError):
        return None


def can_patient_cancel(appointment: Appointment, now: datetime | None = None) -> bool:
    """Patient cancellation policy, evaluated while holding the row lock."""
    if appointment.status not in {"pending", "scheduled", "paid", "confirmed"}:
        return False
    current = now or datetime.now(UTC)
    start = _appointment_start(appointment)
    return bool(
        current.tzinfo is not None
        and start is not None
        and (start - current).total_seconds() >= 24 * 3600
        and can_transition_status(appointment.status, AppointmentStatus.CANCELLED)
    )


def apply_appointment_decision(
    db: Session, *, callback_data: str, chat_id: int,
    now: datetime | None = None,
) -> str:
    """Commit exactly one owned decision; return a non-sensitive result code.

    The link is locked before the appointment, so revocation and the decision
    have a definite order. A refreshed row lock prevents stale identity-map
    state from overriding a registrar's canonical status update.
    """
    parsed = parse_appointment_callback(callback_data)
    if parsed is None or isinstance(chat_id, bool) or not isinstance(chat_id, int) or chat_id <= 0:
        return "invalid"
    action, nonce, masked_id, masked_revision, supplied = parsed
    if action not in {"c", "x"}:
        return "invalid"
    try:
        link = (
            db.query(TelegramUser)
            .filter(TelegramUser.chat_id == chat_id)
            .with_for_update(of=TelegramUser)
            .populate_existing()
            .first()
        )
        if not link or not link.patient_id or not link.active or link.blocked or not (
            link.notifications_enabled and link.appointment_reminders
        ):
            db.rollback()
            return "unavailable"
        epoch = getattr(link, "patient_link_epoch", None)
        if epoch is None:
            db.rollback()
            return "unavailable"
        id_mask, revision_mask = _masks(chat_id, link.id, epoch, nonce)
        appointment_id, revision = masked_id ^ id_mask, masked_revision ^ revision_mask
        if not appointment_id or not hmac.compare_digest(
            supplied, _mac(action, appointment_id, revision, chat_id, link.id, epoch, nonce)
        ):
            db.rollback()
            return "stale"
        appointment = (
            db.query(Appointment)
            .filter(Appointment.id == appointment_id)
            .with_for_update(of=Appointment)
            .populate_existing()
            .first()
        )
        if not appointment or appointment.patient_id != link.patient_id:
            db.rollback()
            return "unavailable"
        if appointment.occurrence_revision != revision:
            db.rollback()
            return "stale"
        # Unknown/legacy states must not normalize to pending implicitly.
        if appointment.status not in {"pending", "scheduled", "paid", "confirmed"}:
            db.rollback()
            return "unavailable"

        start = _appointment_start(appointment)
        current = now or datetime.now(UTC)
        if current.tzinfo is None or start is None or start <= current:
            db.rollback()
            return "unavailable"

        if action == "c":
            if appointment.patient_rsvp_revision == revision and appointment.patient_rsvp_at:
                db.rollback()
                return "already_confirmed"
            appointment.patient_rsvp_at = current.astimezone(UTC)
            appointment.patient_rsvp_revision = revision
            db.commit()
            return "confirmed"

        # Match the established patient cancellation cutoff and the canonical
        # state machine. The payment record is never changed by RSVP.
        if not can_patient_cancel(appointment, current):
            db.rollback()
            return "unavailable"
        appointment.status = AppointmentStatus.CANCELLED.value
        appointment.updated_at = current.astimezone(UTC)
        db.commit()
        return "cancelled"
    except Exception:
        db.rollback()
        raise


def preview_appointment_decision(db: Session, *, callback_data: str, chat_id: int) -> dict | None:
    """Verify a view capability and produce explicit actions for this occurrence.

    The caller must have verified the authenticated private Telegram actor.
    Locks are released before any external send: revocation may therefore race
    the send itself, while subsequent action callbacks always recheck it.
    """
    parsed = parse_appointment_callback(callback_data)
    if parsed is None or parsed[0] != "v" or isinstance(chat_id, bool) or not isinstance(chat_id, int) or chat_id <= 0:
        return None
    _, nonce, masked_id, masked_revision, supplied = parsed
    try:
        link = (db.query(TelegramUser).filter(TelegramUser.chat_id == chat_id)
                .with_for_update(of=TelegramUser).populate_existing().first())
        if not link or not link.patient_id or not link.active or link.blocked or not (
            link.notifications_enabled and link.appointment_reminders
        ):
            return None
        epoch = getattr(link, "patient_link_epoch", None)
        if epoch is None:
            return None
        id_mask, revision_mask = _masks(chat_id, link.id, epoch, nonce)
        appointment_id, revision = masked_id ^ id_mask, masked_revision ^ revision_mask
        if not appointment_id or not hmac.compare_digest(
            supplied, _mac("v", appointment_id, revision, chat_id, link.id, epoch, nonce)
        ):
            return None
        appointment = (db.query(Appointment).filter(Appointment.id == appointment_id)
                       .with_for_update(of=Appointment).populate_existing().first())
        if (not appointment or appointment.patient_id != link.patient_id
            or appointment.occurrence_revision != revision
            or appointment.status not in {"pending", "scheduled", "paid", "confirmed"}):
            return None
        start = _appointment_start(appointment)
        now = datetime.now(UTC)
        if start is None or start <= now:
            return None
        doctor = appointment.doctor
        doctor_name = (getattr(getattr(doctor, "user", None), "full_name", None)
                       or getattr(doctor, "specialty", None) or "не указан")
        department = appointment.department_name or "не указано"
        service_names = []
        for item in appointment.services or []:
            if isinstance(item, str):
                service_names.append(item)
            elif isinstance(item, dict):
                label = item.get("name") or item.get("name_ru") or item.get("code")
                if isinstance(label, str):
                    service_names.append(label)
        services = ", ".join(service_names)[:600] or "не указаны"
        text = (f"Запись №{appointment.id}\nДата: {appointment.appointment_date.isoformat()}\n"
                f"Время: {appointment.appointment_time or 'не указано'}\nВрач: {doctor_name}\n"
                f"Отделение: {department}\nУслуги: {services}")
        return {
            "text": text,
            "confirm_data": make_appointment_callback("c", appointment_id, revision, chat_id, link.id, epoch),
            "cancel_data": (make_appointment_callback("x", appointment_id, revision, chat_id, link.id, epoch)
                            if can_patient_cancel(appointment, now) else None),
        }
    finally:
        db.rollback()
