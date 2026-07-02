"""Repository helpers for mobile api extended API."""

from __future__ import annotations

from sqlalchemy.orm import Session


class MobileApiExtendedApiRepository:
    """Shared DB session adapter for mobile api extended service."""

    def __init__(self, db: Session):
        self.db = db
