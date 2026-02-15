"""Repository helpers for telegram bot management API."""

from __future__ import annotations

from sqlalchemy.orm import Session


class TelegramBotManagementApiRepository:
    """Shared DB session adapter for telegram bot management service."""

    def __init__(self, db: Session):
        self.db = db
