"""TGCONFIRM-BE-001 (audit #3892, group 20) — patient Telegram confirm callback.

The callback constructs the confirmation API call from a nonexistent
``Settings.API_BASE_URL``; with ``extra="ignore"`` no environment variable
could ever create the attribute, so EVERY patient confirmation failed with
AttributeError and the visit stayed pending. The contract tests pin:

1. the supported configuration surface (``Settings.API_BASE_URL`` exists),
2. the outbound POST targets ``{origin}/api/v1/telegram/visits/confirm``
   exactly once with the token payload,
3. an unset origin fails honestly (configuration error, no outgoing call,
   no internal/localhost assumption).

No real Telegram API, no real backend HTTP call: httpx.AsyncClient is
faked; Settings is the real application model.
"""

from __future__ import annotations

import asyncio

import pytest

from app.core.config import Settings
from app.services.telegram import bot as bot_module
from app.services.telegram.bot import ClinicTelegramBot


@pytest.fixture()
def fake_httpx(monkeypatch: pytest.MonkeyPatch):
    calls: list[dict] = []

    class _FakeResponse:
        def __init__(self, status_code: int, payload: dict) -> None:
            self.status_code = status_code
            self._payload = payload

        def json(self) -> dict:
            return self._payload

    class _FakeAsyncClient:
        last_instance: _FakeAsyncClient | None = None

        def __init__(self, *args, **kwargs) -> None:
            self.post_calls: list[dict] = []
            _FakeAsyncClient.last_instance = self

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc) -> None:
            return None

        async def post(self, url: str, **kwargs):
            self.post_calls.append({"url": url, **kwargs})
            calls.append(self.post_calls[-1])
            return _FakeResponse(200, {"success": True, "message": "confirmed"})

    monkeypatch.setattr("httpx.AsyncClient", _FakeAsyncClient)
    return calls


def test_settings_declares_api_base_url_field():
    """TGCONFIRM-BE-001: the Settings model must DECLARE the API_BASE_URL
    field. The historical bug was a callback referencing an attribute the
    model never had (extra='ignore' made it unfixable via env) — every
    confirmation died with AttributeError before any HTTP call."""
    assert "API_BASE_URL" in Settings.model_fields


def test_confirm_posts_to_configured_origin_with_api_v1_prefix(
    monkeypatch: pytest.MonkeyPatch, fake_httpx
):
    """With an explicitly configured origin the callback POSTs exactly once
    to {origin}/api/v1/telegram/visits/confirm and returns the API payload
    on 200."""
    monkeypatch.setattr(
        bot_module.settings, "API_BASE_URL", "https://api.clinic.example/"
    )
    bot = ClinicTelegramBot()

    result = asyncio.run(bot._confirm_visit_via_api("tok-123", 777))

    assert result == {"success": True, "message": "confirmed"}
    assert len(fake_httpx) == 1
    call = fake_httpx[0]
    assert call["url"] == "https://api.clinic.example/api/v1/telegram/visits/confirm"
    assert call["json"] == {"token": "tok-123", "channel": "telegram"}


def test_confirm_without_config_fails_honestly_without_outgoing_call(
    monkeypatch: pytest.MonkeyPatch, fake_httpx
):
    """An unset API_BASE_URL must fail honestly with a configuration error —
    no AttributeError, no silent internal/localhost default, no HTTP call."""
    monkeypatch.setattr(bot_module.settings, "API_BASE_URL", None)
    bot = ClinicTelegramBot()

    result = asyncio.run(bot._confirm_visit_via_api("tok-123", 777))

    assert result["success"] is False
    assert "API_BASE_URL" in result["message"]
    assert fake_httpx == []
