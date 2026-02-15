"""Repository helpers for patient appointments API."""

from __future__ import annotations

from sqlalchemy.orm import Session


class PatientAppointmentsApiRepository:
    """Shared DB session adapter for patient appointments service."""

    def __init__(self, db: Session):
        self.db = db
