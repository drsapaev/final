"""Admin read-model for appointments with doctor/user/cabinet linkage enrichment."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.core.security import require_roles
from app.crud.appointment import appointment as appointment_crud
from app.models.clinic import Doctor
from app.models.online_queue import DailyQueue
from app.models.patient import Patient
from app.models.user import User

router = APIRouter(prefix="/admin/appointments", tags=["admin-appointments"])


def _parse_iso_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Неверный формат даты. Используйте YYYY-MM-DD",
        ) from exc


def _get_patient_display_name(patient: Patient | None, patient_id: int | None) -> str:
    if patient:
        return patient.short_name()
    if patient_id:
        return f"Пациент #{patient_id}"
    return "Пациент"


def _build_doctor_summary(doctor: Doctor | None) -> tuple[dict[str, Any] | None, list[str]]:
    warnings: list[str] = []
    if not doctor:
        return None, ["missing_doctor_record"]

    user = doctor.user
    if not doctor.user_id:
        warnings.append("doctor_without_user")
    if doctor.user_id and not user:
        warnings.append("missing_doctor_user")
    if user and not user.is_active:
        warnings.append("doctor_user_inactive")
    if not doctor.active:
        warnings.append("doctor_inactive")
    if not doctor.cabinet:
        warnings.append("doctor_cabinet_missing")

    summary = {
        "id": doctor.id,
        "user_id": doctor.user_id,
        "full_name": (user.full_name or user.username) if user else None,
        "email": user.email if user else None,
        "role": user.role if user else None,
        "specialty": doctor.specialty,
        "cabinet": doctor.cabinet,
        "active": doctor.active,
        "user_active": user.is_active if user else None,
    }
    return summary, warnings


def _resolve_effective_cabinet(
    db: Session,
    *,
    appointment_date: date | None,
    doctor: Doctor | None,
) -> tuple[str | None, str | None, list[str]]:
    warnings: list[str] = []
    queue_cabinet = None
    doctor_cabinet = doctor.cabinet if doctor else None

    if appointment_date and doctor:
        today_queue = (
            db.query(DailyQueue)
            .filter(
                DailyQueue.day == appointment_date,
                DailyQueue.specialist_id == doctor.id,
            )
            .order_by(DailyQueue.id.asc())
            .first()
        )
        if today_queue:
            queue_cabinet = today_queue.cabinet_number
            if doctor_cabinet and queue_cabinet and queue_cabinet != doctor_cabinet:
                warnings.append("queue_cabinet_stale")

    effective = queue_cabinet or doctor_cabinet
    if not effective:
        warnings.append("effective_cabinet_missing")

    return effective, queue_cabinet, warnings


@router.get("", response_model=dict[str, Any])
def list_admin_appointments(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    patient_id: int | None = Query(None),
    doctor_id: int | None = Query(None),
    status_filter: str | None = Query(None, alias="status"),
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin")),
):
    """Получить записи с согласованным doctor/cabinet read-model для админки."""
    from_date = _parse_iso_date(date_from)
    to_date = _parse_iso_date(date_to)

    appointments = appointment_crud.get_appointments(
        db,
        skip=skip,
        limit=limit,
        patient_id=patient_id,
        doctor_id=doctor_id,
        date_from=from_date.isoformat() if from_date else None,
        date_to=to_date.isoformat() if to_date else None,
    )

    result: list[dict[str, Any]] = []
    for appointment in appointments:
        if status_filter and appointment.status != status_filter:
            continue

        patient = (
            db.query(Patient).filter(Patient.id == appointment.patient_id).first()
            if appointment.patient_id
            else None
        )
        doctor = (
            db.query(Doctor).filter(Doctor.id == appointment.doctor_id).first()
            if appointment.doctor_id
            else None
        )

        doctor_summary, doctor_warnings = _build_doctor_summary(doctor)
        effective_cabinet, queue_cabinet, cabinet_warnings = _resolve_effective_cabinet(
            db,
            appointment_date=appointment.appointment_date,
            doctor=doctor,
        )
        integrity_warnings = doctor_warnings + cabinet_warnings

        result.append(
            {
                "id": appointment.id,
                "patientId": appointment.patient_id,
                "patientName": _get_patient_display_name(patient, appointment.patient_id),
                "phone": patient.phone if patient else None,
                "doctorId": appointment.doctor_id,
                "doctorName": doctor_summary["full_name"] if doctor_summary else None,
                "doctorSpecialization": doctor_summary["specialty"] if doctor_summary else None,
                "appointmentDate": (
                    appointment.appointment_date.isoformat()
                    if appointment.appointment_date
                    else None
                ),
                "appointmentTime": appointment.appointment_time,
                "duration": 30,
                "status": appointment.status,
                "reason": appointment.notes or "",
                "notes": appointment.notes,
                "doctor": doctor_summary,
                "doctorCabinet": doctor_summary["cabinet"] if doctor_summary else None,
                "queueCabinet": queue_cabinet,
                "effectiveCabinet": effective_cabinet,
                "integrityWarnings": integrity_warnings,
                "hasIntegrityWarnings": len(integrity_warnings) > 0,
                "createdAt": (
                    appointment.created_at.isoformat() if appointment.created_at else None
                ),
                "updatedAt": (
                    appointment.updated_at.isoformat() if appointment.updated_at else None
                ),
            }
        )

    return result
