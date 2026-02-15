"""Repository helpers for phrase suggest API."""

from __future__ import annotations

from sqlalchemy.orm import Session


class PhraseSuggestApiRepository:
    """Shared DB session adapter for phrase suggest service."""

    def __init__(self, db: Session):
        self.db = db
