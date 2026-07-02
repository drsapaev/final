"""Repository helpers for online queue API."""

from __future__ import annotations

from sqlalchemy.orm import Session


class OnlineQueueApiRepository:
    """Shared DB session adapter for online queue service."""

    def __init__(self, db: Session):
        self.db = db
