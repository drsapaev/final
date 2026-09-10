"""Service layer for payment cancellation endpoint."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from app.db.transactions import transaction as transaction_ctx
from app.models.enums import PaymentStatus
from app.repositories.payment_cancel_repository import PaymentCancelRepository
from app.services.billing_service import BillingService
from app.services.payment_invariant_service import PaymentInvariantService
from app.services.payment_state_checks import can_transition_transaction_status
from app.services.visit_lifecycle_service import VisitLifecycleService

logger = logging.getLogger(__name__)


@dataclass
class PaymentCancelDomainError(Exception):
    status_code: int
    detail: str


class PaymentCancelService:
    """Orchestrates payment cancellation and status updates."""

    def __init__(self, db, payment_manager):  # type: ignore[no-untyped-def]
        self.repository = PaymentCancelRepository(db)
        self.billing_service = BillingService(db)
        self.payment_invariant_service = PaymentInvariantService(db)
        self.visit_lifecycle_service = VisitLifecycleService(db)
        self.payment_manager = payment_manager
        self.db = db

    def cancel_payment(
        self,
        *,
        payment_id: int,
        reason: str | None = None,
    ) -> dict[str, Any]:
        payment = self.repository.get_payment(payment_id)
        if not payment:
            raise PaymentCancelDomainError(status_code=404, detail="Платеж не найден")

        if payment.status not in [
            PaymentStatus.PENDING.value,
            PaymentStatus.PROCESSING.value,
        ]:
            detail = (
                "Оплаченный платеж необходимо оформить как возврат"
                if payment.status
                in [PaymentStatus.PAID.value, "completed"]
                else f"Платеж со статусом {payment.status} нельзя отменить"
            )
            raise PaymentCancelDomainError(status_code=400, detail=detail)

        # PRE-CHECK: validate PaymentTransaction cardinality BEFORE
        # calling the external provider cancel. If >1 row exists, the
        # 1:1 contract invariant is already violated — raise now so we
        # don't leave the provider cancelled while the local Payment
        # stays unchanged (which would happen if we raised 500 only
        # after the provider call succeeded).
        #
        # This is a soft (unlocked) count. The definitive check with
        # FOR UPDATE locks still runs inside
        # _cancel_payment_and_transaction. If the count changes between
        # this pre-check and the locked check (e.g. a webhook inserts
        # a second Tx during the cancel call — itself a producer bug),
        # the locked check catches it and raises 500. At that point the
        # provider cancel has already succeeded, but the 500 response
        # signals the invariant violation to the operator.
        tx_count = self.repository.count_transactions_by_payment_id(payment_id)
        if tx_count > 1:
            raise PaymentCancelDomainError(
                status_code=500,
                detail=(
                    f"Payment {payment_id} has {tx_count} "
                    "PaymentTransaction rows — expected exactly 1 "
                    "(1:1 contract). Manual data reconciliation required "
                    "before cancellation can proceed safely."
                ),
            )

        if payment.provider and payment.provider_payment_id:
            result = self.payment_manager.cancel_payment(
                payment.provider, payment.provider_payment_id
            )
            if result.success:
                self._cancel_payment_and_transaction(
                    payment_id=payment.id,
                    expected_visit_id=payment.visit_id,
                    meta={**(payment.provider_data or {}), **result.provider_data},
                    reason=reason,
                )
            else:
                # PAY-REAUDIT-28 P0-6: провайдер отклонил отмену — НЕ меняем
                # локальный статус. Раньше код помечал платёж как CANCELLED
                # даже при неудаче у провайдера, что приводило к рассинхрону:
                # локально "отменён", у провайдера — активен (двойной расход).
                logger.error(
                    "Provider cancel failed for payment_id=%s provider=%s: %s",
                    payment.id, payment.provider, result.error_message,
                )
                raise PaymentCancelDomainError(
                    status_code=502,
                    detail=(
                        f"Провайдер отклонил отмену: {result.error_message}. "
                        "Статус платежа не изменён. Повторите попытку или обратитесь к провайдеру."
                    ),
                )
        else:
            self._cancel_payment_and_transaction(
                payment_id=payment.id,
                expected_visit_id=payment.visit_id,
                reason=reason,
            )

        payment = self.repository.get_payment(payment_id)
        if not payment:
            raise PaymentCancelDomainError(
                status_code=500, detail="Платеж не найден после отмены"
            )

        return {
            "success": True,
            "payment_id": payment.id,
            "status": payment.status,
            "message": "Платеж отменен",
        }

    def _cancel_payment_and_transaction(
        self,
        *,
        payment_id: int,
        expected_visit_id: int | None,
        meta: dict[str, Any] | None = None,
        reason: str | None = None,
    ) -> None:
        """Atomically cancel Payment and linked PaymentTransaction.

        The visit projection, Payment, linked PaymentTransaction, cancellation
        reason, and linked invoices are updated inside one ``transaction_ctx``
        so that a failure rolls the complete local mutation back. The Payment is
        updated via ``billing_service.update_payment_status(commit=False)``
        — this internally acquires ``SELECT Payment ... FOR UPDATE``
        (see ``billing_service_pkg/_payments.py:409-414``) and flushes
        the change without committing. The PaymentTransaction rows are
        then read via ``get_transactions_by_payment_id_for_update()``
        which acquires ``SELECT PaymentTransaction ... FOR UPDATE`` on
        every linked row, closing the TOCTOU window against concurrent
        webhook writes.

        FOLLOWUP-8: this fixes the root cause of the Payment ↔
        PaymentTransaction inconsistency that PR #2657's defensive
        guard was compensating for.

        Branching on the number of linked transactions follows an
        explicit 0 / 1 / >1 structure:
          - 0 rows: cash payment path — Payment has no online transaction.
          - 1 row: validate transition via shared
            ``can_transition_transaction_status``; update
            ``tx.status = 'cancelled'`` if allowed, otherwise log
            warning and skip (terminal transactions like 'refunded' must not be
            overwritten).
          - >1 rows: 1:1 contract invariant violation — raise
            ``PaymentCancelDomainError(500)``. Do NOT silently pick
            first. Matches existing project pattern for invariant
            violations (cf. ``payment_read_service.py:195``,
            ``payment_create_service.py:117``).
        """
        with transaction_ctx(self.db):
            # Lock order is Visit -> Payment -> PaymentTransaction -> Invoice,
            # matching the other cashier payment mutations.
            if expected_visit_id is not None:
                self.visit_lifecycle_service.restore_operational_status_after_payment_change(
                    expected_visit_id,
                    commit=False,
                )

            locked_payment = self.repository.get_payment_for_update(payment_id)
            if not locked_payment:
                raise PaymentCancelDomainError(
                    status_code=404,
                    detail="Платеж не найден",
                )
            if locked_payment.visit_id != expected_visit_id:
                raise PaymentCancelDomainError(
                    status_code=409,
                    detail="Визит платежа изменился; повторите операцию",
                )
            if locked_payment.status not in [
                PaymentStatus.PENDING.value,
                PaymentStatus.PROCESSING.value,
            ]:
                raise PaymentCancelDomainError(
                    status_code=409,
                    detail="Статус платежа изменился; обновите данные и повторите операцию",
                )

            # 1. Update Payment status (no commit yet).
            #    billing_service.update_payment_status(commit=False)
            #    acquires SELECT Payment ... FOR UPDATE internally
            #    and flushes the UPDATE without committing.
            try:
                payment = self.billing_service.update_payment_status(
                    payment_id=payment_id,
                    new_status=PaymentStatus.CANCELLED.value,
                    meta=meta,
                    commit=False,
                )
            except ValueError as exc:
                raise PaymentCancelDomainError(
                    status_code=409,
                    detail=f"Невозможно отменить платеж: {exc}",
                ) from exc

            if reason:
                payment.note = f"Отменён: {reason}"
                # Test and some batch sessions disable autoflush. Persist the
                # note before invoice reconciliation uses populate_existing().
                self.db.flush()

            # 2. Find linked PaymentTransaction by payment_id FK with
            #    row-level lock (SELECT ... FOR UPDATE).
            #    Zero rows = cash payment (no online transaction exists)
            #    — nothing to sync.
            #    >1 row = data-integrity invariant violation. Payment ↔
            #    PaymentTransaction is 1:1 by contract; multiple rows
            #    indicate a producer bug or manual DB modification that
            #    must be reconciled manually, not silently papered over.
            transactions = (
                self.repository.get_transactions_by_payment_id_for_update(
                    payment_id
                )
            )

            if len(transactions) == 1:
                tx = transactions[0]
                current_tx_status = tx.status or ""

                if not can_transition_transaction_status(
                    current_tx_status, "cancelled"
                ):
                    # Transaction already in terminal state (refunded /
                    # already cancelled). Payment.status update still
                    # commits — the inconsistency this introduces is
                    # benign because the transaction is terminal and
                    # cannot transition further.
                    logger.warning(
                        "PaymentCancelService: skipping transaction status "
                        "update — transition not allowed "
                        "current=%s target=cancelled transaction_id=%s "
                        "payment_id=%s",
                        current_tx_status,
                        getattr(tx, "id", None),
                        payment_id,
                    )
                else:
                    tx.status = "cancelled"
            elif len(transactions) > 1:
                # len(transactions) > 1 — invariant violation.
                raise PaymentCancelDomainError(
                    status_code=500,
                    detail=(
                        f"Payment {payment_id} has {len(transactions)} "
                        "PaymentTransaction rows — expected exactly 1 "
                        "(1:1 contract). Manual data reconciliation required "
                        "before cancellation can proceed safely."
                    ),
                )

            if expected_visit_id is not None:
                self.payment_invariant_service.synchronize_linked_invoices(
                    visit_id=expected_visit_id,
                    payment_method=payment.method,
                )
