"""Repository helpers for advanced analytics API."""

from __future__ import annotations

from sqlalchemy.orm import Session


class AdvancedAnalyticsApiRepository:
    """Shared DB session adapter for advanced analytics service."""

    def __init__(self, db: Session):
        self.db = db
