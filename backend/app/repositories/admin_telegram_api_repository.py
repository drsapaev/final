"""Repository helpers for admin telegram API."""

from __future__ import annotations

from sqlalchemy.orm import Session


class AdminTelegramApiRepository:
    """Shared DB session adapter for admin telegram service."""

    def __init__(self, db: Session):
        self.db = db
