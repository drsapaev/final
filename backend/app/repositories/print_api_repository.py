"""Repository helpers for print API."""

from __future__ import annotations

from sqlalchemy.orm import Session


class PrintApiRepository:
    """Shared DB session adapter for print service."""

    def __init__(self, db: Session):
        self.db = db
