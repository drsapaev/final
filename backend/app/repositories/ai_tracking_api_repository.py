"""Repository helpers for ai tracking API."""

from __future__ import annotations

from sqlalchemy.orm import Session


class AiTrackingApiRepository:
    """Shared DB session adapter for ai tracking service."""

    def __init__(self, db: Session):
        self.db = db
