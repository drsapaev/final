"""Repository helpers for visit confirmation API."""

from __future__ import annotations

from sqlalchemy.orm import Session


class VisitConfirmationApiRepository:
    """Shared DB session adapter for visit confirmation service."""

    def __init__(self, db: Session):
        self.db = db
