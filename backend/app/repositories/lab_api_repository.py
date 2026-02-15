"""Repository helpers for lab API."""

from __future__ import annotations

from sqlalchemy.orm import Session


class LabApiRepository:
    """Shared DB session adapter for lab service."""

    def __init__(self, db: Session):
        self.db = db
