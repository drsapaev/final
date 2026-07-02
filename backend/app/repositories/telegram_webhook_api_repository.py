"""Repository helpers for telegram webhook API."""

from __future__ import annotations

from sqlalchemy.orm import Session


class TelegramWebhookApiRepository:
    """Shared DB session adapter for telegram webhook service."""

    def __init__(self, db: Session):
        self.db = db
