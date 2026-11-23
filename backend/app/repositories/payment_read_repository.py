"""Repository helpers for payment read/query flows."""

from __future__ import annotations

from sqlalchemy import insert
from sqlalchemy.orm import Session

from app.models.audit import AuditLog
from app.models.payment import Payment


class PaymentReadRepository:
    """Encapsulates ORM operations used by payment read service."""

    def __init__(self, db: Session):
        self.db = db

    def get_payment(
        self, payment_id: int, *, for_update: bool = False, refresh: bool = False,
    ) -> Payment | None:
        query = self.db.query(Payment).filter(Payment.id == payment_id)
        if refresh or for_update:
            query = query.populate_existing()
        if for_update:
            query = query.with_for_update()
        return query.first()

    def list_payments_by_visit(self, visit_id: int) -> list[Payment]:
        return self.db.query(Payment).filter(Payment.visit_id == visit_id).all()

    def record_provider_transition(self, payment: Payment, *, previous_status: str) -> None:
        """Append an audit event in the caller's transaction using INSERT-only access."""
        self.db.execute(
            insert(AuditLog.__table__).inline().values(
                action="payment_provider_status_changed",
                event_type="PAYMENT_PROVIDER_STATUS_CHANGED",
                entity_type="payment",
                entity_id=payment.id,
                resource_type="payment",
                resource_id=str(payment.id),
                actor_type="system",
                outcome="success",
                payload={
                    "previous_status": previous_status,
                    "new_status": payment.status,
                    "amount": format(payment.amount, "f"),
                    "currency": payment.currency,
                    "provider": payment.provider,
                },
            )
        )
