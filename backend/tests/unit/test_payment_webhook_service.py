from __future__ import annotations

import hashlib
import hmac
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from app.services.payment_webhook import PaymentWebhookService


@pytest.mark.unit
class TestPaymentWebhookService:
    def test_verify_payme_signature_true_for_valid_signature(self):
        data = {"id": "tx-1", "amount": 1000, "state": 2}
        sign_string = "amount=1000;id=tx-1;state=2"
        secret = "secret-key"
        signature = hmac.new(
            secret.encode("utf-8"),
            sign_string.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

        assert (
            PaymentWebhookService.verify_payme_signature(data, signature, secret)
            is True
        )

    def test_verify_click_signature_true_for_valid_signature(self):
        data = {
            "click_trans_id": "1",
            "service_id": "2",
            "merchant_trans_id": "3",
            "amount": "400",
            "action": "0",
            "sign_time": "2026-02-14 10:00:00",
        }
        sign_string = (
            f"{data['click_trans_id']}{data['service_id']}{data['merchant_trans_id']}"
            f"{data['amount']}{data['action']}{data['sign_time']}"
        )
        data["sign_string"] = hashlib.md5(sign_string.encode("utf-8")).hexdigest()

        assert PaymentWebhookService.verify_click_signature(data, "unused-secret") is True

    def test_get_webhook_summary_uses_repository_counts(self, db_session):
        repository = SimpleNamespace(
            count_webhooks=lambda: 10,
            get_pending_webhooks=lambda: [1, 2, 3],
            get_failed_webhooks=lambda: [4],
            count_transactions=lambda: 20,
            get_transactions_by_status=lambda status: [1, 2]
            if status == "success"
            else [3],
        )
        with patch(
            "app.services.payment_webhook.PaymentWebhookProcessingRepository",
            return_value=repository,
        ):
            summary = PaymentWebhookService.get_webhook_summary(db_session)

        assert summary["webhooks"]["total"] == 10
        assert summary["webhooks"]["pending"] == 3
        assert summary["webhooks"]["failed"] == 1
        assert summary["transactions"]["total"] == 20
        assert summary["transactions"]["successful"] == 2
        assert summary["transactions"]["failed"] == 1
