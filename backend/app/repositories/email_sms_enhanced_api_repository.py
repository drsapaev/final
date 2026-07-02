"""Repository helpers for email sms enhanced API."""

from __future__ import annotations

from sqlalchemy.orm import Session


class EmailSmsEnhancedApiRepository:
    """Shared DB session adapter for email sms enhanced service."""

    def __init__(self, db: Session):
        self.db = db
