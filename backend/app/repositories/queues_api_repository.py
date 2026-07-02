"""Repository helpers for queues API."""

from __future__ import annotations

from sqlalchemy.orm import Session


class QueuesApiRepository:
    """Shared DB session adapter for queues service."""

    def __init__(self, db: Session):
        self.db = db
