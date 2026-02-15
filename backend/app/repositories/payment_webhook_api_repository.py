"""Repository helpers for payment webhook API."""

from __future__ import annotations

from sqlalchemy.orm import Session


class PaymentWebhookApiRepository:
    """Shared DB session adapter for payment webhook service."""

    def __init__(self, db: Session):
        self.db = db
