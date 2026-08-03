"""Repository helpers for payment cancellation flow."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.payment import Payment
from app.models.payment_webhook import PaymentTransaction


class PaymentCancelRepository:
    """Encapsulates ORM operations used by payment cancel service."""

    def __init__(self, db: Session):
        self.db = db

    def get_payment(self, payment_id: int) -> Payment | None:
        return self.db.query(Payment).filter(Payment.id == payment_id).first()

    def get_transactions_by_payment_id_for_update(
        self, payment_id: int
    ) -> list[PaymentTransaction]:
        """Lock all PaymentTransaction rows linked to ``payment_id`` for update.

        Uses ``SELECT ... FOR UPDATE`` (via ``with_for_update()``) to
        acquire row-level locks on every PaymentTransaction pointing at
        this Payment. This is the symmetric counterpart of
        ``billing_service.update_payment_status``'s own
        ``with_for_update()`` on the Payment row.

        Why this matters (FOLLOWUP-8 TOCTOU guard):

        Inside ``PaymentCancelService._cancel_payment_and_transaction``,
        the Payment row is already locked by the
        ``billing_service.update_payment_status(commit=False)`` call
        (which does ``SELECT Payment ... FOR UPDATE`` internally —
        see ``billing_service_pkg/_payments.py:409-414``). That lock
        serializes concurrent ``cancel_payment()`` calls on the same
        Payment.

        However, a *concurrent webhook handler* (provider_webhook_service)
        may write to ``PaymentTransaction.status`` without going through
        this cancel path. Without ``FOR UPDATE`` on our Tx read, the
        following race is possible:

            Cancel A: lock Payment → read Tx (no lock, sees 'processing')
                                                 ↓
            Webhook B: read Tx (no lock) → write tx.status='completed' → commit
                                                 ↓
            Cancel A: write tx.status='cancelled' → commit
                       ↑ overwrites 'completed' silently

        With ``FOR UPDATE`` on the Tx read, webhook B's write blocks
        until cancel A commits or rolls back. The status we read is
        the status we mutate.

        Must be called inside a ``transaction_ctx`` block so the lock
        is released on commit/rollback.
        """
        return (
            self.db.query(PaymentTransaction)
            .filter(PaymentTransaction.payment_id == payment_id)
            .with_for_update()
            .all()
        )
