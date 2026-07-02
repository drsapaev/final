"""Repository helpers for monitoring API."""

from __future__ import annotations

from sqlalchemy.orm import Session


class MonitoringApiRepository:
    """Shared DB session adapter for monitoring service."""

    def __init__(self, db: Session):
        self.db = db
