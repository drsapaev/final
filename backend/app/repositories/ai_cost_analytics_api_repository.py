"""Repository helpers for ai cost analytics API."""

from __future__ import annotations

from sqlalchemy.orm import Session


class AiCostAnalyticsApiRepository:
    """Shared DB session adapter for ai cost analytics service."""

    def __init__(self, db: Session):
        self.db = db
