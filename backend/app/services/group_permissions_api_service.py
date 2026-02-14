"""Service layer for group_permissions endpoints."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.repositories.group_permissions_api_repository import GroupPermissionsApiRepository
from app.services.group_permissions_service import get_group_permissions_service


@dataclass
class GroupPermissionsApiDomainError(Exception):
    status_code: int
    detail: str


class GroupPermissionsApiService:
    """Builds API payloads for group/role/permission management endpoints."""

    def __init__(
        self,
        db: Session,
        repository: GroupPermissionsApiRepository | None = None,
        permission_service=None,
    ):
        self.db = db
        self.repository = repository or GroupPermissionsApiRepository(db)
        self.permission_service = permission_service or get_group_permissions_service()

    def get_user_permissions_payload(self, *, user_id: int, use_cache: bool) -> dict:
        user = self.repository.get_user(user_id)
        if not user:
            raise GroupPermissionsApiDomainError(404, "Пользователь не найден")

        permissions = self.permission_service.get_user_permissions(self.db, user_id, use_cache)
        roles = [role.name for role in user.roles if role.is_active]
        groups = [group.name for group in user.groups if group.is_active]

        return {
            "user_id": user_id,
            "username": user.username,
            "permissions": list(permissions),
            "permissions_count": len(permissions),
            "roles": roles,
            "groups": groups,
        }

    def list_groups_payload(
        self,
        *,
        active_only: bool,
        group_type: str | None,
        limit: int,
    ) -> list[dict]:
        groups = self.repository.list_groups(
            active_only=active_only,
            group_type=group_type,
            limit=limit,
        )
        return [
            {
                "id": group.id,
                "name": group.name,
                "display_name": group.display_name,
                "description": group.description,
                "group_type": group.group_type,
                "is_active": group.is_active,
                "users_count": len([u for u in group.users if u.is_active]),
                "roles_count": len([r for r in group.roles if r.is_active]),
            }
            for group in groups
        ]

    def list_roles_payload(
        self,
        *,
        active_only: bool,
        include_system: bool,
        limit: int,
    ) -> list[dict]:
        roles = self.repository.list_roles(
            active_only=active_only,
            include_system=include_system,
            limit=limit,
        )
        return [
            {
                "id": role.id,
                "name": role.name,
                "display_name": role.display_name,
                "description": role.description,
                "level": role.level,
                "is_active": role.is_active,
                "is_system": role.is_system,
                "permissions_count": len([p for p in role.permissions if p.is_active]),
            }
            for role in roles
        ]

    def list_permissions_payload(
        self,
        *,
        active_only: bool,
        category: str | None,
        limit: int,
    ) -> list[dict]:
        permissions = self.repository.list_permissions(
            active_only=active_only,
            category=category,
            limit=limit,
        )
        return [
            {
                "id": permission.id,
                "name": permission.name,
                "codename": permission.codename,
                "description": permission.description,
                "category": permission.category,
                "is_active": permission.is_active,
            }
            for permission in permissions
        ]

    def create_permission_override(
        self,
        *,
        user_id: int,
        permission_id: int,
        override_type: str,
        reason: str | None,
        expires_hours: int | None,
        granted_by_user_id: int,
        granted_by_username: str,
    ) -> dict:
        user = self.repository.get_user(user_id)
        if not user:
            raise GroupPermissionsApiDomainError(404, "Пользователь не найден")

        permission = self.repository.get_permission(permission_id)
        if not permission:
            raise GroupPermissionsApiDomainError(404, "Разрешение не найдено")

        existing = self.repository.get_active_override(
            user_id=user_id,
            permission_id=permission_id,
        )
        if existing:
            raise GroupPermissionsApiDomainError(
                400,
                "Переопределение для этого разрешения уже существует",
            )

        expires_at = None
        if expires_hours:
            expires_at = datetime.utcnow() + timedelta(hours=expires_hours)

        override = self.repository.create_override(
            user_id=user_id,
            permission_id=permission_id,
            override_type=override_type,
            reason=reason,
            expires_at=expires_at,
            granted_by=granted_by_user_id,
        )

        self.permission_service._clear_user_cache(user_id)

        return {
            "success": True,
            "message": (
                f"Переопределение разрешения '{permission.name}' "
                f"создано для пользователя '{user.username}'"
            ),
            "override_id": override.id,
            "override_type": override_type,
            "expires_at": expires_at.isoformat() if expires_at else None,
            "created_by": granted_by_username,
            "created_at": override.created_at.isoformat(),
        }

    def rollback(self) -> None:
        self.repository.rollback()
