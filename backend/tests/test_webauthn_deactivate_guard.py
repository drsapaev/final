"""Fail-first regression tests for WEBAUTHN-BE-003 (audit group 33, #4063).

``POST /webauthn/credentials/{credential_id}/deactivate`` authenticated solely
via the long-lived Telegram ``initData`` session (legacy max_age=24h,
replay_check=False): a phished initData blob allowed listing and silently
removing every passkey — no WebAuthn ceremony, no re-authentication, and no
last-credential guard (full lockout). Deactivation of an already-inactive
credential returned the same 200 ``{"deactivated": true}`` as a real removal.

Fix contract (wave 3c-3):
- destructive window: the deactivate handler resolves initData with
  ``max_age_seconds=900`` (15 min) instead of the 24h legacy window;
- last-credential guard: deactivating the patient's ONLY active passkey is
  rejected with ``409 {"reason": "last_active_credential"}`` (no lockout);
- inactive/unknown credentials return the SAME opaque
  ``404 {"reason": "credential_not_found"}`` (no state disclosure);
- deactivation is logged (audit trail) — the phish still needs a fresh
  signature, and the last passkey is safe.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from types import SimpleNamespace
from urllib.parse import urlencode

import pytest

DEACTIVATE_PATH = "/api/v1/webauthn/credentials/{cid}/deactivate"
BOT_TOKEN = "123456:test-mini-app-token"


def _cred_b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode()


def _make_credential(db_session, patient_id: int, n: int, active: bool = True):
    from app.models.passkey_credential import PasskeyCredential

    cred = PasskeyCredential(
        patient_id=patient_id,
        credential_id=_cred_b64(f"cred-{patient_id}-{n}".encode()),
        public_key=_cred_b64(f"pubkey-{patient_id}-{n}".encode()),
        sign_count=0,
        active=active,
    )
    db_session.add(cred)
    db_session.commit()
    return cred


@pytest.fixture()
def fake_scope(monkeypatch):
    """Bypass telegram auth at the endpoint boundary; capture max_age window."""
    captured: dict = {}

    def _fake_resolve(
        db, *, init_data_payload=None, entry_token=None, expected_section=None, **kwargs
    ):
        captured["max_age_seconds"] = kwargs.get("max_age_seconds")
        if init_data_payload == "stale-payload":
            raise RuntimeError("auth_failed")
        return SimpleNamespace(patient_id=4242), "init_data"

    from app.api.v1.endpoints.telegram_webhook import _clinic_bot

    monkeypatch.setattr(
        _clinic_bot, "_resolve_mini_app_patient_scope_from_auth", _fake_resolve
    )
    return captured


def _post(client, cid: int, init_data: str = "fresh-payload"):
    return client.post(DEACTIVATE_PATH.format(cid=cid), json={"init_data": init_data})


class TestWebAuthnBE003DeactivateGuard:
    def test_last_active_credential_rejected_409(self, client, db_session, fake_scope):
        """RED: the only active passkey could be silently removed (lockout).
        GREEN: 409 last_active_credential, credential stays active."""
        cred = _make_credential(db_session, 4242, 1)

        r = _post(client, cred.id)

        assert r.status_code == 409, (r.status_code, r.text[:200])
        assert r.json() == {"detail": {"reason": "last_active_credential"}}
        db_session.refresh(cred)
        assert cred.active is True, "last passkey must NOT be deactivated"

    def test_second_credential_deactivates_ok(self, client, db_session, fake_scope):
        """The legitimate case is preserved: with >=2 active passkeys,
        deactivating one still returns 200 and keeps the other active."""
        c1 = _make_credential(db_session, 4242, 1)
        c2 = _make_credential(db_session, 4242, 2)

        r = _post(client, c1.id)

        assert r.status_code == 200, (r.status_code, r.text[:200])
        assert r.json() == {"deactivated": True, "credential_id": c1.id}
        db_session.refresh(c1)
        db_session.refresh(c2)
        assert c1.active is False
        assert c2.active is True

    def test_already_inactive_uniform_404(self, client, db_session, fake_scope):
        """RED: re-deactivating an inactive credential returned the same 200
        {"deactivated": true}. GREEN: opaque 404, same as unknown id."""
        c1 = _make_credential(db_session, 4242, 1)
        _make_credential(db_session, 4242, 2)
        _post(client, c1.id)

        r = _post(client, c1.id)
        assert r.status_code == 404, (r.status_code, r.text[:200])
        assert r.json() == {"detail": {"reason": "credential_not_found"}}

    def test_unknown_credential_uniform_404(self, client, db_session, fake_scope):
        r = _post(client, 999999)
        assert r.status_code == 404
        assert r.json() == {"detail": {"reason": "credential_not_found"}}

    def test_destructive_window_900s_applied(self, client, db_session, fake_scope):
        """The handler must resolve initData with the 15-min destructive
        window (not the 24h legacy window)."""
        _make_credential(db_session, 4242, 1)
        _make_credential(db_session, 4242, 2)
        _post(client, 999999)
        assert (
            fake_scope.get("max_age_seconds") == 900
        ), "deactivate must use max_age_seconds=900 (WEBAUTHN-BE-003)"


class TestWebAuthnBE003FreshInitData:
    def test_validate_rejects_payload_older_than_900s(self):
        """Direct validator contract for the destructive window."""
        from app.services.telegram_mini_app_init_data import (
            TelegramMiniAppInitDataError,
            validate_telegram_mini_app_init_data,
        )

        def signed(auth_age_s: int) -> str:
            params = {
                "auth_date": str(int(time.time()) - auth_age_s),
                "query_id": "AAEAAAE",
                "user": json.dumps({"id": 777}, separators=(",", ":")),
            }
            dcs = "\n".join(f"{k}={v}" for k, v in sorted(params.items()))
            secret = hmac.new(
                b"WebAppData", BOT_TOKEN.encode(), hashlib.sha256
            ).digest()
            sig = hmac.new(secret, dcs.encode(), hashlib.sha256).hexdigest()
            return urlencode({**params, "hash": sig})

        from datetime import UTC, datetime

        now_dt = datetime.fromtimestamp(time.time(), UTC)
        with pytest.raises(TelegramMiniAppInitDataError):
            validate_telegram_mini_app_init_data(
                signed(3600),
                bot_token=BOT_TOKEN,
                max_age_seconds=900,
                replay_check=False,
                now=now_dt,
            )
        ok = validate_telegram_mini_app_init_data(
            signed(60),
            bot_token=BOT_TOKEN,
            max_age_seconds=900,
            replay_check=False,
            now=now_dt,
        )
        assert ok is not None

    def test_resolver_propagates_destructive_window(self, db_session, monkeypatch):
        """RED: the patient-scope resolver had no max_age parameter at all —
        every caller was stuck with the 24h legacy window."""
        from app.api.v1.endpoints.telegram_webhook import _clinic_bot
        from app.services.telegram_mini_app_init_data import (
            TelegramMiniAppInitDataError,
        )

        monkeypatch.setattr(
            _clinic_bot, "_get_configured_bot_token", lambda db: BOT_TOKEN
        )

        params = {
            "auth_date": str(
                int(time.time()) - 7200
            ),  # 2h old: fresh for legacy, stale for 900s
            "query_id": "AAEAAAE",
            "user": json.dumps({"id": 777}, separators=(",", ":")),
        }
        dcs = "\n".join(f"{k}={v}" for k, v in sorted(params.items()))
        secret = hmac.new(b"WebAppData", BOT_TOKEN.encode(), hashlib.sha256).digest()
        sig = hmac.new(secret, dcs.encode(), hashlib.sha256).hexdigest()
        stale = urlencode({**params, "hash": sig})

        with pytest.raises(TelegramMiniAppInitDataError):
            _clinic_bot._resolve_mini_app_patient_scope_from_init_data(
                db_session, stale, max_age_seconds=900
            )
