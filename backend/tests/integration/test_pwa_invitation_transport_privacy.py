"""Synthetic PWA transport retains its capability without logging it."""

from types import SimpleNamespace

import pytest

from app.services.notifications_pkg import NotificationSenderService


@pytest.mark.asyncio
@pytest.mark.parametrize("failure_mode", ["response", "exception"])
async def test_pwa_sms_is_neutral_and_provider_failure_never_logs_capability(
    monkeypatch, caplog, failure_mode
):
    token = "SYNTHETIC-CAPABILITY-EXAMPLE"
    phone = "+15550000001"
    messages = []

    class FakeManager:
        async def send_sms(self, destination, text):
            messages.append((destination, text))
            if failure_mode == "exception":
                raise RuntimeError(f"provider echoed {destination} {text}")
            return SimpleNamespace(
                success=False,
                provider="synthetic",
                error=f"provider echoed {destination} {text}",
            )

    monkeypatch.setattr(
        "app.services.sms_providers.get_sms_manager", lambda: FakeManager()
    )
    patient = SimpleNamespace(id=42, phone=phone)
    result = await NotificationSenderService()._send_pwa_invitation(
        patient,
        {
            "confirmation_token": token,
            "visit_date": "SYNTHETIC-DATE",
            "visit_time": "12:34",
            "doctor_name": "SYNTHETIC-DOCTOR",
            "total_amount": "123.45",
        },
    )
    assert result["success"] is False
    assert len(messages) == 1
    body = messages[0][1]
    assert "#token=" + token in body
    assert "SYNTHETIC-DOCTOR" not in body
    assert "SYNTHETIC-DATE" not in body
    assert "123.45" not in body
    assert token not in caplog.text
    assert phone not in caplog.text
    assert "#token=" not in caplog.text


@pytest.mark.asyncio
@pytest.mark.parametrize("provider_name", ["eskiz", "playmobile"])
async def test_sms_adapter_does_not_log_echoed_exception(
    monkeypatch, caplog, provider_name
):
    from unittest.mock import AsyncMock

    from app.services.sms_providers import (
        EskizSMSProvider,
        PlayMobileSMSProvider,
        SMSMessage,
    )

    token = "SYNTHETIC-ADAPTER-CAPABILITY"
    phone = "+15550000002"
    body = f"Open https://example.test/confirm-visit#token={token}"

    class FailingClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def post(self, url, **kwargs):
            raise RuntimeError(f"echo {phone} {body}")

    monkeypatch.setattr("httpx.AsyncClient", FailingClient)
    if provider_name == "eskiz":
        provider = EskizSMSProvider("synthetic", "synthetic")
        provider._get_auth_token = AsyncMock(return_value="synthetic-auth")
    else:
        provider = PlayMobileSMSProvider("synthetic", "synthetic")
    result = await provider.send_sms(SMSMessage(phone=phone, text=body))
    assert result.success is False
    assert token not in caplog.text
    assert phone not in caplog.text
    assert body not in caplog.text
    assert token not in str(result.error)
