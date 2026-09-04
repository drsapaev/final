"""Regression tests for provider_webhook terminal-payment handling.

P2-3 (post-merge stabilization): verifies the invariant

    Terminal financial state must not be silently regressed by a
    later provider callback.

The defense introduced by PR #2698 is ``is_terminal_payment()`` in
``payment_state_checks.py``, checked in
``ProviderWebhookService._update_payment_status()`` (line 72).

These regression tests close the coverage gaps identified in the
P2-3 audit:

1. The P2 fix branch in ``_update_payment_status`` had ZERO direct
   test coverage — every existing test mocked it, bypassing the
   ``is_terminal_payment`` short-circuit entirely.

2. Click and Kaspi had NO terminal-state regression tests — only
   Payme had them (``TestPaymeTerminalStatePreservation``).

Per the user's directive: "If the current defense is_terminal_payment
is sufficient — do NOT change production code." The defense IS
sufficient for the invariant (terminal states {refunded, cancelled,
void} are correctly preserved). These tests pin that behavior without
changing production code.

FINDINGS DOCUMENTED (status as of Finding A fix):
- FINDING A: FIXED — the comment at provider_webhook_service.py:69 now
  correctly lists terminal statuses as (refunded/cancelled/void), excluding
  "paid". This was always a doc-only mismatch — paid is NOT terminal by
  design (it can transition to refunded/cancelled/void). The paid→failed
  case correctly falls through to BillingService which rejects it.
- FINDING C: when a NEW webhook (different transaction_id) arrives
  for an already-terminal payment with new_status="paid", BillingService
  raises ValueError → outer except rolls back → audit trail lost.
  This is an audit-trail-preservation issue, NOT a terminal-payment
  regression. Tracked as separate follow-up.

Run:
    pytest backend/tests/regression/test_p2_3_provider_webhook_terminal.py -v
"""
from __future__ import annotations

import logging
from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

from app.services.provider_webhook_service import ProviderWebhookService


@pytest.mark.unit
class TestUpdatePaymentStatusTerminalShortCircuit:
    """Direct unit tests for _update_payment_status P2 fix branch.

    These tests do NOT mock _update_payment_status — they let it run
    with a mocked repository and BillingService, so the actual
    is_terminal_payment short-circuit logic is exercised.

    This closes FINDING D: the P2 fix branch had zero direct coverage.
    """

    def _make_service(self, db_session, payment_status="refunded"):
        """Create a service with mocked repository and BillingService.

        The repository returns a payment with the given status.
        BillingService.update_payment_status is mocked to track calls.
        """
        payment = SimpleNamespace(
            id=44,
            amount=Decimal("1000"),
            status=payment_status,
            paid_at=None,
            provider_data={"order_id": "clinic_44_1700000000"},
        )
        repository = SimpleNamespace(
            get_payment_by_id=Mock(return_value=payment),
            get_payment_by_id_for_update=Mock(return_value=payment),
        )
        service = ProviderWebhookService(db_session, repository=repository)

        # Mock BillingService.update_payment_status to track if it's called.
        # When called, it sets payment.status = new_status (simulating the
        # real behavior for valid transitions).
        billing_mock = Mock()
        billing_mock.update_payment_status = Mock(
            side_effect=lambda payment_id, new_status, commit=False: (
                setattr(payment, 'status', new_status) or payment
            )
        )
        return service, payment, billing_mock, repository

    @pytest.mark.parametrize("terminal_status", ["refunded", "cancelled", "void"])
    def test_short_circuits_failed_on_terminal_payment(
        self, db_session, terminal_status, caplog
    ):
        """P2 fix: _update_payment_status with terminal payment + new_status='failed'
        must short-circuit — return payment unchanged, BillingService NOT called.

        This is the core P2 fix: a late 'failed' callback on a terminal payment
        must NOT change the status.
        """
        service, payment, billing_mock, _ = self._make_service(
            db_session, payment_status=terminal_status
        )

        with patch(
            "app.services.billing_service.BillingService",
            return_value=billing_mock,
        ):
            with caplog.at_level(logging.WARNING):
                result = service._update_payment_status(
                    payment_id=44, new_status="failed", commit=False
                )

        # ─── THE REGRESSION ASSERTIONS ─────────────────────────────
        # 1. Payment status unchanged (terminal preserved).
        assert result.status == terminal_status, (
            f"Terminal payment status '{terminal_status}' was regressed to "
            f"'{result.status}'. The P2 fix short-circuit did not fire."
        )
        # 2. BillingService.update_payment_status was NOT called.
        billing_mock.update_payment_status.assert_not_called(), (
            "BillingService.update_payment_status was called despite the "
            "payment being in a terminal state. The P2 fix short-circuit "
            "should have prevented this call."
        )
        # 3. Warning log emitted.
        assert any(
            "webhook.skip_failed_transition" in record.message
            for record in caplog.records
        ), (
            "Expected 'webhook.skip_failed_transition' warning log, "
            f"got: {[record.message for record in caplog.records]}"
        )

    def test_falls_through_for_paid_to_failed(self, db_session):
        """Documents that 'paid' is NOT terminal — paid→failed falls through
        to BillingService.

        This is correct behavior: paid is not terminal (it can transition to
        refunded/cancelled/void). A paid→failed transition is invalid and
        BillingService will reject it with ValueError.

        FINDING A: FIXED — the comment at provider_webhook_service.py:69
        previously said terminal includes "paid", but is_terminal_payment()
        excludes paid. The comment was corrected to list only
        (refunded/cancelled/void). This test pins the actual behavior.
        """
        service, payment, billing_mock, _ = self._make_service(
            db_session, payment_status="paid"
        )

        with patch(
            "app.services.billing_service.BillingService",
            return_value=billing_mock,
        ):
            service._update_payment_status(
                payment_id=44, new_status="failed", commit=False
            )

        # paid is NOT terminal → BillingService IS called.
        billing_mock.update_payment_status.assert_called_once_with(
            payment_id=44, new_status="failed", commit=False
        )

    @pytest.mark.parametrize("terminal_status", ["refunded", "cancelled", "void"])
    def test_falls_through_for_non_failed_target_on_terminal(
        self, db_session, terminal_status
    ):
        """P2 fix only short-circuits when new_status='failed'.

        For other targets (e.g. 'paid'), it falls through to BillingService,
        which will reject the transition (terminal→non-terminal is invalid).

        Note: BillingService raising ValueError on terminal→paid is a SEPARATE
        concern (FINDING C — audit-trail loss). This test only verifies that
        the P2 fix does NOT short-circuit for non-failed targets.
        """
        service, payment, billing_mock, _ = self._make_service(
            db_session, payment_status=terminal_status
        )

        with patch(
            "app.services.billing_service.BillingService",
            return_value=billing_mock,
        ):
            service._update_payment_status(
                payment_id=44, new_status="paid", commit=False
            )

        # P2 fix only short-circuits for new_status='failed'.
        # For 'paid', it falls through to BillingService.
        billing_mock.update_payment_status.assert_called_once_with(
            payment_id=44, new_status="paid", commit=False
        )

    def test_short_circuit_returns_same_payment_object(self, db_session):
        """The short-circuit must return the payment object (not None),
        so the caller can still update provider_data on it."""
        service, payment, billing_mock, _ = self._make_service(
            db_session, payment_status="refunded"
        )

        with patch(
            "app.services.billing_service.BillingService",
            return_value=billing_mock,
        ):
            result = service._update_payment_status(
                payment_id=44, new_status="failed", commit=False
            )

        assert result is payment, (
            "Short-circuit must return the payment object so the caller "
            "can update provider_data. Got a different object."
        )

    def test_short_circuit_handles_missing_repository_method(self, db_session):
        """If repository lacks get_payment_by_id, the P2 fix falls through
        to BillingService (defensive — no crash)."""
        repository = SimpleNamespace()  # no get_payment_by_id
        service = ProviderWebhookService(db_session, repository=repository)

        billing_mock = Mock()
        billing_mock.update_payment_status = Mock(return_value=SimpleNamespace(status="failed"))

        with patch(
            "app.services.billing_service.BillingService",
            return_value=billing_mock,
        ):
            # Should not raise — falls through to BillingService.
            result = service._update_payment_status(
                payment_id=44, new_status="failed", commit=False
            )

        billing_mock.update_payment_status.assert_called_once()


@pytest.mark.unit
class TestClickTerminalStatePreservation:
    """Terminal-state preservation tests for Click webhook handler.

    Mirrors TestPaymeTerminalStatePreservation but for Click.
    Closes FINDING E: Click had no terminal-state regression tests.

    These tests mock the repository and BillingService but do NOT mock
    _update_payment_status — so the P2 fix logic runs.
    """

    def _make_click_service(
        self,
        db_session,
        payment_status="refunded",
        payment_provider_data=None,
    ):
        """Create a service with mocked repository for Click webhook testing."""
        payment = SimpleNamespace(
            id=44,
            visit_id=10,
            amount=Decimal("1000"),
            status=payment_status,
            paid_at=None,
            provider_data=payment_provider_data or {"order_id": "clinic_44_1700000000"},
        )
        repository = SimpleNamespace(
            get_existing_transaction=Mock(return_value=None),  # not a duplicate
            get_payment_by_id=Mock(return_value=payment),
            get_payment_by_id_for_update=Mock(return_value=payment),
            create_webhook=Mock(return_value=SimpleNamespace(
                id=33, status="pending", error_message=None,
            )),
            create_transaction=Mock(return_value=SimpleNamespace(id=77)),
        )
        service = ProviderWebhookService(db_session, repository=repository)

        # Mock BillingService — when update_payment_status is called,
        # it simulates the real behavior:
        # - same-status: no-op (idempotent)
        # - valid transition: set status
        # - invalid transition (terminal→non-terminal): raise ValueError
        from app.services.payment_state_checks import is_valid_payment_transition

        def _billing_update(payment_id, new_status, commit=False):
            if payment.status == new_status:
                return payment  # idempotent
            if not is_valid_payment_transition(payment.status, new_status):
                raise ValueError(
                    f"Переход статуса с '{payment.status}' на '{new_status}' недопустим"
                )
            payment.status = new_status
            if new_status == "paid" and not payment.paid_at:
                payment.paid_at = datetime.now(UTC)
            return payment

        billing_mock = Mock()
        billing_mock.update_payment_status = Mock(side_effect=_billing_update)

        return service, payment, billing_mock, repository

    def _click_webhook_data(self, action="post"):
        return {
            "click_trans_id": "click_trans_123",
            "merchant_trans_id": "clinic_44_1700000000",
            "amount": 1000,
            "action": action,
            "sign_string": "valid_signature",
        }

    def _mock_provider_manager(self, result_status="completed", payment_id="clinic_44_1700000000"):
        """Mock the payment manager that processes the webhook."""
        result = SimpleNamespace(
            success=True,
            status=result_status,
            payment_id=payment_id,
            amount=Decimal("1000"),
            error_message=None,
            provider_data={"method": "Click", "transaction_id": "click_trans_123"},
        )
        return SimpleNamespace(
            get_provider=Mock(return_value=SimpleNamespace(
                validate_webhook_signature=Mock(return_value=True),
            )),
            process_webhook=Mock(return_value=result),
        )

    def test_click_success_callback_preserves_refunded_payment(self, db_session):
        """Click success callback on a refunded payment must NOT regress it.

        The payment stays 'refunded'. The P2 fix short-circuits if the
        mapped status is 'failed', but for a success callback the mapped
        status is 'paid'. BillingService rejects refunded→paid (ValueError),
        which is caught by the outer except and returns an error response.

        This test pins the CURRENT behavior: the invariant is preserved
        (payment stays refunded), but the webhook returns an error to the
        provider (FINDING C — audit-trail loss is a separate follow-up).
        """
        service, payment, billing_mock, _ = self._make_click_service(
            db_session, payment_status="refunded"
        )

        with patch(
            "app.services.provider_webhook_service.get_payment_manager",
            return_value=self._mock_provider_manager(),
        ), patch(
            "app.services.billing_service.BillingService",
            return_value=billing_mock,
        ):
            result = service.process_click_webhook(self._click_webhook_data())

        # ─── THE REGRESSION ASSERTION ──────────────────────────────
        # Payment status must NOT be regressed from 'refunded'.
        assert payment.status == "refunded", (
            f"Refunded payment was regressed to '{payment.status}'. "
            f"Terminal payment state must be preserved."
        )

    def test_click_success_callback_preserves_cancelled_payment(self, db_session):
        """Click success callback on a cancelled payment must NOT regress it."""
        service, payment, billing_mock, _ = self._make_click_service(
            db_session, payment_status="cancelled"
        )

        with patch(
            "app.services.provider_webhook_service.get_payment_manager",
            return_value=self._mock_provider_manager(),
        ), patch(
            "app.services.billing_service.BillingService",
            return_value=billing_mock,
        ):
            result = service.process_click_webhook(self._click_webhook_data())

        assert payment.status == "cancelled", (
            f"Cancelled payment was regressed to '{payment.status}'."
        )

    def test_click_success_callback_preserves_void_payment(self, db_session):
        """Click success callback on a void payment must NOT regress it."""
        service, payment, billing_mock, _ = self._make_click_service(
            db_session, payment_status="void"
        )

        with patch(
            "app.services.provider_webhook_service.get_payment_manager",
            return_value=self._mock_provider_manager(),
        ), patch(
            "app.services.billing_service.BillingService",
            return_value=billing_mock,
        ):
            result = service.process_click_webhook(self._click_webhook_data())

        assert payment.status == "void", (
            f"Void payment was regressed to '{payment.status}'."
        )

    def test_click_failure_callback_short_circuits_on_refunded(self, db_session):
        """Click failure callback on a refunded payment: P2 fix short-circuits.

        The payment stays 'refunded'. BillingService is NOT called.
        The webhook failure record is still committed (simulated here
        by the create_webhook mock).
        """
        service, payment, billing_mock, repo = self._make_click_service(
            db_session, payment_status="refunded"
        )

        # Failure callback: provider returns success=False
        fail_manager = self._mock_provider_manager()
        fail_manager.process_webhook.return_value = SimpleNamespace(
            success=False,
            status="failed",
            payment_id="clinic_44_1700000000",
            amount=Decimal("1000"),
            error_message="Provider error",
            provider_data={"method": "Click", "error": "timeout"},
        )

        with patch(
            "app.services.provider_webhook_service.get_payment_manager",
            return_value=fail_manager,
        ), patch(
            "app.services.billing_service.BillingService",
            return_value=billing_mock,
        ):
            result = service.process_click_webhook(self._click_webhook_data())

        # ─── THE REGRESSION ASSERTIONS ─────────────────────────────
        # 1. Payment stays refunded (terminal preserved).
        assert payment.status == "refunded", (
            f"Refunded payment was regressed to '{payment.status}' "
            f"by a failure callback."
        )
        # 2. BillingService.update_payment_status was NOT called
        #    (P2 fix short-circuited).
        billing_mock.update_payment_status.assert_not_called()

    def test_click_failure_callback_short_circuits_on_cancelled(self, db_session):
        """Click failure callback on a cancelled payment: P2 fix short-circuits."""
        service, payment, billing_mock, _ = self._make_click_service(
            db_session, payment_status="cancelled"
        )

        fail_manager = self._mock_provider_manager()
        fail_manager.process_webhook.return_value = SimpleNamespace(
            success=False,
            status="failed",
            payment_id="clinic_44_1700000000",
            amount=Decimal("1000"),
            error_message="Provider error",
            provider_data={"method": "Click", "error": "timeout"},
        )

        with patch(
            "app.services.provider_webhook_service.get_payment_manager",
            return_value=fail_manager,
        ), patch(
            "app.services.billing_service.BillingService",
            return_value=billing_mock,
        ):
            result = service.process_click_webhook(self._click_webhook_data())

        assert payment.status == "cancelled"
        billing_mock.update_payment_status.assert_not_called()

    def test_click_duplicate_webhook_returns_already_processed(self, db_session):
        """Click duplicate webhook (same click_trans_id) returns 'Already processed'
        without re-evaluating payment status.

        This is the idempotency path: get_existing_transaction finds a match
        and returns immediately.
        """
        existing_tx = SimpleNamespace(
            id=77,
            payment_id=44,
            webhook_id=33,
            status="completed",
        )
        payment = SimpleNamespace(
            id=44, visit_id=10, amount=Decimal("1000"),
            status="refunded", paid_at=None, provider_data={},
        )
        repository = SimpleNamespace(
            get_existing_transaction=Mock(return_value=existing_tx),
            get_payment_by_id=Mock(return_value=payment),
            get_payment_by_id_for_update=Mock(return_value=payment),
            create_webhook=Mock(),
            create_transaction=Mock(),
        )
        service = ProviderWebhookService(db_session, repository=repository)

        billing_mock = Mock()
        billing_mock.update_payment_status = Mock()

        with patch(
            "app.services.provider_webhook_service.get_payment_manager",
            return_value=self._mock_provider_manager(),
        ), patch(
            "app.services.billing_service.BillingService",
            return_value=billing_mock,
        ):
            result = service.process_click_webhook(self._click_webhook_data())

        # ─── THE REGRESSION ASSERTIONS ─────────────────────────────
        assert result["error"] == 0
        assert result["error_note"] == "Already processed"
        # Payment status NOT re-evaluated.
        assert payment.status == "refunded"
        # BillingService NOT called (idempotent short-circuit).
        billing_mock.update_payment_status.assert_not_called()
        # No new webhook record created.
        repository.create_webhook.assert_not_called()


@pytest.mark.unit
class TestKaspiTerminalStatePreservation:
    """Terminal-state preservation tests for Kaspi webhook handler.

    Mirrors TestClickTerminalStatePreservation but for Kaspi.
    Closes FINDING E: Kaspi had no terminal-state regression tests.
    """

    def _make_kaspi_service(
        self,
        db_session,
        payment_status="refunded",
        payment_provider_data=None,
    ):
        """Create a service with mocked repository for Kaspi webhook testing."""
        payment = SimpleNamespace(
            id=44,
            visit_id=10,
            amount=Decimal("1000"),
            status=payment_status,
            paid_at=None,
            provider_data=payment_provider_data or {"order_id": "kaspi_44"},
        )
        repository = SimpleNamespace(
            get_existing_transaction=Mock(return_value=None),
            get_payment_by_id=Mock(return_value=payment),
            get_payment_by_provider_payment_id_for_update=Mock(return_value=payment),
            create_webhook=Mock(return_value=SimpleNamespace(
                id=33, status="pending", error_message=None,
            )),
            create_transaction=Mock(return_value=SimpleNamespace(id=77)),
        )
        service = ProviderWebhookService(db_session, repository=repository)

        from app.services.payment_state_checks import is_valid_payment_transition

        def _billing_update(payment_id, new_status, commit=False):
            if payment.status == new_status:
                return payment
            if not is_valid_payment_transition(payment.status, new_status):
                raise ValueError(
                    f"Переход статуса с '{payment.status}' на '{new_status}' недопустим"
                )
            payment.status = new_status
            if new_status == "paid" and not payment.paid_at:
                payment.paid_at = datetime.now(UTC)
            return payment

        billing_mock = Mock()
        billing_mock.update_payment_status = Mock(side_effect=_billing_update)

        return service, payment, billing_mock, repository

    def _kaspi_webhook_data(self):
        return {
            "transaction_id": "kaspi_trans_123",
            "payment_id": "kaspi_44",
            "amount": 1000,
            "currency": "KZT",
            "signature": "valid_signature",
        }

    def _mock_provider_manager(self, result_status="completed", payment_id="kaspi_44"):
        result = SimpleNamespace(
            success=True,
            status=result_status,
            payment_id=payment_id,
            amount=Decimal("1000"),
            error_message=None,
            provider_data={"method": "Kaspi", "transaction_id": "kaspi_trans_123"},
        )
        return SimpleNamespace(
            get_provider=Mock(return_value=SimpleNamespace(
                validate_webhook_signature=Mock(return_value=True),
            )),
            process_webhook=Mock(return_value=result),
        )

    def test_kaspi_success_callback_preserves_refunded_payment(self, db_session):
        """Kaspi success callback on a refunded payment must NOT regress it."""
        service, payment, billing_mock, _ = self._make_kaspi_service(
            db_session, payment_status="refunded"
        )

        with patch(
            "app.services.provider_webhook_service.get_payment_manager",
            return_value=self._mock_provider_manager(),
        ), patch(
            "app.services.billing_service.BillingService",
            return_value=billing_mock,
        ):
            result = service.process_kaspi_webhook(self._kaspi_webhook_data())

        assert payment.status == "refunded", (
            f"Refunded payment was regressed to '{payment.status}'."
        )

    def test_kaspi_success_callback_preserves_cancelled_payment(self, db_session):
        """Kaspi success callback on a cancelled payment must NOT regress it."""
        service, payment, billing_mock, _ = self._make_kaspi_service(
            db_session, payment_status="cancelled"
        )

        with patch(
            "app.services.provider_webhook_service.get_payment_manager",
            return_value=self._mock_provider_manager(),
        ), patch(
            "app.services.billing_service.BillingService",
            return_value=billing_mock,
        ):
            result = service.process_kaspi_webhook(self._kaspi_webhook_data())

        assert payment.status == "cancelled"

    def test_kaspi_success_callback_preserves_void_payment(self, db_session):
        """Kaspi success callback on a void payment must NOT regress it."""
        service, payment, billing_mock, _ = self._make_kaspi_service(
            db_session, payment_status="void"
        )

        with patch(
            "app.services.provider_webhook_service.get_payment_manager",
            return_value=self._mock_provider_manager(),
        ), patch(
            "app.services.billing_service.BillingService",
            return_value=billing_mock,
        ):
            result = service.process_kaspi_webhook(self._kaspi_webhook_data())

        assert payment.status == "void"

    def test_kaspi_failure_callback_short_circuits_on_refunded(self, db_session):
        """Kaspi failure callback on a refunded payment: P2 fix short-circuits."""
        service, payment, billing_mock, _ = self._make_kaspi_service(
            db_session, payment_status="refunded"
        )

        fail_manager = self._mock_provider_manager()
        fail_manager.process_webhook.return_value = SimpleNamespace(
            success=False,
            status="failed",
            payment_id="kaspi_44",
            amount=Decimal("1000"),
            error_message="Provider error",
            provider_data={"method": "Kaspi", "error": "timeout"},
        )

        with patch(
            "app.services.provider_webhook_service.get_payment_manager",
            return_value=fail_manager,
        ), patch(
            "app.services.billing_service.BillingService",
            return_value=billing_mock,
        ):
            result = service.process_kaspi_webhook(self._kaspi_webhook_data())

        assert payment.status == "refunded"
        billing_mock.update_payment_status.assert_not_called()

    def test_kaspi_duplicate_webhook_returns_already_processed(self, db_session):
        """Kaspi duplicate webhook returns 'Already processed' without
        re-evaluating payment status."""
        existing_tx = SimpleNamespace(
            id=77,
            payment_id=44,
            webhook_id=33,
            status="completed",
        )
        payment = SimpleNamespace(
            id=44, visit_id=10, amount=Decimal("1000"),
            status="refunded", paid_at=None, provider_data={},
        )
        repository = SimpleNamespace(
            get_existing_transaction=Mock(return_value=existing_tx),
            get_payment_by_id=Mock(return_value=payment),
            get_payment_by_provider_payment_id_for_update=Mock(return_value=payment),
            create_webhook=Mock(),
            create_transaction=Mock(),
        )
        service = ProviderWebhookService(db_session, repository=repository)

        billing_mock = Mock()
        billing_mock.update_payment_status = Mock()

        with patch(
            "app.services.provider_webhook_service.get_payment_manager",
            return_value=self._mock_provider_manager(),
        ), patch(
            "app.services.billing_service.BillingService",
            return_value=billing_mock,
        ):
            result = service.process_kaspi_webhook(self._kaspi_webhook_data())

        # ─── THE REGRESSION ASSERTIONS ─────────────────────────────
        assert result.get("status") == "success" or result.get("error") is None or "Already" in str(result)
        # Payment status NOT re-evaluated.
        assert payment.status == "refunded"
        # BillingService NOT called.
        billing_mock.update_payment_status.assert_not_called()
        # No new webhook record created.
        repository.create_webhook.assert_not_called()
