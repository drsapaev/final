"""Repository helpers for feature flags API."""

from __future__ import annotations

from sqlalchemy.orm import Session


class FeatureFlagsApiRepository:
    """Shared DB session adapter for feature flags service."""

    def __init__(self, db: Session):
        self.db = db
