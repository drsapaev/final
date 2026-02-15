"""Repository helpers for ai API."""

from __future__ import annotations

from sqlalchemy.orm import Session


class AiApiRepository:
    """Shared DB session adapter for ai service."""

    def __init__(self, db: Session):
        self.db = db
