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

    def get_payment_by_id_for_update(self, payment_id: int) -> Payment | None:
        """Lock the payment row for update (SELECT ... FOR UPDATE).

        Used in webhook duplicate-processing to prevent TOCTOU races:
        a cashier cancellation (via PaymentCancelService →
        billing_service.update_payment_status which uses
        with_for_update) can commit a terminal status between our
        read and write. This method acquires the row lock so that
        the status we read is the status we mutate.

        Must be called inside a transaction_ctx block.
        """
        return (
            self.db.query(Payment)
            .filter(Payment.id == payment_id)
            .with_for_update()
            .first()
        )

    def get_payment_by_provider_payment_id(
        self, provider_payment_id: str
    ) -> Payment | None:
        return (
            self.db.query(Payment)
            .filter(Payment.provider_payment_id == provider_payment_id)
            .first()
        )

    def get_payment_by_provider_payment_id_for_update(
        self, provider_payment_id: str
    ) -> Payment | None:
        """Lock the payment row for update (SELECT ... FOR UPDATE).

        Symmetric counterpart of ``get_payment_by_id_for_update``. Used
        by Kaspi webhook handler (which looks up Payment by
        ``provider_payment_id`` instead of by ``id``) to prevent TOCTOU
        races against concurrent cashier cancellations.

        FOLLOWUP-10: before this method existed, the Kaspi handler read
        Payment without a lock, then mutated ``payment.status`` and
        inserted a new ``PaymentTransaction`` row. A concurrent
        ``PaymentCancelService.cancel_payment()`` call (which acquires
        ``SELECT Payment ... FOR UPDATE`` via
        ``billing_service.update_payment_status``) could commit a
        terminal status between the Kaspi handler's unlocked read and
        its write, leaving Payment and PaymentTransaction in
        inconsistent states.

        Must be called inside a ``transaction_ctx`` block so the lock
        is released on commit/rollback.
        """
        return (
            self.db.query(Payment)
            .filter(Payment.provider_payment_id == provider_payment_id)
            .with_for_update()
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
