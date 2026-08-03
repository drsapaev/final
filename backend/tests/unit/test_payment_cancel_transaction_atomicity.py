"""Tests for PaymentCancelService atomic transaction update (FOLLOWUP-8).

Validates that cancel_payment() atomically updates both Payment.status
and PaymentTransaction.status in a single DB transaction, with
row-level locking on both tables.
"""
from __future__ import annotations

from unittest.mock import patch

import pytest

from app.models.payment import Payment
from app.models.payment_webhook import PaymentTransaction
from app.services.payment_cancel_service import (
    PaymentCancelDomainError,
    PaymentCancelService,
)
from app.services.payment_providers.base import PaymentResult


class _FakePaymentManager:
    def __init__(self, result: PaymentResult):
        self.result = result

    def cancel_payment(self, provider_name: str, provider_payment_id: str) -> PaymentResult:
        return self.result


@pytest.mark.unit
class TestPaymentCancelTransactionAtomicity:
    """Verify atomic cancellation of Payment + PaymentTransaction."""

    def _create_payment_with_transaction(
        self, db_session, test_visit, payment_status="processing",
        tx_status="processing", provider="click"
    ):
        payment = Payment(
            visit_id=test_visit.id,
            amount=10_000.0,
            currency="UZS",
            method="online",
            status=payment_status,
            provider=provider,
            provider_payment_id="provider-123",
            provider_data={"source": "unit"},
        )
        db_session.add(payment)
        db_session.flush()

        tx = PaymentTransaction(
            transaction_id="tx-123",
            provider=provider,
            amount=1_000_000,
            currency="UZS",
            status=tx_status,
            payment_id=payment.id,
            webhook_id=None,
            visit_id=test_visit.id,
            provider_data={"method": "CreateTransaction"},
        )
        db_session.add(tx)
        db_session.commit()
        db_session.refresh(payment)
        db_session.refresh(tx)
        return payment, tx

    def test_cancel_updates_payment_and_transaction_atomically(
        self, db_session, test_visit
    ):
        """Both Payment.status and PaymentTransaction.status are 'cancelled'
        after cancel."""
        payment, tx = self._create_payment_with_transaction(
            db_session, test_visit, payment_status="processing", tx_status="processing"
        )

        service = PaymentCancelService(
            db_session, _FakePaymentManager(PaymentResult(success=True))
        )
        result = service.cancel_payment(payment_id=payment.id)

        db_session.refresh(payment)
        db_session.refresh(tx)
        assert result["success"] is True
        assert payment.status == "cancelled"
        assert tx.status == "cancelled"

    def test_cancel_rolls_back_on_transaction_error(
        self, db_session, test_visit
    ):
        """If an exception occurs after Payment is updated but before
        Transaction is updated, both are rolled back.

        Patches billing_service.update_payment_status to call the
        original (with commit=False) and then raise RuntimeError —
        simulating a failure between Payment.status write and the
        PaymentTransaction lookup. transaction_ctx must roll back
        BOTH writes.
        """
        payment, tx = self._create_payment_with_transaction(
            db_session, test_visit, payment_status="processing", tx_status="processing"
        )

        service = PaymentCancelService(
            db_session, _FakePaymentManager(PaymentResult(success=True))
        )

        original_update = service.billing_service.update_payment_status

        def update_then_fail(*args, **kwargs):
            kwargs["commit"] = False
            original_update(*args, **kwargs)
            # Simulate failure after Payment is updated but before
            # the PaymentTransaction query/lock runs.
            raise RuntimeError("Simulated failure before transaction update")

        with patch.object(
            service.billing_service, "update_payment_status", side_effect=update_then_fail
        ):
            with pytest.raises(RuntimeError):
                service.cancel_payment(payment_id=payment.id)

        # Both should be unchanged due to transaction_ctx rollback.
        db_session.refresh(payment)
        db_session.refresh(tx)
        assert payment.status == "processing"
        assert tx.status == "processing"

    def test_cancel_does_not_update_terminal_transaction(
        self, db_session, test_visit
    ):
        """If transaction is already 'refunded' (terminal), it stays
        'refunded' — not overwritten to 'cancelled'."""
        payment, tx = self._create_payment_with_transaction(
            db_session, test_visit, payment_status="processing", tx_status="refunded"
        )

        service = PaymentCancelService(
            db_session, _FakePaymentManager(PaymentResult(success=True))
        )
        result = service.cancel_payment(payment_id=payment.id)

        db_session.refresh(payment)
        db_session.refresh(tx)
        assert payment.status == "cancelled"
        assert tx.status == "refunded"  # NOT overwritten

    def test_cancel_cash_payment_no_transaction(self, db_session, test_visit):
        """Cash payment (no PaymentTransaction) still works — no error."""
        payment = Payment(
            visit_id=test_visit.id,
            amount=10_000.0,
            currency="UZS",
            method="cash",
            status="pending",
        )
        db_session.add(payment)
        db_session.commit()
        db_session.refresh(payment)

        service = PaymentCancelService(
            db_session, _FakePaymentManager(PaymentResult(success=True))
        )
        result = service.cancel_payment(payment_id=payment.id)

        db_session.refresh(payment)
        assert result["success"] is True
        assert payment.status == "cancelled"

    def test_cancel_idempotent_does_not_break_consistency(
        self, db_session, test_visit
    ):
        """Calling cancel twice on already-cancelled payment raises error
        but doesn't corrupt state."""
        payment, tx = self._create_payment_with_transaction(
            db_session, test_visit, payment_status="processing", tx_status="processing"
        )

        service = PaymentCancelService(
            db_session, _FakePaymentManager(PaymentResult(success=True))
        )
        # First cancel succeeds.
        service.cancel_payment(payment_id=payment.id)

        db_session.refresh(payment)
        db_session.refresh(tx)
        assert payment.status == "cancelled"
        assert tx.status == "cancelled"

        # Second cancel should raise (status not cancellable).
        with pytest.raises(PaymentCancelDomainError) as exc_info:
            service.cancel_payment(payment_id=payment.id)
        assert exc_info.value.status_code == 400

    def test_cancel_online_payment_with_completed_transaction(
        self, db_session, test_visit
    ):
        """Transaction 'completed' → 'cancelled' (valid non-terminal
        transition) + Payment 'processing' → 'cancelled'."""
        payment, tx = self._create_payment_with_transaction(
            db_session, test_visit, payment_status="processing", tx_status="completed"
        )

        service = PaymentCancelService(
            db_session, _FakePaymentManager(PaymentResult(success=True))
        )
        result = service.cancel_payment(payment_id=payment.id)

        db_session.refresh(payment)
        db_session.refresh(tx)
        assert result["success"] is True
        assert payment.status == "cancelled"
        assert tx.status == "cancelled"

    def test_cancel_multiple_transactions_raises_invariant_error(
        self, db_session, test_visit
    ):
        """If Payment has >1 linked PaymentTransaction (1:1 contract
        violation), cancel must raise PaymentCancelDomainError(500)
        and NOT silently pick the first one.

        Critical: the entire transaction_ctx must roll back —
        Payment.status must remain unchanged.
        """
        payment, _ = self._create_payment_with_transaction(
            db_session, test_visit, payment_status="processing", tx_status="processing"
        )

        # Insert a second PaymentTransaction row pointing at the same
        # payment_id — simulates producer bug or manual DB modification.
        duplicate_tx = PaymentTransaction(
            transaction_id="tx-DUPLICATE",
            provider="click",
            amount=1_000_000,
            currency="UZS",
            status="processing",
            payment_id=payment.id,
            webhook_id=None,
            visit_id=test_visit.id,
            provider_data={"method": "CreateTransaction"},
        )
        db_session.add(duplicate_tx)
        db_session.commit()
        db_session.refresh(payment)

        service = PaymentCancelService(
            db_session, _FakePaymentManager(PaymentResult(success=True))
        )

        with pytest.raises(PaymentCancelDomainError) as exc_info:
            service.cancel_payment(payment_id=payment.id)

        assert exc_info.value.status_code == 500
        assert "expected exactly 1" in exc_info.value.detail

        # Rollback guarantee: Payment.status must NOT be 'cancelled'.
        db_session.refresh(payment)
        assert payment.status == "processing"

    def test_cancel_multiple_transactions_raises_before_provider_call(
        self, db_session, test_visit
    ):
        """Codex P1 #1 regression guard: the cardinality pre-check must
        fire BEFORE the external provider cancel is called.

        Without the pre-check, the provider cancel would succeed first,
        then the locked cardinality check inside
        _cancel_payment_and_transaction would raise 500 — leaving the
        provider cancelled while the local Payment stays unchanged.

        With the pre-check, payment_manager.cancel_payment() is NEVER
        called when the invariant is already violated.
        """
        payment, _ = self._create_payment_with_transaction(
            db_session, test_visit, payment_status="processing", tx_status="processing"
        )

        duplicate_tx = PaymentTransaction(
            transaction_id="tx-DUPLICATE",
            provider="click",
            amount=1_000_000,
            currency="UZS",
            status="processing",
            payment_id=payment.id,
            webhook_id=None,
            visit_id=test_visit.id,
            provider_data={"method": "CreateTransaction"},
        )
        db_session.add(duplicate_tx)
        db_session.commit()
        db_session.refresh(payment)

        # Use a fake manager that would FAIL the cancel call — if the
        # pre-check works, the manager is never called at all, so the
        # failure never happens. If the pre-check is missing, the
        # manager is called, returns failure, and we'd see a 502
        # instead of the expected 500.
        fake_manager = _FakePaymentManager(
            PaymentResult(success=False, error_message="SHOULD_NOT_BE_CALLED")
        )
        service = PaymentCancelService(db_session, fake_manager)

        # Track whether cancel_payment was invoked on the manager.
        original_cancel = fake_manager.cancel_payment
        call_count = {"n": 0}

        def tracking_cancel(provider_name, provider_payment_id):
            call_count["n"] += 1
            return original_cancel(provider_name, provider_payment_id)

        fake_manager.cancel_payment = tracking_cancel

        with pytest.raises(PaymentCancelDomainError) as exc_info:
            service.cancel_payment(payment_id=payment.id)

        assert exc_info.value.status_code == 500
        assert "expected exactly 1" in exc_info.value.detail
        assert call_count["n"] == 0, (
            "payment_manager.cancel_payment() must NOT be called when "
            "the cardinality pre-check detects >1 PaymentTransaction. "
            f"Was called {call_count['n']} time(s)."
        )


@pytest.mark.unit
class TestPaymentCancelRepositoryLocking:
    """Verify that PaymentCancelRepository acquires FOR UPDATE on Tx rows.

    This is the TOCTOU guard against concurrent webhook writes —
    see payment_cancel_repository.get_transactions_by_payment_id_for_update
    docstring for the race scenario.
    """

    def test_get_transactions_by_payment_id_for_update_uses_with_for_update(
        self, db_session, test_visit
    ):
        """The query must call .with_for_update() to acquire row locks."""
        from app.repositories.payment_cancel_repository import PaymentCancelRepository
        from unittest.mock import MagicMock

        # Build a fake query chain that records whether with_for_update
        # was called. We don't hit the real DB — we just verify the
        # query builder path.
        fake_db = MagicMock()
        fake_query = MagicMock()
        fake_filtered = MagicMock()

        # db.query(PaymentTransaction) -> fake_query
        fake_db.query.return_value = fake_query
        # fake_query.filter(...) -> fake_filtered
        fake_query.filter.return_value = fake_filtered
        # fake_filtered.with_for_update() -> fake_locked
        fake_locked = MagicMock()
        fake_filtered.with_for_update.return_value = fake_locked
        # fake_locked.all() -> []
        fake_locked.all.return_value = []

        repo = PaymentCancelRepository(fake_db)
        result = repo.get_transactions_by_payment_id_for_update(payment_id=42)

        # Verify the chain: query -> filter -> with_for_update -> all
        fake_db.query.assert_called_once()
        fake_query.filter.assert_called_once()
        fake_filtered.with_for_update.assert_called_once_with()
        fake_locked.all.assert_called_once()
        assert result == []
