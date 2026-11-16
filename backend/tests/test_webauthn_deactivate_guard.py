"""Security regressions for authenticated passkey management (PR #4070)."""

from __future__ import annotations

import base64
import json

import pytest

from app.api.deps import create_access_token
from app.models.passkey_credential import PasskeyCredential
from app.models.patient import Patient
from app.models.user import User
from app.models.user_profile import UserProfile
from app.services import patient_otp_service as otp

LIST = "/api/v1/webauthn/credentials/list"
BEGIN = "/api/v1/webauthn/register/begin"
FINISH = "/api/v1/webauthn/register/finish"
DEACTIVATE = "/api/v1/webauthn/credentials/{}/deactivate"


@pytest.fixture
def identities(db_session):
    result = []
    for i in (1, 2):
        user = User(
            username=f"SYNTHETIC-passkey-{i}",
            hashed_password="test-only",
            role="Patient",
            is_active=True,
            is_superuser=False,
        )
        db_session.add(user)
        db_session.flush()
        patient = Patient(
            user_id=user.id, first_name="SYNTHETIC", last_name=f"PATIENT-{i}"
        )
        phone = f"+99800000000{i}"
        db_session.add_all(
            [patient, UserProfile(user_id=user.id, phone=phone, phone_verified=True)]
        )
        db_session.flush()
        result.append((user, patient, phone))
    db_session.commit()
    return result


def _headers(user):
    token = create_access_token(data={"sub": str(user.id)})
    return {"Authorization": f"Bearer {token}"}


def _credential(db, patient, name):
    encoded = base64.urlsafe_b64encode(
        f"SYNTHETIC-{patient.id}-{name}".encode()
    ).decode()
    credential = PasskeyCredential(
        patient_id=patient.id,
        owner_user_id=patient.user_id,
        credential_id=encoded,
        public_key=encoded,
        sign_count=0,
        active=True,
        name=name,
    )
    db.add(credential)
    db.commit()
    return credential


def _step_up(phone, db_session):
    """Exercise the real verification-grant issuer and store without sending SMS."""
    service = otp.get_patient_otp_service()
    code = "123456"
    binding = service.binding_for_phone(db_session, phone)
    record = {
        "version": 1,
        "code_hash": otp._hash_code(code),
        "user_id": binding.user_id if binding else None,
        "auth_epoch": binding.auth_epoch if binding else None,
    }
    service._get_backend().set(f"{otp._NS_LOGIN}:code:{phone}", json.dumps(record), 300)
    grant = service.verify_login_otp(phone, code, db=db_session)["verification_grant"]
    return {"phone": phone, "verification_grant": grant}


def test_list_is_scoped_to_authenticated_patient(client, db_session, identities):
    user, patient, _ = identities[0]
    _, other_patient, _ = identities[1]
    own = _credential(db_session, patient, "own")
    _credential(db_session, other_patient, "other")
    response = client.post(
        LIST, headers=_headers(user), json={"patient_id": other_patient.id}
    )
    assert response.status_code == 200, response.text
    assert [item["id"] for item in response.json()["credentials"]] == [own.id]


def test_unowned_legacy_and_relinked_credentials_are_not_visible_or_manageable(
    client, db_session, identities
):
    user, patient, phone = identities[0]
    other_user, _, _ = identities[1]
    legacy = _credential(db_session, patient, "legacy")
    legacy.owner_user_id = None
    relinked = _credential(db_session, patient, "relinked")
    relinked.owner_user_id = other_user.id
    db_session.commit()
    headers = _headers(user)
    listed = client.post(LIST, headers=headers, json={})
    assert listed.status_code == 200
    assert listed.json()["credentials"] == []
    for credential in (legacy, relinked):
        response = client.post(
            DEACTIVATE.format(credential.id),
            headers=headers,
            json=_step_up(phone, db_session),
        )
        assert response.status_code == 404, response.text
        db_session.refresh(credential)
        assert credential.active is True


def test_last_active_credential_remains_usable(client, db_session, identities):
    user, patient, phone = identities[0]
    credential = _credential(db_session, patient, "last")
    legacy = _credential(db_session, patient, "legacy-not-counted")
    legacy.owner_user_id = None
    db_session.commit()
    response = client.post(
        DEACTIVATE.format(credential.id),
        headers=_headers(user),
        json=_step_up(phone, db_session),
    )
    assert response.status_code == 409, response.text
    assert response.json()["detail"]["reason"] == "last_active_credential"
    db_session.refresh(credential)
    assert credential.active is True


def test_deactivation_consumes_grant_and_preserves_other_key(
    client, db_session, identities
):
    user, patient, phone = identities[0]
    first = _credential(db_session, patient, "first")
    second = _credential(db_session, patient, "second")
    step_up = _step_up(phone, db_session)
    response = client.post(
        DEACTIVATE.format(first.id), headers=_headers(user), json=step_up
    )
    assert response.status_code == 200, response.text
    replay = client.post(
        DEACTIVATE.format(second.id), headers=_headers(user), json=step_up
    )
    assert replay.status_code == 403
    db_session.refresh(first)
    db_session.refresh(second)
    assert first.active is False and second.active is True


def test_foreign_unknown_and_inactive_credentials_return_same_404(
    client, db_session, identities
):
    user, patient, phone = identities[0]
    _, foreign_patient, _ = identities[1]
    _credential(db_session, patient, "spare")
    inactive = _credential(db_session, patient, "inactive")
    inactive.active = False
    db_session.commit()
    foreign = _credential(db_session, foreign_patient, "foreign")
    bodies = []
    for credential_id in (inactive.id, foreign.id, 9999999):
        response = client.post(
            DEACTIVATE.format(credential_id),
            headers=_headers(user),
            json=_step_up(phone, db_session),
        )
        assert response.status_code == 404, response.text
        bodies.append(response.json())
    assert bodies == [{"detail": {"reason": "credential_not_found"}}] * 3
    db_session.refresh(foreign)
    assert foreign.active is True


def test_grant_for_other_patient_is_rejected_and_consumed(
    client, db_session, identities
):
    user, patient, _ = identities[0]
    _, _, other_phone = identities[1]
    first = _credential(db_session, patient, "first")
    _credential(db_session, patient, "second")
    step_up = _step_up(other_phone, db_session)
    response = client.post(
        DEACTIVATE.format(first.id), headers=_headers(user), json=step_up
    )
    assert response.status_code == 403
    assert (
        otp.get_patient_otp_service().consume_grant(step_up["verification_grant"])
        is None
    )
    db_session.refresh(first)
    assert first.active is True


def test_unverified_or_ambiguous_phone_cannot_authorize_mutation(
    client, db_session, identities
):
    user, patient, phone = identities[0]
    other, _, _ = identities[1]
    first = _credential(db_session, patient, "first")
    _credential(db_session, patient, "second")
    profile = db_session.query(UserProfile).filter_by(user_id=other.id).one()
    profile.phone = phone
    db_session.commit()
    response = client.post(
        DEACTIVATE.format(first.id),
        headers=_headers(user),
        json=_step_up(phone, db_session),
    )
    assert response.status_code == 403
    profile.phone_verified = False
    own_profile = db_session.query(UserProfile).filter_by(user_id=user.id).one()
    own_profile.phone_verified = False
    db_session.commit()
    response = client.post(
        DEACTIVATE.format(first.id),
        headers=_headers(user),
        json=_step_up(phone, db_session),
    )
    assert response.status_code == 403
    db_session.refresh(first)
    assert first.active is True


def test_registration_requires_single_use_step_up(
    client, db_session, identities, monkeypatch
):
    from app.services import webauthn_service as ws

    user, _, phone = identities[0]
    monkeypatch.setattr(ws, "WEBAUTHN_AVAILABLE", True)
    monkeypatch.setattr(
        ws,
        "begin_passkey_registration",
        lambda *a, **k: (k["step_up"](), {"ceremony_id": "synthetic"})[1],
    )
    headers = _headers(user)
    assert client.post(BEGIN, headers=headers, json={}).status_code == 400
    step_up = _step_up(phone, db_session)
    response = client.post(BEGIN, headers=headers, json=step_up)
    assert response.status_code == 200, response.text
    assert client.post(BEGIN, headers=headers, json=step_up).status_code == 403


def test_nonpatient_bearer_cannot_manage_passkeys(client, db_session, identities):
    user, _, phone = identities[0]
    user.role = "Doctor"
    db_session.commit()
    for path, payload, expected in [
        (LIST, {}, 401),
        (DEACTIVATE.format(1), _step_up(phone, db_session), 403),
    ]:
        response = client.post(path, headers=_headers(user), json=payload)
        assert response.status_code == expected, response.text


def test_step_up_store_failure_is_unavailable_and_does_not_mutate(
    client, db_session, identities, monkeypatch
):
    user, patient, phone = identities[0]
    first = _credential(db_session, patient, "first")
    _credential(db_session, patient, "second")
    service = otp.get_patient_otp_service()

    def fail_store(_grant):
        raise otp.PatientOtpError(503, "store offline")

    monkeypatch.setattr(service, "consume_grant", fail_store)
    response = client.post(
        DEACTIVATE.format(first.id),
        headers=_headers(user),
        json={"phone": phone, "verification_grant": "x" * 32},
    )
    assert response.status_code == 503
    assert response.json() == {"detail": {"reason": "step_up_unavailable"}}
    db_session.refresh(first)
    assert first.active is True


def test_management_openapi_documents_security_bodies_and_errors(client):
    schema = client.get("/openapi.json").json()
    paths = schema["paths"]
    cases = {
        BEGIN: ({"phone", "verification_grant"}, {"400", "401", "403", "503"}),
        FINISH: ({"ceremony_id", "credential_response"}, {"400", "401", "403", "503"}),
        LIST: (set(), {"401", "403"}),
        "/api/v1/webauthn/credentials/{credential_id}/deactivate": (
            {"phone", "verification_grant"},
            {"400", "401", "403", "404", "409", "503"},
        ),
    }
    for path, (required_fields, statuses) in cases.items():
        operation = paths[path]["post"]
        assert operation.get("security"), path
        assert statuses <= operation["responses"].keys(), path
        if not required_fields:
            continue
        request_body = operation["requestBody"]
        assert request_body.get("required") is True, path
        request_schema = request_body["content"]["application/json"]["schema"]
        if "$ref" in request_schema:
            request_schema = schema["components"]["schemas"][
                request_schema["$ref"].rsplit("/", 1)[-1]
            ]
        assert required_fields <= set(request_schema.get("required", [])), path
        properties = request_schema["properties"]
        for field in required_fields - {"credential_response"}:
            assert properties[field].get("type") == "string", (path, field)
        if "credential_response" in required_fields:
            assert properties["credential_response"].get("type") == "object"


@pytest.mark.parametrize("operation", ["list", "deactivate"])
def test_scoped_patient_session_rejects_relink_between_dependency_and_handler(
    client, db_session, identities, operation
):
    from app.api.deps import get_current_user
    from app.main import app

    user, old_patient, phone = identities[0]
    _, new_patient, _ = identities[1]
    key = _credential(db_session, new_patient, "relink-target")
    spare = _credential(db_session, new_patient, "relink-spare")
    key.owner_user_id = spare.owner_user_id = user.id
    db_session.commit()
    token = create_access_token(
        data={
            "sub": str(user.id),
            "scope": "patient_portal",
            "patient_id": old_patient.id,
        }
    )

    async def authenticated_then_relinked():
        principal = await get_current_user(token=token, db=db_session)
        old_patient.user_id = None
        new_patient.user_id = None
        db_session.flush()
        new_patient.user_id = user.id
        db_session.commit()
        return principal

    app.dependency_overrides[get_current_user] = authenticated_then_relinked
    headers = {"Authorization": f"Bearer {token}"}
    if operation == "list":
        response = client.post(LIST, headers=headers, json={})
    else:
        response = client.post(
            DEACTIVATE.format(key.id), headers=headers, json=_step_up(phone, db_session)
        )
    assert response.status_code in (401, 403), response.text
    db_session.refresh(key)
    assert key.active is True


def test_unscoped_patient_session_uses_current_relinked_card(
    client, db_session, identities
):
    user, old_patient, phone = identities[0]
    _, new_patient, _ = identities[1]
    old_patient.user_id = None
    new_patient.user_id = None
    db_session.flush()
    new_patient.user_id = user.id
    db_session.commit()
    key = _credential(db_session, new_patient, "current")
    _credential(db_session, new_patient, "spare")
    headers = _headers(user)
    listed = client.post(LIST, headers=headers, json={})
    assert listed.status_code == 200, listed.text
    assert key.id in [item["id"] for item in listed.json()["credentials"]]
    response = client.post(
        DEACTIVATE.format(key.id), headers=headers, json=_step_up(phone, db_session)
    )
    assert response.status_code == 200, response.text
    db_session.refresh(key)
    assert key.active is False
