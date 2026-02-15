"""Repository helpers for queue position API."""

from __future__ import annotations

from sqlalchemy.orm import Session


class QueuePositionApiRepository:
    """Shared DB session adapter for queue position service."""

    def __init__(self, db: Session):
        self.db = db
