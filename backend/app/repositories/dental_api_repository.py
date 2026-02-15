"""Repository helpers for dental API."""

from __future__ import annotations

from sqlalchemy.orm import Session


class DentalApiRepository:
    """Shared DB session adapter for dental service."""

    def __init__(self, db: Session):
        self.db = db
