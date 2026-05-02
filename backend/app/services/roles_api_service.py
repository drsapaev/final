"""Service layer for roles endpoints."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.repositories.roles_api_repository import RolesApiRepository


@dataclass
class RolesApiDomainError(Exception):
    status_code: int
    detail: str


class RolesApiService:
    """Handles role endpoint business rules and persistence."""

    def __init__(
        self,
        db: Session,
        repository: RolesApiRepository | None = None,
    ):
        self.repository = repository or RolesApiRepository(db)

    def list_roles(self, *, is_active: bool | None, is_system: bool | None):
        return self.repository.list_roles(is_active=is_active, is_system=is_system)

    def list_active_roles(self):
        return self.repository.list_active_roles()

    def get_role_or_error(self, role_id: int):
        role = self.repository.get_role(role_id)
        if not role:
            raise RolesApiDomainError(404, "Роль не найдена")
        return role

    def create_role(self, role_data: dict):
        existing = self.repository.get_role_by_name(role_data["name"])
        if existing:
            raise RolesApiDomainError(
                400,
                f"Роль с именем '{role_data['name']}' уже существует",
            )

        try:
            return self.repository.create_role(role_data)
        except Exception:
            self.repository.rollback()
            raise

    def update_role(self, *, role_id: int, update_data: dict):
        role = self.get_role_or_error(role_id)

        if role.is_system:
            allowed_fields = {"display_name", "description"}
            for field in update_data:
                if field not in allowed_fields:
                    raise RolesApiDomainError(
                        400,
                        f"Нельзя изменить поле '{field}' для системной роли",
                    )

        for field, value in update_data.items():
            setattr(role, field, value)

        try:
            return self.repository.save_role(role)
        except Exception:
            self.repository.rollback()
            raise

    def delete_role(self, *, role_id: int) -> None:
        role = self.get_role_or_error(role_id)
        if role.is_system:
            raise RolesApiDomainError(400, "Нельзя удалить системную роль")

        try:
            self.repository.delete_role(role)
        except Exception:
            self.repository.rollback()
            raise
