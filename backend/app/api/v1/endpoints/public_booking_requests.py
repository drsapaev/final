"""Admin/Registrar queue for public booking requests."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_active_roles
from app.models.user import User
from app.schemas.public_booking_request import (
    PublicBookingRequestAction,
    PublicBookingRequestErrorOut,
    PublicBookingRequestPatientOut,
    PublicBookingRequestStaffListOut,
    PublicBookingRequestStatus,
)
from app.services.patient_access_audit import log_patient_access
from app.services.public_booking_request_service import (
    PublicBookingRequestError,
    PublicBookingRequestService,
)

router = APIRouter()


def _raise_request_error(exc: PublicBookingRequestError) -> None:
    raise HTTPException(
        status_code=exc.status_code,
        detail={"code": exc.code},
        headers={"Cache-Control": "no-store"},
    ) from exc


def _audit_staff_request(
    *,
    db: Session,
    request: Request,
    actor: User,
    result: PublicBookingRequestPatientOut,
    action: str,
) -> None:
    log_patient_access(
        db=db,
        actor_user=actor,
        subject_patient_id=result.patient_id,
        resource_type="public_booking_request",
        resource_id=str(result.id),
        action=action,
        outcome="success",
        request=request,
    )


@router.get(
    "",
    response_model=PublicBookingRequestStaffListOut,
    responses={
        401: {"description": "Authentication required."},
        403: {"description": "Admin or Registrar role required."},
    },
    operation_id="staff_list_public_booking_requests",
    summary="List public booking requests for staff review",
)
def list_public_booking_requests(
    request: Request,
    response: Response,
    status_filter: Annotated[
        PublicBookingRequestStatus | None,
        Query(alias="status"),
    ] = PublicBookingRequestStatus.PENDING,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_active_roles("Admin", "Registrar")),
) -> PublicBookingRequestStaffListOut:
    response.headers["Cache-Control"] = "no-store"
    items = PublicBookingRequestService(db).list_for_staff(
        status_filter=status_filter.value if status_filter is not None else None,
        limit=limit,
        offset=offset,
    )
    for item in items:
        _audit_staff_request(
            db=db,
            request=request,
            actor=current_user,
            result=item,
            action="view",
        )
    return PublicBookingRequestStaffListOut(items=items)


@router.post(
    "/{request_id}/request-new-time",
    response_model=PublicBookingRequestPatientOut,
    responses={
        401: {"description": "Authentication required."},
        403: {"description": "Admin or Registrar role required."},
        404: {"model": PublicBookingRequestErrorOut},
        409: {"model": PublicBookingRequestErrorOut},
    },
    operation_id="staff_request_new_public_booking_time",
    summary="Ask the patient to choose another time without reserving one",
)
def request_new_public_booking_time(
    request_id: UUID,
    body: PublicBookingRequestAction,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_active_roles("Admin", "Registrar")),
) -> PublicBookingRequestPatientOut:
    response.headers["Cache-Control"] = "no-store"
    try:
        result = PublicBookingRequestService(db).request_new_time_for_staff(
            request_id=request_id,
            actor_user_id=current_user.id,
            expected_version=body.expected_version,
        )
    except PublicBookingRequestError as exc:
        _raise_request_error(exc)
    _audit_staff_request(
        db=db,
        request=request,
        actor=current_user,
        result=result,
        action="request_new_time",
    )
    return result


@router.post(
    "/{request_id}/reject",
    response_model=PublicBookingRequestPatientOut,
    responses={
        401: {"description": "Authentication required."},
        403: {"description": "Admin or Registrar role required."},
        404: {"model": PublicBookingRequestErrorOut},
        409: {"model": PublicBookingRequestErrorOut},
    },
    operation_id="staff_reject_public_booking_request",
    summary="Reject a pending public booking request",
)
def reject_public_booking_request(
    request_id: UUID,
    body: PublicBookingRequestAction,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_active_roles("Admin", "Registrar")),
) -> PublicBookingRequestPatientOut:
    response.headers["Cache-Control"] = "no-store"
    try:
        result = PublicBookingRequestService(db).reject_for_staff(
            request_id=request_id,
            actor_user_id=current_user.id,
            expected_version=body.expected_version,
        )
    except PublicBookingRequestError as exc:
        _raise_request_error(exc)
    _audit_staff_request(
        db=db,
        request=request,
        actor=current_user,
        result=result,
        action="reject",
    )
    return result
