"""Repository helpers for analytics predictive API."""

from __future__ import annotations

from sqlalchemy.orm import Session


class AnalyticsPredictiveApiRepository:
    """Shared DB session adapter for analytics predictive service."""

    def __init__(self, db: Session):
        self.db = db
