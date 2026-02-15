"""Repository helpers for doctor integration API."""

from __future__ import annotations

from sqlalchemy.orm import Session


class DoctorIntegrationApiRepository:
    """Shared DB session adapter for doctor integration service."""

    def __init__(self, db: Session):
        self.db = db
