from __future__ import annotations

import logging
from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest
from sqlalchemy import event

from app.models.payment import Payment
from app.models.payment_webhook import PaymentTransaction, PaymentWebhook

from app.services.payment_providers.click import ClickProvider
from app.services.provider_webhook_service import ProviderWebhookService


@pytest.fixture
def click_provider():
    return ClickProvider({
        "service_id": "synthetic-service",
        "merchant_id": "synthetic-merchant",
        "secret_key": "synthetic-config",
    })


@pytest.mark.parametrize(
    ("signature", "reason"),
    [(None, "Missing signature"), ("SYNTHETIC_RECEIVED", "Signature mismatch")],
)
def test_click_signature_diagnostics_omit_callback_and_signatures(
    click_provider, monkeypatch, caplog, signature, reason,
):
    payload = {"error_note": "SYNTHETIC_CALLBACK"}
    monkeypatch.setattr(
        click_provider, "_generate_webhook_signature", Mock(return_value="SYNTHETIC_EXPECTED")
    )

    assert not click_provider.validate_webhook_signature(payload, signature)
    assert reason in caplog.text
    assert "SYNTHETIC_CALLBACK" not in caplog.text
    assert "SYNTHETIC_EXPECTED" not in caplog.text
    assert "SYNTHETIC_RECEIVED" not in caplog.text


@pytest.mark.parametrize(
    ("failure", "error_message", "logged_reason"),
    [
        (None, "Неверная подпись webhook", "Неверная подпись"),
        (RuntimeError("SYNTHETIC_EXCEPTION_DETAIL"), "Внутренняя ошибка", "Internal error type=RuntimeError"),
    ],
)
def test_click_adapter_errors_omit_callback_and_exception_details(
    click_provider, monkeypatch, caplog, failure, error_message, logged_reason,
):
    payload = {"error_note": "SYNTHETIC_CALLBACK", "sign_string": "SYNTHETIC_RECEIVED"}
    monkeypatch.setattr(
        click_provider, "_generate_webhook_signature",
        Mock(return_value="SYNTHETIC_EXPECTED", side_effect=failure),
    )

    result = click_provider.process_webhook(payload)

    assert not result.success
    assert result.error_message == error_message
    assert logged_reason in caplog.text
    assert "SYNTHETIC_" not in caplog.text


@pytest.mark.parametrize(
    ("action", "error", "status"),
    [(0, 0, "processing"), (1, 0, "completed"), (1, -1, "failed")],
)
def test_click_adapter_logs_callback_status_without_payment_fields(
    click_provider, monkeypatch, caplog, action, error, status,
):
    payload = {
        "click_trans_id": "SYNTHETIC-TRANSACTION",
        "merchant_trans_id": "SYNTHETIC-ORDER",
        "amount": 182753,
        "action": action,
        "error": error,
        "sign_string": "synthetic-signature",
    }
    monkeypatch.setattr(
        click_provider,
        "_generate_webhook_signature",
        Mock(return_value=payload["sign_string"]),
    )
    caplog.set_level(logging.INFO, logger="app.services.payment_providers.base")

    result = click_provider.process_webhook(payload)

    assert result.success
    assert result.status == status
    assert result.payment_id == payload["merchant_trans_id"]
    assert result.provider_data["click_trans_id"] == payload["click_trans_id"]
    assert result.provider_data["amount"] == "1827.53"
    assert any("process_webhook" in message and status in message for message in caplog.messages)
    assert payload["click_trans_id"] not in caplog.text
    assert payload["merchant_trans_id"] not in caplog.text
    assert result.provider_data["amount"] not in caplog.text


@pytest.mark.unit
class TestProviderWebhookService:
    def test_webhook_error_responses_and_logs_omit_internal_details(self, client, caplog):
        private_detail = "SYNTHETIC-DRIVER-DIAGNOSTIC"
        with patch(
            "app.services.provider_webhook_service.get_payment_manager",
            side_effect=RuntimeError(private_detail),
        ):
            click = client.post("/api/v1/payments/webhook/click", json={})
            payme = client.post("/api/v1/payments/webhook/payme", json={"id": "synthetic-rpc"})

        assert click.status_code == payme.status_code == 200
        assert click.json() == {"error": -1, "error_note": "Internal server error"}
        assert payme.json() == {
            "error": {"code": -32603, "message": "Internal server error"},
            "id": "synthetic-rpc",
        }
        assert private_detail not in caplog.text
        assert "Click webhook error type=RuntimeError" in caplog.text
        assert "Payme webhook error type=RuntimeError" in caplog.text

    def test_click_webhook_requires_signature(self, db_session):
        service = ProviderWebhookService(db_session)
        try:
            def _mock_update_status(payment_id, new_status, commit=False):
                payment.status = new_status
                if new_status == "paid" and not getattr(payment, 'paid_at', None):
                    from datetime import datetime, UTC
                    payment.paid_at = datetime.now(UTC)
                return payment
            service._update_payment_status = Mock(side_effect=_mock_update_status)
        except NameError:
            pass  # no payment variable in this test

        result = service.process_click_webhook({"merchant_trans_id": "1"})

        assert result["error"] == -1
        assert result["error_note"] == "Missing signature"

    @pytest.mark.parametrize("valid_signature", [False, True])
    def test_click_callback_service_logs_omit_request_fields(self, caplog, valid_signature):
        payload = {
            "click_trans_id": "SYNTHETIC-TRANSACTION",
            "merchant_trans_id": "SYNTHETIC-ORDER",
            "amount": 182753,
            "action": 1,
            "sign_string": "synthetic-signature",
        }
        db = Mock()
        repository = Mock()
        repository.get_existing_transaction.return_value = SimpleNamespace(
            payment_id=44, amount=Decimal("182753"), webhook_id=33, status="completed",
        )
        repository.get_payment_by_id.return_value = SimpleNamespace(
            provider="click", currency="UZS", provider_payment_id=payload["merchant_trans_id"],
        )
        manager = Mock()
        manager.get_provider.return_value.validate_webhook_signature.return_value = valid_signature
        service = ProviderWebhookService(db, repository=repository)
        caplog.set_level(logging.INFO, logger=ProviderWebhookService.__module__)

        with patch("app.services.provider_webhook_service.get_payment_manager", return_value=manager):
            result = service.process_click_webhook(payload)

        if valid_signature:
            assert result["error"] == 0
            assert result["error_note"] == "Already processed"
            assert result["click_trans_id"] == payload["click_trans_id"]
            assert result["merchant_trans_id"] == payload["merchant_trans_id"]
            assert result["merchant_prepare_id"] == 33
            assert result["payment_status"] is None
            repository.create_webhook.assert_not_called()
            repository.get_payment_by_id_for_update.assert_not_called()
            repository.create_transaction.assert_not_called()
            db.commit.assert_not_called()
            assert "already processed" in caplog.text
        else:
            assert result == {"error": -1, "error_note": "Invalid signature"}
            repository.get_existing_transaction.assert_not_called()
            assert "Invalid signature" in caplog.text
        repository.create_webhook.assert_not_called()
        repository.create_transaction.assert_not_called()
        db.commit.assert_not_called()
        assert "Click webhook received" in caplog.text
        assert payload["click_trans_id"] not in caplog.text
        assert payload["merchant_trans_id"] not in caplog.text
        request_fields = {"click_trans_id", "merchant_trans_id", "action"}
        assert all(request_fields.isdisjoint(vars(record)) for record in caplog.records)

    def test_payme_webhook_requires_auth_header(self, db_session):
        service = ProviderWebhookService(db_session)
        try:
            def _mock_update_status(payment_id, new_status, commit=False):
                payment.status = new_status
                if new_status == "paid" and not getattr(payment, 'paid_at', None):
                    from datetime import datetime, UTC
                    payment.paid_at = datetime.now(UTC)
                return payment
            service._update_payment_status = Mock(side_effect=_mock_update_status)
        except NameError:
            pass  # no payment variable in this test

        result = service.process_payme_webhook({"id": 123, "method": "CheckPerformTransaction"}, None)

        assert result["id"] == 123
        assert result["error"]["code"] == -32504
        assert result["error"]["message"] == "Missing Authorization header"

    def test_payme_perform_existing_transaction_marks_payment_paid(self, db_session):
        transaction = SimpleNamespace(
            id=77,
            payment_id=44,
            visit_id=55,
            webhook_id=33,
            status="processing",
            provider_data={"method": "CreateTransaction"},
        )
        payment = SimpleNamespace(
            id=44,
            visit_id=55,
            provider_payment_id="clinic_44_1700000000",
            amount=Decimal("1000"),
            status="processing",
            paid_at=None,
            provider_data={"order_id": "clinic_44_1700000000"},
        )
        repository = SimpleNamespace(
            get_existing_transaction=Mock(return_value=transaction),
            get_payment_by_id=Mock(return_value=payment),
            get_payment_by_id_for_update=Mock(return_value=payment),
            get_processed_webhook=Mock(return_value=None),
        )
        manager = SimpleNamespace(
            get_provider=Mock(
                return_value=SimpleNamespace(
                    validate_webhook_signature=Mock(return_value=True)
                )
            )
        )
        service = ProviderWebhookService(db_session, repository=repository)
        try:
            def _mock_update_status(payment_id, new_status, commit=False):
                payment.status = new_status
                if new_status == "paid" and not getattr(payment, 'paid_at', None):
                    from datetime import datetime, UTC
                    payment.paid_at = datetime.now(UTC)
                return payment
            service._update_payment_status = Mock(side_effect=_mock_update_status)
        except NameError:
            pass  # no payment variable in this test

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
            visit_id=55,
            webhook_id=33,
            status="processing",
            provider_data={"method": "CreateTransaction"},
        )
        payment = SimpleNamespace(
            id=44,
            visit_id=55,
            provider_payment_id="clinic_44_1700000000",
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
        try:
            def _mock_update_status(payment_id, new_status, commit=False):
                payment.status = new_status
                if new_status == "paid" and not getattr(payment, 'paid_at', None):
                    from datetime import datetime, UTC
                    payment.paid_at = datetime.now(UTC)
                return payment
            service._update_payment_status = Mock(side_effect=_mock_update_status)
        except NameError:
            pass  # no payment variable in this test

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

    @pytest.mark.parametrize("method", ["CheckPerformTransaction", "CreateTransaction"])
    @pytest.mark.parametrize("bound", [True, False])
    def test_payme_requires_issued_order(self, db_session, method, bound):
        from datetime import UTC, datetime

        order = "SYNTHETIC-PAYME-ORDER"
        payment = SimpleNamespace(
            id=44, visit_id=55, amount=Decimal("1000.00"), status="pending", provider_data={},
        )
        webhook = SimpleNamespace(id=33, status="pending", created_at=datetime(2030, 1, 1, tzinfo=UTC))
        repository = Mock()
        repository.get_existing_transaction.return_value = None
        repository.get_payment_by_provider_payment_id_for_update.return_value = payment if bound else None
        repository.create_webhook.return_value = webhook
        manager = Mock()
        manager.get_provider.return_value.validate_webhook_signature.return_value = True
        manager.process_webhook.return_value = SimpleNamespace(
            success=True,
            payment_id=order,
            status="pending" if method == "CheckPerformTransaction" else "processing",
            provider_data={"amount": "1000.00"},
        )
        service = ProviderWebhookService(db_session, repository=repository)
        service._update_payment_status = Mock(return_value=payment)
        params = {"amount": 100000, "account": {"order_id": order}}
        if method == "CreateTransaction":
            params.update(id="synthetic-payme-receipt", time=1735689600000)

        with patch("app.services.provider_webhook_service.get_payment_manager", return_value=manager):
            response = service.process_payme_webhook(
                {"id": "synthetic-request", "method": method, "params": params},
                "Basic synthetic",
            )

        repository.get_payment_by_provider_payment_id_for_update.assert_called_once_with(
            provider="payme", provider_payment_id=order
        )
        if not bound:
            assert response["error"]["code"] == -31050
            assert response["error"]["data"] == "order_id"
            assert webhook.error_message == "provider_payment_binding_unavailable"
        elif method == "CheckPerformTransaction":
            assert response["result"] == {"allow": True}
        else:
            assert response["result"]["state"] == 1
        writes_expected = bound and method == "CreateTransaction"
        assert service._update_payment_status.called is writes_expected
        assert repository.create_transaction.called is writes_expected

    @pytest.mark.parametrize(
        ("state", "code"),
        [
            ("orphan", -31003),
            ("missing_payment", -31003),
            ("changed_link", -31003),
            ("changed_visit", -31003),
            ("changed_order", -31050),
        ],
    )
    def test_payme_replay_requires_current_payment_link(self, db_session, state, code):
        initial = SimpleNamespace(payment_id=None if state == "orphan" else 44)
        changed = SimpleNamespace(
            payment_id=45 if state == "changed_link" else 44,
            visit_id=56 if state == "changed_visit" else 55,
        )
        payment = SimpleNamespace(id=44, visit_id=55, provider_payment_id="SYNTHETIC-ORDER")
        repository = Mock()
        repository.get_existing_transaction.side_effect = [initial, changed]
        repository.get_payment_by_id_for_update.return_value = None if state == "missing_payment" else payment
        manager = Mock()
        manager.get_provider.return_value.validate_webhook_signature.return_value = True
        service = ProviderWebhookService(db_session, repository=repository)
        service._update_payment_status = Mock()
        params = {"id": "synthetic-payme-receipt"}
        if state == "changed_order":
            params["account"] = {"order_id": "OTHER-SYNTHETIC-ORDER"}

        with patch("app.services.provider_webhook_service.get_payment_manager", return_value=manager):
            response = service.process_payme_webhook(
                {
                    "id": "synthetic-replay",
                    "method": "PerformTransaction",
                    "params": params,
                },
                "Basic synthetic",
            )

        assert response["error"]["code"] == code
        service._update_payment_status.assert_not_called()
        repository.create_transaction.assert_not_called()
        if state in {"changed_link", "changed_visit"}:
            repository.get_payment_by_id_for_update.assert_called_once_with(44, provider="payme")
            repository.get_existing_transaction.assert_called_with(
                transaction_id="synthetic-payme-receipt", provider="payme", for_update=True
            )

    def test_payme_perform_requires_existing_transaction(self, db_session):
        repository = Mock()
        repository.get_existing_transaction.return_value = None
        manager = Mock()
        manager.get_provider.return_value.validate_webhook_signature.return_value = True
        service = ProviderWebhookService(db_session, repository=repository)

        with patch("app.services.provider_webhook_service.get_payment_manager", return_value=manager):
            response = service.process_payme_webhook(
                {
                    "id": "synthetic-perform",
                    "method": "PerformTransaction",
                    "params": {"id": "unregistered-synthetic-receipt"},
                },
                "Basic synthetic",
            )

        assert response["error"]["code"] == -31003
        repository.create_webhook.assert_not_called()
        repository.create_transaction.assert_not_called()

    @pytest.mark.parametrize("evidence", ["missing", "mismatched_amount", "wrong_method"])
    def test_payme_create_replay_requires_matching_creation_evidence(self, db_session, evidence):
        order = "SYNTHETIC-PAYME-ORDER"
        reference = "synthetic-payme-create"
        params = {"id": reference, "amount": 100000, "account": {"order_id": order}}
        payment = SimpleNamespace(id=44, visit_id=55, provider_payment_id=order, amount=Decimal("1000"))
        transaction = SimpleNamespace(
            id=41, payment_id=44, visit_id=55, webhook_id=73,
            transaction_id=reference, amount=100000, currency="UZS",
        )
        receipt = SimpleNamespace(
            raw_data={
                "method": "PerformTransaction" if evidence == "wrong_method" else "CreateTransaction",
                "params": params,
            },
            amount=100001 if evidence == "mismatched_amount" else 100000,
            currency="UZS",
        )
        repository = Mock()
        repository.get_existing_transaction.return_value = transaction
        repository.get_payment_by_id_for_update.return_value = payment
        repository.get_processed_webhook.return_value = None if evidence == "missing" else receipt
        manager = Mock()
        manager.get_provider.return_value.validate_webhook_signature.return_value = True
        service = ProviderWebhookService(db_session, repository=repository)

        with patch("app.services.provider_webhook_service.get_payment_manager", return_value=manager):
            response = service.process_payme_webhook(
                {"id": "synthetic-create-replay", "method": "CreateTransaction", "params": params},
                "Basic synthetic",
            )

        assert response["error"]["code"] == -32400
        repository.get_processed_webhook.assert_called_once_with(
            webhook_id=73, provider="payme", transaction_id=order
        )
        repository.create_webhook.assert_not_called()
        repository.create_transaction.assert_not_called()

    @pytest.mark.parametrize("action", [0, 1])
    def test_click_holds_new_legacy_callbacks_without_selecting_a_payment(self, action):
        db = Mock()
        webhook = SimpleNamespace(id=33)
        repository = Mock()
        repository.get_existing_transaction.return_value = None
        repository.create_webhook.return_value = webhook
        manager = Mock()
        manager.get_provider.return_value.validate_webhook_signature.return_value = True
        service = ProviderWebhookService(db, repository=repository)
        callback = {
            "click_trans_id": "synthetic-transaction",
            "merchant_trans_id": "SYNTHETIC-ORDER",
            "amount": 100000,
            "action": action,
            "sign_string": "synthetic-signature",
        }

        with patch("app.services.provider_webhook_service.get_payment_manager", return_value=manager):
            result = service.process_click_webhook(callback)

        assert result == {"error": -1, "error_note": "Payment reconciliation required"}
        assert webhook.error_message == "provider_reconciliation_required"
        assert webhook.processed_at is not None
        assert repository.create_webhook.call_args.kwargs["status"] == "failed"
        assert repository.create_webhook.call_args.kwargs["raw_data"] == callback
        db.commit.assert_called_once()
        manager.process_webhook.assert_not_called()
        repository.get_payment_by_id.assert_not_called()
        repository.get_payment_by_id_for_update.assert_not_called()
        repository.create_transaction.assert_not_called()

    def test_click_webhook_refuses_mutation_if_receipt_commit_fails(self):
        db = Mock()
        db.commit.side_effect = RuntimeError("synthetic receipt write error")
        repository = Mock()
        repository.get_existing_transaction.return_value = None
        manager = Mock()
        manager.get_provider.return_value.validate_webhook_signature.return_value = True
        service = ProviderWebhookService(db, repository=repository)

        with patch("app.services.provider_webhook_service.get_payment_manager", return_value=manager):
            result = service.process_click_webhook({
                "click_trans_id": "synthetic-click",
                "merchant_trans_id": "clinic_44_1700000000",
                "amount": 100000,
                "sign_string": "synthetic-signature",
            })

        assert result == {"error": -1, "error_note": "Internal server error"}
        repository.create_webhook.assert_called_once()
        db.rollback.assert_called_once()
        manager.process_webhook.assert_not_called()
        repository.get_payment_by_id_for_update.assert_not_called()
        repository.create_transaction.assert_not_called()

    def test_click_rollback_omits_private_diagnostics(self, caplog):
        marker = "SYNTHETIC-PRIVATE-FINANCIAL-DIAGNOSTIC"
        db = Mock()
        repository = Mock()
        repository.get_existing_transaction.return_value = None
        repository.create_webhook.side_effect = RuntimeError(marker)
        manager = Mock()
        manager.get_provider.return_value.validate_webhook_signature.return_value = True
        service = ProviderWebhookService(db, repository=repository)

        with patch("app.services.provider_webhook_service.get_payment_manager", return_value=manager):
            response = service.process_click_webhook({
                "click_trans_id": "synthetic-click",
                "merchant_trans_id": "SYNTHETIC-ORDER",
                "amount": 100000,
                "sign_string": "synthetic-signature",
            })

        assert response == {"error": -1, "error_note": "Internal server error"}
        db.commit.assert_not_called()
        db.rollback.assert_called_once()
        assert "Click webhook error type=RuntimeError" in caplog.text
        assert marker not in caplog.text

    @pytest.mark.parametrize("succeeded", [True, False])
    @pytest.mark.parametrize("bound", [True, False])
    def test_kaspi_webhook_requires_locked_provider_binding(self, db_session, succeeded, bound):
        """Either callback outcome may only mutate the matching locked row."""
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
            get_payment_by_provider_payment_id_for_update=Mock(
                return_value=payment if bound else None
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
                    success=succeeded,
                    payment_id="kaspi-pay-123",
                    status="completed",
                    provider_data={"amount": Decimal("1000")},
                    error_message=None if succeeded else "Synthetic provider error",
                )
            ),
        )
        service = ProviderWebhookService(db_session, repository=repository)
        try:
            def _mock_update_status(payment_id, new_status, commit=False):
                payment.status = new_status
                if new_status == "paid" and not getattr(payment, 'paid_at', None):
                    from datetime import datetime, UTC
                    payment.paid_at = datetime.now(UTC)
                return payment
            service._update_payment_status = Mock(side_effect=_mock_update_status)
        except NameError:
            pass  # no payment variable in this test

        with patch(
            "app.services.provider_webhook_service.get_payment_manager",
            return_value=manager,
        ):
            response = service.process_kaspi_webhook(
                {
                    "transaction_id": "kaspi-1",
                    "merchant_id": "m1",
                    "amount": 100000,
                    "currency": "KZT",
                    "signature": "valid",
                }
            )

        repository.get_payment_by_provider_payment_id_for_update.assert_called_once_with(
            provider="kaspi", provider_payment_id="kaspi-pay-123"
        )
        assert response["status"] == ("success" if succeeded else "error")
        assert response["payment_id"] == (payment.id if bound else None)
        assert repository.create_transaction.called is (bound and succeeded)
        if bound:
            assert payment.status == ("paid" if succeeded else "failed")
        else:
            service._update_payment_status.assert_not_called()
            assert webhook.status == "failed"
            if succeeded:
                assert webhook.error_message == "provider_payment_binding_unavailable"

    def test_extract_payment_id_from_order(self, db_session):
        service = ProviderWebhookService(db_session)
        try:
            def _mock_update_status(payment_id, new_status, commit=False):
                payment.status = new_status
                if new_status == "paid" and not getattr(payment, 'paid_at', None):
                    from datetime import datetime, UTC
                    payment.paid_at = datetime.now(UTC)
                return payment
            service._update_payment_status = Mock(side_effect=_mock_update_status)
        except NameError:
            pass  # no payment variable in this test

        assert service._extract_payment_id_from_order("clinic_55_1700000000") == 55
        assert service._extract_payment_id_from_order("bad_order") is None

    def test_map_provider_status_to_payment_status(self, db_session):
        service = ProviderWebhookService(db_session)
        try:
            def _mock_update_status(payment_id, new_status, commit=False):
                payment.status = new_status
                if new_status == "paid" and not getattr(payment, 'paid_at', None):
                    from datetime import datetime, UTC
                    payment.paid_at = datetime.now(UTC)
                return payment
            service._update_payment_status = Mock(side_effect=_mock_update_status)
        except NameError:
            pass  # no payment variable in this test

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
        paid_at=None,
    ):
        transaction = SimpleNamespace(
            id=77,
            payment_id=44,
            visit_id=55,
            webhook_id=33,
            transaction_id="payme-tx-1",
            amount=100000,
            currency="UZS",
            status=transaction_status,
            payme_cancel_receipt=None,
            provider_data=transaction_provider_data
            or {"method": "CreateTransaction"},
        )
        payment = SimpleNamespace(
            id=44,
            visit_id=55,
            provider_payment_id="clinic_44_1700000000",
            amount=Decimal("1000"),
            currency="UZS",
            status=payment_status,
            paid_at=paid_at,
            provider_data=payment_provider_data
            or {"order_id": "clinic_44_1700000000"},
        )
        # locked_payment simulates a TOCTOU race: the unlocked read sees
        # the original status, but the FOR UPDATE read sees a different
        # status (e.g. another transaction committed "cancelled" between
        # the two reads).
        locked_payment = SimpleNamespace(
            id=44,
            visit_id=55,
            provider_payment_id="clinic_44_1700000000",
            amount=Decimal("1000"),
            currency="UZS",
            status=locked_payment_status or payment_status,
            paid_at=paid_at,
            provider_data=payment_provider_data
            or {"order_id": "clinic_44_1700000000"},
        )
        repository = SimpleNamespace(
            get_existing_transaction=Mock(return_value=transaction),
            get_payment_by_id=Mock(return_value=payment),
            get_payment_by_id_for_update=Mock(return_value=locked_payment),
            get_processed_webhook=Mock(return_value=None),
        )
        manager = SimpleNamespace(
            get_provider=Mock(
                return_value=SimpleNamespace(
                    validate_webhook_signature=Mock(return_value=True)
                )
            )
        )
        service = ProviderWebhookService(db_session, repository=repository)
        try:
            def _mock_update_status(payment_id, new_status, commit=False):
                payment.status = new_status
                if new_status == "paid" and not getattr(payment, 'paid_at', None):
                    from datetime import datetime, UTC
                    payment.paid_at = datetime.now(UTC)
                return payment
            service._update_payment_status = Mock(side_effect=_mock_update_status)
        except NameError:
            pass  # no payment variable in this test
        # Issue #06: mock _update_payment_status to simulate status changes
        try:
            def _mock_update_status(payment_id, new_status, commit=False):
                # Update both payment and locked_payment
                payment.status = new_status
                if locked_payment and hasattr(locked_payment, 'status'):
                    locked_payment.status = new_status
                if new_status == "paid" and not getattr(payment, 'paid_at', None):
                    from datetime import datetime, UTC
                    payment.paid_at = datetime.now(UTC)
                    if hasattr(locked_payment, 'paid_at'):
                        locked_payment.paid_at = payment.paid_at
                # Return locked_payment (not payment) — this matches the real
                # BillingService.update_payment_status() which does FOR UPDATE
                # and returns the locked object. The webhook code then updates
                # provider_data on the returned object.
                return locked_payment if locked_payment else payment
            service._update_payment_status = Mock(side_effect=_mock_update_status)
        except NameError:
            pass
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

    def _call_cancel(self, service, reason=1, auth_header="Basic valid", *, amount=None):
        params = {"id": "payme-tx-1", "reason": reason}
        if amount is not None:
            params["amount"] = amount
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
                    "params": params,
                },
                auth_header,
            )

    # --- Terminal payment states: PerformTransaction must NOT overwrite ---

    def test_perform_does_not_overwrite_refunded_payment(self, db_session):
        service, tx, payment, _locked = self._make_service(
            db_session, payment_status="refunded"
        )
        result = self._call_perform(service)
        assert result["error"]["code"] == -31008
        assert payment.status == "refunded"
        assert _locked.status == "refunded"

    def test_perform_does_not_overwrite_cancelled_payment(self, db_session):
        service, tx, payment, _locked = self._make_service(
            db_session, payment_status="cancelled"
        )
        result = self._call_perform(service)
        assert result["error"]["code"] == -31008
        assert payment.status == "cancelled"
        assert _locked.status == "cancelled"

    def test_perform_does_not_overwrite_void_payment(self, db_session):
        service, tx, payment, _locked = self._make_service(
            db_session, payment_status="void"
        )
        result = self._call_perform(service)
        assert result["error"]["code"] == -31008
        assert payment.status == "void"
        assert _locked.status == "void"

    # --- failed → paid blocked (not a valid direct transition) ---

    def test_perform_does_not_overwrite_failed_payment_to_paid(self, db_session):
        service, tx, payment, _locked = self._make_service(
            db_session, payment_status="failed"
        )
        result = self._call_perform(service)
        assert result["error"]["code"] == -31008
        assert payment.status == "failed"
        assert _locked.status == "failed"

    # --- Idempotent same-status: allowed, status not mutated ---

    def test_perform_replays_the_first_time_and_original_merchant_receipt(self, db_session):
        original_paid_at = datetime(2025, 1, 1, tzinfo=UTC)
        service, tx, _payment, locked = self._make_service(
            db_session,
            transaction_status="completed",
            payment_status="paid",
            paid_at=original_paid_at,
        )
        tx.transaction_id = "payme-tx-1"
        tx.amount = 100000
        tx.currency = "UZS"
        service.repository.get_processed_webhook.return_value = SimpleNamespace(
            id=tx.webhook_id,
            amount=tx.amount,
            currency=tx.currency,
            raw_data={
                "method": "CreateTransaction",
                "params": {
                    "id": tx.transaction_id,
                    "account": {"order_id": locked.provider_payment_id},
                },
            },
        )

        first = self._call_perform(service)
        retry = self._call_perform(service)

        assert first["result"] == retry["result"] == {
            "state": 2,
            "perform_time": int(original_paid_at.timestamp() * 1000),
            "transaction": tx.webhook_id,
        }
        service._update_payment_status.assert_not_called()
        assert locked.paid_at == original_paid_at

    def test_perform_requires_reconciliation_when_legacy_completion_time_is_missing(self, db_session):
        service, tx, _payment, locked = self._make_service(
            db_session, transaction_status="completed", payment_status="paid"
        )
        result = self._call_perform(service)

        assert result["error"]["code"] == -32400
        assert locked.paid_at is None
        assert tx.status == "completed"
        service._update_payment_status.assert_not_called()

    def test_perform_does_not_charge_payment_if_its_transaction_is_terminal(self, db_session):
        service, tx, _payment, locked = self._make_service(
            db_session, transaction_status="cancelled", payment_status="processing"
        )
        result = self._call_perform(service)

        assert result["error"]["code"] == -31008
        assert tx.status == "cancelled"
        assert locked.status == "processing"
        assert locked.paid_at is None
        service._update_payment_status.assert_not_called()

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

    def test_cancel_declines_inconsistent_payment_and_transaction(self, db_session):
        service, transaction, _payment, locked = self._make_service(
            db_session, payment_status="refunded"
        )

        response = self._call_cancel(service)

        assert response["error"]["code"] == -31007
        assert transaction.status == "processing"
        assert locked.status == "refunded"
        assert transaction.payme_cancel_receipt is None
        service._update_payment_status.assert_not_called()

    @pytest.mark.parametrize("status", ["cancelled", "refunded"])
    def test_cancel_requires_reconciliation_of_a_legacy_receipt(self, db_session, status):
        service, transaction, _payment, locked = self._make_service(
            db_session, transaction_status=status, payment_status=status
        )

        response = self._call_cancel(service)

        assert response["error"]["code"] == -32400
        assert "result" not in response
        assert transaction.status == locked.status == status
        assert transaction.payme_cancel_receipt is None
        service._update_payment_status.assert_not_called()

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
        assert result["error"]["code"] == -31008
        assert _locked.status == "cancelled"

    def test_toctou_refunded_during_unlocked_read(self, db_session):
        """Unlocked read sees 'processing', locked read sees 'refunded'."""
        service, tx, payment, _locked = self._make_service(
            db_session,
            transaction_status="completed",
            payment_status="processing",
            locked_payment_status="refunded",
        )
        result = self._call_perform(service)
        assert result["error"]["code"] == -31008
        assert _locked.status == "refunded"

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

    @pytest.mark.parametrize(
        ("tx_status", "payment_status", "reason", "expected_status", "expected_state"),
        [
            ("processing", "processing", 4, "cancelled", -1),
            ("completed", "paid", 1, "refunded", -2),
        ],
    )
    def test_cancel_uses_locked_state_and_replays_the_first_receipt(
        self, db_session, tx_status, payment_status, reason, expected_status, expected_state,
    ):
        from app.models.audit import AuditLog
        from app.services.provider_webhook_service import PAYME_TX_PRE_CANCEL_STATE_ACTION

        service, transaction, _payment, locked = self._make_service(
            db_session, transaction_status=tx_status, payment_status=payment_status
        )

        first = self._call_cancel(service, reason=reason)
        replay = self._call_cancel(service, reason=5)
        receipt = transaction.payme_cancel_receipt

        assert first["result"] == replay["result"] == {
            "transaction": transaction.id,
            "cancel_time": receipt["cancel_time"],
            "state": expected_state,
        }
        assert first["payment_status"] == expected_status
        assert replay["payment_status"] is None
        assert receipt["reason"] == reason
        assert receipt["amount_minor"] == 100000
        assert receipt["currency"] == "UZS"
        assert locked.status == transaction.status == expected_status
        service._update_payment_status.assert_called_once_with(
            payment_id=locked.id, new_status=expected_status, commit=False
        )
        audit = db_session.query(AuditLog).filter_by(
            action=PAYME_TX_PRE_CANCEL_STATE_ACTION, entity_id=transaction.id
        ).one()
        assert audit.payload == {"pre_cancel_status": tx_status}

    @pytest.mark.parametrize(("field", "value"), [
        ("payment_id", 45),
        ("amount_minor", 101000),
        ("currency", "KZT"),
        ("state", -1),
        ("cancel_time", None),
    ])
    def test_cancel_checks_durable_receipt_before_acknowledging(self, db_session, field, value):
        service, transaction, _payment, _locked = self._make_service(
            db_session, transaction_status="refunded", payment_status="refunded"
        )
        transaction.payme_cancel_receipt = {
            "payment_id": 44, "amount_minor": 100000, "currency": "UZS",
            "state": -2, "cancel_time": 1735689600000, "transaction": 33,
            field: value,
        }

        response = self._call_cancel(service)

        assert response["error"]["code"] == -32400
        service._update_payment_status.assert_not_called()

    def test_cancel_checks_original_transaction_amount(self, db_session):
        service, transaction, _payment, locked = self._make_service(db_session)
        transaction.amount = 99000

        response = self._call_cancel(service, reason=4, amount=100000)

        assert response["error"]["code"] == -31001
        assert locked.status == transaction.status == "processing"
        assert transaction.payme_cancel_receipt is None
        service._update_payment_status.assert_not_called()


    def _check_payme(self, service):
        manager = Mock()
        manager.get_provider.return_value.validate_webhook_signature.return_value = True
        with patch("app.services.provider_webhook_service.get_payment_manager", return_value=manager):
            return service.process_payme_webhook(
                {"id": "check-request", "method": "CheckTransaction", "params": {"id": "payme-tx-1"}},
                "Basic valid",
            )

    @pytest.mark.parametrize(
        ("transaction_status", "payment_status", "state"),
        [
            ("processing", "processing", 1),
            ("completed", "paid", 2),
            ("cancelled", "cancelled", -1),
            ("refunded", "refunded", -2),
        ],
    )
    def test_check_transaction_returns_only_the_verified_lifecycle(
        self, db_session, transaction_status, payment_status, state,
    ):
        created_at = datetime(2025, 1, 1, tzinfo=UTC)
        paid_at = datetime(2025, 1, 2, tzinfo=UTC) if state in {2, -2} else None
        cancel_time = 1735862400000 if state < 0 else 0
        service, transaction, _payment, locked = self._make_service(
            db_session, transaction_status=transaction_status, payment_status=payment_status, paid_at=paid_at,
        )
        service.repository.get_processed_webhook.return_value = SimpleNamespace(
            id=transaction.webhook_id, amount=transaction.amount, currency="UZS", created_at=created_at,
            raw_data={
                "method": "CreateTransaction",
                "params": {
                    "id": transaction.transaction_id,
                    "account": {"order_id": locked.provider_payment_id},
                },
            },
        )
        if state < 0:
            transaction.payme_cancel_receipt = {
                "payment_id": locked.id, "amount_minor": transaction.amount, "currency": "UZS",
                "state": state, "cancel_time": cancel_time, "transaction": transaction.webhook_id, "reason": 5,
            }
        transaction_before = dict(transaction.provider_data)
        payment_before = dict(locked.provider_data)

        response = self._check_payme(service)

        assert response == {
            "id": "check-request",
            "result": {
                "create_time": int(created_at.timestamp() * 1000),
                "perform_time": int(paid_at.timestamp() * 1000) if paid_at else 0,
                "cancel_time": cancel_time,
                "transaction": str(transaction.webhook_id),
                "state": state,
                "reason": 5 if state < 0 else None,
            },
        }
        assert transaction.provider_data == transaction_before
        assert locked.provider_data == payment_before
        service._update_payment_status.assert_not_called()

    def test_check_requires_stored_cancellation_evidence_for_legacy_refund(self, db_session):
        service, transaction, _payment, locked = self._make_service(
            db_session, transaction_status="refunded", payment_status="refunded",
            paid_at=datetime(2025, 1, 2, tzinfo=UTC),
        )
        service.repository.get_processed_webhook.return_value = SimpleNamespace(
            id=transaction.webhook_id, amount=transaction.amount, currency="UZS",
            created_at=datetime(2025, 1, 1, tzinfo=UTC),
            raw_data={
                "method": "CreateTransaction",
                "params": {
                    "id": transaction.transaction_id,
                    "account": {"order_id": locked.provider_payment_id},
                },
            },
        )

        response = self._check_payme(service)

        assert response["error"]["code"] == -32400
        assert "result" not in response
        service._update_payment_status.assert_not_called()


class TestPaymeStatement:
    _start = 1735689600000
    _end = 1735776000000

    def _call(self, service, method, params, *, authorized=True):
        manager = Mock()
        manager.get_provider.return_value.validate_webhook_signature.return_value = authorized
        with patch("app.services.provider_webhook_service.get_payment_manager", return_value=manager):
            response = service.process_payme_webhook(
                {"id": "statement-request", "method": method, "params": params},
                "Basic synthetic",
            )
        manager.process_webhook.assert_not_called()
        return response

    @staticmethod
    def _create_rows(db, visit_id, external_id, payme_time, *, provider="payme"):
        order = f"synthetic-order-{external_id}"
        payment = Payment(
            visit_id=visit_id, method="online", status="processing",
            amount=Decimal("12.50"), currency="UZS", provider=provider, provider_payment_id=order,
        )
        callback = PaymentWebhook(
            provider=provider, webhook_id=f"synthetic-hook-{external_id}",
            transaction_id=order, status="processed", amount=1250, currency="UZS",
            created_at=datetime(2030, 1, 1, tzinfo=UTC),
            raw_data={
                "method": "CreateTransaction",
                "params": {
                    "id": external_id, "time": payme_time, "amount": 1250,
                    "account": {"order_id": order, "unsupported_field": "synthetic-extra"},
                },
            },
        )
        db.add_all([payment, callback])
        db.flush()
        db.add(PaymentTransaction(
            provider=provider, transaction_id=external_id, amount=1250, currency="UZS",
            status="processing", payment_id=payment.id, webhook_id=callback.id, visit_id=visit_id,
        ))
        db.flush()
        return callback

    def test_statement_uses_original_payme_time_in_one_read(self, db_session, test_visit):
        latest = self._create_rows(db_session, test_visit.id, "latest", self._end)
        first = self._create_rows(db_session, test_visit.id, "first", self._start)
        self._create_rows(db_session, test_visit.id, "outside", self._end + 1)
        self._create_rows(db_session, test_visit.id, "different-provider", self._start, provider="kaspi")
        db_session.add_all([
            PaymentWebhook(
                provider="payme", webhook_id=f"synthetic-non-create-{status}",
                transaction_id="synthetic-order-unaccepted", status=status, amount=1250, currency="UZS",
                raw_data={"method": method, "params": {"time": self._start}},
            )
            for status, method in (
                ("failed", "CreateTransaction"),
                ("processed", "CheckPerformTransaction"),
            )
        ])
        db_session.flush()
        first_id, latest_id = first.id, latest.id

        received = []
        connection = db_session.connection()

        def collect(_conn, _cursor, statement, _params, _context, _executemany):
            received.append(statement.strip())

        event.listen(connection, "before_cursor_execute", collect)
        try:
            service = ProviderWebhookService(db_session)
            response = self._call(service, "GetStatement", {"from": self._start, "to": self._end})
        finally:
            event.remove(connection, "before_cursor_execute", collect)

        expected_lifecycle = {
            "amount": 1250, "create_time": 1893456000000, "perform_time": 0,
            "cancel_time": 0, "state": 1, "reason": None,
        }
        assert response == {
            "id": "statement-request",
            "result": {"transactions": [
                {
                    **expected_lifecycle,
                    "id": "first", "time": self._start, "transaction": str(first_id),
                    "account": {"order_id": "synthetic-order-first"},
                },
                {
                    **expected_lifecycle,
                    "id": "latest", "time": self._end, "transaction": str(latest_id),
                    "account": {"order_id": "synthetic-order-latest"},
                },
            ]},
        }
        assert len(received) == 1
        assert received[0].startswith("SELECT")
        assert "FOR UPDATE" not in received[0]
        assert self._call(service, "GetStatement", {
            "from": self._start - 1, "to": self._start - 1,
        })["result"] == {"transactions": []}

    def test_statement_requires_history_of_unlinked_successful_receipt(self, db_session):
        db_session.add(PaymentWebhook(
            provider="payme", webhook_id="synthetic-unlinked-create", transaction_id="synthetic-unlinked-order",
            status="processed", amount=1250, currency="UZS",
            raw_data={"method": "CreateTransaction", "params": {"time": self._start}},
        ))
        db_session.flush()
        service = ProviderWebhookService(db_session)
        result = self._call(service, "GetStatement", {"from": self._start, "to": self._end})
        assert result["error"]["code"] == -32400
        assert self._call(service, "GetStatement", {
            "from": self._start + 1, "to": self._end,
        })["result"] == {"transactions": []}

    @pytest.mark.parametrize("payme_time", [None, "1735689600000", 173568960000000000000])
    def test_statement_flags_missing_or_invalid_legacy_payme_time(self, db_session, test_visit, payme_time):
        self._create_rows(db_session, test_visit.id, "legacy", payme_time)
        self._create_rows(db_session, test_visit.id, "complete", self._start)
        service = ProviderWebhookService(db_session)

        response = self._call(service, "GetStatement", {"from": self._start, "to": self._end})

        assert response["error"]["code"] == -32400
        assert "result" not in response

    @pytest.mark.parametrize("params", [
        {"from": 1735689600000},
        {"from": 1735776000000, "to": 1735689600000},
        {"from": True, "to": 1735689600000},
        {"from": "1735689600000", "to": 1735689600000},
    ])
    def test_statement_rejects_invalid_period_before_query(self, db_session, params):
        repository = Mock()
        result = self._call(ProviderWebhookService(db_session, repository), "GetStatement", params)

        assert result["error"]["code"] == -32602
        assert not repository.mock_calls

    def test_statement_requires_payme_authorization_before_query(self, db_session):
        repository = Mock()
        result = self._call(
            ProviderWebhookService(db_session, repository), "GetStatement",
            {"from": self._start, "to": self._end}, authorized=False,
        )

        assert result["error"]["code"] == -32504
        assert not repository.mock_calls

    def test_unsupported_method_is_rejected_before_transaction_handling(self, db_session):
        repository = Mock()
        result = self._call(ProviderWebhookService(db_session, repository), "UnsupportedMethod", {})

        assert result["error"]["code"] == -32601
        assert not repository.mock_calls

    def test_new_create_requires_original_payme_time(self, db_session):
        repository = Mock()
        repository.get_existing_transaction.return_value = None
        result = self._call(
            ProviderWebhookService(db_session, repository), "CreateTransaction",
            {"id": "synthetic-missing-time", "account": {"order_id": "synthetic-order"}, "amount": 1250},
        )

        assert result["error"]["code"] == -32602
        repository.create_webhook.assert_not_called()
        repository.create_transaction.assert_not_called()


    @pytest.mark.parametrize("amount", ["1250", True, 0, 2_147_483_648])
    def test_new_create_rejects_amount_outside_its_persisted_contract(self, db_session, amount):
        repository = Mock()
        repository.get_existing_transaction.return_value = None
        result = self._call(
            ProviderWebhookService(db_session, repository), "CreateTransaction",
            {
                "id": "synthetic-invalid-amount", "time": self._start,
                "account": {"order_id": "synthetic-order"}, "amount": amount,
            },
        )

        assert result["error"]["code"] == -32602
        repository.create_webhook.assert_not_called()
        repository.create_transaction.assert_not_called()
