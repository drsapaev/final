"""Repository helpers for telegram integration API."""

from __future__ import annotations

from sqlalchemy.orm import Session


class TelegramIntegrationApiRepository:
    """Shared DB session adapter for telegram integration service."""

    def __init__(self, db: Session):
        self.db = db
