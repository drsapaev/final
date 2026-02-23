"""Repository helpers for cardio API."""

from __future__ import annotations

from sqlalchemy.orm import Session


class CardioApiRepository:
    """Shared DB session adapter for cardio service."""

    def __init__(self, db: Session):
        self.db = db
