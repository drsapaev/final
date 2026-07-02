"""Repository helpers for medical equipment API."""

from __future__ import annotations

from sqlalchemy.orm import Session


class MedicalEquipmentApiRepository:
    """Shared DB session adapter for medical equipment service."""

    def __init__(self, db: Session):
        self.db = db
