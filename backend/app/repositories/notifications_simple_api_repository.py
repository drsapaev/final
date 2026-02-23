"""Repository helpers for notifications simple API."""

from __future__ import annotations

from sqlalchemy.orm import Session


class NotificationsSimpleApiRepository:
    """Shared DB session adapter for notifications simple service."""

    def __init__(self, db: Session):
        self.db = db
