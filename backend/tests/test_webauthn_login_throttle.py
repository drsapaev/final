"""Fail-first regression tests for WEBAUTHN-BE-002 (audit group 33, #4063).

``/webauthn/login/begin`` and ``/login/finish`` are fully unauthenticated,
take an arbitrary ``patient_id`` from the body and carried no rate limiting:
distinct 400/500 shapes revealed whether a patient id exists / has an active
passkey (anonymous enumeration), ``login/begin`` stored a challenge in the
shared cache for ANY caller-supplied id (unbounded cache growth), and
assertion attempts were unthrottled.

Fix contract (wave 3c-2):
- begin returns a byte-identical 200 shape for known patients without an
  active passkey and for unknown ids, and does NOT cache a challenge unless
  the patient actually has an active credential (cache can no longer be
  grown by anonymous probing);
- finish returns one uniform ``403 {"reason": "auth_finish_failed"}`` for
  every pre-verification failure (non-numeric id, unknown id, no challenge,
  no active credential) — details stay in server logs;
- both endpoints are IP-rate-limited (slowapi, like the rest of the auth
  plane).
"""

from __future__ import annotations

import base64

import pytest

FINISH_PATH = "/api/v1/webauthn/login/finish"
BEGIN_PATH = "/api/v1/webauthn/login/begin"


def _cred_b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode()


@pytest.fixture()
def webauthn_enabled(monkeypatch):
    """Flip the service into its available mode without the optional lib.

    ``_check_webauthn_available()`` (503 guard) reads the module-level
    ``WEBAUTHN_AVAILABLE``; without the library installed the options
    generator name does not exist either — plant a stub (monkeypatch
    removes it again on undo).
    """
    from types import SimpleNamespace

    from app.services import webauthn_service as ws

    monkeypatch.setattr(ws, "WEBAUTHN_AVAILABLE", True, raising=False)
    if not hasattr(ws, "generate_authentication_options"):
        monkeypatch.setattr(
            ws,
            "generate_authentication_options",
            lambda **kwargs: SimpleNamespace(challenge=b"challenge-bytes"),
            raising=False,
        )


@pytest.fixture()
def patient_with_passkey(db_session):
    from app.models.passkey_credential import PasskeyCredential

    pid = 4242
    db_session.add(
        PasskeyCredential(
            patient_id=pid,
            credential_id=_cred_b64(b"cred-4242"),
            public_key=_cred_b64(b"pubkey-4242"),
            sign_count=0,
            active=True,
        )
    )
    db_session.commit()
    return pid


class TestWebAuthnBE002NoEnumeration:
    def test_begin_does_not_cache_challenge_for_unknown_patient(
        self, client, db_session, webauthn_enabled
    ):
        """RED: begin cached a challenge for ANY caller-supplied id.
        GREEN: identical 200 shape, but the cache stays empty — the dummy
        challenge can never complete a ceremony."""
        cache = _cache_manager()
        cache.delete("webauthn_auth_challenge:999999")

        r = client.post(BEGIN_PATH, json={"patient_id": 999999})
        assert r.status_code == 200
        body = r.json()["options"]
        assert body["challenge"]
        assert (
            cache.get("webauthn_auth_challenge:999999") is None
        ), "challenge must not be cached for a patient without an active passkey"

    def test_begin_caches_challenge_when_active_passkey_exists(
        self, client, db_session, patient_with_passkey, webauthn_enabled
    ):
        """GREEN side of the cache rule: with an active credential the
        challenge IS cached (otherwise no login could ever complete)."""
        cache = _cache_manager()
        cache.delete(f"webauthn_auth_challenge:{patient_with_passkey}")

        r = client.post(BEGIN_PATH, json={"patient_id": patient_with_passkey})
        assert r.status_code == 200
        assert cache.get(f"webauthn_auth_challenge:{patient_with_passkey}")

    def test_begin_uniform_shape_known_vs_unknown(
        self, client, patient_with_passkey, webauthn_enabled
    ):
        """Known-with-passkey and unknown ids must return the same 200 shape
        (same keys) so begin cannot be used for enumeration."""
        known = client.post(BEGIN_PATH, json={"patient_id": patient_with_passkey})
        unknown = client.post(BEGIN_PATH, json={"patient_id": 888888})
        assert known.status_code == unknown.status_code == 200
        assert set(known.json().keys()) == set(unknown.json().keys())
        assert set(known.json()["options"].keys()) == set(
            unknown.json()["options"].keys()
        )
        assert known.json()["options"]["challenge"]
        assert unknown.json()["options"]["challenge"]

    def test_finish_uniform_403_for_all_preverify_failures(
        self, client, db_session, patient_with_passkey, webauthn_enabled
    ):
        """RED: non-numeric id → 500, unknown id → 403 with the raw service
        message ("No active passkey found for patient"), no challenge → 403
        with another message. GREEN: every pre-verify failure is the same
        opaque 403 {"reason": "auth_finish_failed"}."""
        cases = [
            {"patient_id": "not-a-number", "assertion_response": {"id": "x"}},
            {"patient_id": 777777, "assertion_response": {"id": "x"}},
            {
                "patient_id": patient_with_passkey,
                "assertion_response": {"id": "x"},
            },
        ]
        for payload in cases:
            r = client.post(FINISH_PATH, json=payload)
            assert r.status_code == 403, (payload, r.status_code, r.text[:200])
            assert r.json() == {"detail": {"reason": "auth_finish_failed"}}, (
                payload,
                r.text[:200],
            )


class TestWebAuthnBE002RateLimit:
    def test_login_begin_rate_limited_per_ip(
        self, client, monkeypatch, webauthn_enabled
    ):
        """RED: no limiter — N rapid anonymous begins all 200.
        GREEN: the IP limiter kicks in and returns 429 within N requests."""
        from app.core.rate_limiter import limiter

        monkeypatch.setattr(limiter, "enabled", True)
        try:
            limiter.reset()
        except Exception:
            pass

        statuses = []
        for i in range(15):
            r = client.post(BEGIN_PATH, json={"patient_id": 900000 + i})
            statuses.append(r.status_code)
        assert 429 in statuses, statuses


def _cache_manager():
    from app.core.cache import cache_manager

    return cache_manager
