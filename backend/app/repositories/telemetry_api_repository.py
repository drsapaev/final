"""Repository helpers for telemetry API."""

from __future__ import annotations

from sqlalchemy.orm import Session


class TelemetryApiRepository:
    """Shared DB session adapter for telemetry service."""

    def __init__(self, db: Session):
        self.db = db
