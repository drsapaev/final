from __future__ import annotations

import pytest
from fastapi import Request
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


@pytest.mark.parametrize(
    ("provider", "method_name"),
    [("click", "process_click_webhook"), ("payme", "process_payme_webhook"), ("kaspi", "process_kaspi_webhook")],
)
def test_provider_webhook_bypasses_user_cache_without_buffering(client, monkeypatch, provider, method_name):
    from starlette.requests import Request

    def forbid_body_buffer(_self):
        raise AssertionError("generic middleware must not buffer a provider callback")

    import jwt

    from app.core.config import settings
    from app.middleware.idempotency_middleware import IdempotencyMiddleware

    token = jwt.encode({"sub": "1", "type": "access", "exp": 4_102_444_800, "auth_epoch": 0},
                       settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    monkeypatch.setattr(IdempotencyMiddleware, "_verified_principal",
                        lambda *_: (_ for _ in ()).throw(AssertionError("provider callbacks bypass principal cache")))
    calls = []

    def fake_processor(_self, *args):
        calls.append(args)
        return {"call": len(calls)}

    monkeypatch.setattr(Request, "body", forbid_body_buffer)
    monkeypatch.setattr(payment_webhooks.ProviderWebhookService, method_name, fake_processor)
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {token}", "Idempotency-Key": "same-key"}
    path = f"/api/v1/payments/webhook/{provider}"
    assert client.post(path, content=b'{}', headers=headers).json() == {"call": 1}
    assert client.post(path, content=b'{}', headers=headers).json() == {"call": 2}
    assert len(calls) == 2


@pytest.mark.parametrize("provider", ["click", "payme", "kaspi"])
def test_webhook_with_user_key_still_enforces_streaming_limit(client, monkeypatch, provider):
    from starlette.requests import Request

    def forbid_body_buffer(_self):
        raise AssertionError("generic middleware must not buffer a provider callback")

    monkeypatch.setattr(Request, "body", forbid_body_buffer)
    monkeypatch.setattr(payment_webhooks, "MAX_PAYMENT_WEBHOOK_BODY_BYTES", 3)
    response = client.post(f"/api/v1/payments/webhook/{provider}", content=b'{"large":true}',
                           headers={"Content-Type": "application/json", "Authorization": "Bearer synthetic", "Idempotency-Key": "same-key"})
    assert response.status_code == 413


@pytest.mark.parametrize(("method", "path"), [
    ("GET", "/api/v1/payments/webhook/click"),
    ("POST", "/api/v1/payments/webhook/click/extra"),
    ("POST", "/api/v1/payments/webhook/other"),
    ("POST", "/api/v1/payments/init"),
])
def test_webhook_exemption_is_limited_to_its_own_post_routes(method, path):
    from app.middleware.idempotency_middleware import (
        _is_provider_webhook_idempotency_exempt,
    )

    assert not _is_provider_webhook_idempotency_exempt(method, path)


def test_internal_click_ingress_persists_before_return_with_retained_key_even_when_disabled(monkeypatch):
    import base64
    import hashlib
    import json
    from urllib.parse import urlencode

    from fastapi import FastAPI
    from pydantic import SecretStr

    from app.core.config import settings
    from app.services.click_receipt_service import ClickReceiptError, StoredClickReceipt

    calls = []

    class FakeReceiptService:
        def __init__(self, db, **kwargs):
            assert kwargs["keyring"] == {"v1": b"K" * 64}

        def store(self, **kwargs):
            calls.append(kwargs)
            if len(calls) == 2:
                raise ClickReceiptError("synthetic storage failure")
            return StoredClickReceipt(id=1, created=True, confidence="authenticated")

    monkeypatch.setattr(settings, "CLICK_ENABLED", False)
    monkeypatch.setattr(settings, "CLICK_SERVICE_ID", "100")
    monkeypatch.setattr(settings, "CLICK_SECRET_KEY", "new")
    monkeypatch.setattr(settings, "CLICK_WEBHOOK_CREDENTIALS", SecretStr(json.dumps([{"service_id": "100", "secret": "old"}])))
    monkeypatch.setattr(settings, "CLICK_RECEIPT_KEYS", SecretStr(json.dumps({"v1": base64.b64encode(b"K" * 64).decode()})))
    monkeypatch.setattr(settings, "CLICK_RECEIPT_ACTIVE_VERSION", "v1")
    monkeypatch.setattr(payment_webhooks, "ClickReceiptService", FakeReceiptService)
    app = FastAPI()

    @app.post("/test-only-click")
    async def endpoint(request: Request):
        receipt, observation = await payment_webhooks._store_click_callback(request, object())
        return {"stored": receipt.id, "phase": observation.action}

    fields = {"click_trans_id": "12", "service_id": "100", "merchant_trans_id": "invoice_1",
              "amount": "12.00", "action": "0", "error": "0", "error_note": "",
              "sign_time": "2026-11-17 10:00:00", "click_paydoc_id": "42"}
    fields["sign_string"] = hashlib.md5(b"12100oldinvoice_112.0002026-11-17 10:00:00", usedforsecurity=False).hexdigest()
    body = urlencode(fields).encode()
    with TestClient(app) as client:
        first = client.post("/test-only-click", content=body, headers={"content-type": "application/x-www-form-urlencoded"})
        assert first.status_code == 200 and first.json() == {"stored": 1, "phase": 0}
        assert calls[0]["secret_key"] == "old" and calls[0]["body"] == body
        retry = client.post("/test-only-click", content=body, headers={"content-type": "application/x-www-form-urlencoded"})
        assert retry.status_code == 503
        fields["sign_string"] = "0" * 32
        invalid = client.post("/test-only-click", content=urlencode(fields), headers={"content-type": "application/x-www-form-urlencoded"})
        assert invalid.status_code == 400 and len(calls) == 2
