"""Repository helpers for emr versioning enhanced API."""

from __future__ import annotations

from sqlalchemy.orm import Session


class EmrVersioningEnhancedApiRepository:
    """Shared DB session adapter for emr versioning enhanced service."""

    def __init__(self, db: Session):
        self.db = db
