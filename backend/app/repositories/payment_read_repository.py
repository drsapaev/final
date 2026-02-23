"""Repository helpers for payment read/query flows."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.payment import Payment


class PaymentReadRepository:
    """Encapsulates ORM operations used by payment read service."""

    def __init__(self, db: Session):
        self.db = db

    def get_payment(self, payment_id: int) -> Payment | None:
        return self.db.query(Payment).filter(Payment.id == payment_id).first()

    def list_payments_by_visit(self, visit_id: int) -> list[Payment]:
        return self.db.query(Payment).filter(Payment.visit_id == visit_id).all()
