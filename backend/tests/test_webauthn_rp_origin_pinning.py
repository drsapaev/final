"""Fail-first regression tests for WEBAUTHN-BE-001 (audit group 33, #4063).

WebAuthn's core anti-phishing guarantee is the origin/RP-ID binding: the
browser signs over the origin it is talking to, and the server must verify
the assertion against the RP ID/origin it TRUSTS — its own, not values
echoed by the caller. ``webauthn.py`` read ``rp_id``/``origin`` from the
request body (defaults ``localhost``/``http://localhost:3000``) and passed
them to the service as the *expected* verification values, so attacker
input was verified against attacker input.

Fix contract (wave 3c): RP ID and origin are server-pinned from
``settings.FRONTEND_URL`` (RP ID = hostname, origin = ``scheme://netloc``);
client-supplied ``rp_id``/``origin`` are ignored everywhere (options and
verification), for both registration and authentication. Tests monkeypatch
the module-level webauthn callables (the library itself is an optional
production dependency — not in requirements) and capture the kwargs that
would reach the verification layer.

All four flows are covered: registration begin (options embed the RP),
registration finish (``expected_origin``/``expected_rp_id``), authentication
begin, authentication finish.
"""

from __future__ import annotations

from types import SimpleNamespace
from urllib.parse import urlparse

import pytest

EVIL_RP = "evil.example"
EVIL_ORIGIN = "https://evil.example"


def _server_rp_origin():
    """The same pinning rule the service must apply (settings-derived)."""
    from app.core.config import settings

    parsed = urlparse(settings.FRONTEND_URL)
    rp_id = parsed.hostname
    origin = f"{parsed.scheme or 'https'}://{parsed.netloc}"
    return rp_id, origin


@pytest.fixture()
def webauthn_stub(monkeypatch):
    """Make the service flow testable without the optional webauthn lib.

    The service imports the webauthn callables at module import time inside
    a try/except — without the library installed those module attributes do
    not exist at all, so plant placeholders first (monkeypatch will remove
    them again on undo). Individual tests then replace them with capturing
    fakes.
    """
    from app.services import webauthn_service as ws

    monkeypatch.setattr(ws, "WEBAUTHN_AVAILABLE", True, raising=False)
    for name in (
        "generate_registration_options",
        "verify_registration_response",
        "generate_authentication_options",
        "verify_authentication_response",
    ):
        if not hasattr(ws, name):
            monkeypatch.setattr(ws, name, None, raising=False)
    return ws


class TestWebAuthnBE001ServerPinnedRp:
    def test_registration_begin_uses_server_rp(
        self, db_session, webauthn_stub, monkeypatch
    ):
        """RED: options embedded the client-supplied RP ID (evil.example).
        GREEN: the options generator receives only the server RP ID."""
        ws = webauthn_stub
        captured: dict = {}

        def fake_generate_registration_options(**kwargs):
            captured.update(kwargs)
            return SimpleNamespace(challenge=b"challenge-bytes")

        monkeypatch.setattr(
            ws, "generate_registration_options", fake_generate_registration_options
        )

        options = ws.begin_passkey_registration(
            db_session,
            1,
            rp_id=EVIL_RP,
            rp_name="Evil RP",
        )

        server_rp, _ = _server_rp_origin()
        assert captured["rp_id"] == server_rp, captured
        assert options["rp"]["id"] == server_rp

    def test_registration_finish_pins_server_origin(
        self, db_session, webauthn_stub, monkeypatch
    ):
        """RED: verify_registration_response got expected_origin=evil.example.
        GREEN: expected values are server-pinned regardless of body input."""
        from app.core.cache import cache_manager

        ws = webauthn_stub
        cache_manager.set("webauthn_reg_challenge:1", "challenge-bytes", ttl=300)
        captured: dict = {}

        def fake_verify_registration_response(**kwargs):
            captured.update(kwargs)
            raise ValueError("stop-capture")

        monkeypatch.setattr(
            ws, "verify_registration_response", fake_verify_registration_response
        )

        with pytest.raises(ValueError, match="stop-capture"):
            ws.finish_passkey_registration(
                db_session,
                1,
                credential_response={"id": "x"},
                rp_id=EVIL_RP,
                origin=EVIL_ORIGIN,
            )

        server_rp, server_origin = _server_rp_origin()
        assert captured["expected_origin"] == server_origin, captured
        assert captured["expected_rp_id"] == server_rp, captured

    def test_authentication_begin_uses_server_rp(
        self, db_session, webauthn_stub, monkeypatch
    ):
        """RED: login options embedded the client-supplied RP ID.
        GREEN: the options generator receives only the server RP ID."""
        ws = webauthn_stub
        captured: dict = {}

        def fake_generate_authentication_options(**kwargs):
            captured.update(kwargs)
            return SimpleNamespace(challenge=b"challenge-bytes")

        monkeypatch.setattr(
            ws, "generate_authentication_options", fake_generate_authentication_options
        )

        options = ws.begin_passkey_authentication(db_session, 1, rp_id=EVIL_RP)

        server_rp, _ = _server_rp_origin()
        assert captured["rp_id"] == server_rp, captured
        assert options["rpId"] == server_rp

    def test_authentication_finish_pins_server_origin(
        self, db_session, webauthn_stub, monkeypatch
    ):
        """RED: verify_authentication_response got expected_origin=evil.example
        for the unauthenticated login plane. GREEN: server-pinned values."""
        from app.core.cache import cache_manager
        from app.models.passkey_credential import PasskeyCredential

        ws = webauthn_stub
        cache_manager.set("webauthn_auth_challenge:7", "challenge-bytes", ttl=300)
        db_session.add(
            PasskeyCredential(
                patient_id=7,
                credential_id="Y3JlZC1pZA==",  # urlsafe b64 of 'cred-id'
                public_key="cHVia2V5",  # urlsafe b64 of 'pubkey'
                sign_count=0,
                active=True,
            )
        )
        db_session.commit()
        captured: dict = {}

        def fake_verify_authentication_response(**kwargs):
            captured.update(kwargs)
            raise ValueError("stop-capture")

        monkeypatch.setattr(
            ws, "verify_authentication_response", fake_verify_authentication_response
        )

        with pytest.raises(ValueError, match="stop-capture"):
            ws.finish_passkey_authentication(
                db_session,
                7,
                assertion_response={"id": "x"},
                rp_id=EVIL_RP,
                origin=EVIL_ORIGIN,
            )

        server_rp, server_origin = _server_rp_origin()
        assert captured["expected_origin"] == server_origin, captured
        assert captured["expected_rp_id"] == server_rp, captured
