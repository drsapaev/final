"""Repository helpers for two factor sms email API."""

from __future__ import annotations

from sqlalchemy.orm import Session


class TwoFactorSmsEmailApiRepository:
    """Shared DB session adapter for two factor sms email service."""

    def __init__(self, db: Session):
        self.db = db
