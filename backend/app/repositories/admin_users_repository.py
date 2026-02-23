"""Repository helpers for admin users endpoint."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.user import User


class AdminUsersRepository:
    """Encapsulates user list query for admin endpoints."""

    def __init__(self, db: Session):
        self.db = db

    def list_users(self) -> list[User]:
        stmt = select(User).order_by(User.id.asc())
        return self.db.execute(stmt).scalars().all()
