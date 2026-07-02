"""Repository helpers for wait time analytics API."""

from __future__ import annotations

from sqlalchemy.orm import Session


class WaitTimeAnalyticsApiRepository:
    """Shared DB session adapter for wait time analytics service."""

    def __init__(self, db: Session):
        self.db = db
