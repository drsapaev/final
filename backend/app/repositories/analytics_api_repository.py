"""Repository helpers for analytics API."""

from __future__ import annotations

from sqlalchemy.orm import Session


class AnalyticsApiRepository:
    """Shared DB session adapter for analytics service."""

    def __init__(self, db: Session):
        self.db = db
