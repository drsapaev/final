"""Service layer for admin users endpoint."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.repositories.admin_users_repository import AdminUsersRepository


class AdminUsersService:
    """Builds admin user payloads from repository data."""

    def __init__(
        self,
        db: Session,
        repository: AdminUsersRepository | None = None,
    ):
        self.repository = repository or AdminUsersRepository(db)

    def list_users(self) -> list[dict]:
        users = self.repository.list_users()
        return [
            {
                "id": u.id,
                "username": u.username,
                "full_name": u.full_name,
                "email": u.email,
                "role": getattr(u, "role", None),
                "is_active": getattr(u, "is_active", True),
            }
            for u in users
        ]
