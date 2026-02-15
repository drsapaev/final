"""Repository helpers for admin AI API."""

from __future__ import annotations

from sqlalchemy.orm import Session


class AdminAiApiRepository:
    """Shared DB session adapter for admin AI service."""

    def __init__(self, db: Session):
        self.db = db
