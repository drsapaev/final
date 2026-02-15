"""Repository helpers for payment webhooks API."""

from __future__ import annotations

from sqlalchemy.orm import Session


class PaymentWebhooksApiRepository:
    """Shared DB session adapter for payment webhooks service."""

    def __init__(self, db: Session):
        self.db = db
