"""Repository helpers for auth API."""

from __future__ import annotations

from sqlalchemy.orm import Session


class AuthApiRepository:
    """Shared DB session adapter for auth service."""

    def __init__(self, db: Session):
        self.db = db
