"""Repository helpers for online queue legacy API."""

from __future__ import annotations

from sqlalchemy.orm import Session


class OnlineQueueLegacyApiRepository:
    """Shared DB session adapter for online queue legacy service."""

    def __init__(self, db: Session):
        self.db = db
