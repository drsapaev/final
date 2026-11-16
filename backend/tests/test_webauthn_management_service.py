"""Registration and management security with a real WebAuthn verifier."""

import hashlib
import json

import cbor2
import pytest
from cryptography.hazmat.primitives.asymmetric import ec
from webauthn.helpers.exceptions import InvalidRegistrationResponse

from app.core.config import settings
from app.models.patient import Patient
from app.models.user import User
from app.services import webauthn_service as ws


@pytest.fixture
def identity(db_session, monkeypatch):
    monkeypatch.setattr(settings, "TESTING", True)
    monkeypatch.setattr(settings, "FRONTEND_URL", "https://clinic.example")
    user = User(
        username="synthetic-management",
        hashed_password="synthetic",
        role="Patient",
        is_active=True,
        is_superuser=False,
    )
    db_session.add(user)
    db_session.flush()
    patient = Patient(user_id=user.id, first_name="Synthetic", last_name="Patient")
    db_session.add(patient)
    db_session.commit()
    return patient.id, user.id


def response(options, *, origin="https://clinic.example", uv=True):
    key = ec.generate_private_key(ec.SECP256R1()).public_key().public_numbers()
    cose = cbor2.dumps(
        {
            1: 2,
            3: -7,
            -1: 1,
            -2: key.x.to_bytes(32, "big"),
            -3: key.y.to_bytes(32, "big"),
        }
    )
    credential_id = b"synthetic-credential-\xff"
    auth_data = (
        hashlib.sha256(b"clinic.example").digest()
        + bytes([0x41 | (0x04 if uv else 0)])
        + bytes(4)
        + bytes(16)
        + len(credential_id).to_bytes(2, "big")
        + credential_id
        + cose
    )
    client = json.dumps(
        {"type": "webauthn.create", "challenge": options["challenge"], "origin": origin}
    ).encode()
    return {
        "id": ws._b64url(credential_id),
        "rawId": ws._b64url(credential_id),
        "type": "public-key",
        "response": {
            "clientDataJSON": ws._b64url(client),
            "attestationObject": ws._b64url(
                cbor2.dumps({"fmt": "none", "attStmt": {}, "authData": auth_data})
            ),
        },
    }


def begin(db, ids):
    return ws.begin_passkey_registration(
        db, *ids, "synthetic-session", rp_name="Synthetic Clinic"
    )


def finish(db, ids, options, credential):
    return ws.finish_passkey_registration(
        db,
        *ids,
        "synthetic-session",
        ceremony_id=options["ceremony_id"],
        credential_response=credential,
    )


def test_real_registration_and_single_use(db_session, identity, monkeypatch):
    options = begin(db_session, identity)
    assert len(ws._decode_b64url(options["user"]["id"])) == 32
    assert options["user"]["name"] == "patient"
    assert options["user"]["displayName"] == "Patient"
    assert options["authenticatorSelection"]["userVerification"] == "required"
    assert options["authenticatorSelection"]["residentKey"] == "required"
    credential = finish(db_session, identity, options, response(options))
    assert credential.credential_id == "c3ludGhldGljLWNyZWRlbnRpYWwt_w=="
    monkeypatch.setattr(settings, "SECRET_KEY", "SYNTHETIC-rotated-secret-key")
    again = begin(db_session, identity)
    assert again["user"]["id"] == options["user"]["id"]
    assert [item["id"] for item in again["excludeCredentials"]] == [
        ws._b64url(b"synthetic-credential-\xff")
    ]
    with pytest.raises(ValueError):
        finish(db_session, identity, options, response(options))


@pytest.mark.parametrize("kwargs", [{"origin": "https://evil.example"}, {"uv": False}])
def test_real_verifier_rejects_origin_and_missing_uv(db_session, identity, kwargs):
    options = begin(db_session, identity)
    with pytest.raises(InvalidRegistrationResponse):
        finish(db_session, identity, options, response(options, **kwargs))
    with pytest.raises(ValueError):
        finish(db_session, identity, options, response(options))


def test_ceremony_binding_and_separation(db_session, identity):
    a, b = begin(db_session, identity), begin(db_session, identity)
    assert a["ceremony_id"] != b["ceremony_id"]
    with pytest.raises(ValueError):
        ws._consume_ceremony(a["ceremony_id"], identity[0])
    with pytest.raises(ValueError):
        ws._consume_registration_ceremony(a["ceremony_id"], *identity, "other-session")
    with pytest.raises(ValueError):
        ws._consume_registration_ceremony(
            a["ceremony_id"], *identity, "synthetic-session"
        )
    assert ws._consume_registration_ceremony(
        b["ceremony_id"], *identity, "synthetic-session"
    ) == ws._decode_b64url(b["challenge"])


@pytest.mark.parametrize(
    "change", ["inactive", "superuser", "role", "relinked", "deleted"]
)
def test_live_identity_rechecked_after_begin(db_session, identity, change):
    options = begin(db_session, identity)
    user = db_session.get(User, identity[1])
    patient = db_session.get(Patient, identity[0])
    if change == "inactive":
        user.is_active = False
    elif change == "superuser":
        user.is_superuser = True
    elif change == "role":
        user.role = "Admin"
    elif change == "relinked":
        patient.user_id = None
    else:
        patient.is_deleted = True
    db_session.commit()
    with pytest.raises(ValueError, match="identity unavailable"):
        finish(db_session, identity, options, response(options))


def test_registration_begin_rechecks_identity_before_exposing_keys(
    db_session, identity
):
    options = begin(db_session, identity)
    finish(db_session, identity, options, response(options))
    patient = db_session.get(Patient, identity[0])
    patient.user_id = None
    db_session.commit()
    with pytest.raises(ValueError, match="identity unavailable"):
        begin(db_session, identity)


def test_relink_and_legacy_credentials_fail_closed(db_session, identity):
    from app.models.passkey_credential import PasskeyCredential

    options = begin(db_session, identity)
    old_key = finish(db_session, identity, options, response(options))
    new_user = User(
        username="synthetic-new-owner",
        hashed_password="synthetic",
        role="Patient",
        is_active=True,
        is_superuser=False,
    )
    db_session.add(new_user)
    db_session.flush()
    legacy = PasskeyCredential(
        patient_id=identity[0],
        owner_user_id=None,
        credential_id="bGVnYWN5",
        public_key="cHVibGlj",
        active=True,
    )
    current = PasskeyCredential(
        patient_id=identity[0],
        owner_user_id=new_user.id,
        credential_id="bmV3",
        public_key="cHVibGlj",
        active=True,
    )
    db_session.add_all([legacy, current])
    patient = db_session.get(Patient, identity[0])
    patient.user_id = new_user.id
    db_session.commit()
    new_user_id = new_user.id
    old_id, legacy_id, current_id = old_key.id, legacy.id, current.id
    assert [
        key.id
        for key in ws.list_patient_passkeys(
            db_session, identity[0], user_id=new_user_id
        )
    ] == [current_id]
    assert not ws.deactivate_passkey(
        db_session, identity[0], old_id, user_id=new_user_id
    )
    assert not ws.deactivate_passkey(
        db_session, identity[0], legacy_id, user_id=new_user_id
    )
    with pytest.raises(ValueError, match="last_active_credential"):
        ws.deactivate_passkey(db_session, identity[0], current_id, user_id=new_user_id)
    for key in ("c3ludGhldGljLWNyZWRlbnRpYWwt_w", "bGVnYWN5"):
        ceremony_id = ws.secrets.token_urlsafe(32)
        ws._store_ceremony(None, ceremony_id, identity[0], b"synthetic-challenge")
        with pytest.raises(ValueError, match="No active passkey"):
            ws.finish_passkey_authentication(
                db_session,
                identity[0],
                ceremony_id=ceremony_id,
                assertion_response={"id": key},
            )
