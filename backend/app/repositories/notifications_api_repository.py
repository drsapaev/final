"""Repository helpers for notifications API."""

from __future__ import annotations

from sqlalchemy.orm import Session


class NotificationsApiRepository:
    """Shared DB session adapter for notifications service."""

    def __init__(self, db: Session):
        self.db = db
