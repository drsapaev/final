"""Repository helpers for emr ai enhanced API."""

from __future__ import annotations

from sqlalchemy.orm import Session


class EmrAiEnhancedApiRepository:
    """Shared DB session adapter for emr ai enhanced service."""

    def __init__(self, db: Session):
        self.db = db
