"""Repository helpers for queue limits API."""

from __future__ import annotations

from sqlalchemy.orm import Session


class QueueLimitsApiRepository:
    """Shared DB session adapter for queue limits service."""

    def __init__(self, db: Session):
        self.db = db
