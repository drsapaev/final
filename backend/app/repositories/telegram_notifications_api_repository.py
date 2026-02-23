"""Repository helpers for telegram notifications API."""

from __future__ import annotations

from sqlalchemy.orm import Session


class TelegramNotificationsApiRepository:
    """Shared DB session adapter for telegram notifications service."""

    def __init__(self, db: Session):
        self.db = db
