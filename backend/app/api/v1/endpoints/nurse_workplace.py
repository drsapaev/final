"""NURSE-V2 N2-2 — admin endpoints for nurse workplace assignments.

Scope item 4 of the owner design-GO (2026-09-19): the admin/backend
contract for CREATE / READ / DEACTIVATE of NurseWorkplaceAssignment
rows. Admin-only (require_roles("Admin")); superuser bypasses per the
standard require_roles contract. No serving endpoints here — call-next
/ start / complete-service are N2-3, the tablet surface is N2-5.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_roles
from app.models.user import User
from app.schemas.nurse_workplace import (
    NurseWorkplaceAssignmentCreateRequest,
    NurseWorkplaceAssignmentListResponse,
    NurseWorkplaceAssignmentResponse,
)
from app.services.nurse_workplace_api_service import (
    NurseWorkplaceApiDomainError,
    NurseWorkplaceApiService,
)

router = APIRouter()

_BASE_PATH = "/admin/nurse-workplace-assignments"


def _to_response(data: dict) -> NurseWorkplaceAssignmentResponse:
    return NurseWorkplaceAssignmentResponse(**data)


@router.post(
    _BASE_PATH,
    response_model=NurseWorkplaceAssignmentResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_nurse_workplace_assignment(
    payload: NurseWorkplaceAssignmentCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin")),
):
    """Assign a Nurse User to a QueueResource workplace (D2 FINAL).

    404 — referenced user/resource not found; 400 — the user is not an
    active Nurse or the resource is inactive; 409 — an active
    assignment for the same (user, resource) pair already exists.
    """
    try:
        data = NurseWorkplaceApiService(db).create_assignment(
            user_id=payload.user_id,
            queue_resource_id=payload.queue_resource_id,
            cabinet_override=payload.cabinet_override,
        )
    except NurseWorkplaceApiDomainError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    return _to_response(data)


@router.get(_BASE_PATH, response_model=NurseWorkplaceAssignmentListResponse)
def list_nurse_workplace_assignments(
    user_id: int | None = Query(None, description="Filter by target Nurse user"),
    queue_resource_id: int | None = Query(None, description="Filter by QueueResource"),
    active: bool | None = Query(None, description="Filter by is_active (default: all)"),
    limit: int = Query(100, ge=1, le=500, description="Page size"),
    offset: int = Query(0, ge=0, description="Page offset"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin")),
):
    """Paged list of workplace assignments (active first, newest first)."""
    items, total = NurseWorkplaceApiService(db).list_assignments(
        user_id=user_id,
        queue_resource_id=queue_resource_id,
        active=active,
        limit=limit,
        offset=offset,
    )
    return NurseWorkplaceAssignmentListResponse(
        items=[_to_response(item) for item in items], total=total
    )


@router.get(
    f"{_BASE_PATH}/{{assignment_id}}",
    response_model=NurseWorkplaceAssignmentResponse,
)
def get_nurse_workplace_assignment(
    assignment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin")),
):
    """Read a single workplace assignment by id (404 when missing)."""
    try:
        data = NurseWorkplaceApiService(db).get_assignment(assignment_id)
    except NurseWorkplaceApiDomainError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    return _to_response(data)


@router.post(
    f"{_BASE_PATH}/{{assignment_id}}/deactivate",
    response_model=NurseWorkplaceAssignmentResponse,
)
def deactivate_nurse_workplace_assignment(
    assignment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin")),
):
    """Deactivate an assignment (the row stays as history; D2 FINAL).

    404 — assignment not found; 409 — already inactive. A new active row
    for the same (user, resource) pair may be created afterwards.
    """
    try:
        data = NurseWorkplaceApiService(db).deactivate_assignment(assignment_id)
    except NurseWorkplaceApiDomainError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    return _to_response(data)
