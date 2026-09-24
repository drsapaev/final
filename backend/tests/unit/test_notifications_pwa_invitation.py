"""Regression: PWA invitation deep link must build from the canonical
public frontend base URL.

Staging acceptance (Check 5b, main 53ec8ddb) found a P1: the PWA leg of
visit-confirmation reminders always failed before the SMS transport was
reached — ``_send_pwa_invitation`` read ``settings.PWA_BASE_URL``, a
setting that has never existed on ``app.core.config.Settings`` (orphaned
reference introduced with the notifications.py split in PR #3320).
The worker observed ``AttributeError: 'Settings' object has no attribute
'PWA_BASE_URL'`` → retry backoff → delivery failed.

Canonical decision (confirmed by repo conventions, not invented):
the PWA is served by the SAME frontend origin, and every other public
deep link in the codebase — the structurally identical password-reset
token link, Telegram web-app buttons, queue URLs, QR codes, payment
entry — is built from ``settings.FRONTEND_URL``. Production docs
(SETUP_PRODUCTION.md) configure exactly one public URL. Therefore the
PWA invitation link must use the same canonical setting instead of a
second source of truth.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.core.config import Settings, settings
from app.services.notifications_pkg import NotificationSenderService


def test_settings_exposes_canonical_public_frontend_base_url() -> None:
    """Settings must provide the public base URL the PWA link derives from."""
    # The field is declared on the Settings class (not an ad-hoc attribute),
    # so the deep-link builder has a typed, validated source of truth.
    assert "FRONTEND_URL" in Settings.model_fields
    base = settings.FRONTEND_URL
    assert isinstance(base, str) and base.startswith(("http://", "https://"))


def test_settings_normalizes_frontend_url_trailing_slash() -> None:
    """FRONTEND_URL must never carry whitespace or a trailing slash.

    Deep links are built as ``f"{settings.FRONTEND_URL}/path"`` — a
    configured trailing slash would produce ``"//path"`` URLs that miss
    the intended React Router route (review P2: normalization via
    ``rstrip("/")").
    """
    assert (
        Settings(
            SECRET_KEY="unit-test-only-secret-key-32chars!!",
            FRONTEND_URL="https://clinic.example.com/",
        ).FRONTEND_URL
        == "https://clinic.example.com"
    )
    assert (
        Settings(
            SECRET_KEY="unit-test-only-secret-key-32chars!!",
            FRONTEND_URL="  https://clinic.example.com///  ",
        ).FRONTEND_URL
        == "https://clinic.example.com"
    )


@pytest.mark.asyncio
async def test_pwa_invitation_uses_canonical_frontend_url(monkeypatch) -> None:
    """_send_pwa_invitation must build <FRONTEND_URL>/confirm-visit#token=
    and hand the phone + link to the SMS transport without AttributeError.

    RED on main before the fix: ``settings.PWA_BASE_URL`` does not exist,
    so the URL construction raised AttributeError inside the try/except and
    the method returned ``{"success": False, "error": "'Settings' object
    has no attribute 'PWA_BASE_URL'"}`` — the SMS transport was never
    reached.
    """
    # Trailing slash on purpose (review P2): the builder must normalize
    # the base, so the SMS link can never contain "//confirm-visit".
    public_base = "https://clinic.example.com/"
    monkeypatch.setattr(settings, "FRONTEND_URL", public_base)

    service = NotificationSenderService()

    # Mock ONLY the external SMS transport boundary (the provider manager
    # that ChannelsMixin.send_sms dispatches to); _send_pwa_invitation and
    # send_sms themselves run for real.
    sent: list[tuple[str, str]] = []

    class _StubSMSManager:
        async def send_sms(self, phone: str, text: str):  # noqa: ANN001
            sent.append((phone, text))
            return SimpleNamespace(
                success=True, provider="stub", message_id="stub-1", status="sent"
            )

    monkeypatch.setattr(
        "app.services.sms_providers.get_sms_manager",
        lambda: _StubSMSManager(),
    )

    # Synthetic fixture only (AGENTS.md policy): 00-operator prefix does
    # not exist in the +998 numbering plan, the last name carries the
    # SYNTHETIC- marker (same convention as synthetic_seed.py).
    patient = SimpleNamespace(
        id=42,
        phone="+998000000000",
        first_name="Синтетик",
        last_name="SYNTHETIC-Testpatient",
    )
    token = "visit-confirm-token-123"
    data = {
        "visit_id": 7,
        "confirmation_token": token,
        "visit_date": "25.09.2026",
        "visit_time": "10:30",
        "doctor_name": "SYNTHETIC Test Doctor",
        "total_amount": 150000,
    }

    result = await service._send_pwa_invitation(patient, data)

    expected_url = f"https://clinic.example.com/confirm-visit#token={token}"

    # (4) no AttributeError swallowed into the result …
    assert result.get("success") is True, (
        f"PWA invitation failed before the SMS transport: {result.get('error')!r}"
    )
    # (5) … the success contract is the pwa channel with the built link …
    assert result.get("channel") == "pwa"
    assert result.get("pwa_url") == expected_url
    assert token not in expected_url.split("#", 1)[0]
    # (3) … and the SMS transport got the expected phone and link.
    assert len(sent) == 1, "SMS transport must be called exactly once"
    phone, sms_text = sent[0]
    assert phone == "+998000000000"
    assert expected_url in sms_text
