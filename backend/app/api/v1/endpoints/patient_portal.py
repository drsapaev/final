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

Review hardening (round 2, PR #3340):

- P1 (soft-deleted card): `_require_patient` rejects `Patient.is_deleted`,
  matching the Mini App SSOT (`patient_link_invalid`) — soft deletion only
  flips the flag, `User.patient` keeps resolving, so the check must be
  explicit or a soft-deleted card keeps full PHI/booking access.
- P1 (deactivated user): the shared dependency composes
  `get_current_active_user` + `require_roles("Patient")` — `require_roles`
  alone delegates to `get_current_user`, which never checks `is_active`,
  so an admin-deactivated account would keep a valid JWT until expiry.
- P1 (department persistence): a provided `department` is resolved through
  the canonical `Department.key` (active rows only) and the created
  `Appointment` gets `department_id` — the raw string is display metadata,
  the routing context lives in `departments.id`.
- P2 (typed contract): all four endpoints publish explicit response/error
  Pydantic DTOs (no more `dict[str, Any]`), so the generated TypeScript
  gives PR-C2 a compile-time contract and the OpenAPI documents the real
  4xx surface.
- P2 (booking idempotency): `POST /patients/booking` REQUIRES an
  `Idempotency-Key` header. The global idempotency middleware is opt-in —
  without a mandated key a lost response + browser retry would double-book
  date-only/department-only requests (no slot lock covers those shapes).

Review hardening (round 3, PR #3340):

- P2 (cabinet policy SSOT): `PatientPortalCabinetPolicy` now carries the
  full Mini App policy payload including `medical_details_in_chat` —
  FastAPI response filtering silently dropped the field before, so the
  JWT portal did NOT return the same cabinet payload as the SSOT.
- P2 (typed 404 surface): the three endpoints that can raise
  `_require_patient`'s `404 patient_profile_required` (preview, booking,
  forms) now DECLARE it — only cabinet did. Booking additionally declares
  the doctor-eligibility 404.
- P2 (internal creation schema): `department_id` moved OFF the shared
  `AppointmentCreate` onto `PatientPortalAppointmentCreate` — the legacy
  `POST /appointments/` endpoint inherits every shared field, so a
  client-owned routing FK there would bypass the portal's department
  validation entirely.
- P2 (denied audit rows): portal refusals write `outcome="denied"
  `patient_access_audit` rows with the failure reason (soft-deleted card
  403, unknown/inactive department 400, doctor eligibility 404, occupied
  slot 409) — the SSOT Mini App writes denied rows for auth/scope
  failures; the JWT portal previously audited successes only.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import date, datetime
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
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
from app.crud.clinic import clinic_today
from app.models.clinic import Doctor
from app.models.department import Department
from app.models.user import User
from app.schemas import appointment as appointment_schemas
from app.services.appointment_booking_routing import (
    attach_department_id,
    lock_department_for_booking,
    resolve_booking_department,
    resolve_doctor_routing_department,
)
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


# ---------------------------------------------------------------------------
# Request DTO
# ---------------------------------------------------------------------------


class PatientPortalBookingRequest(BaseModel):
    """Same validation contract as the Mini App booking preview request."""

    appointment_date: date = Field(alias="appointmentDate")
    appointment_time: str | None = Field(default=None, alias="appointmentTime")
    doctor_id: int | None = Field(default=None, alias="doctorId")
    department: str | None = None
    notes: str | None = None
    services: list[str] | None = None

    model_config = {"populate_by_name": True}


# ---------------------------------------------------------------------------
# Response DTOs (P2: explicit public contract — no dict[str, Any])
# ---------------------------------------------------------------------------


class PatientPortalErrorDetail(BaseModel):
    """Structured portal error body (scope / request-shaped failures)."""

    reason: str
    message: str | None = None


class PatientPortalErrorResponse(BaseModel):
    # The 401/403 layer (get_current_user / require_roles SSOT) raises plain
    # string details; portal scope guards raise {"reason": ...}. The union
    # keeps the published schema honest about both runtime shapes.
    detail: PatientPortalErrorDetail | str
    # Round-6 (owner P2, PR #3340): the keyed-write middleware answers 409/
    # 503 bodies that carry a machine top-level `code` the client MUST
    # branch on (retry same key vs. new key vs. reconcile vs. wait for
    # Redis): `idempotency_in_flight`, `idempotency_uncertain_outcome`,
    # `idempotency_payload_mismatch`, `idempotency_scope_mismatch`,
    # `idempotency_unavailable` (503), `idempotency_key_invalid` (400).
    # Endpoint-level errors (e.g. the slot-occupied 409) carry no code —
    # the field stays optional to describe both runtime shapes honestly.
    code: str | None = None


class PatientPortalScope(BaseModel):
    type: str
    patient_id: int


class PatientPortalBookingAppointment(BaseModel):
    """Draft appointment echo (Mini App payload + resolved department_id)."""

    patient_id: int
    doctor_id: int | None = None
    department: str | None = None
    department_id: int | None = None
    appointment_date: date
    appointment_time: str | None = None
    notes: str | None = None
    status: str
    visit_type: str | None = None
    payment_type: str | None = None
    services: list[str] = []
    payment_amount: float | None = None
    payment_currency: str | None = None
    payment_provider: str | None = None
    payment_transaction_id: str | None = None
    payment_webhook_id: int | None = None
    payment_processed_at: datetime | None = None


class PatientPortalBookingPreviewResponse(BaseModel):
    preview_only: bool
    mutation_allowed: bool
    message_key: str
    scope: PatientPortalScope
    appointment: PatientPortalBookingAppointment


class PatientPortalBookingCreatedResponse(BaseModel):
    created: bool
    appointment_id: int
    preview: PatientPortalBookingPreviewResponse


class PatientPortalCabinetAppointmentsItem(BaseModel):
    id: int
    date: str | None = None
    time: str | None = None
    status: str
    department: str | None = None


class PatientPortalCabinetVisitsItem(BaseModel):
    id: int
    date: str | None = None
    status: str


class PatientPortalCabinetQueueItem(BaseModel):
    number: int
    status: str
    cabinet: str | None = None


class PatientPortalCabinetPayments(BaseModel):
    billed: str
    paid: str
    pending: str
    debt: str
    linked_visit_count: int
    active_queue_count: int


class PatientPortalCabinetReportsItem(BaseModel):
    id: int
    name: str
    ready_at: str | None = None
    status: str


class PatientPortalCabinetPolicy(BaseModel):
    # Round-3 (owner P2): full SSOT payload parity with the Mini App
    # cabinet builder (`medical_details_in_chat` was silently dropped by
    # response filtering before — the JWT portal did not return the same
    # cabinet payload the SSOT contract promises).
    plain_telegram_chat_allowed: bool
    medical_details_in_chat: bool
    pdf_included: bool


class PatientPortalCabinetSummaryResponse(BaseModel):
    scope: PatientPortalScope
    patient: dict[str, str]
    appointments: list[PatientPortalCabinetAppointmentsItem]
    visits: list[PatientPortalCabinetVisitsItem]
    queue: list[PatientPortalCabinetQueueItem]
    payments: PatientPortalCabinetPayments
    reports: list[PatientPortalCabinetReportsItem]
    policy: PatientPortalCabinetPolicy


class PatientPortalFormField(BaseModel):
    key: str
    label: str
    type: str
    required: bool
    max_length: int | None = None
    options: list[str] = []


class PatientPortalFormSubmission(BaseModel):
    id: int
    form_id: str
    schema_version: int
    status: str
    answers: dict[str, Any]
    submitted_at: str | None = None
    updated_at: str | None = None


class PatientPortalFormItem(BaseModel):
    id: str
    title: str
    description: str
    fields: list[PatientPortalFormField]
    submission: PatientPortalFormSubmission | None = None


class PatientPortalFormsPolicy(BaseModel):
    plain_telegram_chat_allowed: bool
    medical_details_in_chat: bool
    storage_enabled: bool


class PatientPortalFormsResponse(BaseModel):
    preview_only: bool
    mutation_allowed: bool
    message_key: str
    scope: PatientPortalScope
    forms: list[PatientPortalFormItem]
    policy: PatientPortalFormsPolicy


# ---------------------------------------------------------------------------
# Principal / scope guards (P1: active user + non-deleted patient)
# ---------------------------------------------------------------------------


def _active_portal_user_audited(resource_type: str, action: str) -> Callable[..., User]:
    """Portal principal factory: ACTIVE Patient user + denied audit rows.

    Round-4 (owner P2): the previous composed dependency
    (`get_current_active_user` + `require_roles("Patient")`) let FastAPI
    refuse a DEACTIVATED account BEFORE the endpoint body ran — the
    `_require_patient_audited` trail writer never executed, so the
    deactivated-but-still-linked card's access attempt left NO row in the
    per-patient PHI trail. Same defect class `require_active_roles`
    (PR #3333) fixed for the control plane: resolve the actor FIRST, write
    the denied row, THEN raise the 403.

    The audit row carries the linked card as the subject when one exists
    (the per-patient trail is keyed by patient) and names the machine
    reason `user_deactivated` with `surface: jwt_portal`.
    """
    role_gate = deps.require_roles("Patient")

    def _dep(
        request: Request,
        db: Session = Depends(deps.get_db),
        current_user: User = Depends(deps.get_current_user),
        _role_gated: User = Depends(role_gate),
    ) -> User:
        # The role gate dependency has already run (and audits its own
        # denials) — everyone reaching this line carries the Patient role,
        # active or not. The active check below closes the deactivated
        # account WITH its audit row (403 fires only after the row lands;
        # the audit writer is non-blocking and never breaks the refusal).
        if not bool(getattr(current_user, "is_active", False)):
            patient = getattr(current_user, "patient", None)
            _log_portal_denied(
                db,
                request=request,
                current_user=current_user,
                resource_type=resource_type,
                action=action,
                reason="user_deactivated",
                subject_patient_id=(
                    int(patient.id) if patient is not None else None
                ),
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"reason": "user_deactivated"},
            )
        return current_user

    # Publish the RBAC policy for the idempotency middleware (Codex R6 #3092
    # convention: the middleware reads `required_roles` off the endpoint's
    # dependency callable — each factory product carries it).
    _dep.required_roles = ("Patient",)  # type: ignore[attr-defined]
    return _dep


def _patient_portal_scope(patient_id: int) -> TelegramMiniAppSessionScope:
    """JWT portal scope: patient identity without Telegram linkage."""
    return TelegramMiniAppSessionScope(
        scope_type="patient",
        telegram_user_id=None,
        telegram_chat_id=None,
        patient_id=int(patient_id),
    )


def _require_patient(current_user: User) -> int:
    patient = current_user.patient
    if patient is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"reason": "patient_profile_required"},
        )
    # P1 (round 2): soft deletion only flips `Patient.is_deleted` — the
    # `User.patient` relationship keeps resolving and `user_id` stays linked.
    # Same SSOT check as the Mini App scope resolver (`patient_link_invalid`):
    # a soft-deleted card must not read PHI or create appointments.
    if getattr(patient, "is_deleted", False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"reason": "patient_link_invalid"},
        )
    return int(patient.id)


def _deny_reason(detail: Any) -> str:
    """Extract the machine-readable failure reason from an HTTPException."""
    if isinstance(detail, dict):
        reason = detail.get("reason")
        if isinstance(reason, str):
            return reason
        message = detail.get("message")
        if isinstance(message, str):
            return message
    if isinstance(detail, str):
        return detail
    return "portal_error"


def _log_portal_denied(
    db: Session,
    *,
    request: Request,
    current_user: User,
    resource_type: str,
    action: str,
    reason: str,
    scope: TelegramMiniAppSessionScope | None = None,
    subject_patient_id: int | None = None,
) -> None:
    """Round-3 (owner P2): denied access rows for the JWT portal.

    Mirrors the Mini App SSOT, which writes `outcome="denied"` rows for
    auth/scope failures: every portal refusal with a resolvable subject
    now leaves a row (soft-deleted card 403, unknown/inactive department
    400, doctor eligibility 404, occupied slot 409), so post-revocation
    access attempts stay visible in the per-patient trail. A refusal with
    NO subject (no linked card at all) is skipped by the audit builder —
    the same SSOT boundary the Mini App auth-failure path applies (the
    PHI trail is keyed by patient).
    """
    log_patient_access(
        db=db,
        scope=scope,
        actor_user=current_user,
        subject_patient_id=subject_patient_id,
        resource_type=resource_type,
        action=action,
        outcome="denied",
        request=request,
        extra_data={"reason": reason, "surface": "jwt_portal"},
    )


def _require_patient_audited(
    db: Session,
    request: Request,
    current_user: User,
    *,
    resource_type: str,
    action: str,
) -> int:
    """`_require_patient` + denied audit rows (round-3 owner P2).

    The 403 `patient_link_invalid` refusal carries the soft-deleted card id
    as the audit subject — the post-revocation attempt is exactly the row
    the per-patient trail must not lose. The 404 (no card) case has no
    subject; the audit builder skips it (SSOT boundary, see
    `_log_portal_denied`).
    """
    try:
        return _require_patient(current_user)
    except HTTPException as exc:
        patient = getattr(current_user, "patient", None)
        subject = (
            int(patient.id)
            if patient is not None and exc.status_code == status.HTTP_403_FORBIDDEN
            else None
        )
        _log_portal_denied(
            db,
            request=request,
            current_user=current_user,
            resource_type=resource_type,
            action=action,
            reason=_deny_reason(exc.detail),
            subject_patient_id=subject,
        )
        raise


# ---------------------------------------------------------------------------
# Error mapping helpers
# ---------------------------------------------------------------------------

# Portal booking extends the Mini App request-shaped reasons with the
# canonical department resolution failures (P1 round 2).
_PORTAL_BOOKING_REQUEST_ERROR_REASONS = frozenset(
    MINI_APP_BOOKING_REQUEST_ERROR_REASONS
) | {"department_unknown", "department_inactive"}


def _booking_scope_status_code(reason: str) -> int:
    # Same public contract as the Mini App booking endpoints: request-shaped
    # problems are 400, identity/scope problems are 403.
    if reason in _PORTAL_BOOKING_REQUEST_ERROR_REASONS:
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


def _resolve_portal_department(
    db: Session, department: str | None, *, for_update: bool = False
) -> Department | None:
    """Resolve a booking `department` to an ACTIVE department row (P1).

    Round-11 (PR #3340 parity): the implementation moved to the shared
    booking-routing service so the Mini App booking endpoints resolve the
    SAME canonical routing context through the SAME helper — one SSOT for
    every protected patient booking surface.

    Round-12 (owner P1, PR #3386 review): ``for_update=True`` — create
    paths whose resolved row IS the final routing context read the row
    ``FOR UPDATE`` so the active check is atomic with the appointment
    INSERT (see ``lock_department_for_booking``).
    """
    return resolve_booking_department(db, department, for_update=for_update)


def _with_resolved_department(
    payload: dict[str, Any], department_row: Department | None
) -> dict[str, Any]:
    """Attach the resolved `department_id` to an echo payload (typed field)."""
    return attach_department_id(payload, department_row)


def _resolve_doctor_routing_department(
    doctor_row: Doctor,
    submitted_department_row: Department | None,
) -> Department:
    """Round-9/10 (owner P1, PR #3340) canonical doctor-department routing.

    Round-11 (PR #3340 parity): the implementation moved to the shared
    booking-routing service (see `_resolve_portal_department`) — the Mini
    App booking endpoints now enforce the identical contract through the
    SAME helper.
    """
    return resolve_doctor_routing_department(doctor_row, submitted_department_row)


# Shared OpenAPI error responses (P2: documented error surface).
_PORTAL_400 = {
    "description": (
        "Request-shaped validation failure (see detail.reason); on keyed "
        "endpoints also an invalid Idempotency-Key header "
        "(code=idempotency_key_invalid)"
    ),
    "model": PatientPortalErrorResponse,
}
_PORTAL_401 = {
    "description": "Missing/invalid JWT or revoked token",
    "model": PatientPortalErrorResponse,
}
_PORTAL_403 = {
    "description": "Role/scope denied (staff role, deactivated user, invalid link)",
    "model": PatientPortalErrorResponse,
}
_PORTAL_404 = {
    "description": "JWT user has no linked Patient profile",
    "model": PatientPortalErrorResponse,
}
_PORTAL_404_BOOKING = {
    "description": (
        "JWT user has no linked Patient profile, or the requested doctor "
        "is not eligible for new appointments (doctor_not_eligible)"
    ),
    "model": PatientPortalErrorResponse,
}
_PORTAL_409 = {
    "description": (
        "Doctor time slot already occupied; or an idempotency conflict "
        "surfaced by the middleware — retry/reconcile decision reads the "
        "top-level code: idempotency_payload_mismatch / "
        "idempotency_in_flight / idempotency_uncertain_outcome / "
        "idempotency_scope_mismatch"
    ),
    "model": PatientPortalErrorResponse,
}
_PORTAL_503 = {
    "description": (
        "Required distributed idempotency coordination is temporarily "
        "unavailable (code=idempotency_unavailable). Non-executing: retry "
        "the SAME Idempotency-Key after recovery"
    ),
    "model": PatientPortalErrorResponse,
}
# Round-7 (owner P2, PR #3340): the preview endpoint is processed by the
# same opt-in middleware whenever it carries an Idempotency-Key (the PR's
# operation-scoping contract exercises exactly that), so its published
# surface must describe the keyed outcomes too. Shared descriptions with a
# preview-specific 409 note (a keyed preview can never hit the slot-409).
_PORTAL_PREVIEW_409 = {
    "description": (
        "Idempotency conflict surfaced by the middleware — retry/reconcile "
        "decision reads the top-level code: idempotency_payload_mismatch / "
        "idempotency_in_flight / idempotency_uncertain_outcome / "
        "idempotency_scope_mismatch. The non-mutating preview has no "
        "endpoint-level slot conflict."
    ),
    "model": PatientPortalErrorResponse,
}


@router.get(
    "/cabinet/summary",
    response_model=PatientPortalCabinetSummaryResponse,
    responses={401: _PORTAL_401, 403: _PORTAL_403, 404: _PORTAL_404},
)
def get_patient_cabinet_summary(
    request: Request,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(
        _active_portal_user_audited("cabinet_summary", "view")
    ),
):
    """Home-screen summary for the JWT patient portal (own scope only)."""
    patient_id = _require_patient_audited(
        db, request, current_user, resource_type="cabinet_summary", action="view"
    )
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


@router.post(
    "/booking/preview",
    response_model=PatientPortalBookingPreviewResponse,
    responses={
        400: _PORTAL_400,
        401: _PORTAL_401,
        403: _PORTAL_403,
        404: _PORTAL_404,
        409: _PORTAL_PREVIEW_409,
        503: _PORTAL_503,
    },
)
def preview_patient_portal_booking(
    request_body: PatientPortalBookingRequest,
    request: Request,
    idempotency_key: str | None = Header(
        None,
        alias="Idempotency-Key",
        min_length=1,
        max_length=128,
        description=(
            "Optional. When sent, the keyed preview is processed by the "
            "idempotency middleware under the preview's OWN operation scope "
            "(a key shared with POST /patients/booking never cross-replays "
            "the two operations). Same key + same payload replays the "
            "preview; same key + changed payload is a 409 "
            "idempotency_payload_mismatch. Oversized keys are a 400 "
            "idempotency_key_invalid."
        ),
    ),
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(_active_portal_user_audited("appointment", "preview")),
):
    """Non-mutating booking preview for the JWT patient portal.

    Round-7 (owner P2): the keyed surface is PUBLISHED — the middleware
    processes every preview that carries an Idempotency-Key (the operation
    -scoping contract depends on it), so 409/503 are real runtime outcomes
    of this endpoint, not undocumented surprises."""
    patient_id = _require_patient_audited(
        db, request, current_user, resource_type="appointment", action="preview"
    )
    scope = _patient_portal_scope(patient_id)
    try:
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
                # Round-9 (owner P2, PR #3340): the past-day check follows
                # the CLINIC's calendar (Asia/Tashkent queue-settings SSOT
                # `clinic_today`), not the UTC host's `date.today()` — on a
                # UTC host between 00:00 and 04:59 Tashkent time the old
                # validation accepted the previous clinic day and let
                # patients create already-past appointments.
                today=clinic_today(db),
            )
        except TelegramMiniAppSessionScopeError as exc:
            raise _raise_scope_error(
                exc, _booking_scope_status_code(exc.reason)
            ) from exc
        # P1 (round 2): the department must resolve (canonical key, active) even
        # for a preview — PR-C2 submits what preview accepted, so a failure here
        # must surface BEFORE the create call.
        # Round-4 (owner P2): resolve the SSOT-NORMALIZED draft value — the
        # builder stripped the raw request string, so resolving the raw one
        # could 400 on " cardio " the preview had already accepted.
        department_row = _resolve_portal_department(db, preview.draft.department)
        # Round-9 (owner P1): a doctor-booking preview returns the SAME
        # routing context create will persist — the doctor's canonical
        # department (or a controlled 400 for a departmentless/mismatched
        # doctor). A missing Doctor row keeps the pre-round-9 preview
        # shape; create's eligibility gate still answers 404 for it.
        if preview.draft.doctor_id is not None:
            doctor_row = (
                db.query(Doctor).filter(Doctor.id == preview.draft.doctor_id).first()
            )
            if doctor_row is not None:
                department_row = _resolve_doctor_routing_department(
                    doctor_row, department_row
                )
    except HTTPException as exc:
        # Round-3 (owner P2): denial leaves a trail row (SSOT parity).
        _log_portal_denied(
            db,
            request=request,
            current_user=current_user,
            resource_type="appointment",
            action="preview",
            reason=_deny_reason(exc.detail),
            scope=scope,
        )
        raise
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
            "department_id": int(department_row.id) if department_row else None,
        },
    )
    return _with_resolved_department(preview.to_response_payload(), department_row)


@router.post(
    "/booking",
    status_code=status.HTTP_201_CREATED,
    response_model=PatientPortalBookingCreatedResponse,
    responses={
        400: _PORTAL_400,
        401: _PORTAL_401,
        403: _PORTAL_403,
        404: _PORTAL_404_BOOKING,
        409: _PORTAL_409,
        503: _PORTAL_503,
    },
)
def create_patient_portal_booking(
    request_body: PatientPortalBookingRequest,
    request: Request,
    idempotency_key: str = Header(
        ...,
        alias="Idempotency-Key",
        min_length=1,
        max_length=128,
        description=(
            "Required. Retries of the SAME booking attempt must reuse the "
            "same key — the middleware replays the committed response instead "
            "of creating a second appointment. Bounded to 128 characters "
            "(longer keys are a 400 idempotency_key_invalid)."
        ),
    ),
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(_active_portal_user_audited("appointment", "create")),
):
    """Create one trusted patient-portal appointment (own scope only).

    Mirrors the Mini App creation contract: same draft validation, same
    per-doctor FOR UPDATE slot reservation taken BEFORE eligibility, same
    409 on occupied slots, same lifecycle eligibility for the doctor.

    Merged-#3340 follow-up (P1): the FINAL routing department is re-read
    with ``populate_existing().with_for_update()`` in THIS transaction and
    its ``active`` re-validated before the INSERT — the persisted routing
    context can no longer reference a department that a concurrently
    committed admin transaction deactivated (or deleted).

    P2 (round 2): the `Idempotency-Key` header is REQUIRED. The global
    idempotency middleware only protects requests that carry a key —
    without a mandated key a lost response + automatic browser retry of a
    date-only/department-only request (no doctor slot lock applies) would
    create duplicate appointments. Same key + same payload replays the
    committed 201; same key + changed payload is a 409.

    P2 (round 3): creation goes through the portal-INTERNAL
    `PatientPortalAppointmentCreate` — the persisted `department_id` is the
    server-resolved FK from `_resolve_portal_department`, never a
    client-owned field (the shared `AppointmentCreate` no longer accepts
    one, closing the legacy-endpoint bypass).
    """
    patient_id = _require_patient_audited(
        db, request, current_user, resource_type="appointment", action="create"
    )
    scope = _patient_portal_scope(patient_id)
    try:
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
                # Round-9 (owner P2): clinic-local calendar — see preview.
                today=clinic_today(db),
            )
        except TelegramMiniAppSessionScopeError as exc:
            raise _raise_scope_error(
                exc, _booking_scope_status_code(exc.reason)
            ) from exc
        # P1 (round 2): resolve BEFORE any mutation — unknown/inactive keys are a
        # 400, never a silently-NULL routing context on the created row.
        # Round-4 (owner P2): SSOT-NORMALIZED draft value (see preview).
        # Round-12 parity note (PR #3386 merge): the resolution stays UP FRONT
        # (the owner-reviewed #3402 order) — the Mini App surface keeps its
        # eligibility-first ordering, the divergence is intentional and
        # flagged for review.
        department_row = _resolve_portal_department(db, preview.draft.department)

        draft_payload = preview.draft.to_appointment_create_payload()

        if preview.draft.doctor_id is not None:
            # Atomic slot reservation — concurrent same-slot writers
            # (web/mobile/telegram) serialize on the doctor row. The lock is
            # taken BEFORE eligibility so a concurrent deactivation must commit
            # first (same ordering as the Mini App create path).
            doctor_row = lock_doctor_for_slot_reservation(db, preview.draft.doctor_id)

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

            if doctor_row is not None:
                # Round-9 (owner P1): the persisted routing context is the
                # doctor's CANONICAL department — resolved AFTER eligibility
                # so the established doctor_not_eligible contract is
                # unchanged, and BEFORE the slot check (a routing refusal
                # never creates anything). The submitted department either
                # matches the doctor's own or the request is a controlled
                # 400; a departmentless doctor is an explicit refusal, not a
                # NULL department_id.
                department_row = _resolve_doctor_routing_department(
                    doctor_row, department_row
                )

        # Merged-#3340 follow-up (owner P1): the final routing department is
        # re-read under the booking row lock and `active` re-validated
        # ATOMICALLY with the INSERT below. The plain resolves above guard
        # only the SNAPSHOT they observed — an admin deactivation (or a
        # delete) committing between that snapshot and this transaction
        # previously produced an appointment routed at an INACTIVE
        # department. The lock is taken for BOTH shapes (submitted-key and
        # doctor-canonical), AFTER the routing context is final and BEFORE
        # the occupancy check — a department refusal (400) still outranks
        # a slot conflict (409), and the lock is held until
        # `appointment_crud.create` commits, so a concurrent
        # deactivate/delete serializes BEHIND this booking.
        if department_row is not None:
            department_row = lock_department_for_booking(db, department_row)

        if preview.draft.doctor_id is not None and preview.draft.appointment_time:
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
    except HTTPException as exc:
        # Round-3 (owner P2): denial leaves a trail row (SSOT parity) —
        # unknown/inactive department 400, doctor eligibility 404, occupied
        # slot 409, scope refusals. Successes audit below as before.
        _log_portal_denied(
            db,
            request=request,
            current_user=current_user,
            resource_type="appointment",
            action="create",
            reason=_deny_reason(exc.detail),
            scope=scope,
        )
        raise

    appointment_create_payload = dict(draft_payload)
    appointment_create_payload.pop("department", None)
    if department_row is not None:
        # P1 (round 2): persist the routing context — `department` as a raw
        # string is display metadata; `departments.id` is what the schedule,
        # queues and department-schedule reads actually join on.
        appointment_create_payload["department_id"] = int(department_row.id)
    # Round-3 (owner P2): portal-INTERNAL schema — the ONLY place
    # `department_id` can enter an Appointment, and only from the
    # server-resolved department row above.
    appointment_in = appointment_schemas.PatientPortalAppointmentCreate(
        **appointment_create_payload
    )
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
            "department_id": int(department_row.id) if department_row else None,
        },
    )

    return {
        "created": True,
        "appointment_id": int(appointment.id),
        "preview": _with_resolved_department(
            preview.to_response_payload(), department_row
        ),
    }


@router.get(
    "/forms",
    response_model=PatientPortalFormsResponse,
    responses={400: _PORTAL_400, 401: _PORTAL_401, 403: _PORTAL_403, 404: _PORTAL_404},
)
def get_patient_portal_forms(
    request: Request,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(_active_portal_user_audited("patient_form", "view")),
):
    """Read-only protected forms metadata + saved answers for the JWT portal.

    Submissions remain Telegram-only in this PR (see module docstring).
    """
    patient_id = _require_patient_audited(
        db, request, current_user, resource_type="patient_form", action="view"
    )
    scope = _patient_portal_scope(patient_id)
    try:
        try:
            forms_preview = build_telegram_mini_app_patient_forms_preview(
                db,
                scope,
                patient_id=patient_id,
            )
        except TelegramMiniAppSessionScopeError as exc:
            raise _raise_scope_error(exc, _forms_scope_status_code(exc.reason)) from exc
    except HTTPException as exc:
        # Round-3 (owner P2): denial leaves a trail row (SSOT parity).
        _log_portal_denied(
            db,
            request=request,
            current_user=current_user,
            resource_type="patient_form",
            action="view",
            reason=_deny_reason(exc.detail),
            scope=scope,
        )
        raise
    log_patient_access(
        db=db,
        scope=scope,
        resource_type="patient_form",
        action="view",
        outcome="success",
        request=request,
    )
    return forms_preview.to_response_payload()
