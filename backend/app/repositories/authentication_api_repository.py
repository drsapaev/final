"""Repository helpers for authentication endpoints."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.authentication import UserSession


class AuthenticationApiRepository:
    """Encapsulates ORM operations used directly by authentication endpoints."""

    def __init__(self, db: Session):
        self.db = db

    def commit(self) -> None:
        self.db.commit()

    def refresh_user(self, user) -> None:
        self.db.refresh(user)

    def rollback(self) -> None:
        self.db.rollback()

    def get_user_session(self, session_id: int) -> UserSession | None:
        return self.db.query(UserSession).filter(UserSession.id == session_id).first()
