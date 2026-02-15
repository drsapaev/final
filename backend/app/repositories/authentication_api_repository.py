"""Repository helpers for authentication API."""

from __future__ import annotations

from sqlalchemy.orm import Session


class AuthenticationApiRepository:
    """Shared DB session adapter for authentication service."""

    def __init__(self, db: Session):
        self.db = db
