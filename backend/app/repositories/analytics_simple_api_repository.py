"""Repository helpers for analytics simple API."""

from __future__ import annotations

from sqlalchemy.orm import Session


class AnalyticsSimpleApiRepository:
    """Shared DB session adapter for analytics simple service."""

    def __init__(self, db: Session):
        self.db = db
