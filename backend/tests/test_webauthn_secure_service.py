"""Security contracts for the WebAuthn challenge and patient session."""

from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace

import jwt
import pytest

from app.core.config import settings
from app.models.passkey_credential import PasskeyCredential
from app.models.patient import Patient
from app.models.user import User
from app.services import webauthn_service as ws


@pytest.fixture
def webauthn(monkeypatch):
    monkeypatch.setattr(settings, "FRONTEND_URL", "https://clinic.example")
    monkeypatch.setattr(settings, "TESTING", True)
    monkeypatch.setattr(ws, "WEBAUTHN_AVAILABLE", True)
    monkeypatch.setattr(
        ws,
        "generate_authentication_options",
        lambda **_: SimpleNamespace(challenge=b"\xff\x00\x80challenge"),
        raising=False,
    )
    with ws._test_ceremonies_lock:
        ws._test_ceremonies.clear()
    yield
    with ws._test_ceremonies_lock:
        ws._test_ceremonies.clear()


@pytest.fixture
def linked_patient(db_session, admin_user):
    user = User(
        username="passkey-patient",
        hashed_password="synthetic",
        role="Patient",
        is_active=True,
        is_superuser=False,
    )
    db_session.add(user)
    db_session.flush()
    patient = Patient(
        id=admin_user.id,
        user_id=user.id,
        first_name="Synthetic",
        last_name="Patient",
    )
    db_session.add(patient)
    db_session.flush()
    db_session.add_all(
        [
            PasskeyCredential(
                patient_id=patient.id,
                owner_user_id=user.id,
                credential_id="Zmlyc3Q=",
                public_key="cHVibGljMQ==",
                sign_count=0,
                active=True,
            ),
            PasskeyCredential(
                patient_id=patient.id,
                owner_user_id=user.id,
                credential_id="c2Vjb25k",
                public_key="cHVibGljMg==",
                sign_count=0,
                active=True,
            ),
        ]
    )
    db_session.commit()
    assert patient.id != user.id
    return patient, user, admin_user


def test_binary_challenge_roundtrip_and_isolated_ceremonies(
    db_session, linked_patient, webauthn
):
    patient, _, _ = linked_patient
    a = ws.begin_passkey_authentication(db_session, patient.id)
    b = ws.begin_passkey_authentication(db_session, patient.id)
    assert a["ceremony_id"] != b["ceremony_id"]
    assert ws._decode_b64url(a["challenge"]) == b"\xff\x00\x80challenge"
    assert (
        ws._consume_ceremony(a["ceremony_id"], patient.id) == b"\xff\x00\x80challenge"
    )
    with pytest.raises(ValueError):
        ws._consume_ceremony(a["ceremony_id"], patient.id)
    assert (
        ws._consume_ceremony(b["ceremony_id"], patient.id) == b"\xff\x00\x80challenge"
    )


def test_concurrent_consumption_is_single_use(db_session, linked_patient, webauthn):
    patient, _, _ = linked_patient
    options = ws.begin_passkey_authentication(db_session, patient.id)

    def consume(_):
        try:
            return ws._consume_ceremony(options["ceremony_id"], patient.id)
        except ValueError:
            return None

    with ThreadPoolExecutor(max_workers=8) as executor:
        results = list(executor.map(consume, range(8)))
    assert results.count(b"\xff\x00\x80challenge") == 1
    assert results.count(None) == 7


def test_finish_selects_asserted_key_and_issues_linked_patient_token(
    db_session, linked_patient, webauthn, monkeypatch
):
    patient, user, admin = linked_patient
    options = ws.begin_passkey_authentication(db_session, patient.id)
    captured = {}

    def verify(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(new_sign_count=1)

    monkeypatch.setattr(ws, "verify_authentication_response", verify, raising=False)
    result = ws.finish_passkey_authentication(
        db_session,
        patient.id,
        assertion_response={"id": "c2Vjb25k", "rawId": "c2Vjb25k"},
        ceremony_id=options["ceremony_id"],
    )
    assert captured["expected_challenge"] == b"\xff\x00\x80challenge"
    assert captured["credential_public_key"] == b"public2"
    assert captured["require_user_verification"] is True
    payload = jwt.decode(
        result["access_token"], settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
    )
    assert payload["sub"] == str(user.id)
    assert payload["sub"] != str(admin.id)
    assert payload["scope"] == "patient_portal"
    assert payload["patient_id"] == patient.id
    assert result["user"]["role"] == "Patient"
    assert "refresh_token" not in result


def test_assertion_id_must_match_raw_id_and_patient(
    db_session, linked_patient, webauthn, monkeypatch
):
    patient, _, _ = linked_patient
    verifier = []
    monkeypatch.setattr(
        ws,
        "verify_authentication_response",
        lambda **kwargs: verifier.append(kwargs),
        raising=False,
    )
    for assertion in [
        {"id": "Zmlyc3Q", "rawId": "c2Vjb25k"},
        {"id": "dW5rbm93bg", "rawId": "dW5rbm93bg"},
    ]:
        options = ws.begin_passkey_authentication(db_session, patient.id)
        with pytest.raises(ValueError):
            ws.finish_passkey_authentication(
                db_session,
                patient.id,
                assertion_response=assertion,
                ceremony_id=options["ceremony_id"],
            )
    assert not verifier


@pytest.mark.parametrize(
    "invalid", ["staff", "inactive", "superuser", "unlinked", "deleted"]
)
def test_no_session_for_unqualified_linked_user(
    db_session, linked_patient, webauthn, monkeypatch, invalid
):
    patient, user, _ = linked_patient
    if invalid == "staff":
        user.role = "Admin"
    elif invalid == "inactive":
        user.is_active = False
    elif invalid == "superuser":
        user.is_superuser = True
    elif invalid == "unlinked":
        patient.user_id = None
    else:
        patient.is_deleted = True
    db_session.commit()
    monkeypatch.setattr(
        ws,
        "verify_authentication_response",
        lambda **_: SimpleNamespace(new_sign_count=1),
        raising=False,
    )
    options = ws.begin_passkey_authentication(db_session, patient.id)
    with pytest.raises(ValueError):
        ws.finish_passkey_authentication(
            db_session,
            patient.id,
            assertion_response={"id": "Zmlyc3Q"},
            ceremony_id=options["ceremony_id"],
        )


def test_wrong_patient_or_unknown_ceremony_fails(db_session, linked_patient, webauthn):
    patient, _, _ = linked_patient
    options = ws.begin_passkey_authentication(db_session, patient.id)
    with pytest.raises(ValueError):
        ws._consume_ceremony(options["ceremony_id"], patient.id + 1)
    with pytest.raises(ValueError):
        ws._consume_ceremony(options["ceremony_id"], patient.id)
    dummy = ws.begin_passkey_authentication(db_session, 123456789)
    with pytest.raises(ValueError):
        ws.finish_passkey_authentication(
            db_session,
            123456789,
            assertion_response={"id": "Zmlyc3Q"},
            ceremony_id=dummy["ceremony_id"],
        )


def test_expired_ceremony_is_rejected(
    db_session, linked_patient, webauthn, monkeypatch
):
    patient, _, _ = linked_patient
    clock = [100.0]
    monkeypatch.setattr(ws.time, "monotonic", lambda: clock[0])
    options = ws.begin_passkey_authentication(db_session, patient.id)
    clock[0] += 301
    with pytest.raises(ValueError):
        ws._consume_ceremony(options["ceremony_id"], patient.id)


def test_redis_lua_failure_fails_closed(webauthn):
    class RedisDouble:
        def eval(self, *args):
            raise ConnectionError("synthetic Redis failure")

    with pytest.raises(ws.WebAuthnStoreUnavailable):
        ws._store_ceremony(RedisDouble(), "b" * 43, 7, b"secret")


def test_production_redis_failure_does_not_fallback(webauthn, monkeypatch):
    import redis

    def fail(*args, **kwargs):
        raise redis.ConnectionError("unavailable")

    monkeypatch.setattr(settings, "TESTING", False)
    monkeypatch.setattr(ws, "_redis_ceremony_clients", {})
    monkeypatch.setattr(redis.Redis, "from_url", fail)
    with pytest.raises(ws.WebAuthnStoreUnavailable):
        ws._ceremony_store()


@pytest.mark.parametrize("has_totp", [False, True])
@pytest.mark.parametrize(
    "origin, should_pass",
    [("https://clinic.example", True), ("https://evil.example", False)],
)
def test_real_webauthn_signed_assertion_checks_origin(
    client,
    db_session,
    linked_patient,
    webauthn,
    monkeypatch,
    origin,
    should_pass,
    has_totp,
):
    """Use a real EC signature and the optional library's verifier."""
    import hashlib
    import json

    import cbor2
    import webauthn as real
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import ec
    from webauthn.helpers.exceptions import InvalidAuthenticationResponse

    patient, user, _ = linked_patient
    user.auth_epoch = 9
    if has_totp:
        from app.models.two_factor_auth import TwoFactorAuth
        from app.services.two_factor_service import get_two_factor_service

        db_session.add(
            TwoFactorAuth(
                user_id=user.id,
                totp_enabled=True,
                totp_verified=True,
                totp_secret=get_two_factor_service().generate_totp_secret(),
            )
        )
    credential = (
        db_session.query(PasskeyCredential)
        .filter_by(patient_id=patient.id, credential_id="Zmlyc3Q=")
        .one()
    )
    key = ec.generate_private_key(ec.SECP256R1())
    public = key.public_key().public_numbers()
    cose = {
        1: 2,
        3: -7,
        -1: 1,
        -2: public.x.to_bytes(32, "big"),
        -3: public.y.to_bytes(32, "big"),
    }
    credential.public_key = ws._b64url(cbor2.dumps(cose))
    # Legacy database encoding uses padded URL-safe base64.
    credential.public_key += "=" * (-len(credential.public_key) % 4)
    db_session.commit()
    monkeypatch.setattr(
        ws, "generate_authentication_options", real.generate_authentication_options
    )
    monkeypatch.setattr(
        ws,
        "verify_authentication_response",
        real.verify_authentication_response,
        raising=False,
    )

    options = ws.begin_passkey_authentication(db_session, patient.id)
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
    assertion = {
        "id": "Zmlyc3Q",
        "rawId": "Zmlyc3Q",
        "type": "public-key",
        "response": {
            "authenticatorData": ws._b64url(authenticator_data),
            "clientDataJSON": ws._b64url(client_data),
            "signature": ws._b64url(signature),
            "userHandle": None,
        },
    }
    if should_pass:
        response = client.post(
            "/api/v1/webauthn/login/finish",
            json={
                "patient_id": patient.id,
                "assertion_response": assertion,
                "ceremony_id": options["ceremony_id"],
            },
        )
        assert response.status_code == 200, response.text
        assert response.headers["cache-control"] == "no-store"
        result = response.json()
        assert result["user"]["id"] == user.id
        if has_totp:
            assert result["requires_2fa"] is True
            assert result["two_factor_method"] == "totp"
            assert result["pending_2fa_token"]
            assert "access_token" not in result and "refresh_token" not in result
        else:
            claims = jwt.decode(
                result["access_token"],
                settings.SECRET_KEY,
                algorithms=[settings.ALGORITHM],
            )
            assert claims["sub"] == str(user.id) and claims["auth_epoch"] >= 9
    else:
        with pytest.raises(InvalidAuthenticationResponse):
            ws.finish_passkey_authentication(
                db_session,
                patient.id,
                assertion_response=assertion,
                ceremony_id=options["ceremony_id"],
            )


def test_identified_challenge_issued_before_epoch_revocation_cannot_login(
    db_session, linked_patient, webauthn, monkeypatch
):
    patient, user, _ = linked_patient
    monkeypatch.setattr(
        ws,
        "verify_authentication_response",
        lambda **_: SimpleNamespace(new_sign_count=1),
        raising=False,
    )
    challenge = ws.begin_passkey_authentication(db_session, patient.id)
    user.auth_epoch += 1
    db_session.commit()
    with pytest.raises(ValueError):
        ws.finish_passkey_authentication(
            db_session,
            patient.id,
            assertion_response={"id": "c2Vjb25k", "rawId": "c2Vjb25k"},
            ceremony_id=challenge["ceremony_id"],
        )


def test_inconsistent_second_factor_never_bypasses_passkey_login(
    db_session, linked_patient, webauthn, monkeypatch
):
    from app.models.two_factor_auth import TwoFactorAuth

    patient, user, _ = linked_patient
    db_session.add(
        TwoFactorAuth(user_id=user.id, totp_enabled=True, totp_verified=False)
    )
    db_session.commit()
    monkeypatch.setattr(
        ws,
        "verify_authentication_response",
        lambda **_: SimpleNamespace(new_sign_count=1),
        raising=False,
    )
    options = ws.begin_passkey_authentication(db_session, patient.id)
    with pytest.raises(ValueError):
        ws.finish_passkey_authentication(
            db_session,
            patient.id,
            ceremony_id=options["ceremony_id"],
            assertion_response={"id": "c2Vjb25k", "rawId": "c2Vjb25k"},
        )
    key = (
        db_session.query(PasskeyCredential)
        .filter_by(patient_id=patient.id, credential_id="c2Vjb25k")
        .one()
    )
    assert key.sign_count == 0
