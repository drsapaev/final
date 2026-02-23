"""Repository helpers for queue auto close API."""

from __future__ import annotations

from sqlalchemy.orm import Session


class QueueAutoCloseApiRepository:
    """Shared DB session adapter for queue auto close service."""

    def __init__(self, db: Session):
        self.db = db
