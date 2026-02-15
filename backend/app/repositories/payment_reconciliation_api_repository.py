"""Repository helpers for payment reconciliation API."""

from __future__ import annotations

from sqlalchemy.orm import Session


class PaymentReconciliationApiRepository:
    """Shared DB session adapter for payment reconciliation service."""

    def __init__(self, db: Session):
        self.db = db
