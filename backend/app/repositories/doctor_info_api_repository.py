"""Repository helpers for doctor info API."""

from __future__ import annotations

from sqlalchemy.orm import Session


class DoctorInfoApiRepository:
    """Shared DB session adapter for doctor info service."""

    def __init__(self, db: Session):
        self.db = db
