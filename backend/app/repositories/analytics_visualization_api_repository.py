"""Repository helpers for analytics visualization API."""

from __future__ import annotations

from sqlalchemy.orm import Session


class AnalyticsVisualizationApiRepository:
    """Shared DB session adapter for analytics visualization service."""

    def __init__(self, db: Session):
        self.db = db
