"""Repository helpers for utils API."""

from __future__ import annotations

from sqlalchemy.orm import Session


class UtilsApiRepository:
    """Shared DB session adapter for utils service."""

    def __init__(self, db: Session):
        self.db = db
