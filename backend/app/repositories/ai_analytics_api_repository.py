"""Repository helpers for ai analytics API."""

from __future__ import annotations

from sqlalchemy.orm import Session


class AiAnalyticsApiRepository:
    """Shared DB session adapter for ai analytics service."""

    def __init__(self, db: Session):
        self.db = db
