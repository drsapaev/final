"""Repository helpers for payment reconciliation flows."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from app.models.payment import Payment
from app.models.payment_webhook import PaymentTransaction


class PaymentReconciliationRepository:
    """Encapsulates ORM access for reconciliation services."""

    def __init__(self, db: Session):
        self.db = db

    def list_transactions_for_provider(
        self,
        *,
        provider_name: str,
        start_at: datetime,
        end_at: datetime,
    ) -> list[PaymentTransaction]:
        return (
            self.db.query(PaymentTransaction)
            .filter(
                PaymentTransaction.provider == provider_name,
                PaymentTransaction.created_at >= start_at,
                PaymentTransaction.created_at <= end_at,
            )
            .all()
        )

    def list_pending_payments_for_provider(
        self,
        *,
        provider_name: str,
        cutoff_date: datetime,
    ) -> list[Payment]:
        return (
            self.db.query(Payment)
            .filter(
                Payment.provider == provider_name,
                Payment.status.in_(["pending", "processing"]),
                Payment.created_at >= cutoff_date,
            )
            .all()
        )

    def get_completed_transaction_for_payment(
        self,
        *,
        payment_id: int,
        provider_name: str,
    ) -> PaymentTransaction | None:
        return (
            self.db.query(PaymentTransaction)
            .filter(
                PaymentTransaction.payment_id == payment_id,
                PaymentTransaction.provider == provider_name,
                PaymentTransaction.status == "completed",
            )
            .first()
        )
