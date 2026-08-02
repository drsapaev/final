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
        repository = SimpleNamespace(
            get_existing_transaction=Mock(return_value=transaction),
            get_payment_by_id=Mock(return_value=payment),
        )
        manager = SimpleNamespace(
            get_provider=Mock(
                return_value=SimpleNamespace(
                    validate_webhook_signature=Mock(return_value=True)
                )
            )
        )
        service = ProviderWebhookService(db_session, repository=repository)
        return service, transaction, payment

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
        service, tx, payment = self._make_service(
            db_session, payment_status="refunded"
        )
        result = self._call_perform(service)
        assert result["result"]["state"] == 2
        assert payment.status == "refunded"  # NOT overwritten to "paid"
        assert result["payment_status"] == "refunded"  # response shows truth

    def test_perform_does_not_overwrite_cancelled_payment(self, db_session):
        service, tx, payment = self._make_service(
            db_session, payment_status="cancelled"
        )
        result = self._call_perform(service)
        assert result["result"]["state"] == 2
        assert payment.status == "cancelled"
        assert result["payment_status"] == "cancelled"

    def test_perform_does_not_overwrite_void_payment(self, db_session):
        service, tx, payment = self._make_service(
            db_session, payment_status="void"
        )
        result = self._call_perform(service)
        assert result["result"]["state"] == 2
        assert payment.status == "void"
        assert result["payment_status"] == "void"

    # --- failed → paid blocked (not a valid direct transition) ---

    def test_perform_does_not_overwrite_failed_payment_to_paid(self, db_session):
        service, tx, payment = self._make_service(
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
        service, tx, payment = self._make_service(
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
        service, tx, payment = self._make_service(
            db_session,
            transaction_status="completed",
            payment_status="paid",
        )
        result = self._call_perform(service)
        assert result["result"]["state"] == 2
        assert tx.status == "completed"  # unchanged

    # --- Regression: non-terminal forward transitions still allowed ---

    def test_perform_on_processing_payment_allowed(self, db_session):
        service, tx, payment = self._make_service(
            db_session, payment_status="processing"
        )
        result = self._call_perform(service)
        assert result["result"]["state"] == 2
        assert payment.status == "paid"  # transition allowed
        assert tx.status == "completed"
        assert payment.paid_at is not None

    def test_perform_on_pending_payment_allowed(self, db_session):
        service, tx, payment = self._make_service(
            db_session, payment_status="pending"
        )
        result = self._call_perform(service)
        assert result["result"]["state"] == 2
        assert payment.status == "paid"

    # --- CancelTransaction: terminal states preserved ---

    def test_cancel_on_refunded_payment_blocked(self, db_session):
        """refunded → cancelled is not allowed (refunded is terminal)."""
        service, tx, payment = self._make_service(
            db_session, payment_status="refunded"
        )
        result = self._call_cancel(service, reason=1)
        assert result["result"]["state"] == -1
        assert payment.status == "refunded"  # NOT overwritten to "cancelled"
        assert result["payment_status"] == "refunded"

    def test_cancel_on_cancelled_payment_idempotent(self, db_session):
        """cancelled → cancelled is idempotent (same-status)."""
        service, tx, payment = self._make_service(
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
        service, tx, payment = self._make_service(
            db_session,
            payment_status="refunded",
            payment_provider_data=dict(original_provider_data),
        )
        self._call_perform(service)
        # payment.status is NOT mutated (refunded is terminal)
        assert payment.status == "refunded"
        # BUT provider_data IS updated with the new webhook info
        assert payment.provider_data["method"] == "PerformTransaction"
        assert payment.provider_data["transaction_id"] == "payme-tx-1"
        assert "params" in payment.provider_data
        # Original data is preserved (merge, not replace)
        assert payment.provider_data["order_id"] == "clinic_44_1700000000"

    def test_blocked_transaction_transition_still_updates_tx_provider_data(
        self, db_session
    ):
        """Same audit-trail preservation for transaction.provider_data."""
        service, tx, payment = self._make_service(
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

        service, tx, payment = self._make_service(
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
