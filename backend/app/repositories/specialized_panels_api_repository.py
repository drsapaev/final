"""Repository helpers for specialized panels API."""

from __future__ import annotations

from sqlalchemy.orm import Session


class SpecializedPanelsApiRepository:
    """Shared DB session adapter for specialized panels service."""

    def __init__(self, db: Session):
        self.db = db
