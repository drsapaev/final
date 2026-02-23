from __future__ import annotations

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

    def test_extract_payment_id_from_order(self, db_session):
        service = ProviderWebhookService(db_session)

        assert service._extract_payment_id_from_order("clinic_55_1700000000") == 55
        assert service._extract_payment_id_from_order("bad_order") is None

    def test_map_provider_status_to_payment_status(self, db_session):
        service = ProviderWebhookService(db_session)

        assert service._map_provider_status_to_payment_status("completed") == "paid"
        assert service._map_provider_status_to_payment_status("unknown-status") == "failed"
