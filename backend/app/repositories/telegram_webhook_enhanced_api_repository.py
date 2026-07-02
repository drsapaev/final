"""Repository helpers for telegram webhook enhanced API."""

from __future__ import annotations

from sqlalchemy.orm import Session


class TelegramWebhookEnhancedApiRepository:
    """Shared DB session adapter for telegram webhook enhanced service."""

    def __init__(self, db: Session):
        self.db = db
