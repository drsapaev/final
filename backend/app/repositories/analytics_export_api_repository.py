"""Repository helpers for analytics export API."""

from __future__ import annotations

from sqlalchemy.orm import Session


class AnalyticsExportApiRepository:
    """Shared DB session adapter for analytics export service."""

    def __init__(self, db: Session):
        self.db = db
