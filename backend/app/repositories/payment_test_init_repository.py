"""Repository helpers for payment test-init flow."""

from __future__ import annotations

from sqlalchemy.orm import Session


class PaymentTestInitRepository:
    """Encapsulates DB transaction calls for payment test-init service."""

    def __init__(self, db: Session):
        self.db = db

    def rollback(self) -> None:
        self.db.rollback()
