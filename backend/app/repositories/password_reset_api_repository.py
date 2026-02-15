"""Repository helpers for password reset API."""

from __future__ import annotations

from sqlalchemy.orm import Session


class PasswordResetApiRepository:
    """Shared DB session adapter for password reset service."""

    def __init__(self, db: Session):
        self.db = db
