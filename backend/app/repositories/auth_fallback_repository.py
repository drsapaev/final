"""Repository helpers for fallback auth endpoints."""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models.user import User


class AuthFallbackRepository:
    """Encapsulates direct user lookups for simplified auth endpoints."""

    def __init__(self, db: Session):
        self.db = db

    def get_user_credentials_row(self, *, username: str):
        stmt = text(
            """
            SELECT id, username, email, full_name, role, is_active, is_superuser, hashed_password
            FROM users
            WHERE username = :username OR email = :username
            """
        )
        result = self.db.execute(stmt, {"username": username})
        return result.fetchone()

    def get_user_model(self, *, username: str) -> User | None:
        return (
            self.db.query(User)
            .filter((User.username == username) | (User.email == username))
            .first()
        )

