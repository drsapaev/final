"""Repository helpers for print api API."""

from __future__ import annotations

from sqlalchemy.orm import Session


class PrintApiApiRepository:
    """Shared DB session adapter for print api service."""

    def __init__(self, db: Session):
        self.db = db
