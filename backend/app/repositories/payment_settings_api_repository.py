"""Repository helpers for payment settings API."""

from __future__ import annotations

from sqlalchemy.orm import Session


class PaymentSettingsApiRepository:
    """Shared DB session adapter for payment settings service."""

    def __init__(self, db: Session):
        self.db = db
