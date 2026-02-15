"""Repository helpers for reports API."""

from __future__ import annotations

from sqlalchemy.orm import Session


class ReportsApiRepository:
    """Shared DB session adapter for reports service."""

    def __init__(self, db: Session):
        self.db = db
