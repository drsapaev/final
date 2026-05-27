from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.api.v1.endpoints import payment_webhook


def test_legacy_payme_webhook_rejects_oversized_json_before_processing(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_if_called(*args, **kwargs):
        raise AssertionError("legacy Payme webhook processor should not be called")

    monkeypatch.setattr(payment_webhook, "MAX_LEGACY_PAYMENT_WEBHOOK_BODY_BYTES", 3)
    monkeypatch.setattr(
        payment_webhook.PaymentWebhookApiService,
        "process_payme_webhook",
        fail_if_called,
    )

    response = client.post(
        "/api/v1/webhooks/payment/payme",
        content=b'{"oversized": true}',
        headers={
            "Content-Type": "application/json",
            "X-Payme-Signature": "test-signature",
        },
    )

    assert response.status_code == 413
    assert response.json()["detail"] == "Payment webhook payload is too large"


def test_legacy_click_webhook_rejects_oversized_form_before_processing(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_if_called(*args, **kwargs):
        raise AssertionError("legacy Click webhook processor should not be called")

    monkeypatch.setattr(payment_webhook, "MAX_LEGACY_PAYMENT_WEBHOOK_BODY_BYTES", 3)
    monkeypatch.setattr(
        payment_webhook.PaymentWebhookApiService,
        "process_click_webhook",
        fail_if_called,
    )

    response = client.post(
        "/api/v1/webhooks/payment/click",
        content=b"merchant_trans_id=oversized",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )

    assert response.status_code == 413
    assert response.json()["detail"] == "Payment webhook payload is too large"
