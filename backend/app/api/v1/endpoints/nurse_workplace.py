"""NURSE-V2 N2-2 — admin endpoints for nurse workplace assignments.

Scope item 4 of the owner design-GO (2026-09-19): the admin/backend
contract for CREATE / READ / DEACTIVATE of NurseWorkplaceAssignment
rows. Admin-only, and — review P1 (PR #3333) — gated by
require_active_roles("Admin"): the control plane fails closed for a
DEACTIVATED Admin holding an unexpired JWT (403, no DB writes).
Superuser bypasses the role check per the standard require_roles
contract (an active superuser only). No serving endpoints here —
call-next / start / complete-service are N2-3, the tablet surface is
N2-5.

Review P2 (PR #3333): the domain-error contract (400/404/409) is
published on the FastAPI decorators via NurseWorkplaceErrorDetail so
backend/openapi.json and the generated frontend api.ts describe the
responses the service actually returns.

Review P2, round 2 (PR #3333): the auth-error contract (401/403) is
published too — on ALL FOUR operations. The runtime already proves
both codes (test_nurse_workplace_endpoints.py: no JWT -> 401, wrong
role -> 403, deactivated Admin with an unexpired JWT -> 403 via
require_active_roles); the generated clients must not silently drop
them. Same typed {"detail": ...} body (NurseWorkplaceErrorDetail) —
the shape FastAPI's HTTPException returns for the auth failures.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_active_roles
from app.models.user import User
from app.schemas.nurse_workplace import (
    NurseWorkplaceAssignmentCreateRequest,
    NurseWorkplaceAssignmentListResponse,
    NurseWorkplaceAssignmentResponse,
    NurseWorkplaceErrorDetail,
)
from app.services.nurse_workplace_api_service import (
    NurseWorkplaceApiDomainError,
    NurseWorkplaceApiService,
)

router = APIRouter()

_BASE_PATH = "/admin/nurse-workplace-assignments"


def _to_response(data: dict) -> NurseWorkplaceAssignmentResponse:
    return NurseWorkplaceAssignmentResponse(**data)


# Review P2 round 2 (PR #3333): the shared auth-error contract of the
# whole control plane. 401 — JWT missing/invalid (get_current_user);
# 403 — not Admin (role gate), or a DEACTIVATED Admin / superuser holding
# an unexpired JWT (require_active_roles fails closed). Published on every
# operation below so backend/openapi.json and the generated frontend
# api.ts describe the auth failures the runtime actually returns.
_AUTH_ERROR_RESPONSES = {
    401: {
        "model": NurseWorkplaceErrorDetail,
        "description": "Требуется аутентификация (JWT отсутствует или недействителен)",
    },
    403: {
        "model": NurseWorkplaceErrorDetail,
        "description": (
            "Только активная роль Admin: не Admin, либо деактивированный "
            "(супер)админ с ещё действующим JWT"
        ),
    },
}


@router.post(
    _BASE_PATH,
    response_model=NurseWorkplaceAssignmentResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        400: {
            "model": NurseWorkplaceErrorDetail,
            "description": (
                "Целевой пользователь не Nurse / деактивирован, либо "
                "QueueResource неактивен"
            ),
        },
        404: {
            "model": NurseWorkplaceErrorDetail,
            "description": "Пользователь или QueueResource не найден",
        },
        409: {
            "model": NurseWorkplaceErrorDetail,
            "description": (
                "Активное назначение для пары (user, queue_resource) уже существует"
            ),
        },
        **_AUTH_ERROR_RESPONSES,
    },
)
def create_nurse_workplace_assignment(
    payload: NurseWorkplaceAssignmentCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_active_roles("Admin")),
):
    """Assign a Nurse User to a QueueResource workplace (D2 FINAL).

    404 — referenced user/resource not found; 400 — the user is not an
    active Nurse or the resource is inactive; 409 — an active
    assignment for the same (user, resource) pair already exists;
    401/403 — the control-plane auth contract (see
    _AUTH_ERROR_RESPONSES).
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


@router.get(
    _BASE_PATH,
    response_model=NurseWorkplaceAssignmentListResponse,
    responses={**_AUTH_ERROR_RESPONSES},
)
def list_nurse_workplace_assignments(
    user_id: int | None = Query(None, description="Filter by target Nurse user"),
    queue_resource_id: int | None = Query(None, description="Filter by QueueResource"),
    active: bool | None = Query(None, description="Filter by is_active (default: all)"),
    limit: int = Query(100, ge=1, le=500, description="Page size"),
    offset: int = Query(0, ge=0, description="Page offset"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_active_roles("Admin")),
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
    responses={
        404: {
            "model": NurseWorkplaceErrorDetail,
            "description": "Назначение не найдено",
        },
        **_AUTH_ERROR_RESPONSES,
    },
)
def get_nurse_workplace_assignment(
    assignment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_active_roles("Admin")),
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
    responses={
        404: {
            "model": NurseWorkplaceErrorDetail,
            "description": "Назначение не найдено",
        },
        409: {
            "model": NurseWorkplaceErrorDetail,
            "description": "Назначение уже деактивировано",
        },
        **_AUTH_ERROR_RESPONSES,
    },
)
def deactivate_nurse_workplace_assignment(
    assignment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_active_roles("Admin")),
):
    """Deactivate an assignment (the row stays as history; D2 FINAL).

    404 — assignment not found; 409 — already inactive. A new active row
    for the same (user, resource) pair may be created afterwards;
    401/403 — the control-plane auth contract (see
    _AUTH_ERROR_RESPONSES).
    """
    try:
        data = NurseWorkplaceApiService(db).deactivate_assignment(assignment_id)
    except NurseWorkplaceApiDomainError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    return _to_response(data)
