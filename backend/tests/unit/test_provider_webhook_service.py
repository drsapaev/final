from __future__ import annotations

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

    def test_extract_payment_id_from_order(self, db_session):
        service = ProviderWebhookService(db_session)

        assert service._extract_payment_id_from_order("clinic_55_1700000000") == 55
        assert service._extract_payment_id_from_order("bad_order") is None

    def test_map_provider_status_to_payment_status(self, db_session):
        service = ProviderWebhookService(db_session)

        assert service._map_provider_status_to_payment_status("completed") == "paid"
        assert service._map_provider_status_to_payment_status("unknown-status") == "failed"
