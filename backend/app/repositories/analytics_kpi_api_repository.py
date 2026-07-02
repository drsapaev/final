"""Repository helpers for analytics kpi API."""

from __future__ import annotations

from sqlalchemy.orm import Session


class AnalyticsKpiApiRepository:
    """Shared DB session adapter for analytics kpi service."""

    def __init__(self, db: Session):
        self.db = db
