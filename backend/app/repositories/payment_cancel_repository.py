"""Repository helpers for payment cancellation flow."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.payment import Payment


class PaymentCancelRepository:
    """Encapsulates ORM operations used by payment cancel service."""

    def __init__(self, db: Session):
        self.db = db

    def get_payment(self, payment_id: int) -> Payment | None:
        return self.db.query(Payment).filter(Payment.id == payment_id).first()
