"""Repository helpers for appointment flow API."""

from __future__ import annotations

from sqlalchemy.orm import Session


class AppointmentFlowApiRepository:
    """Shared DB session adapter for appointment flow service."""

    def __init__(self, db: Session):
        self.db = db
