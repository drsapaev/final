"""Patient portal JWT endpoints (Phase 1 / PR-C1).

Canonical JWT-authenticated patient self-service endpoints for the web
portal (`/patient` after Phase 0 OTP login). They deliberately REUSE the
Telegram Mini App service layer as the single source of truth:

- booking draft/preview/validation: `build_telegram_mini_app_appointment_booking_preview`
- forms metadata + saved answers (read-only): `build_telegram_mini_app_patient_forms_preview`
- cabinet summary payload assembly: `_mini_app_patient_cabinet_summary_payload`
  (SSOT delegation into the mini-app module — no duplicated aggregation logic)

Identity differs only at the scope boundary: a JWT session resolves to
`current_user.patient` and builds a `TelegramMiniAppSessionScope` without
Telegram identity (telegram ids stay None). The Mini App endpoints keep
resolving identity from initData/entry tokens and are NOT modified.

Deliberately OUT of scope here (Telegram-only write path, no schema change
in this PR): `POST` form submissions — `telegram_patient_form_submissions
.telegram_chat_id` is NOT NULL, a web submission path needs its own schema
decision first.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api import deps
from app.api.v1.endpoints.telegram_webhook._clinic_bot import (
    _mini_app_patient_cabinet_summary_payload,
)
from app.api.v1.endpoints.telegram_webhook._helpers import (
    MINI_APP_BOOKING_REQUEST_ERROR_REASONS,
    MINI_APP_FORMS_REQUEST_ERROR_REASONS,
)
from app.crud.appointment import appointment as appointment_crud
from app.models.user import User
from app.schemas import appointment as appointment_schemas
from app.services.appointment_eligibility import ensure_doctor_eligible_for_appointment
from app.services.appointment_slot_guard import lock_doctor_for_slot_reservation
from app.services.patient_access_audit import log_patient_access
from app.services.telegram_mini_app_init_data import (
    TelegramMiniAppSessionScope,
    TelegramMiniAppSessionScopeError,
    build_telegram_mini_app_appointment_booking_preview,
    build_telegram_mini_app_patient_forms_preview,
)

router = APIRouter()


def _patient_portal_scope(patient_id: int) -> TelegramMiniAppSessionScope:
    """JWT portal scope: patient identity without Telegram linkage."""
    return TelegramMiniAppSessionScope(
        scope_type="patient",
        telegram_user_id=None,
        telegram_chat_id=None,
        patient_id=int(patient_id),
    )


def _require_patient(current_user: User) -> int:
    if not current_user.patient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"reason": "patient_profile_required"},
        )
    return int(current_user.patient.id)


def _booking_scope_status_code(reason: str) -> int:
    # Same public contract as the Mini App booking endpoints: request-shaped
    # problems are 400, identity/scope problems are 403.
    if reason in MINI_APP_BOOKING_REQUEST_ERROR_REASONS:
        return status.HTTP_400_BAD_REQUEST
    return status.HTTP_403_FORBIDDEN


def _forms_scope_status_code(reason: str) -> int:
    if reason in MINI_APP_FORMS_REQUEST_ERROR_REASONS:
        return status.HTTP_400_BAD_REQUEST
    return status.HTTP_403_FORBIDDEN


def _raise_scope_error(
    exc: TelegramMiniAppSessionScopeError, status_code: int
) -> HTTPException:
    return HTTPException(
        status_code=status_code,
        detail={"reason": exc.reason},
    )


class PatientPortalBookingRequest(BaseModel):
    """Same validation contract as the Mini App booking preview request."""

    appointment_date: date = Field(alias="appointmentDate")
    appointment_time: str | None = Field(default=None, alias="appointmentTime")
    doctor_id: int | None = Field(default=None, alias="doctorId")
    department: str | None = None
    notes: str | None = None
    services: list[str] | None = None

    model_config = {"populate_by_name": True}


@router.get("/cabinet/summary", response_model=dict[str, Any])
def get_patient_cabinet_summary(
    request: Request,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.require_roles("Patient")),
):
    """Home-screen summary for the JWT patient portal (own scope only)."""
    patient_id = _require_patient(current_user)
    scope = _patient_portal_scope(patient_id)
    # SSOT: payload assembly lives in the mini-app module (Phase 1 C1 keeps
    # aggregation in one place; the function reads only scope.scope_type and
    # scope.patient_id, both identical for the JWT portal scope).
    payload = _mini_app_patient_cabinet_summary_payload(db, scope)
    log_patient_access(
        db=db,
        scope=scope,
        resource_type="cabinet_summary",
        action="view",
        outcome="success",
        request=request,
    )
    return payload


@router.post("/booking/preview", response_model=dict[str, Any])
def preview_patient_portal_booking(
    request_body: PatientPortalBookingRequest,
    request: Request,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.require_roles("Patient")),
):
    """Non-mutating booking preview for the JWT patient portal."""
    patient_id = _require_patient(current_user)
    scope = _patient_portal_scope(patient_id)
    try:
        preview = build_telegram_mini_app_appointment_booking_preview(
            scope,
            patient_id=patient_id,
            appointment_date=request_body.appointment_date,
            appointment_time=request_body.appointment_time,
            doctor_id=request_body.doctor_id,
            department=request_body.department,
            notes=request_body.notes,
            services=request_body.services,
        )
    except TelegramMiniAppSessionScopeError as exc:
        raise _raise_scope_error(exc, _booking_scope_status_code(exc.reason)) from exc
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
        },
    )
    return preview.to_response_payload()


@router.post(
    "/booking", status_code=status.HTTP_201_CREATED, response_model=dict[str, Any]
)
def create_patient_portal_booking(
    request_body: PatientPortalBookingRequest,
    request: Request,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.require_roles("Patient")),
):
    """Create one trusted patient-portal appointment (own scope only).

    Mirrors the Mini App creation contract: same draft validation, same
    per-doctor FOR UPDATE slot reservation taken BEFORE eligibility, same
    409 on occupied slots, same lifecycle eligibility for the doctor.
    """
    patient_id = _require_patient(current_user)
    scope = _patient_portal_scope(patient_id)
    try:
        preview = build_telegram_mini_app_appointment_booking_preview(
            scope,
            patient_id=patient_id,
            appointment_date=request_body.appointment_date,
            appointment_time=request_body.appointment_time,
            doctor_id=request_body.doctor_id,
            department=request_body.department,
            notes=request_body.notes,
            services=request_body.services,
        )
    except TelegramMiniAppSessionScopeError as exc:
        raise _raise_scope_error(exc, _booking_scope_status_code(exc.reason)) from exc

    draft_payload = preview.draft.to_appointment_create_payload()

    if preview.draft.doctor_id is not None:
        # Atomic slot reservation — concurrent same-slot writers
        # (web/mobile/telegram) serialize on the doctor row. The lock is
        # taken BEFORE eligibility so a concurrent deactivation must commit
        # first (same ordering as the Mini App create path).
        lock_doctor_for_slot_reservation(db, preview.draft.doctor_id)

        try:
            ensure_doctor_eligible_for_appointment(db, preview.draft.doctor_id)
        except HTTPException as exc:
            raise HTTPException(
                status_code=exc.status_code,
                detail={
                    "reason": "doctor_not_eligible",
                    "message": exc.detail,
                },
            ) from exc

        if preview.draft.appointment_time:
            if appointment_crud.is_time_slot_occupied(
                db,
                doctor_id=preview.draft.doctor_id,
                appointment_date=preview.draft.appointment_date,
                appointment_time=preview.draft.appointment_time,
            ):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail={"reason": "appointment_time_slot_occupied"},
                )

    appointment_create_payload = dict(draft_payload)
    appointment_create_payload.pop("department", None)
    appointment_in = appointment_schemas.AppointmentCreate(**appointment_create_payload)
    appointment = appointment_crud.create(db=db, obj_in=appointment_in)

    log_patient_access(
        db=db,
        scope=scope,
        resource_type="appointment",
        resource_id=str(appointment.id),
        action="create",
        outcome="success",
        request=request,
        extra_data={
            "appointment_date": str(preview.draft.appointment_date),
            "appointment_time": preview.draft.appointment_time,
            "department": preview.draft.department,
        },
    )

    return {
        "created": True,
        "appointment_id": int(appointment.id),
        "preview": preview.to_response_payload(),
    }


@router.get("/forms", response_model=dict[str, Any])
def get_patient_portal_forms(
    request: Request,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.require_roles("Patient")),
):
    """Read-only protected forms metadata + saved answers for the JWT portal.

    Submissions remain Telegram-only in this PR (see module docstring).
    """
    patient_id = _require_patient(current_user)
    scope = _patient_portal_scope(patient_id)
    try:
        forms_preview = build_telegram_mini_app_patient_forms_preview(
            db,
            scope,
            patient_id=patient_id,
        )
    except TelegramMiniAppSessionScopeError as exc:
        raise _raise_scope_error(exc, _forms_scope_status_code(exc.reason)) from exc
    log_patient_access(
        db=db,
        scope=scope,
        resource_type="patient_form",
        action="view",
        outcome="success",
        request=request,
    )
    return forms_preview.to_response_payload()
