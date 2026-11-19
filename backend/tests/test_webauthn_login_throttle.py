"""Fail-first regression tests for WEBAUTHN-BE-002 (audit group 33, #4063).

``/webauthn/login/begin`` and ``/login/finish`` are fully unauthenticated,
take an arbitrary ``patient_id`` from the body and carried no rate limiting:
distinct 400/500 shapes revealed whether a patient id exists / has an active
passkey (anonymous enumeration), ``login/begin`` stored a challenge in the
shared cache for ANY caller-supplied id (unbounded cache growth), and
assertion attempts were unthrottled.

Fix contract:
- begin performs the same quota-bounded store operation for known and
  unknown patients, avoiding existence leaks during Redis failures or quota
  saturation;
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

    from app.core.config import settings
    from app.services import webauthn_service as ws

    monkeypatch.setattr(settings, "FRONTEND_URL", "https://clinic.example")
    with ws._test_ceremonies_lock:
        ws._test_ceremonies.clear()
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
    from app.models.patient import Patient
    from app.models.user import User

    pid = 4242
    user = User(
        username="SYNTHETIC-passkey-login",
        hashed_password="test-only",
        role="Patient",
        is_active=True,
        is_superuser=False,
    )
    db_session.add(user)
    db_session.flush()
    db_session.add(
        Patient(id=pid, user_id=user.id, first_name="SYNTHETIC", last_name="PATIENT")
    )
    db_session.flush()
    db_session.add(
        PasskeyCredential(
            patient_id=pid,
            owner_user_id=user.id,
            credential_id=_cred_b64(b"cred-4242"),
            public_key=_cred_b64(b"pubkey-4242"),
            sign_count=0,
            active=True,
        )
    )
    db_session.commit()
    return pid


class TestWebAuthnBE002NoEnumeration:
    def test_begin_stores_bounded_dummy_for_unknown_patient(
        self, client, db_session, webauthn_enabled
    ):
        """Unknown users follow the same storage path and cannot log in."""
        from app.services import webauthn_service as ws

        r = client.post(BEGIN_PATH, json={"patient_id": 999999})
        assert r.status_code == 200
        body = r.json()["options"]
        assert body["challenge"]
        assert f"webauthn:login:{body['ceremony_id']}" in ws._test_ceremonies
        finish = client.post(
            FINISH_PATH,
            json={
                "patient_id": 999999,
                "ceremony_id": body["ceremony_id"],
                "assertion_response": {"id": "x", "rawId": "x"},
            },
        )
        assert finish.status_code == 403

    def test_begin_caches_challenge_when_active_passkey_exists(
        self, client, db_session, patient_with_passkey, webauthn_enabled
    ):
        """GREEN side of the cache rule: with an active credential the
        challenge IS cached (otherwise no login could ever complete)."""
        from app.services import webauthn_service as ws

        r = client.post(BEGIN_PATH, json={"patient_id": patient_with_passkey})
        assert r.status_code == 200
        ceremony_id = r.json()["options"]["ceremony_id"]
        assert f"webauthn:login:{ceremony_id}" in ws._test_ceremonies

    @pytest.mark.parametrize("owner", ["missing", "different"])
    def test_unowned_or_relinked_key_cannot_complete_login(
        self, client, db_session, patient_with_passkey, webauthn_enabled, owner
    ):
        from app.models.passkey_credential import PasskeyCredential
        from app.models.user import User
        from app.services import webauthn_service as ws

        credential = (
            db_session.query(PasskeyCredential)
            .filter_by(patient_id=patient_with_passkey)
            .one()
        )
        if owner == "missing":
            credential.owner_user_id = None
        else:
            previous_owner = User(
                username="SYNTHETIC-previous-owner",
                hashed_password="test-only",
                role="Patient",
                is_active=True,
                is_superuser=False,
            )
            db_session.add(previous_owner)
            db_session.flush()
            credential.owner_user_id = previous_owner.id
        db_session.commit()

        response = client.post(BEGIN_PATH, json={"patient_id": patient_with_passkey})
        assert response.status_code == 200
        ceremony_id = response.json()["options"]["ceremony_id"]
        assert f"webauthn:login:{ceremony_id}" in ws._test_ceremonies
        encoded_id = credential.credential_id.rstrip("=")
        finish = client.post(
            FINISH_PATH,
            json={
                "patient_id": patient_with_passkey,
                "ceremony_id": ceremony_id,
                "assertion_response": {"id": encoded_id, "rawId": encoded_id},
            },
        )
        assert finish.status_code == 403

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
            {
                "patient_id": "not-a-number",
                "assertion_response": {"id": "x"},
                "ceremony_id": "a",
            },
            {
                "patient_id": 777777,
                "assertion_response": {"id": "x"},
                "ceremony_id": "a",
            },
            {
                "patient_id": patient_with_passkey,
                "assertion_response": {"id": "x"},
                "ceremony_id": "a",
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


@pytest.mark.parametrize(
    "path",
    [
        "/api/v1/webauthn/register/begin",
        "/api/v1/webauthn/register/finish",
        "/api/v1/webauthn/credentials/list",
        "/api/v1/webauthn/credentials/1/deactivate",
    ],
)
def test_management_rejects_replayed_init_data_without_bearer(client, path):
    response = client.post(path, json={"init_data": "replayed-payload"})
    assert response.status_code == 401


@pytest.mark.parametrize(
    "payload", [[], None, {"patient_id": True}, {"patient_id": -1}]
)
def test_login_begin_rejects_malformed_body_without_server_error(
    client, webauthn_enabled, payload
):
    response = client.post(BEGIN_PATH, json=payload)
    assert response.status_code == 400


def test_login_reports_store_unavailable_without_fallback(
    client, webauthn_enabled, monkeypatch
):
    from app.services import webauthn_service as ws

    def unavailable():
        raise ws.WebAuthnStoreUnavailable("offline")

    monkeypatch.setattr(ws, "_ceremony_store", unavailable)
    begin = client.post(BEGIN_PATH, json={"patient_id": 123})
    finish = client.post(
        FINISH_PATH,
        json={
            "patient_id": 123,
            "ceremony_id": "a" * 43,
            "assertion_response": {"id": "x"},
        },
    )
    assert begin.status_code == finish.status_code == 503
    assert (
        begin.json()
        == finish.json()
        == {"detail": {"reason": "auth_temporarily_unavailable"}}
    )


DISCOVERABLE_BEGIN = "/api/v1/webauthn/login/discoverable/begin"
DISCOVERABLE_FINISH = "/api/v1/webauthn/login/discoverable/finish"


@pytest.fixture
def discoverable_redis(monkeypatch):
    """Use isolated namespaced keys in a disposable or CI Redis."""
    import os
    import uuid

    import redis

    from app.services import webauthn_service as ws

    url = os.getenv("WEBAUTHN_TEST_REDIS_URL") or os.getenv("ARQ_REDIS_URL")
    if not url:
        pytest.skip(
            "set WEBAUTHN_TEST_REDIS_URL or ARQ_REDIS_URL for Redis integration"
        )
    store = redis.Redis.from_url(url, decode_responses=True, socket_connect_timeout=2)
    try:
        store.ping()
    except redis.RedisError as exc:
        pytest.fail(f"configured test Redis is unavailable: {type(exc).__name__}")
    prefix = f"webauthn:{{discoverable}}:test:{uuid.uuid4().hex}:"
    monkeypatch.setattr(ws, "_DISCOVERABLE_PREFIX", prefix)
    monkeypatch.setattr(ws, "_discoverable_store", lambda: store)
    yield store
    keys = list(store.scan_iter(match=prefix + "*"))
    if keys:
        store.delete(*keys)
    store.close()


@pytest.mark.parametrize(
    "origin,bad_handle,owner_state,expected,revoke_before_second,has_totp,factor_case",
    [
        ("https://clinic.example", False, "active", 200, False, False, "none"),
        *[
            ("https://clinic.example", False, "active", 200, False, True, mode)
            for mode in ("totp", "backup", "disabled", "replaced")
        ],
        ("https://clinic.example", False, "active", 200, True, True, "totp"),
        ("https://evil.example", False, "active", 403, False, True, "totp"),
        ("https://clinic.example", True, "active", 403, False, True, "totp"),
        *[
            ("https://clinic.example", False, state, 403, False, True, "totp")
            for state in ("relinked", "inactive_user", "inactive_key")
        ],
    ],
)
def test_discoverable_login_without_patient_id_uses_signed_assertion_once(
    client,
    db_session,
    patient_with_passkey,
    webauthn_enabled,
    discoverable_redis,
    origin,
    bad_handle,
    owner_state,
    expected,
    revoke_before_second,
    has_totp,
    factor_case,
):
    """Real WebAuthn signature, real Redis GETDEL and a canonical patient JWT."""
    import hashlib
    import json

    import cbor2
    import jwt
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import ec

    from app.core.config import settings
    from app.models.passkey_credential import PasskeyCredential
    from app.models.patient import Patient
    from app.models.user import User
    from app.services import webauthn_service as ws

    credential = (
        db_session.query(PasskeyCredential)
        .filter_by(patient_id=patient_with_passkey)
        .one()
    )
    patient = db_session.query(Patient).filter_by(id=patient_with_passkey).one()
    db_session.query(User).filter_by(id=patient.user_id).one().auth_epoch = 7
    secret = None
    if has_totp:
        from app.models.two_factor_auth import TwoFactorAuth, TwoFactorBackupCode
        from app.services.two_factor_service import get_two_factor_service

        factor_service = get_two_factor_service()
        secret = factor_service.generate_totp_secret()
        factor = TwoFactorAuth(
            user_id=patient.user_id,
            totp_secret=secret,
            totp_enabled=True,
            totp_verified=True,
        )
        db_session.add(factor)
        db_session.flush()
        backup_code = "TEST1234"
        db_session.add(
            TwoFactorBackupCode(
                two_factor_auth_id=factor.id,
                code=factor_service._hash_backup_code(backup_code),
            )
        )
    key = ec.generate_private_key(ec.SECP256R1())
    public = key.public_key().public_numbers()
    credential.public_key = ws._b64url(
        cbor2.dumps(
            {
                1: 2,
                3: -7,
                -1: 1,
                -2: public.x.to_bytes(32, "big"),
                -3: public.y.to_bytes(32, "big"),
            }
        )
    )
    credential.public_key += "=" * (-len(credential.public_key) % 4)
    if owner_state == "relinked":
        replacement = User(
            username="SYNTHETIC-replacement-user",
            hashed_password="test-only",
            role="Patient",
            is_active=True,
            is_superuser=False,
        )
        db_session.add(replacement)
        db_session.flush()
        patient.user_id = replacement.id
    elif owner_state == "inactive_user":
        db_session.query(User).filter_by(id=patient.user_id).one().is_active = False
    elif owner_state == "inactive_key":
        credential.active = False
    db_session.commit()

    begin = client.post(DISCOVERABLE_BEGIN, json={})
    assert begin.status_code == 200, begin.text
    options = begin.json()["options"]
    client_data = json.dumps(
        {"type": "webauthn.get", "challenge": options["challenge"], "origin": origin},
        separators=(",", ":"),
    ).encode()
    authenticator_data = (
        hashlib.sha256(b"clinic.example").digest() + b"\x05" + (1).to_bytes(4, "big")
    )
    signature = key.sign(
        authenticator_data + hashlib.sha256(client_data).digest(),
        ec.ECDSA(hashes.SHA256()),
    )
    encoded_id = credential.credential_id.rstrip("=")
    assertion = {
        "id": encoded_id,
        "rawId": encoded_id,
        "type": "public-key",
        "response": {
            "authenticatorData": ws._b64url(authenticator_data),
            "clientDataJSON": ws._b64url(client_data),
            "signature": ws._b64url(signature),
            "userHandle": ws._b64url(b"wrong-patient") if bad_handle else None,
        },
    }
    payload = {"ceremony_id": options["ceremony_id"], "assertion_response": assertion}
    finish = client.post(DISCOVERABLE_FINISH, json=payload)
    assert finish.status_code == expected, finish.text
    if expected == 200:
        assert "access_token" not in finish.json()
        next_options = finish.json()["next_options"]
        assert next_options["allowCredentials"] == [
            {"type": "public-key", "id": encoded_id}
        ]
        client_data_2 = json.dumps(
            {
                "type": "webauthn.get",
                "challenge": next_options["challenge"],
                "origin": origin,
            },
            separators=(",", ":"),
        ).encode()
        auth_data_2 = (
            hashlib.sha256(b"clinic.example").digest()
            + b"\x05"
            + (2).to_bytes(4, "big")
        )
        signature_2 = key.sign(
            auth_data_2 + hashlib.sha256(client_data_2).digest(),
            ec.ECDSA(hashes.SHA256()),
        )
        assertion_2 = {
            **assertion,
            "response": {
                **assertion["response"],
                "authenticatorData": ws._b64url(auth_data_2),
                "clientDataJSON": ws._b64url(client_data_2),
                "signature": ws._b64url(signature_2),
            },
        }
        if revoke_before_second:
            db_session.query(User).filter_by(id=patient.user_id).one().auth_epoch += 1
            db_session.commit()
        complete_body = {
            "ceremony_id": next_options["ceremony_id"],
            "assertion_response": assertion_2,
        }
        complete = client.post(
            "/api/v1/webauthn/login/discoverable/complete", json=complete_body
        )
        if revoke_before_second:
            assert complete.status_code == 403, complete.text
            assert "access_token" not in complete.text
        else:
            assert complete.status_code == 200, complete.text
            assert complete.headers["cache-control"] == "no-store"
            completed = complete.json()
            if has_totp:
                assert completed["requires_2fa"] is True
                assert completed["two_factor_method"] == "totp"
                assert (
                    "access_token" not in completed and "refresh_token" not in completed
                )
                pending = completed["pending_2fa_token"]
                code = factor_service.generate_totp_code(secret)
                if factor_case == "disabled":
                    factor.totp_enabled = factor.totp_verified = False
                    db_session.commit()
                elif factor_case == "replaced":
                    replacement_secret = factor_service.generate_totp_secret()
                    while factor_service.verify_totp_code(replacement_secret, code):
                        replacement_secret = factor_service.generate_totp_secret()
                    factor.totp_secret = replacement_secret
                    db_session.commit()
                wrong_code = next(
                    f"{number:06d}"
                    for number in range(100)
                    if not factor_service.verify_totp_code(secret, f"{number:06d}")
                    and (
                        factor_case != "replaced"
                        or not factor_service.verify_totp_code(
                            replacement_secret, f"{number:06d}"
                        )
                    )
                )
                wrong = client.post(
                    "/api/v1/2fa/verify",
                    json={"pending_2fa_token": pending, "totp_code": wrong_code},
                )
                assert wrong.status_code == 200 and not wrong.json()["success"]
                assert not wrong.json().get("access_token")
                if factor_case == "replaced":
                    old = client.post(
                        "/api/v1/2fa/verify",
                        json={"pending_2fa_token": pending, "totp_code": code},
                    )
                    assert old.status_code == 200 and not old.json()["success"]
                    assert not old.json().get("access_token")
                    code = factor_service.generate_totp_code(replacement_secret)
                factor_payload = (
                    {"backup_code": backup_code}
                    if factor_case == "backup"
                    else {"totp_code": code}
                )
                verified = client.post(
                    "/api/v1/2fa/verify",
                    json={"pending_2fa_token": pending, **factor_payload},
                )
                if factor_case == "disabled":
                    assert verified.status_code in (200, 401)
                    assert not verified.json().get("access_token")
                    completed = None
                else:
                    assert verified.status_code == 200 and verified.json()["success"], (
                        verified.text
                    )
                    assert verified.json().get("refresh_token") is None
                    completed = verified.json()
                    replay_factor = client.post(
                        "/api/v1/2fa/verify",
                        json={"pending_2fa_token": pending, **factor_payload},
                    )
                    assert replay_factor.status_code == 401
            if completed is not None:
                claims = jwt.decode(
                    completed["access_token"],
                    settings.SECRET_KEY,
                    algorithms=[settings.ALGORITHM],
                )
                assert claims["sub"] == str(patient.user_id)
                assert (
                    claims["auth_epoch"]
                    == db_session.query(User.auth_epoch)
                    .filter_by(id=patient.user_id)
                    .scalar()
                )
                assert claims["auth_epoch"] >= 7
                assert (
                    claims["scope"] == "patient_portal"
                    and claims["patient_id"] == patient.id
                )
        assert (
            client.post(
                "/api/v1/webauthn/login/discoverable/complete", json=complete_body
            ).status_code
            == 403
        )
    else:
        assert finish.json() == {"detail": {"reason": "auth_finish_failed"}}
    replay = client.post(DISCOVERABLE_FINISH, json=payload)
    assert replay.status_code == 403
    assert replay.json() == {"detail": {"reason": "auth_finish_failed"}}


@pytest.mark.parametrize(
    "quota", ["_DISCOVERABLE_CLIENT_LIMIT", "_DISCOVERABLE_GLOBAL_LIMIT"]
)
def test_discoverable_begin_quota_returns_429_and_bounds_redis(
    client, webauthn_enabled, discoverable_redis, monkeypatch, quota
):
    from app.services import webauthn_service as ws

    monkeypatch.setattr(ws, quota, 1)
    assert client.post(DISCOVERABLE_BEGIN, json={}).status_code == 200
    response = client.post(DISCOVERABLE_BEGIN, json={})
    assert response.status_code == 429, response.text
    keys = list(
        discoverable_redis.scan_iter(
            match=ws._DISCOVERABLE_PREFIX + "discoverable:" + "?" * 43
        )
    )
    assert len(keys) == 1
    assert 0 < discoverable_redis.ttl(keys[0]) <= ws._CEREMONY_TTL


def test_discoverable_login_fails_closed_when_redis_is_unavailable(
    client, webauthn_enabled, monkeypatch
):
    from app.services import webauthn_service as ws

    def unavailable():
        raise ws.WebAuthnStoreUnavailable("offline")

    monkeypatch.setattr(ws, "_discoverable_store", unavailable)
    begin = client.post(DISCOVERABLE_BEGIN, json={})
    finish = client.post(
        DISCOVERABLE_FINISH,
        json={"ceremony_id": "a" * 43, "assertion_response": {"id": "x"}},
    )
    assert begin.status_code == finish.status_code == 503


def test_legacy_begin_saturation_is_uniform_and_bounded(
    client, patient_with_passkey, webauthn_enabled, discoverable_redis, monkeypatch
):
    from app.services import webauthn_service as ws

    monkeypatch.setattr(ws, "_ceremony_store", lambda: discoverable_redis)
    monkeypatch.setattr(ws, "_DISCOVERABLE_GLOBAL_LIMIT", 1)
    assert client.post(BEGIN_PATH, json={"patient_id": 987654321}).status_code == 200
    known = client.post(BEGIN_PATH, json={"patient_id": patient_with_passkey})
    unknown = client.post(BEGIN_PATH, json={"patient_id": 888888})
    assert known.status_code == unknown.status_code == 200
    assert set(known.json()["options"]) == set(unknown.json()["options"])
    keys = list(
        discoverable_redis.scan_iter(
            match=ws._DISCOVERABLE_PREFIX + "login:" + "?" * 43
        )
    )
    assert len(keys) == 1
    for response, patient_id in ((known, patient_with_passkey), (unknown, 888888)):
        finish = client.post(
            FINISH_PATH,
            json={
                "patient_id": patient_id,
                "ceremony_id": response.json()["options"]["ceremony_id"],
                "assertion_response": {"id": "x", "rawId": "x"},
            },
        )
        assert finish.status_code == 403


def test_legacy_begin_redis_eval_failure_is_uniform(
    client, patient_with_passkey, webauthn_enabled, monkeypatch
):
    import redis

    from app.services import webauthn_service as ws

    class BrokenStore:
        def eval(self, *args, **kwargs):
            raise redis.ConnectionError("unavailable")

    monkeypatch.setattr(ws, "_ceremony_store", lambda: BrokenStore())
    known = client.post(BEGIN_PATH, json={"patient_id": patient_with_passkey})
    unknown = client.post(BEGIN_PATH, json={"patient_id": 888888})
    assert known.status_code == unknown.status_code == 503
    assert (
        known.json()
        == unknown.json()
        == {"detail": {"reason": "auth_temporarily_unavailable"}}
    )


def test_registered_random_handle_survives_secret_rotation_and_discoverable_login(
    client,
    db_session,
    patient_with_passkey,
    webauthn_enabled,
    discoverable_redis,
    monkeypatch,
):
    """Register through HTTP and use the same real key/handle for signed login."""
    import hashlib
    import json

    import cbor2
    import jwt
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import ec

    from app.api.deps import create_access_token
    from app.core.config import settings
    from app.models.patient import Patient
    from app.models.user_profile import UserProfile
    from app.services import patient_otp_service as otp
    from app.services import webauthn_service as ws

    patient = db_session.query(Patient).filter_by(id=patient_with_passkey).one()
    phone = "+998000000001"
    db_session.add(
        UserProfile(user_id=patient.user_id, phone=phone, phone_verified=True)
    )
    db_session.commit()

    def step_up():
        otp_service = otp.get_patient_otp_service()
        binding = otp_service.binding_for_phone(db_session, phone)
        record = {
            "version": 1,
            "code_hash": otp._hash_code("123456"),
            "user_id": binding.user_id,
            "auth_epoch": binding.auth_epoch,
        }
        otp_service._get_backend().set(
            f"{otp._NS_LOGIN}:code:{phone}", json.dumps(record), 300
        )
        return {
            "phone": phone,
            "verification_grant": otp_service.verify_login_otp(
                phone, "123456", db=db_session
            )["verification_grant"],
        }

    def headers():
        token = create_access_token(data={"sub": str(patient.user_id)})
        return {"Authorization": f"Bearer {token}"}

    auth = headers()
    begin = client.post("/api/v1/webauthn/register/begin", headers=auth, json=step_up())
    assert begin.status_code == 200, begin.text
    registration = begin.json()["options"]
    user_handle = registration["user"]["id"]
    assert len(ws._decode_b64url(user_handle)) == 32
    assert ws._decode_b64url(user_handle) not in (
        str(patient.id).encode(),
        str(patient.user_id).encode(),
    )
    assert registration["user"]["name"] == "patient"
    assert registration["user"]["displayName"] == "Patient"

    key = ec.generate_private_key(ec.SECP256R1())
    public = key.public_key().public_numbers()
    cose = cbor2.dumps(
        {
            1: 2,
            3: -7,
            -1: 1,
            -2: public.x.to_bytes(32, "big"),
            -3: public.y.to_bytes(32, "big"),
        }
    )
    raw_id = b"SYNTHETIC-registered-discoverable-key"
    encoded_id = ws._b64url(raw_id)
    registration_auth_data = (
        hashlib.sha256(b"clinic.example").digest()
        + b"\x45"
        + bytes(4)
        + bytes(16)
        + len(raw_id).to_bytes(2, "big")
        + raw_id
        + cose
    )
    create_data = json.dumps(
        {
            "type": "webauthn.create",
            "challenge": registration["challenge"],
            "origin": "https://clinic.example",
        },
        separators=(",", ":"),
    ).encode()
    attestation = {
        "id": encoded_id,
        "rawId": encoded_id,
        "type": "public-key",
        "response": {
            "clientDataJSON": ws._b64url(create_data),
            "attestationObject": ws._b64url(
                cbor2.dumps(
                    {"fmt": "none", "attStmt": {}, "authData": registration_auth_data}
                )
            ),
        },
    }
    finished = client.post(
        "/api/v1/webauthn/register/finish",
        headers=auth,
        json={
            "ceremony_id": registration["ceremony_id"],
            "credential_response": attestation,
        },
    )
    assert finished.status_code == 200, finished.text

    monkeypatch.setattr(settings, "SECRET_KEY", "SYNTHETIC-rotated-secret-key")
    after_rotation = client.post(
        "/api/v1/webauthn/register/begin", headers=headers(), json=step_up()
    )
    assert after_rotation.status_code == 200, after_rotation.text
    next_options = after_rotation.json()["options"]
    assert next_options["user"]["id"] == user_handle
    assert encoded_id in [item["id"] for item in next_options["excludeCredentials"]]

    def assert_with_handle(handle):
        response = client.post(DISCOVERABLE_BEGIN, json={})
        assert response.status_code == 200, response.text
        options = response.json()["options"]
        data = json.dumps(
            {
                "type": "webauthn.get",
                "challenge": options["challenge"],
                "origin": "https://clinic.example",
            },
            separators=(",", ":"),
        ).encode()
        auth_data = (
            hashlib.sha256(b"clinic.example").digest()
            + b"\x05"
            + (1).to_bytes(4, "big")
        )
        signature = key.sign(
            auth_data + hashlib.sha256(data).digest(), ec.ECDSA(hashes.SHA256())
        )
        assertion = {
            "id": encoded_id,
            "rawId": encoded_id,
            "type": "public-key",
            "response": {
                "authenticatorData": ws._b64url(auth_data),
                "clientDataJSON": ws._b64url(data),
                "signature": ws._b64url(signature),
                "userHandle": handle,
            },
        }
        payload = {
            "ceremony_id": options["ceremony_id"],
            "assertion_response": assertion,
        }
        return client.post(DISCOVERABLE_FINISH, json=payload)

    bad = assert_with_handle(ws._b64url(b"SYNTHETIC-other-user"))
    assert bad.status_code == 403
    good = assert_with_handle(user_handle)
    assert good.status_code == 200, good.text
    assert "access_token" not in good.json()
    next_options = good.json()["next_options"]
    data = json.dumps(
        {
            "type": "webauthn.get",
            "challenge": next_options["challenge"],
            "origin": "https://clinic.example",
        },
        separators=(",", ":"),
    ).encode()
    auth_data = (
        hashlib.sha256(b"clinic.example").digest() + b"\x05" + (2).to_bytes(4, "big")
    )
    signature = key.sign(
        auth_data + hashlib.sha256(data).digest(), ec.ECDSA(hashes.SHA256())
    )
    assertion = {
        "id": encoded_id,
        "rawId": encoded_id,
        "type": "public-key",
        "response": {
            "authenticatorData": ws._b64url(auth_data),
            "clientDataJSON": ws._b64url(data),
            "signature": ws._b64url(signature),
            "userHandle": user_handle,
        },
    }
    complete = client.post(
        "/api/v1/webauthn/login/discoverable/complete",
        json={
            "ceremony_id": next_options["ceremony_id"],
            "assertion_response": assertion,
        },
    )
    assert complete.status_code == 200, complete.text
    claims = jwt.decode(
        complete.json()["access_token"],
        settings.SECRET_KEY,
        algorithms=[settings.ALGORITHM],
    )
    assert claims["sub"] == str(patient.user_id) and claims["patient_id"] == patient.id
