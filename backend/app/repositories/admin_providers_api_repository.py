"""Repository helpers for admin providers API."""

from __future__ import annotations

from sqlalchemy.orm import Session


class AdminProvidersApiRepository:
    """Shared DB session adapter for admin providers service."""

    def __init__(self, db: Session):
        self.db = db
