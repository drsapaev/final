"""Repository helpers for queue API."""

from __future__ import annotations

from sqlalchemy.orm import Session


class QueueApiRepository:
    """Shared DB session adapter for queue service."""

    def __init__(self, db: Session):
        self.db = db
