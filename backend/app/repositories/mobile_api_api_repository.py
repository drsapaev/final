"""Repository helpers for mobile api API."""

from __future__ import annotations

from sqlalchemy.orm import Session


class MobileApiApiRepository:
    """Shared DB session adapter for mobile api service."""

    def __init__(self, db: Session):
        self.db = db
