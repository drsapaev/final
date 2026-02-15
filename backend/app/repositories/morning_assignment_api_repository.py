"""Repository helpers for morning assignment API."""

from __future__ import annotations

from sqlalchemy.orm import Session


class MorningAssignmentApiRepository:
    """Shared DB session adapter for morning assignment service."""

    def __init__(self, db: Session):
        self.db = db
