"""Repository helpers for simple auth API."""

from __future__ import annotations

from sqlalchemy.orm import Session


class SimpleAuthApiRepository:
    """Shared DB session adapter for simple auth service."""

    def __init__(self, db: Session):
        self.db = db
