"""Repository helpers for telegram bot API."""

from __future__ import annotations

from sqlalchemy.orm import Session


class TelegramBotApiRepository:
    """Shared DB session adapter for telegram bot service."""

    def __init__(self, db: Session):
        self.db = db
