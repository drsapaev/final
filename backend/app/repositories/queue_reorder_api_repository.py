"""Repository helpers for queue reorder API."""

from __future__ import annotations

from sqlalchemy.orm import Session


class QueueReorderApiRepository:
    """Shared DB session adapter for queue reorder service."""

    def __init__(self, db: Session):
        self.db = db
