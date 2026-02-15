"""Repository helpers for online queue new API."""

from __future__ import annotations

from sqlalchemy.orm import Session


class OnlineQueueNewApiRepository:
    """Shared DB session adapter for online queue new service."""

    def __init__(self, db: Session):
        self.db = db
