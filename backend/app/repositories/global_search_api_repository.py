"""Repository helpers for global search API."""

from __future__ import annotations

from sqlalchemy.orm import Session


class GlobalSearchApiRepository:
    """Shared DB session adapter for global search service."""

    def __init__(self, db: Session):
        self.db = db
