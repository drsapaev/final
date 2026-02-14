from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

import pytest

from app.repositories.payment_webhook_processing_repository import (
    PaymentWebhookProcessingRepository,
)


@pytest.mark.unit
class TestPaymentWebhookProcessingRepository:
    def test_get_provider_by_code_delegates_to_crud(self, db_session):
        repository = PaymentWebhookProcessingRepository(db_session)
        provider = SimpleNamespace(code="click")
        with patch(
            "app.repositories.payment_webhook_processing_repository.get_provider_by_code",
            return_value=provider,
        ) as mock_get_provider:
            result = repository.get_provider_by_code("click")

        assert result is provider
        mock_get_provider.assert_called_once_with(db_session, code="click")

    def test_create_and_update_webhook_delegate_to_crud(self, db_session):
        repository = PaymentWebhookProcessingRepository(db_session)
        webhook_in = SimpleNamespace()
        webhook_obj = SimpleNamespace(id=17)
        with patch(
            "app.repositories.payment_webhook_processing_repository.create_webhook",
            return_value=webhook_obj,
        ) as mock_create_webhook, patch(
            "app.repositories.payment_webhook_processing_repository.update_webhook",
            return_value=webhook_obj,
        ) as mock_update_webhook:
            created = repository.create_webhook(webhook_in)  # type: ignore[arg-type]
            updated = repository.update_webhook(17, {"status": "processed"})

        assert created.id == 17
        assert updated.id == 17
        mock_create_webhook.assert_called_once_with(db_session, webhook_in)
        mock_update_webhook.assert_called_once_with(
            db_session,
            17,
            {"status": "processed"},
        )
