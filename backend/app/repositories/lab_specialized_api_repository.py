"""Repository helpers for lab specialized API."""

from __future__ import annotations

from sqlalchemy.orm import Session


class LabSpecializedApiRepository:
    """Shared DB session adapter for lab specialized service."""

    def __init__(self, db: Session):
        self.db = db
