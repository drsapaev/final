"""Repository helpers for provider webhook processing."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.models.payment import Payment
from app.models.payment_webhook import PaymentTransaction, PaymentWebhook


class ProviderWebhookRepository:
    """Encapsulates ORM operations used by provider webhook service."""

    def __init__(self, db: Session):
        self.db = db

    def get_existing_transaction(
        self, *, transaction_id: str, provider: str
    ) -> PaymentTransaction | None:
        return (
            self.db.query(PaymentTransaction)
            .filter(
                PaymentTransaction.transaction_id == transaction_id,
                PaymentTransaction.provider == provider,
            )
            .first()
        )

    def create_webhook(
        self,
        *,
        provider: str,
        webhook_id: str,
        transaction_id: str,
        amount: int,
        currency: str,
        raw_data: dict[str, Any],
        signature: str | None = None,
        status: str = "pending",
    ) -> PaymentWebhook:
        webhook = PaymentWebhook(
            provider=provider,
            webhook_id=webhook_id,
            transaction_id=transaction_id,
            status=status,
            amount=amount,
            currency=currency,
            raw_data=raw_data,
            signature=signature,
        )
        self.db.add(webhook)
        self.db.flush()
        self.db.refresh(webhook)
        return webhook

    def get_payment_by_id(self, payment_id: int) -> Payment | None:
        return self.db.query(Payment).filter(Payment.id == payment_id).first()

    def get_payment_by_provider_payment_id(
        self, provider_payment_id: str
    ) -> Payment | None:
        return (
            self.db.query(Payment)
            .filter(Payment.provider_payment_id == provider_payment_id)
            .first()
        )

    def create_transaction(
        self,
        *,
        transaction_id: str,
        provider: str,
        amount: int,
        currency: str,
        status: str,
        payment_id: int | None,
        webhook_id: int | None,
        visit_id: int | None,
        provider_data: dict[str, Any] | None,
    ) -> PaymentTransaction:
        transaction = PaymentTransaction(
            transaction_id=transaction_id,
            provider=provider,
            amount=amount,
            currency=currency,
            status=status,
            payment_id=payment_id,
            webhook_id=webhook_id,
            visit_id=visit_id,
            provider_data=provider_data,
        )
        self.db.add(transaction)
        return transaction
