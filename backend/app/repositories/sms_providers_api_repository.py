"""Repository helpers for sms providers API."""

from __future__ import annotations

from sqlalchemy.orm import Session


class SmsProvidersApiRepository:
    """Shared DB session adapter for sms providers service."""

    def __init__(self, db: Session):
        self.db = db
