"""Authorize clinical Telegram deliveries against canonical patient records."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from fastapi import HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.roles import is_doctor_role_spelling
from app.models.appointment import Appointment
from app.models.clinic import Doctor
from app.models.lab import LabOrder, LabReportInstance, LabResult
from app.models.patient import Patient
from app.models.telegram_config import TelegramUser
from app.models.user import User
from app.services.appointment_rsvp import _appointment_start
from app.services.lab_notification_scope import resolve_lab_notification
from app.services.notifications_pkg._helpers import (
    _is_private_telegram_chat_id,
    _patient_telegram_preferences_enabled,
)
from app.services.patient_phone_scope import canonical_phone_identity


class TelegramDeliveryError(BaseModel):
    detail: str


def _not_found() -> HTTPException:
    # Do not disclose which identity or relationship failed.
    return HTTPException(status_code=404, detail="Notification recipient not found")


def _required_id(data: dict[str, Any], keys: tuple[str, ...]) -> int:
    values = [data[key] for key in keys if data.get(key) is not None]
    if not values or any(
        isinstance(value, bool)
        or not (isinstance(value, int) or (isinstance(value, str) and value.isascii() and value.isdigit()))
        for value in values
    ):
        raise HTTPException(status_code=400, detail="A valid resource identifier is required")
    try:
        ids = [int(value) for value in values]
    except (TypeError, ValueError, OverflowError) as exc:
        raise HTTPException(status_code=400, detail="A valid resource identifier is required") from exc
    if any(value <= 0 for value in ids) or len(set(ids)) != 1:
        raise HTTPException(status_code=400, detail="A valid resource identifier is required")
    return ids[0]


def _is_admin(user: User) -> bool:
    return bool(getattr(user, "is_superuser", False)) or str(
        getattr(user, "role", "") or ""
    ).strip().lower() in {"admin", "superadmin"}


def _current_actor(db: Session, user: User, allowed: set[str]) -> User:
    actor = db.query(User).filter(User.id == user.id).populate_existing().first()
    if actor is None or actor.is_active is not True:
        raise _not_found()
    role = str(actor.role or "").strip().lower()
    if not _is_admin(actor) and role not in allowed and not (
        "doctor" in allowed and is_doctor_role_spelling(actor.role)
    ):
        raise _not_found()
    return actor


def _doctor_id(db: Session, user: User) -> int | None:
    if getattr(user, "is_active", None) is not True:
        raise _not_found()
    if _is_admin(user) or not is_doctor_role_spelling(getattr(user, "role", None)):
        return None
    doctor = db.query(Doctor).filter(Doctor.user_id == user.id, Doctor.active.is_(True)).populate_existing().first()
    if doctor is None:
        raise _not_found()
    return doctor.id


def _patient(db: Session, patient_id: int, phone: str | None = None) -> Patient:
    patient = db.query(Patient).filter(Patient.id == patient_id, Patient.is_deleted.is_(False)).populate_existing().first()
    if patient is None:
        raise _not_found()
    if phone is not None:
        requested = canonical_phone_identity(phone)
        if not requested or requested != canonical_phone_identity(patient.phone or ""):
            raise _not_found()
    return patient


def _link(db: Session, patient_id: int, event_type: str, chat_id: int | None = None) -> TelegramUser:
    query = db.query(TelegramUser).filter(
        TelegramUser.patient_id == patient_id,
        TelegramUser.active.is_(True),
        TelegramUser.blocked.is_(False),
    )
    if chat_id is not None:
        query = query.filter(TelegramUser.chat_id == chat_id)
    link = query.order_by(TelegramUser.id.desc()).populate_existing().first()
    if (link is None or not _is_private_telegram_chat_id(link.chat_id)
            or not _patient_telegram_preferences_enabled(link, event_type)):
        raise _not_found()
    return link


def authorize_appointment(
    db: Session, user: User, data: dict[str, Any], *, phone: str | None = None,
    chat_id: int | None = None,
) -> tuple[Appointment, Patient, TelegramUser]:
    user = _current_actor(db, user, {"doctor", "registrar"})
    appointment_id = _required_id(data, ("appointment_id", "id"))
    appointment = db.query(Appointment).filter(Appointment.id == appointment_id).populate_existing().first()
    if appointment is None:
        raise _not_found()
    if str(appointment.status or "").strip().lower() not in {"scheduled", "pending", "confirmed", "paid"}:
        raise HTTPException(status_code=409, detail="Appointment is not eligible for reminders")
    start = _appointment_start(appointment)
    if start is None or start <= datetime.now(UTC):
        raise HTTPException(status_code=409, detail="Appointment is not eligible for reminders")
    doctor_id = _doctor_id(db, user)
    if doctor_id is not None and appointment.doctor_id != doctor_id:
        raise _not_found()
    patient = _patient(db, appointment.patient_id, phone)
    return appointment, patient, _link(db, patient.id, "appointment_reminder", chat_id)


def authorize_lab_result(
    db: Session, user: User, data: dict[str, Any], *, phone: str | None = None,
    chat_id: int | None = None,
) -> tuple[LabResult, LabOrder, Patient, TelegramUser]:
    user = _current_actor(db, user, {"doctor", "lab"})
    result_id = _required_id(data, ("lab_results_id", "lab_result_id", "id"))
    result = db.query(LabResult).filter(LabResult.id == result_id).populate_existing().first()
    order = db.query(LabOrder).filter(LabOrder.id == result.order_id).populate_existing().first() if result else None
    if result is None or order is None:
        raise _not_found()
    patient_id = order.patient_id
    if patient_id is None and result.source_instance_id:
        source = db.query(LabReportInstance).filter(
            LabReportInstance.id == result.source_instance_id,
            LabReportInstance.order_id == order.id,
        ).populate_existing().first()
        patient_id = source.patient_id if source else None
    if patient_id is None:
        raise _not_found()
    patient = _patient(db, patient_id, phone)
    try:
        result, order, _ = resolve_lab_notification(
            db, lab_result_id=result_id, patient_id=patient.id, current_user=user
        )
    except HTTPException as exc:
        if exc.status_code in {403, 404}:
            raise _not_found() from exc
        raise
    return result, order, patient, _link(db, patient.id, "lab_results", chat_id)


def authorize_generic_chat(db: Session, user: User, chat_id: int, event_type: str) -> TelegramUser:
    # Generic caller-provided template data has no verifiable clinical owner.
    # Limit it to admins and require a patient-linked, consenting chat.
    user = _current_actor(db, user, set())
    if not _is_admin(user):
        raise _not_found()
    link = db.query(TelegramUser).filter(TelegramUser.chat_id == chat_id).first()
    if link is None or link.patient_id is None:
        raise _not_found()
    _patient(db, link.patient_id)
    return _link(db, link.patient_id, event_type, chat_id)


def appointment_payload(db: Session, appointment: Appointment) -> dict[str, Any]:
    doctor = db.query(Doctor).filter(Doctor.id == appointment.doctor_id).first() if appointment.doctor_id else None
    return {
        "id": appointment.id,
        "patient_id": appointment.patient_id,
        "doctor_id": appointment.doctor_id,
        "department_id": appointment.department_id,
        "occurrence_revision": appointment.occurrence_revision,
        "doctor": getattr(getattr(doctor, "user", None), "full_name", None) or "Врач",
        "date": appointment.appointment_date.isoformat(),
        "time": appointment.appointment_time,
    }


def lab_payload(result: LabResult) -> dict[str, Any]:
    return {"test_name": result.test_name, "date": result.created_at.date().isoformat() if result.created_at else ""}
