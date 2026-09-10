"""Service layer for payment cancellation endpoint."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from app.db.transactions import transaction as transaction_ctx
from app.models.enums import PaymentStatus
from app.repositories.payment_cancel_repository import PaymentCancelRepository
from app.services.billing_service import BillingService
from app.services.context_facades.emr_facade import (
    EmrContextFacade,
    EmrServiceContractAdapter,
)
from app.services.payment_invariant_service import PaymentInvariantService
from app.services.payment_state_checks import can_transition_transaction_status

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
        self.emr_facade = EmrContextFacade(EmrServiceContractAdapter(db))
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

        self._cancel_payment_and_transaction(
            payment_id=payment.id,
            expected_visit_id=payment.visit_id,
            expected_provider=payment.provider,
            expected_provider_payment_id=payment.provider_payment_id,
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
        expected_provider: str | None,
        expected_provider_payment_id: str | None,
        reason: str | None = None,
    ) -> None:
        """Atomically cancel Payment and linked PaymentTransaction.

        The visit projection, Payment, linked PaymentTransaction, cancellation
        reason, and linked invoices are updated inside one ``transaction_ctx``
        so that a failure rolls the complete local mutation back. For provider
        payments, the Payment and PaymentTransaction locks are deliberately held
        across the external cancellation call. This prevents a webhook or manual
        confirmation from committing a new local status after the initial read
        but before the provider result is reconciled.

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
                self.emr_facade.restore_operational_status_after_payment_change(
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

            if (
                locked_payment.provider != expected_provider
                or locked_payment.provider_payment_id
                != expected_provider_payment_id
            ):
                raise PaymentCancelDomainError(
                    status_code=409,
                    detail="Реквизиты провайдера изменились; обновите данные и повторите операцию",
                )

            # Lock and validate every local row before the irreversible external
            # call. A concurrent webhook uses the same Payment-first lock order,
            # so it cannot change the status until this transaction completes.
            transactions = (
                self.repository.get_transactions_by_payment_id_for_update(payment_id)
            )
            if len(transactions) > 1:
                raise PaymentCancelDomainError(
                    status_code=500,
                    detail=(
                        f"Payment {payment_id} has {len(transactions)} "
                        "PaymentTransaction rows — expected exactly 1 "
                        "(1:1 contract). Manual data reconciliation required "
                        "before cancellation can proceed safely."
                    ),
                )

            # 1. Update Payment status (no commit yet).
            #    billing_service.update_payment_status(commit=False)
            #    acquires SELECT Payment ... FOR UPDATE internally
            #    and flushes the UPDATE without committing.
            try:
                payment = self.billing_service.update_payment_status(
                    payment_id=payment_id,
                    new_status=PaymentStatus.CANCELLED.value,
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

            # 2. Update the already locked PaymentTransaction linked by
            #    payment_id FK.
            #    Zero rows = cash payment (no online transaction exists)
            #    — nothing to sync.
            #    >1 row = data-integrity invariant violation. Payment ↔
            #    PaymentTransaction is 1:1 by contract; multiple rows
            #    indicate a producer bug or manual DB modification that
            #    must be reconciled manually, not silently papered over.
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
            if expected_visit_id is not None:
                self.payment_invariant_service.synchronize_linked_invoices(
                    visit_id=expected_visit_id,
                    payment_method=payment.method,
                )
            self.db.flush()

            # Make the provider call only after every local mutation and
            # reconciliation has flushed successfully. The changes remain
            # uncommitted and the row locks remain held. A provider rejection
            # rolls the transaction back; a success leaves only the final DB
            # commit after the external side effect.
            if locked_payment.provider and locked_payment.provider_payment_id:
                result = self.payment_manager.cancel_payment(
                    locked_payment.provider,
                    locked_payment.provider_payment_id,
                )
                if not result.success:
                    logger.error(
                        "Provider cancel failed for payment_id=%s provider=%s: %s",
                        locked_payment.id,
                        locked_payment.provider,
                        result.error_message,
                    )
                    raise PaymentCancelDomainError(
                        status_code=502,
                        detail=(
                            f"Провайдер отклонил отмену: {result.error_message}. "
                            "Статус платежа не изменён. Повторите попытку или "
                            "обратитесь к провайдеру."
                        ),
                    )
                payment.provider_data = {
                    **(payment.provider_data or {}),
                    **result.provider_data,
                }
                self.db.flush()
