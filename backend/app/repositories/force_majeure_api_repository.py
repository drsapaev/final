"""Repository helpers for force majeure API."""

from __future__ import annotations

from sqlalchemy.orm import Session


class ForceMajeureApiRepository:
    """Shared DB session adapter for force majeure service."""

    def __init__(self, db: Session):
        self.db = db
