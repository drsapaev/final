"""Repository helpers for group_permissions endpoints."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from app.models.role_permission import Permission, Role, UserGroup, UserPermissionOverride
from app.models.user import User


class GroupPermissionsApiRepository:
    """Encapsulates ORM operations used by group permissions API."""

    def __init__(self, db: Session):
        self.db = db

    def get_user(self, user_id: int) -> User | None:
        return self.db.query(User).filter(User.id == user_id).first()

    def list_groups(
        self,
        *,
        active_only: bool,
        group_type: str | None,
        limit: int,
    ) -> list[UserGroup]:
        query = self.db.query(UserGroup)
        if active_only:
            query = query.filter(UserGroup.is_active.is_(True))
        if group_type:
            query = query.filter(UserGroup.group_type == group_type)
        return query.limit(limit).all()

    def list_roles(
        self,
        *,
        active_only: bool,
        include_system: bool,
        limit: int,
    ) -> list[Role]:
        query = self.db.query(Role)
        if active_only:
            query = query.filter(Role.is_active.is_(True))
        if not include_system:
            query = query.filter(Role.is_system.is_(False))
        return query.limit(limit).all()

    def list_permissions(
        self,
        *,
        active_only: bool,
        category: str | None,
        limit: int,
    ) -> list[Permission]:
        query = self.db.query(Permission)
        if active_only:
            query = query.filter(Permission.is_active.is_(True))
        if category:
            query = query.filter(Permission.category == category)
        return query.limit(limit).all()

    def get_permission(self, permission_id: int) -> Permission | None:
        return self.db.query(Permission).filter(Permission.id == permission_id).first()

    def get_active_override(self, *, user_id: int, permission_id: int) -> UserPermissionOverride | None:
        return (
            self.db.query(UserPermissionOverride)
            .filter(
                UserPermissionOverride.user_id == user_id,
                UserPermissionOverride.permission_id == permission_id,
                UserPermissionOverride.is_active.is_(True),
            )
            .first()
        )

    def create_override(
        self,
        *,
        user_id: int,
        permission_id: int,
        override_type: str,
        reason: str | None,
        expires_at: datetime | None,
        granted_by: int,
    ) -> UserPermissionOverride:
        override = UserPermissionOverride(
            user_id=user_id,
            permission_id=permission_id,
            override_type=override_type,
            reason=reason,
            expires_at=expires_at,
            granted_by=granted_by,
        )
        self.db.add(override)
        self.db.commit()
        self.db.refresh(override)
        return override

    def rollback(self) -> None:
        self.db.rollback()

