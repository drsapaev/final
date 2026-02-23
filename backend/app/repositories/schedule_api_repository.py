"""Repository helpers for schedule API."""

from __future__ import annotations

from sqlalchemy.orm import Session


class ScheduleApiRepository:
    """Shared DB session adapter for schedule service."""

    def __init__(self, db: Session):
        self.db = db
