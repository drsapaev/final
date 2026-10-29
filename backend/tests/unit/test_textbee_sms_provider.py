from __future__ import annotations

import json

import httpx
import pytest

from app.services.sms_providers import SMSMessage
from app.services.textbee_sms_provider import TextBeeSMSProvider


@pytest.mark.asyncio
async def test_textbee_queues_one_otp_to_fixed_api_host(monkeypatch):
    requests: list[httpx.Request] = []
    real_async_client = httpx.AsyncClient

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200,
            json={
                "data": {
                    "success": True,
                    "smsBatchId": "batch-123",
                    "recipientCount": 1,
                }
            },
        )

    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda **kwargs: real_async_client(
            transport=httpx.MockTransport(handler), **kwargs
        ),
    )
    provider = TextBeeSMSProvider("test-api-key", device_id="device-1")

    result = await provider.send_sms(
        SMSMessage(phone="+998901112233", text="Код входа: 123456")
    )

    assert result.success is True
    assert result.provider == "textbee"
    assert result.status == "queued"
    assert result.message_id == "batch-123"
    assert len(requests) == 1
    request = requests[0]
    assert str(request.url) == "https://api.textbee.dev/api/v1/gateway/send-sms"
    assert request.headers["x-api-key"] == "test-api-key"
    assert json.loads(request.read()) == {
        "recipients": ["+998901112233"],
        "message": "Код входа: 123456",
        "deviceId": "device-1",
    }


@pytest.mark.asyncio
async def test_textbee_rejects_non_e164_number_without_network(monkeypatch):
    called = False

    def fail_if_called(**kwargs):
        nonlocal called
        called = True
        raise AssertionError("network client must not be created")

    monkeypatch.setattr(httpx, "AsyncClient", fail_if_called)
    result = await TextBeeSMSProvider("test-api-key").send_sms(
        SMSMessage(phone="998901112233", text="test")
    )

    assert result.success is False
    assert result.provider == "textbee"
    assert called is False


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "body",
    [
        {"data": {"success": False, "smsBatchId": "batch-123", "recipientCount": 1}},
        {"data": {"success": True, "smsBatchId": "batch-123", "recipientCount": 2}},
        {"data": {"success": True, "smsBatchId": "batch-123", "recipientCount": True}},
        {"data": {"success": True, "recipientCount": 1}},
    ],
)
async def test_textbee_requires_single_recipient_queue_acceptance(monkeypatch, body):
    real_async_client = httpx.AsyncClient
    transport = httpx.MockTransport(lambda request: httpx.Response(200, json=body))
    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda **kwargs: real_async_client(transport=transport, **kwargs),
    )

    result = await TextBeeSMSProvider("test-api-key").send_sms(
        SMSMessage(phone="+998901112233", text="test")
    )

    assert result.success is False
    assert result.error == "SMS provider send failed"


@pytest.mark.asyncio
async def test_textbee_http_error_is_generic_and_does_not_echo_response(monkeypatch):
    secret_response = {"message": "test-api-key must not be exposed"}
    real_async_client = httpx.AsyncClient
    transport = httpx.MockTransport(
        lambda request: httpx.Response(401, json=secret_response)
    )
    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda **kwargs: real_async_client(transport=transport, **kwargs),
    )

    result = await TextBeeSMSProvider("test-api-key").send_sms(
        SMSMessage(phone="+998901112233", text="test")
    )

    assert result.success is False
    assert result.error == "SMS provider send failed"
    assert "test-api-key" not in str(result)


@pytest.mark.asyncio
async def test_textbee_does_not_leak_transport_exception(caplog, monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        raise RuntimeError("test-api-key must not be logged")

    transport = httpx.MockTransport(handler)
    real_async_client = httpx.AsyncClient
    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda **kwargs: real_async_client(transport=transport, **kwargs),
    )

    result = await TextBeeSMSProvider("test-api-key").send_sms(
        SMSMessage(phone="+998901112233", text="test")
    )

    assert result.success is False
    assert "test-api-key" not in caplog.text
