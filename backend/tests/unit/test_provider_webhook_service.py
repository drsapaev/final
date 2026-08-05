from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

from app.services.provider_webhook_service import ProviderWebhookService


@pytest.mark.unit
class TestProviderWebhookService:
    def test_click_webhook_requires_signature(self, db_session):
        service = ProviderWebhookService(db_session)

        result = service.process_click_webhook({"merchant_trans_id": "1"})

        assert result["error"] == -1
        assert result["error_note"] == "Missing signature"

    def test_payme_webhook_requires_auth_header(self, db_session):
        service = ProviderWebhookService(db_session)

        result = service.process_payme_webhook({"id": 123, "method": "CheckPerformTransaction"}, None)

        assert result["id"] == 123
        assert result["error"]["code"] == -32504
        assert result["error"]["message"] == "Missing Authorization header"

    def test_payme_perform_existing_transaction_marks_payment_paid(self, db_session):
        transaction = SimpleNamespace(
            id=77,
            payment_id=44,
            webhook_id=33,
            status="processing",
            provider_data={"method": "CreateTransaction"},
        )
        payment = SimpleNamespace(
            id=44,
            amount=Decimal("1000"),
            status="processing",
            paid_at=None,
            provider_data={"order_id": "clinic_44_1700000000"},
        )
        repository = SimpleNamespace(
            get_existing_transaction=Mock(return_value=transaction),
            get_payment_by_id=Mock(return_value=payment),
            get_payment_by_id_for_update=Mock(return_value=payment),
        )
        manager = SimpleNamespace(
            get_provider=Mock(
                return_value=SimpleNamespace(
                    validate_webhook_signature=Mock(return_value=True)
                )
            )
        )
        service = ProviderWebhookService(db_session, repository=repository)

        with patch(
            "app.services.provider_webhook_service.get_payment_manager",
            return_value=manager,
        ):
            result = service.process_payme_webhook(
                {
                    "id": "request-1",
                    "method": "PerformTransaction",
                    "params": {"id": "payme-tx-1", "amount": 100000},
                },
                "Basic valid",
            )

        assert result["result"]["state"] == 2
        assert result["payment_id"] == 44
        assert result["payment_status"] == "paid"
        assert transaction.status == "completed"
        assert transaction.provider_data["method"] == "PerformTransaction"
        assert payment.status == "paid"
        assert payment.paid_at is not None
        assert payment.provider_data["order_id"] == "clinic_44_1700000000"
        assert payment.provider_data["transaction_id"] == "payme-tx-1"

    def test_payme_perform_existing_transaction_rejects_amount_mismatch(
        self, db_session
    ):
        transaction = SimpleNamespace(
            id=77,
            payment_id=44,
            webhook_id=33,
            status="processing",
            provider_data={"method": "CreateTransaction"},
        )
        payment = SimpleNamespace(
            id=44,
            amount=Decimal("1000"),
            status="processing",
            paid_at=None,
            provider_data={"order_id": "clinic_44_1700000000"},
        )
        repository = SimpleNamespace(
            get_existing_transaction=Mock(return_value=transaction),
            get_payment_by_id=Mock(return_value=payment),
            get_payment_by_id_for_update=Mock(return_value=payment),
        )
        manager = SimpleNamespace(
            get_provider=Mock(
                return_value=SimpleNamespace(
                    validate_webhook_signature=Mock(return_value=True)
                )
            )
        )
        service = ProviderWebhookService(db_session, repository=repository)

        with patch(
            "app.services.provider_webhook_service.get_payment_manager",
            return_value=manager,
        ):
            result = service.process_payme_webhook(
                {
                    "id": "request-1",
                    "method": "PerformTransaction",
                    "params": {"id": "payme-tx-1", "amount": 100},
                },
                "Basic valid",
            )

        assert result["error"]["code"] == -31001
        assert result["error"]["message"] == "Payment amount mismatch"
        assert result["payment_id"] == 44
        assert result["payment_status"] is None
        assert transaction.status == "processing"
        assert transaction.provider_data == {"method": "CreateTransaction"}
        assert payment.status == "processing"
        assert payment.paid_at is None

    def test_click_webhook_rejects_amount_mismatch_without_marking_payment_paid(
        self, db_session
    ):
        webhook = SimpleNamespace(id=33, status="pending", processed_at=None)
        payment = SimpleNamespace(
            id=44,
            amount=Decimal("1000"),
            status="pending",
            paid_at=None,
            provider_data={},
            visit_id=55,
        )
        repository = SimpleNamespace(
            get_existing_transaction=Mock(return_value=None),
            create_webhook=Mock(return_value=webhook),
            get_payment_by_id=Mock(return_value=payment),
            get_payment_by_id_for_update=Mock(return_value=payment),
            create_transaction=Mock(),
        )
        manager = SimpleNamespace(
            get_provider=Mock(
                return_value=SimpleNamespace(
                    validate_webhook_signature=Mock(return_value=True)
                )
            ),
            process_webhook=Mock(
                return_value=SimpleNamespace(
                    success=True,
                    payment_id="clinic_44_1700000000",
                    status="completed",
                    provider_data={"amount": Decimal("1")},
                )
            ),
        )
        service = ProviderWebhookService(db_session, repository=repository)

        with patch(
            "app.services.provider_webhook_service.get_payment_manager",
            return_value=manager,
        ):
            result = service.process_click_webhook(
                {
                    "click_trans_id": "click-1",
                    "merchant_trans_id": "clinic_44_1700000000",
                    "amount": 100,
                    "sign_string": "valid",
                }
            )

        assert result["error"] == -1
        assert result["error_note"] == "Payment amount mismatch"
        assert result["payment_id"] == 44
        assert result["payment_status"] is None
        assert webhook.status == "failed"
        assert webhook.error_message == "provider_amount_mismatch"
        assert payment.status == "pending"
        assert payment.paid_at is None
        repository.create_transaction.assert_not_called()

    # --- FOLLOWUP-10: Click/Kaspi/Payme must lock Payment before mutation ---

    def test_click_webhook_locks_payment_before_mutation(self, db_session):
        """FOLLOWUP-10 regression guard: Click handler must call
        get_payment_by_id_for_update (not get_payment_by_id) before
        mutating payment.status. Without the lock, a concurrent cashier
        cancel could commit a terminal status between our read and
        write, leaving Payment and PaymentTransaction inconsistent.
        """
        webhook = SimpleNamespace(id=33, status="pending", processed_at=None)
        payment = SimpleNamespace(
            id=44,
            amount=Decimal("1000"),
            status="pending",
            paid_at=None,
            provider_data={},
            visit_id=55,
        )
        repository = SimpleNamespace(
            get_existing_transaction=Mock(return_value=None),
            create_webhook=Mock(return_value=webhook),
            get_payment_by_id=Mock(return_value=payment),
            get_payment_by_id_for_update=Mock(return_value=payment),
            create_transaction=Mock(),
        )
        manager = SimpleNamespace(
            get_provider=Mock(
                return_value=SimpleNamespace(
                    validate_webhook_signature=Mock(return_value=True)
                )
            ),
            process_webhook=Mock(
                return_value=SimpleNamespace(
                    success=True,
                    payment_id="clinic_44_1700000000",
                    status="completed",
                    provider_data={"amount": Decimal("1000")},
                )
            ),
        )
        service = ProviderWebhookService(db_session, repository=repository)

        with patch(
            "app.services.provider_webhook_service.get_payment_manager",
            return_value=manager,
        ):
            service.process_click_webhook(
                {
                    "click_trans_id": "click-1",
                    "merchant_trans_id": "clinic_44_1700000000",
                    "amount": 100000,
                    "sign_string": "valid",
                }
            )

        # The locked variant must be called; the unlocked one must NOT.
        repository.get_payment_by_id_for_update.assert_called_once_with(44)
        repository.get_payment_by_id.assert_not_called()

    def test_kaspi_webhook_locks_payment_before_mutation(self, db_session):
        """FOLLOWUP-10 regression guard: Kaspi handler must call
        get_payment_by_provider_payment_id_for_update (not
        get_payment_by_provider_payment_id) before mutating payment.status.
        """
        webhook = SimpleNamespace(id=33, status="pending", processed_at=None)
        payment = SimpleNamespace(
            id=44,
            amount=Decimal("1000"),
            status="pending",
            paid_at=None,
            provider_data={},
            visit_id=55,
        )
        repository = SimpleNamespace(
            get_existing_transaction=Mock(return_value=None),
            create_webhook=Mock(return_value=webhook),
            get_payment_by_provider_payment_id=Mock(return_value=payment),
            get_payment_by_provider_payment_id_for_update=Mock(
                return_value=payment
            ),
            create_transaction=Mock(),
        )
        manager = SimpleNamespace(
            get_provider=Mock(
                return_value=SimpleNamespace(
                    validate_webhook_signature=Mock(return_value=True)
                )
            ),
            process_webhook=Mock(
                return_value=SimpleNamespace(
                    success=True,
                    payment_id="kaspi-pay-123",
                    status="completed",
                    provider_data={"amount": Decimal("1000")},
                )
            ),
        )
        service = ProviderWebhookService(db_session, repository=repository)

        with patch(
            "app.services.provider_webhook_service.get_payment_manager",
            return_value=manager,
        ):
            service.process_kaspi_webhook(
                {
                    "transaction_id": "kaspi-1",
                    "merchant_id": "m1",
                    "amount": 100000,
                    "currency": "KZT",
                    "signature": "valid",
                }
            )

        # The locked variant must be called; the unlocked one must NOT.
        repository.get_payment_by_provider_payment_id_for_update.assert_called_once_with(
            "kaspi-pay-123"
        )
        repository.get_payment_by_provider_payment_id.assert_not_called()

    def test_extract_payment_id_from_order(self, db_session):
        service = ProviderWebhookService(db_session)

        assert service._extract_payment_id_from_order("clinic_55_1700000000") == 55
        assert service._extract_payment_id_from_order("bad_order") is None

    def test_map_provider_status_to_payment_status(self, db_session):
        service = ProviderWebhookService(db_session)

        assert service._map_provider_status_to_payment_status("completed") == "paid"
        assert service._map_provider_status_to_payment_status("unknown-status") == "failed"


@pytest.mark.unit
class TestPaymeTerminalStatePreservation:
    """Verify that duplicate Payme webhooks do not overwrite terminal payment
    or transaction states. A duplicate PerformTransaction must not reopen a
    refunded/cancelled/void payment; a duplicate CancelTransaction must not
    change a refunded payment to cancelled.

    The audit trail (provider_data) is still updated so devops can see the
    last webhook payload, even when status is not mutated.
    """

    def _make_service(
        self,
        db_session,
        transaction_status="processing",
        payment_status="processing",
        transaction_provider_data=None,
        payment_provider_data=None,
        locked_payment_status=None,
    ):
        transaction = SimpleNamespace(
            id=77,
            payment_id=44,
            webhook_id=33,
            status=transaction_status,
            provider_data=transaction_provider_data
            or {"method": "CreateTransaction"},
        )
        payment = SimpleNamespace(
            id=44,
            amount=Decimal("1000"),
            status=payment_status,
            paid_at=None,
            provider_data=payment_provider_data
            or {"order_id": "clinic_44_1700000000"},
        )
        # locked_payment simulates a TOCTOU race: the unlocked read sees
        # the original status, but the FOR UPDATE read sees a different
        # status (e.g. another transaction committed "cancelled" between
        # the two reads).
        locked_payment = SimpleNamespace(
            id=44,
            amount=Decimal("1000"),
            status=locked_payment_status or payment_status,
            paid_at=None,
            provider_data=payment_provider_data
            or {"order_id": "clinic_44_1700000000"},
        )
        repository = SimpleNamespace(
            get_existing_transaction=Mock(return_value=transaction),
            get_payment_by_id=Mock(return_value=payment),
            get_payment_by_id_for_update=Mock(return_value=locked_payment),
        )
        manager = SimpleNamespace(
            get_provider=Mock(
                return_value=SimpleNamespace(
                    validate_webhook_signature=Mock(return_value=True)
                )
            )
        )
        service = ProviderWebhookService(db_session, repository=repository)
        return service, transaction, payment, locked_payment

    def _call_perform(self, service, auth_header="Basic valid"):
        with patch(
            "app.services.provider_webhook_service.get_payment_manager",
            return_value=SimpleNamespace(
                get_provider=Mock(
                    return_value=SimpleNamespace(
                        validate_webhook_signature=Mock(return_value=True)
                    )
                )
            ),
        ):
            return service.process_payme_webhook(
                {
                    "id": "request-1",
                    "method": "PerformTransaction",
                    "params": {"id": "payme-tx-1", "amount": 100000},
                },
                auth_header,
            )

    def _call_cancel(self, service, reason=1, auth_header="Basic valid"):
        with patch(
            "app.services.provider_webhook_service.get_payment_manager",
            return_value=SimpleNamespace(
                get_provider=Mock(
                    return_value=SimpleNamespace(
                        validate_webhook_signature=Mock(return_value=True)
                    )
                )
            ),
        ):
            return service.process_payme_webhook(
                {
                    "id": "request-1",
                    "method": "CancelTransaction",
                    "params": {
                        "id": "payme-tx-1",
                        "amount": 100000,
                        "reason": reason,
                    },
                },
                auth_header,
            )

    # --- Terminal payment states: PerformTransaction must NOT overwrite ---

    def test_perform_does_not_overwrite_refunded_payment(self, db_session):
        service, tx, payment, _locked = self._make_service(
            db_session, payment_status="refunded"
        )
        result = self._call_perform(service)
        assert result["result"]["state"] == 2
        assert payment.status == "refunded"  # NOT overwritten to "paid"
        assert result["payment_status"] == "refunded"  # response shows truth

    def test_perform_does_not_overwrite_cancelled_payment(self, db_session):
        service, tx, payment, _locked = self._make_service(
            db_session, payment_status="cancelled"
        )
        result = self._call_perform(service)
        assert result["result"]["state"] == 2
        assert payment.status == "cancelled"
        assert result["payment_status"] == "cancelled"

    def test_perform_does_not_overwrite_void_payment(self, db_session):
        service, tx, payment, _locked = self._make_service(
            db_session, payment_status="void"
        )
        result = self._call_perform(service)
        assert result["result"]["state"] == 2
        assert payment.status == "void"
        assert result["payment_status"] == "void"

    # --- failed → paid blocked (not a valid direct transition) ---

    def test_perform_does_not_overwrite_failed_payment_to_paid(self, db_session):
        service, tx, payment, _locked = self._make_service(
            db_session, payment_status="failed"
        )
        result = self._call_perform(service)
        assert result["result"]["state"] == 2
        assert payment.status == "failed"
        assert result["payment_status"] == "failed"

    # --- Idempotent same-status: allowed, status not mutated ---

    def test_perform_on_paid_payment_is_idempotent(self, db_session):
        from datetime import UTC, datetime

        original_paid_at = datetime(2025, 1, 1, tzinfo=UTC)
        service, tx, payment, _locked = self._make_service(
            db_session,
            payment_status="paid",
            payment_provider_data={"order_id": "clinic_44_1700000000"},
        )
        payment.paid_at = original_paid_at
        result = self._call_perform(service)
        assert result["result"]["state"] == 2
        assert payment.status == "paid"
        assert payment.paid_at == original_paid_at  # NOT re-set

    def test_perform_on_completed_transaction_is_idempotent(self, db_session):
        service, tx, payment, _locked = self._make_service(
            db_session,
            transaction_status="completed",
            payment_status="paid",
        )
        result = self._call_perform(service)
        assert result["result"]["state"] == 2
        assert tx.status == "completed"  # unchanged

    # --- Regression: non-terminal forward transitions still allowed ---

    def test_perform_on_processing_payment_allowed(self, db_session):
        service, tx, payment, locked = self._make_service(
            db_session, payment_status="processing"
        )
        result = self._call_perform(service)
        assert result["result"]["state"] == 2
        assert locked.status == "paid"  # transition allowed (on locked object)
        assert tx.status == "completed"
        assert locked.paid_at is not None

    def test_perform_on_pending_payment_allowed(self, db_session):
        service, tx, payment, locked = self._make_service(
            db_session, payment_status="pending"
        )
        result = self._call_perform(service)
        assert result["result"]["state"] == 2
        assert locked.status == "paid"

    # --- CancelTransaction: terminal states preserved ---

    def test_cancel_on_refunded_payment_blocked(self, db_session):
        """refunded → cancelled is not allowed (refunded is terminal)."""
        service, tx, payment, _locked = self._make_service(
            db_session, payment_status="refunded"
        )
        result = self._call_cancel(service, reason=1)
        assert result["result"]["state"] == -1
        assert payment.status == "refunded"  # NOT overwritten to "cancelled"
        assert result["payment_status"] == "refunded"

    def test_cancel_on_cancelled_payment_idempotent(self, db_session):
        """cancelled → cancelled is idempotent (same-status)."""
        service, tx, payment, _locked = self._make_service(
            db_session, payment_status="cancelled"
        )
        result = self._call_cancel(service, reason=1)
        assert result["result"]["state"] == -1
        assert payment.status == "cancelled"

    # --- Audit trail: provider_data always updated, even when status blocked ---

    def test_blocked_transition_still_updates_provider_data(self, db_session):
        """When status overwrite is blocked, provider_data must still receive
        the new webhook payload — preserving the audit trail."""
        original_provider_data = {"order_id": "clinic_44_1700000000"}
        service, tx, payment, locked = self._make_service(
            db_session,
            payment_status="refunded",
            payment_provider_data=dict(original_provider_data),
        )
        self._call_perform(service)
        # locked payment status is NOT mutated (refunded is terminal)
        assert locked.status == "refunded"
        # BUT provider_data IS updated with the new webhook info
        assert locked.provider_data["method"] == "PerformTransaction"
        assert locked.provider_data["transaction_id"] == "payme-tx-1"
        assert "params" in locked.provider_data
        # Original data is preserved (merge, not replace)
        assert locked.provider_data["order_id"] == "clinic_44_1700000000"

    def test_blocked_transaction_transition_still_updates_tx_provider_data(
        self, db_session
    ):
        """Same audit-trail preservation for transaction.provider_data."""
        service, tx, payment, _locked = self._make_service(
            db_session,
            transaction_status="refunded",
            payment_status="refunded",
        )
        self._call_perform(service)
        assert tx.status == "refunded"  # NOT overwritten
        assert tx.provider_data["method"] == "PerformTransaction"
        assert tx.provider_data["transaction_id"] == "payme-tx-1"

    # --- Logging: blocked transitions must log warning ---

    def test_blocked_payment_transition_logs_warning(self, db_session, caplog):
        import logging

        service, tx, payment, _locked = self._make_service(
            db_session, payment_status="refunded"
        )
        with caplog.at_level(logging.WARNING, logger="app.services.provider_webhook_service"):
            self._call_perform(service)
        assert any(
            "ignored invalid payment transition" in rec.message
            and "refunded" in rec.message
            and "paid" in rec.message
            for rec in caplog.records
        )

    # === TOCTOU race condition tests ===

    def test_toctou_cancelled_during_unlocked_read(self, db_session):
        """Unlocked read sees 'processing', locked read sees 'cancelled'.

        The webhook must NOT overwrite the cancelled payment to 'paid'
        — it must see the post-cancellation state via FOR UPDATE.
        """
        service, tx, payment, _locked = self._make_service(
            db_session,
            transaction_status="completed",
            payment_status="processing",        # what unlocked read sees
            locked_payment_status="cancelled",  # what FOR UPDATE sees (TOCTOU)
        )
        result = self._call_perform(service)
        assert result["payment_status"] == "cancelled"

    def test_toctou_refunded_during_unlocked_read(self, db_session):
        """Unlocked read sees 'processing', locked read sees 'refunded'."""
        service, tx, payment, _locked = self._make_service(
            db_session,
            transaction_status="completed",
            payment_status="processing",
            locked_payment_status="refunded",
        )
        result = self._call_perform(service)
        assert result["payment_status"] == "refunded"

    def test_toctou_no_race_normal_path(self, db_session):
        """When there's no race (locked == unlocked), normal forward
        transition proceeds as expected."""
        service, tx, payment, _locked = self._make_service(
            db_session,
            transaction_status="processing",
            payment_status="processing",
            locked_payment_status="processing",  # no race — same status
        )
        result = self._call_perform(service)
        assert result["payment_status"] == "paid"

    # === Payment ↔ Transaction consistency tests ===

    def test_payment_cancelled_blocks_transaction_completed(self, db_session):
        """Payment is cancelled (terminal), transaction is processing.
        Duplicate PerformTransaction must NOT mark transaction completed
        — it would create an inconsistent (cancelled, completed) pair.
        """
        service, tx, payment, _locked = self._make_service(
            db_session,
            transaction_status="processing",   # transaction NOT terminal
            payment_status="cancelled",         # payment IS terminal
        )
        self._call_perform(service)
        assert tx.status == "processing"

    def test_payment_refunded_blocks_transaction_completed(self, db_session):
        """Payment is refunded (terminal), transaction is processing."""
        service, tx, payment, _locked = self._make_service(
            db_session,
            transaction_status="processing",
            payment_status="refunded",
        )
        self._call_perform(service)
        assert tx.status == "processing"

    def test_payment_not_terminal_allows_transaction_transition(self, db_session):
        """When payment is NOT terminal (e.g. processing), transaction
        transition proceeds normally — no defensive block."""
        service, tx, payment, _locked = self._make_service(
            db_session,
            transaction_status="processing",
            payment_status="processing",  # not terminal
        )
        self._call_perform(service)
        assert tx.status == "completed"

    def test_defensive_guard_logs_warning(self, db_session, caplog):
        """When defensive guard blocks transaction transition, it must
        log a warning mentioning 'Payme duplicate-webhook protector' for
        traceability."""
        import logging

        service, tx, payment, _locked = self._make_service(
            db_session,
            transaction_status="processing",
            payment_status="cancelled",
        )
        with caplog.at_level(
            logging.WARNING, logger="app.services.provider_webhook_service"
        ):
            self._call_perform(service)
        assert any(
            "blocked transaction transition because linked payment is terminal"
            in rec.message
            and "Payme duplicate-webhook protector" in rec.message
            for rec in caplog.records
        )

    def test_provider_data_still_updated_when_defensive_guard_blocks(
        self, db_session
    ):
        """Even when the defensive guard blocks transaction.status,
        provider_data must still be updated (audit trail preserved)."""
        service, tx, payment, _locked = self._make_service(
            db_session,
            transaction_status="processing",
            payment_status="cancelled",
        )
        self._call_perform(service)
        assert tx.status == "processing"  # NOT changed
        assert tx.provider_data["method"] == "PerformTransaction"
        assert tx.provider_data["transaction_id"] == "payme-tx-1"

    # --- FOLLOWUP-12: pre-cancel state idempotency (ADR-0019) ---
    #
    # Payme spec (developer.help.paycom.uz/metody-merchant-api/tipy-dannykh):
    #   state -1 = "отменена (начальное состояние 1)" — Tx was in state 1
    #   state -2 = "отменена после завершения (начальное состояние 2)" — Tx was in state 2
    #
    # The CancelTransaction response state must reflect the transition that
    # occurred, based on the Tx status BEFORE the first CancelTransaction.
    # On retry (commit succeeded, response lost), Tx.status has already
    # mutated to 'refunded', so we cannot derive was_completed from it.
    # We persist pre_cancel_status in AuditLog on the first call and recover
    # it on retry (Option A per RFC #2679, ADR-0019 compliance).

    def test_cancel_first_call_on_completed_tx_returns_state_minus_2(
        self, db_session
    ):
        """First CancelTransaction on a completed Tx must return state=-2.

        Scenario: Tx.status='completed' (Payme state 2).
        Expected: response state=-2 (state 2 → -2 per spec).
        AuditLog INSERT persists pre_cancel_status='completed'.
        """
        from app.models.audit import AuditLog
        from app.services.provider_webhook_service import (
            PAYME_TX_PRE_CANCEL_STATE_ACTION,
        )

        service, tx, payment, _locked = self._make_service(
            db_session,
            transaction_status="completed",
            payment_status="paid",
        )
        result = self._call_cancel(service, reason=2)  # reason != 1 → refunded

        assert result["result"]["state"] == -2

        # Verify AuditLog record was persisted with pre_cancel_status
        audit_entry = (
            db_session.query(AuditLog)
            .filter(
                AuditLog.action == PAYME_TX_PRE_CANCEL_STATE_ACTION,
                AuditLog.entity_type == "payment_transaction",
                AuditLog.entity_id == tx.id,
            )
            .first()
        )
        assert audit_entry is not None
        assert audit_entry.payload["pre_cancel_status"] == "completed"

    def test_cancel_first_call_on_processing_tx_returns_state_minus_1(
        self, db_session
    ):
        """First CancelTransaction on a processing Tx must return state=-1.

        Scenario: Tx.status='processing' (Payme state 1).
        Expected: response state=-1 (state 1 → -1 per spec).
        """
        service, tx, payment, _locked = self._make_service(
            db_session,
            transaction_status="processing",
            payment_status="processing",
        )
        result = self._call_cancel(service, reason=1)
        assert result["result"]["state"] == -1

    def test_cancel_retry_after_refunded_returns_state_minus_2(
        self, db_session
    ):
        """REGRESSION TEST for ADR-0019 idempotency defect.

        Scenario (the real failing case from PR #2675 / FOLLOWUP-9):
          Step 1: Tx.status='completed' (Payme state 2)
            → first CancelTransaction (reason=2, refunded)
            → response state=-2 ✅
            → Tx.status mutates to 'refunded'
            → AuditLog INSERT persists pre_cancel_status='completed'

          Step 2: simulate response lost (network drop, gateway timeout)
            → no DB change; Payme will retry

          Step 3: same CancelTransaction retried
            → Tx.status is now 'refunded' (mutated by step 1)
            → AuditLog recovery returns pre_cancel_status='completed'
            → was_completed=True → response state=-2 ✅ (NOT -1)

        Without AuditLog recovery, step 3 would compute:
          was_completed = (Tx.status == 'completed') = False
          → response state=-1 ❌ (wrong, breaks idempotency)

        This is the test that PR #2675's
        test_cancel_response_state_idempotent_on_duplicate_cancel FAILED
        to cover (it tested cancelled → retry, missing the refunded case).
        """
        from app.models.audit import AuditLog
        from app.services.provider_webhook_service import (
            PAYME_TX_PRE_CANCEL_STATE_ACTION,
        )

        # Step 1: first CancelTransaction on a completed Tx
        service, tx, payment, _locked = self._make_service(
            db_session,
            transaction_status="completed",
            payment_status="paid",
        )
        result_step1 = self._call_cancel(service, reason=2)
        assert result_step1["result"]["state"] == -2

        # Verify AuditLog record exists (persisted in step 1)
        audit_entry = (
            db_session.query(AuditLog)
            .filter(
                AuditLog.action == PAYME_TX_PRE_CANCEL_STATE_ACTION,
                AuditLog.entity_type == "payment_transaction",
                AuditLog.entity_id == tx.id,
            )
            .first()
        )
        assert audit_entry is not None
        assert audit_entry.payload["pre_cancel_status"] == "completed"

        # Step 2: simulate Tx.status mutation (already done by step 1 in
        # production; in this test, _make_service used SimpleNamespace so
        # we manually update to simulate the post-step-1 state for retry).
        tx.status = "refunded"

        # Step 3: retry the same CancelTransaction
        # Re-create service with the mutated tx status to simulate retry
        service_retry, tx_retry, payment_retry, _locked_retry = self._make_service(
            db_session,
            transaction_status="refunded",  # mutated by step 1
            payment_status="refunded",
        )
        # Ensure same tx.id so AuditLog recovery finds the record
        tx_retry.id = tx.id
        result_step3 = self._call_cancel(service_retry, reason=2)

        # KEY ASSERTION: step 3 must return -2, NOT -1, even though
        # tx_retry.status is 'refunded' (not 'completed'). The AuditLog
        # record from step 1 provides the correct pre_cancel_status.
        assert result_step3["result"]["state"] == -2
        assert result_step1["result"]["state"] == result_step3["result"]["state"]

    def test_cancel_audit_log_failure_falls_back_to_mutable_state(
        self, db_session, caplog
    ):
        """Strategy 2 (ADR-0019): if AuditLog INSERT fails, the webhook
        must still respond (availability preserved), falling back to
        mutable-state derivation. Idempotency degrades silently.

        This test patches _persist_pre_cancel_state to raise, simulating
        AuditLog INSERT failure. The implementation does a full db.rollback()
        inside _persist_pre_cancel_state to clear the failed INSERT, but
        this rollback MUST NOT discard the Phase 2 payment.status /
        payment.provider_data mutation (Codex P2 review on PR #2684).
        _resolve_was_completed is called BEFORE Phase 2 to ensure this.

        Verifies:
          1. webhook response is still sent (state computed from Tx.status)
          2. logger.warning is emitted (NOT logger.exception — Sentry recursion)
          3. warning contains transaction_id for traceability
          4. payment.status is still mutated to refunded (Phase 2 not rolled back)
          5. payment.provider_data is still updated (Phase 2 not rolled back)
        """
        import logging

        service, tx, payment, _locked = self._make_service(
            db_session,
            transaction_status="completed",
            payment_status="paid",
        )

        with caplog.at_level(logging.WARNING):
            with patch.object(
                service,
                "_persist_pre_cancel_state",
                side_effect=RuntimeError("simulated AuditLog INSERT failure"),
            ):
                result = self._call_cancel(service, reason=2)

        # Webhook still responds (availability preserved)
        assert result["result"]["state"] == -2  # derived from Tx.status='completed'

        # Structured warning was emitted
        warning_messages = [
            rec.getMessage()
            for rec in caplog.records
            if rec.levelno == logging.WARNING
            and "AuditLog" in rec.getMessage()
        ]
        assert any("transaction_id=77" in msg for msg in warning_messages), (
            f"Expected warning with transaction_id=77, got: {warning_messages}"
        )

        # Codex P2: payment.status and payment.provider_data must still be
        # mutated (Phase 2 must not be rolled back by AuditLog failure).
        # reason=2 → provider_status='refunded' → payment_status='refunded'.
        assert payment.status == "refunded", (
            f"Expected payment.status='refunded' (Phase 2 mutation preserved), "
            f"got '{payment.status}'. AuditLog rollback incorrectly discarded "
            "Phase 2 payment mutation."
        )
        assert payment.provider_data.get("method") == "CancelTransaction", (
            f"Expected payment.provider_data['method']='CancelTransaction', "
            f"got {payment.provider_data.get('method')!r}. Phase 2 provider_data "
            "mutation was lost."
        )
