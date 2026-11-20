from app.services.authorization.staff import staff_authorization_service

"""
API endpoints для интеграции панелей врачей с системой
Основа: passport.md стр. 1141-2063
"""

import logging  # noqa: F401
import re  # noqa: F401
import uuid  # noqa: F401
from datetime import UTC, date, datetime, timedelta  # noqa: F401
from decimal import Decimal
from typing import Any  # noqa: F401

from fastapi import APIRouter, Depends, HTTPException, Query, status  # noqa: F401
from pydantic import (  # noqa: F401
    BaseModel,
    Field,
    field_validator,
    model_validator,
)
from sqlalchemy import and_, or_  # noqa: F401
from sqlalchemy.orm import Session  # noqa: F401

logger = logging.getLogger(__name__)

from app.api.deps import (  # noqa: E402, F401  # manual-review: conditional import after config — intentional
    get_db,
    require_roles,
)
from app.crud import (  # noqa: E402, F401  # manual-review: conditional import after config — intentional
    clinic as crud_clinic,
)
from app.crud import (  # noqa: E402, F401  # manual-review: conditional import after config — intentional
    visit as crud_visit,
)
from app.models.appointment import (  # noqa: E402, F401  # manual-review: conditional import after config — intentional
    Appointment,  # noqa: E402, F401  # manual-review: conditional import after config — intentional
)
from app.models.clinic import (  # noqa: E402, F401  # manual-review: conditional import after config — intentional
    Doctor,  # noqa: E402, F401  # manual-review: conditional import after config — intentional
)
from app.models.online_queue import (  # noqa: E402, F401  # manual-review: conditional import after config — intentional
    DailyQueue,
    OnlineQueueEntry,
)
from app.models.service import (  # noqa: E402, F401  # manual-review: conditional import after config — intentional
    Service,  # noqa: E402, F401  # manual-review: conditional import after config — intentional
)
from app.models.user import (  # noqa: E402, F401  # manual-review: conditional import after config — intentional
    User,  # noqa: E402, F401  # manual-review: conditional import after config — intentional
)
from app.models.visit import (  # noqa: E402, F401  # manual-review: conditional import after config — intentional
    Visit,
    VisitService,
)
from app.schemas.misc_endpoints import (
    CompleteVisitRequest,  # noqa: E402, F401  # manual-review: conditional import after config — intentional
)
from app.services.notification_service import (  # noqa: E402, F401  # manual-review: conditional import after config — intentional
    NotificationService,  # noqa: E402, F401  # manual-review: conditional import after config — intentional
)
from app.services.registrar_doctor_eligibility import (
    DOCTOR_QUEUE_SPECIALTY_VARIANTS,
)
from app.services.service_mapping import (  # noqa: E402, F401  # manual-review: conditional import after config — intentional
    get_service_code,  # noqa: E402, F401  # manual-review: conditional import after config — intentional
)

router = APIRouter()


DOCTOR_QUEUE_ALLOWED_TAGS: dict[str, list[str]] = {
    "cardiology": ["cardio", "cardiology", "cardiology_common"],
    "cardio": ["cardio", "cardiology", "cardiology_common"],
    "derma": ["derma", "dermatology"],
    "dermatology": ["derma", "dermatology"],
    "dentist": ["dentist", "dental", "dentistry", "stomatology"],
    "dentistry": ["dentist", "dental", "dentistry", "stomatology"],
    "stomatology": ["dentist", "dental", "dentistry", "stomatology"],
    "lab": ["lab", "laboratory"],
    "laboratory": ["lab", "laboratory"],
    "general": ["general"],
}

DOCTOR_SCHEDULE_NEXT_ROLES = {
    "doctor",
    "cardio",
    "cardiology",
    "derma",
    "dentist",
}


def _normalize_queue_specialty(value: str) -> str:
    return (value or "general").strip().lower()


def _resolve_queue_specialty_variants(specialty: str) -> list[str]:
    """PR-28: return specialty variants for queue lookup.
    Uses hardcoded map for known specialties, but falls back to [specialty]
    for unknown ones (e.g. 'neurology') so new specialties work without code changes.
    """
    normalized = _normalize_queue_specialty(specialty)
    return DOCTOR_QUEUE_SPECIALTY_VARIANTS.get(normalized, [normalized])


def _resolve_queue_allowed_tags(specialty: str) -> list[str]:
    """PR-28: return allowed queue tags for a specialty.
    Uses hardcoded map for known specialties, but falls back to [specialty]
    for unknown ones so new specialties' queues are visible.
    """
    normalized = _normalize_queue_specialty(specialty)
    return DOCTOR_QUEUE_ALLOWED_TAGS.get(normalized, [normalized])


def _serialize_queue_doctor(doctor: Doctor | None, current_user: User, specialty: str):
    normalized = _normalize_queue_specialty(specialty)
    if doctor:
        return {
            "id": doctor.id,
            "name": doctor.user.full_name if doctor.user else f"Врач #{doctor.id}",
            "specialty": doctor.specialty,
            "cabinet": doctor.cabinet,
        }

    return {
        "id": current_user.id,
        "name": current_user.full_name or current_user.username or "Врач",
        "specialty": normalized,
        "cabinet": None,
    }


# ===================== МОДЕЛИ ДАННЫХ =====================


def _doctor_queue_available_actions(entry: OnlineQueueEntry) -> list[str]:
    status_value = (entry.status or "").strip().lower()
    actions_by_status = {
        "waiting": ["call", "no_show"],
        "called": ["start_visit", "send_to_diagnostics", "no_show"],
        "in_progress": ["complete"],
        "diagnostics": [
            "notify_diagnostics_return",
            "complete",
            "mark_incomplete",
        ],
        "no_show": ["restore_next"],
    }
    return actions_by_status.get(status_value, [])


def _doctor_queue_action_flags(entry: OnlineQueueEntry) -> dict[str, bool]:
    actions = set(_doctor_queue_available_actions(entry))
    return {
        "can_call": "call" in actions,
        "can_start_visit": "start_visit" in actions,
        "can_no_show": "no_show" in actions,
        "can_send_to_diagnostics": "send_to_diagnostics" in actions,
        "can_complete": "complete" in actions,
        "can_notify_diagnostics_return": "notify_diagnostics_return" in actions,
        "can_mark_incomplete": "mark_incomplete" in actions,
        "can_restore_next": "restore_next" in actions,
    }


def _ensure_visit_doctor_access(visit: Visit, current_user: User) -> None:
    if staff_authorization_service.has_permission(current_user, "users:manage"):
        return

    doctor = visit.doctor
    if doctor and doctor.user_id == current_user.id:
        return

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="No access to this visit",
    )


def _ensure_legacy_complete_doctor_access(
    db: Session,
    *,
    record_doctor_id: int | None,
    current_user: User,
) -> None:
    if staff_authorization_service.has_permission(current_user, "users:manage"):
        return

    if record_doctor_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No access to complete this record",
        )

    assigned_doctor = db.query(Doctor).filter(Doctor.id == record_doctor_id).first()
    if assigned_doctor:
        if assigned_doctor.user_id == current_user.id:
            return
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No access to complete this record",
        )

    # Legacy writers sometimes stored User.id in doctor_id. Preserve that only
    # when the value does not point at another real Doctor row.
    if record_doctor_id == current_user.id:
        return

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="No access to complete this record",
    )


def _visit_filter_doctor_id(db: Session, current_user: User) -> int:
    doctor = (
        db.query(Doctor)
        .filter(and_(Doctor.user_id == current_user.id, Doctor.active == True))
        .first()
    )
    if doctor:
        return doctor.id
    if staff_authorization_service.has_permission(current_user, "users:manage"):
        return current_user.id
    return -1


def _doctor_schedule_patient_context_exists(
    db: Session,
    *,
    patient_id: int,
    doctor: Doctor,
    current_user: User,
) -> bool:
    doctor_ids = {doctor.id}
    assigned_doctor = db.query(Doctor).filter(Doctor.id == current_user.id).first()
    # Some legacy visit writers stored User.id in doctor_id. Preserve that
    # compatibility only when current_user.id does not point to another Doctor row.
    if not assigned_doctor:
        doctor_ids.add(current_user.id)

    visit_exists = (
        db.query(Visit.id)
        .filter(Visit.patient_id == patient_id, Visit.doctor_id.in_(doctor_ids))
        .first()
        is not None
    )
    if visit_exists:
        return True

    return (
        db.query(Appointment.id)
        .filter(
            Appointment.patient_id == patient_id,
            Appointment.doctor_id.in_(doctor_ids),
        )
        .first()
        is not None
    )


def _ensure_schedule_next_patient_access(
    db: Session,
    *,
    patient_id: int,
    doctor: Doctor | None,
    current_user: User,
) -> None:
    if staff_authorization_service.has_permission(current_user, "users:manage"):
        return
    if (current_user.role or "").strip().lower() not in DOCTOR_SCHEDULE_NEXT_ROLES:
        return
    if not doctor or not _doctor_schedule_patient_context_exists(
        db,
        patient_id=patient_id,
        doctor=doctor,
        current_user=current_user,
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Access denied"
        )


def _probe_schedule_next_patient_evidence(
    db: Session, *, patient_id: int, doctor: Doctor
) -> tuple[str, int]:
    """Find an ownership candidate; it has NO authority until locked/rechecked.

    Historical rows whose doctor_id merely equals users.id are intentionally
    excluded: an absent Doctor row at that id is not a lockable identity.
    """
    visit_id = (
        db.query(Visit.id)
        .filter(Visit.patient_id == patient_id, Visit.doctor_id == doctor.id)
        .order_by(Visit.id).first()
    )
    if visit_id is not None:
        return ("visit", visit_id[0])
    appointment_id = (
        db.query(Appointment.id)
        .filter(Appointment.patient_id == patient_id, Appointment.doctor_id == doctor.id)
        .order_by(Appointment.id).first()
    )
    if appointment_id is not None:
        return ("appointment", appointment_id[0])
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")


def _lock_schedule_next_patient_evidence(
    db: Session, *, patient_id: int, doctor: Doctor, candidate: tuple[str, int]
) -> None:
    """Hold and recheck the exact current assignment through the root commit.

    A Visit candidate must have been included in sorted repeat Visit locks
    before this call. Appointment uses NOWAIT to avoid reverse wait against
    writers that acquire Appointment before Visit. Caller rolls back 55P03.
    """
    kind, row_id = candidate
    if kind == "visit":
        row = (db.query(Visit).filter(Visit.id == row_id)
               .with_for_update(nowait=True).populate_existing().first())
    elif kind == "appointment":
        query = db.query(Appointment).filter(Appointment.id == row_id).populate_existing()
        if db.get_bind().dialect.name == "postgresql":
            query = query.with_for_update(nowait=True)
        row = query.first()
    else:
        row = None
    if row is None or row.patient_id != patient_id or row.doctor_id != doctor.id:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Назначение пациента изменилось; повторите запрос")


class ScheduleNextVisitService(BaseModel):
    service_id: int
    quantity: int = 1
    # Non-finite values are rejected by the endpoint's money validator.
    # Let them reach it so the 422 response does not try to serialize a
    # non-JSON NaN/Infinity in a Pydantic validation-error payload.
    custom_price: Decimal | None = Field(default=None, allow_inf_nan=True)


class ScheduleNextVisitRequest(BaseModel):
    patient_id: int
    services: list[ScheduleNextVisitService] = Field(default_factory=list)
    service_ids: list[int] | None = None
    visit_date: date
    # DOCSCHED-BE-005 (audit #3892, group 18): visit_time — канонический
    # zero-padded HH:MM (HTML time input) или отсутствие (дневная запись без
    # времени). Произвольные строки ('29:99', 'notime', '9:00') больше не
    # попадают в pending-подтверждение и очередь.
    visit_time: str | None = None
    discount_mode: str = Field(
        default="none", pattern="^(none|repeat|benefit|all_free)$"
    )
    all_free: bool = False
    notes: str | None = None
    confirmation_channel: str = Field(
        default="phone", pattern="^(phone|telegram|pwa|auto)$"
    )

    @field_validator("visit_time")
    @classmethod
    def _validate_visit_time_hh_mm(cls, value: str | None) -> str | None:
        """DOCSCHED-BE-005: canonical HH:MM contract (00:00–23:59)."""
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            return None
        if not re.fullmatch(r"([01]\d|2[0-3]):[0-5]\d", normalized):
            raise ValueError(
                "visit_time должен быть временем в формате HH:MM (00:00–23:59)"
            )
        return normalized

    @model_validator(mode="after")
    def normalize_services_payload(self):
        # Backward-compatibility for tests/clients that still send `service_ids`.
        if not self.services and self.service_ids:
            self.services = [
                ScheduleNextVisitService(service_id=service_id)
                for service_id in self.service_ids
            ]

        if not self.services:
            raise ValueError("services or service_ids must be provided")

        return self


class ScheduleNextVisitResponse(BaseModel):
    success: bool
    message: str
    visit_id: int
    status: str  # pending_confirmation
    confirmation: dict[str, Any]
    # DOCSCHED-BE-001 (audit #3892, group 18): True, когда идентичный
    # intent уже был зафиксирован в окне дедупликации и ответ перестроен
    # из СОХРАНЁННОГО визита (второй визит/токен не создавались).
    idempotent_replay: bool = Field(
        default=False,
        description="True при авторизованном повторе ранее сохранённого намерения.",
    )
    price_override_requests: list[dict[str, Any]] = Field(default_factory=list)


# ===================== ОЧЕРЕДЬ ВРАЧА =====================
