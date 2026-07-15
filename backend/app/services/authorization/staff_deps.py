"""
FastAPI dependencies for staff authorization (M5.2).

Usage:
    from app.services.authorization.staff_deps import require_permission

    @router.get("/admin/users")
    def list_users(
        current_user: User = Depends(get_current_user),
        _authz: None = Depends(require_permission("users:manage")),
    ):
        ...

    # Or inline:
    from app.services.authorization.staff import staff_authorization_service
    if not staff_authorization_service.can_read_patient(current_user, patient_id):
        raise HTTPException(status_code=403, detail="Access denied")
"""
from __future__ import annotations

from typing import Callable

from fastapi import Depends, HTTPException, status

from app.api import deps
from app.models.user import User
from app.services.authorization.staff import (
    StaffAuthorizationError,
    StaffAuthorizationService,
    staff_authorization_service,
)


def require_permission(permission: str) -> Callable:
    """FastAPI dependency factory: require a specific permission.

    Usage:
        @router.delete("/admin/users/{id}")
        def delete_user(
            user_id: int,
            current_user: User = Depends(get_current_user),
            _authz: None = Depends(require_permission("users:manage")),
        ):
            ...

    Raises 403 if the current user lacks the permission.
    """
    def _check(current_user: User = Depends(deps.get_current_user)) -> None:
        if not staff_authorization_service.has_permission(current_user, permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"reason": "access_denied", "required_permission": permission},
            )

    return _check


def require_can_read_appointment(
    current_user: User = Depends(deps.get_current_user),
) -> User:
    """Dependency: require appointment:read permission."""
    staff_authorization_service.require_permission(current_user, "appointment:read")
    return current_user


def require_can_write_appointment(
    current_user: User = Depends(deps.get_current_user),
) -> User:
    """Dependency: require appointment:write permission."""
    staff_authorization_service.require_permission(current_user, "appointment:write")
    return current_user


def require_can_read_patient(
    current_user: User = Depends(deps.get_current_user),
) -> User:
    """Dependency: require patient:read permission."""
    staff_authorization_service.require_permission(current_user, "patient:read")
    return current_user


def require_can_write_patient(
    current_user: User = Depends(deps.get_current_user),
) -> User:
    """Dependency: require patient:write permission."""
    staff_authorization_service.require_permission(current_user, "patient:write")
    return current_user


def require_can_read_emr(
    current_user: User = Depends(deps.get_current_user),
) -> User:
    """Dependency: require emr:read permission."""
    staff_authorization_service.require_permission(current_user, "emr:read")
    return current_user


def require_can_write_emr(
    current_user: User = Depends(deps.get_current_user),
) -> User:
    """Dependency: require emr:write permission."""
    staff_authorization_service.require_permission(current_user, "emr:write")
    return current_user


def require_can_manage_queue(
    current_user: User = Depends(deps.get_current_user),
) -> User:
    """Dependency: require queue:manage permission."""
    staff_authorization_service.require_permission(current_user, "queue:manage")
    return current_user


def require_can_manage_users(
    current_user: User = Depends(deps.get_current_user),
) -> User:
    """Dependency: require users:manage permission."""
    staff_authorization_service.require_permission(current_user, "users:manage")
    return current_user


def require_can_manage_payments(
    current_user: User = Depends(deps.get_current_user),
) -> User:
    """Dependency: require payments:manage permission."""
    staff_authorization_service.require_permission(current_user, "payments:manage")
    return current_user


def require_can_export_data(
    current_user: User = Depends(deps.get_current_user),
) -> User:
    """Dependency: require export:data permission."""
    staff_authorization_service.require_permission(current_user, "export:data")
    return current_user
