"""Repository helpers for visit payments API."""

from __future__ import annotations

from sqlalchemy.orm import Session


class VisitPaymentsApiRepository:
    """Shared DB session adapter for visit payments service."""

    def __init__(self, db: Session):
        self.db = db
