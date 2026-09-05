"""
API endpoints for Role management
"""
import logging
from typing import NoReturn

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.core.roles import is_internal_only_role_spelling, is_retired_role_spelling
from app.models.user import User
from app.schemas.role import (
    RoleCreate,
    RoleListResponse,
    RoleOptionResponse,
    RoleOptionsListResponse,
    RoleResponse,
    RoleUpdate,
)
from app.services.roles_api_service import RolesApiDomainError, RolesApiService

logger = logging.getLogger(__name__)

router = APIRouter()
ROLES_PUBLIC_ERROR = "Internal server error"


def _raise_roles_internal_error(operation: str, exc: Exception) -> NoReturn:
    logger.warning(
        "Roles endpoint failed operation=%s error_type=%s",
        operation,
        type(exc).__name__,
    )
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail=ROLES_PUBLIC_ERROR,
    ) from exc


@router.get("/", response_model=RoleListResponse)
async def get_roles(
    is_active: bool | None = Query(None, description="Filter by active status"),
    is_system: bool | None = Query(None, description="Filter by system roles"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get all roles.

    Returns a list of all roles, optionally filtered by active/system status.
    """
    try:
        roles = RolesApiService(db).list_roles(
            is_active=is_active,
            is_system=is_system,
        )

        return RoleListResponse(
            roles=[RoleResponse.model_validate(role) for role in roles],
            total=len(roles)
        )
    except Exception as e:
        _raise_roles_internal_error("get_roles", e)


@router.get("/options", response_model=RoleOptionsListResponse)
async def get_role_options(
    include_all: bool = Query(False, description="Include 'All roles' option for filters"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get roles as options for dropdowns.

    Returns simplified role list with value/label pairs.
    Used for role selection in forms and filters.
    """
    try:
        roles = RolesApiService(db).list_active_roles()

        options = []

        # Add "All roles" option for filters if requested
        if include_all:
            options.append(RoleOptionResponse(value="", label="Все роли"))

        # Add each role
        # M-2b (Codex review P2 follow-up on #3049): retired RBAC spellings
        # never surface as selectable options — a legacy/compatible-deployment
        # catalog row named 'Manager'/'Receptionist' must not leak into the
        # UserModal dropdown mirror (the user-management write schema would
        # 422 any submission with it anyway; the options list is the UI trust
        # boundary). Case-insensitive, per the core/roles.py SSOT set.
        for role in roles:
            if is_retired_role_spelling(role.name):
                continue
            # QD-1.1 (queue resource role cleanup): internal-only sentinel
            # spellings are never selectable options — the 'Resource' rows
            # provisioned by 0055/0056 for doctorless queues are structural
            # non-logins, not user-management vocabulary.
            if is_internal_only_role_spelling(role.name):
                continue
            options.append(RoleOptionResponse(
                value=role.name,
                label=role.display_name
            ))

        return RoleOptionsListResponse(options=options)
    except Exception as e:
        _raise_roles_internal_error("get_role_options", e)


@router.get("/{role_id}", response_model=RoleResponse)
async def get_role(
    role_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a specific role by ID."""
    try:
        role = RolesApiService(db).get_role_or_error(role_id)
        return RoleResponse.model_validate(role)
    except RolesApiDomainError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc


@router.post("/", response_model=RoleResponse, status_code=status.HTTP_201_CREATED)
async def create_role(
    role_data: RoleCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Create a new role.

    Only Admin users can create roles.
    """
    # Check admin permission
    if current_user.role != "Admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Только администраторы могут создавать роли"
        )

    try:
        role = RolesApiService(db).create_role(role_data.model_dump())
        return RoleResponse.model_validate(role)
    except RolesApiDomainError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    except Exception as e:
        _raise_roles_internal_error("create_role", e)


@router.put("/{role_id}", response_model=RoleResponse)
async def update_role(
    role_id: int,
    role_data: RoleUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Update a role.

    Only Admin users can update roles.
    System roles have limited editability.
    """
    # Check admin permission
    if current_user.role != "Admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Только администраторы могут изменять роли"
        )

    try:
        role = RolesApiService(db).update_role(
            role_id=role_id,
            update_data=role_data.model_dump(exclude_unset=True),
        )
        return RoleResponse.model_validate(role)
    except RolesApiDomainError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    except Exception as e:
        _raise_roles_internal_error("update_role", e)


@router.delete("/{role_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
async def delete_role(
    role_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Delete a role.

    Only Admin users can delete roles.
    System roles cannot be deleted.
    """
    # Check admin permission
    if current_user.role != "Admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Только администраторы могут удалять роли"
        )

    try:
        RolesApiService(db).delete_role(role_id=role_id)
    except RolesApiDomainError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    except Exception as e:
        _raise_roles_internal_error("delete_role", e)
