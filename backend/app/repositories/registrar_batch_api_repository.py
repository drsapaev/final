"""Repository helpers for registrar batch API."""

from __future__ import annotations

from sqlalchemy.orm import Session


class RegistrarBatchApiRepository:
    """Shared DB session adapter for registrar batch service."""

    def __init__(self, db: Session):
        self.db = db
