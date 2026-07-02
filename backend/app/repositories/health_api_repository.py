"""Repository helpers for health API."""

from __future__ import annotations

from sqlalchemy.orm import Session


class HealthApiRepository:
    """Shared DB session adapter for health service."""

    def __init__(self, db: Session):
        self.db = db
