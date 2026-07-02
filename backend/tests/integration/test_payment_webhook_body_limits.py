from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.api.v1.endpoints import payment_webhooks


@pytest.mark.parametrize(
    ("path", "method_name"),
    [
        ("/api/v1/payments/webhook/click", "process_click_webhook"),
        ("/api/v1/payments/webhook/payme", "process_payme_webhook"),
        ("/api/v1/payments/webhook/kaspi", "process_kaspi_webhook"),
    ],
)
def test_public_payment_webhook_rejects_oversized_json_before_processing(
    client: TestClient,
    monkeypatch,
    path: str,
    method_name: str,
) -> None:
    def fail_if_called(*args, **kwargs):
        raise AssertionError("provider webhook processor should not be called")

    monkeypatch.setattr(payment_webhooks, "MAX_PAYMENT_WEBHOOK_BODY_BYTES", 3)
    monkeypatch.setattr(
        payment_webhooks.ProviderWebhookService,
        method_name,
        fail_if_called,
    )

    response = client.post(
        path,
        content=b'{"oversized": true}',
        headers={"Content-Type": "application/json"},
    )

    assert response.status_code == 413
    assert response.json()["detail"] == "Payment webhook payload is too large"
