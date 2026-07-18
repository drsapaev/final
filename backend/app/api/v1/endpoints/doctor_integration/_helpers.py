from app.services.authorization.staff import staff_authorization_service
"""
API endpoints для интеграции панелей врачей с системой
Основа: passport.md стр. 1141-2063
"""

import logging  # noqa: F401
import uuid  # noqa: F401
from datetime import UTC, date, datetime, timedelta  # noqa: F401
from typing import Any  # noqa: F401

from fastapi import APIRouter, Depends, HTTPException, Query, status  # noqa: F401
from pydantic import BaseModel, Field, model_validator  # noqa: F401
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
from app.services.service_mapping import (  # noqa: E402, F401  # manual-review: conditional import after config — intentional
    get_service_code,  # noqa: E402, F401  # manual-review: conditional import after config — intentional
)

router = APIRouter()


DOCTOR_QUEUE_SPECIALTY_VARIANTS: dict[str, list[str]] = {
    "cardiology": ["cardiology", "cardio", "Cardiologist", "Cardio"],
    "cardio": ["cardiology", "cardio", "Cardiologist", "Cardio"],
    "derma": ["derma", "dermatology", "Dermatologist"],
    "dermatology": ["derma", "dermatology", "Dermatologist"],
    "dentist": ["dentist", "dental", "dentistry", "Dentist", "stomatology"],
    "dentistry": ["dentist", "dental", "dentistry", "Dentist", "stomatology"],
    "stomatology": ["dentist", "dental", "dentistry", "Dentist", "stomatology"],
    "lab": ["lab", "laboratory", "Laboratory"],
    "laboratory": ["lab", "laboratory", "Laboratory"],
    "general": ["general", "therapy", "therapist", "general_practice"],
}

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
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")


class ScheduleNextVisitService(BaseModel):
    service_id: int
    quantity: int = 1
    custom_price: float | None = None


class ScheduleNextVisitRequest(BaseModel):
    patient_id: int
    services: list[ScheduleNextVisitService] = Field(default_factory=list)
    service_ids: list[int] | None = None
    visit_date: date
    visit_time: str | None = None
    discount_mode: str = Field(
        default="none", pattern="^(none|repeat|benefit|all_free)$"
    )
    all_free: bool = False
    notes: str | None = None
    confirmation_channel: str = Field(
        default="phone", pattern="^(phone|telegram|pwa|auto)$"
    )

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


# ===================== ОЧЕРЕДЬ ВРАЧА =====================


