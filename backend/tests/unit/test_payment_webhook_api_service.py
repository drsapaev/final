from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

import pytest

from app.services.payment_webhook_api_service import (
    PaymentWebhookApiDomainError,
    PaymentWebhookApiService,
)


@pytest.mark.unit
class TestPaymentWebhookApiService:
    def test_process_payme_webhook_handles_repository_exception(self, db_session):
        service = PaymentWebhookApiService(db_session)
        with patch.object(
            service.repository,
            "process_payme_webhook",
            side_effect=RuntimeError("boom"),
        ):
            result = service.process_payme_webhook(data={}, signature="sig")

        assert result["ok"] is False
        assert "boom" in result["message"]

    def test_create_provider_rejects_duplicate_code(self, db_session):
        service = PaymentWebhookApiService(db_session)
        provider_in = SimpleNamespace(code="click")

        with patch.object(service.repository, "get_provider_by_code", return_value=object()):
            with pytest.raises(PaymentWebhookApiDomainError) as exc_info:
                service.create_provider(provider_in)  # type: ignore[arg-type]

        assert exc_info.value.status_code == 400
        assert "already exists" in exc_info.value.detail

    def test_delete_provider_fails_when_repo_delete_false(self, db_session):
        service = PaymentWebhookApiService(db_session)
        with patch.object(service.repository, "get_provider", return_value=object()), patch.object(
            service.repository, "delete_provider", return_value=False
        ):
            with pytest.raises(PaymentWebhookApiDomainError) as exc_info:
                service.delete_provider(10)

        assert exc_info.value.status_code == 500
        assert exc_info.value.detail == "Failed to delete provider"

    def test_list_transactions_applies_filters(self, db_session):
        service = PaymentWebhookApiService(db_session)
        tx1 = SimpleNamespace(provider="click", status="success", visit_id=1)
        with patch.object(service.repository, "list_transactions", return_value=[tx1]) as mocked:
            result = service.list_transactions(
                skip=0, limit=100, provider="click", status="success", visit_id=1
            )

        mocked.assert_called_once_with(
            skip=0,
            limit=100,
            provider="click",
            status="success",
            visit_id=1,
        )
        assert result == [tx1]

    def test_list_webhooks_delegates_filters_to_repository(self, db_session):
        service = PaymentWebhookApiService(db_session)
        webhook = SimpleNamespace(provider="payme", status="pending")
        with patch.object(service.repository, "list_webhooks", return_value=[webhook]) as mocked:
            result = service.list_webhooks(
                skip=10,
                limit=20,
                provider="payme",
                status="pending",
            )

        mocked.assert_called_once_with(
            skip=10,
            limit=20,
            provider="payme",
            status="pending",
        )
        assert result == [webhook]

    def test_get_transaction_not_found(self, db_session):
        service = PaymentWebhookApiService(db_session)
        with patch.object(service.repository, "get_transaction", return_value=None):
            with pytest.raises(PaymentWebhookApiDomainError) as exc_info:
                service.get_transaction(7)

        assert exc_info.value.status_code == 404
        assert exc_info.value.detail == "Transaction not found"
