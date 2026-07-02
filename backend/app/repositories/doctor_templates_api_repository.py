"""Repository helpers for doctor templates API."""

from __future__ import annotations

from sqlalchemy.orm import Session


class DoctorTemplatesApiRepository:
    """Shared DB session adapter for doctor templates service."""

    def __init__(self, db: Session):
        self.db = db
