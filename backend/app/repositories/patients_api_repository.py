"""Repository helpers for patients API."""

from __future__ import annotations

from sqlalchemy.orm import Session


class PatientsApiRepository:
    """Shared DB session adapter for patients service."""

    def __init__(self, db: Session):
        self.db = db
