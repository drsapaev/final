"""Repository helpers for emr ai API."""

from __future__ import annotations

from sqlalchemy.orm import Session


class EmrAiApiRepository:
    """Shared DB session adapter for emr ai service."""

    def __init__(self, db: Session):
        self.db = db
