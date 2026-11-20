"""HTTP boundaries for account-bound phone verification (synthetic data)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from app.api.deps import create_access_token
from app.models.authentication import PasswordResetToken, RefreshToken, UserSession
from app.models.user import User
from app.models.user_profile import UserProfile

OLD_PHONE = "+998000000001"
NEW_PHONE = "+998000000002"
SYNTHETIC_CODE = "012345"


class FakePhoneService:
    """Model the owner-aware contract; actual store atomicity is tested separately."""

    def __init__(self):
        self.records = {}

    async def send_verification_code(self, *, phone, purpose, owner_binding, **kwargs):
        self.records[(phone, purpose)] = owner_binding
        return {"success": True, "message": "sent", "expires_in_minutes": 5, "expires_in_seconds": 299}

    def _visible(self, phone, purpose, actor_id, actor_epoch, actor_jti, allow_admin):
        key = (phone, purpose)
        if key not in self.records:
            return False
        owner = self.records[key]
        return owner == (actor_id, actor_epoch, actor_jti) or (owner is None and allow_admin)

    def verify_code(self, phone, code, purpose, actor_id, actor_epoch, actor_jti, allow_admin):
        if not self._visible(phone, purpose, actor_id, actor_epoch, actor_jti, allow_admin):
            return {"success": False, "error": "missing", "error_code": "CODE_NOT_FOUND"}
        if code != SYNTHETIC_CODE:
            return {"success": False, "error": "invalid", "error_code": "INVALID_CODE"}
        del self.records[(phone, purpose)]
        return {"success": True, "message": "verified", "phone": phone, "verified_at": "synthetic"}

    def get_verification_status(self, phone, purpose, actor_id, actor_epoch, actor_jti, allow_admin):
        return {"exists": self._visible(phone, purpose, actor_id, actor_epoch, actor_jti, allow_admin), "verified": False}

    def cancel_verification(self, phone, purpose, actor_id, actor_epoch, actor_jti, allow_admin):
        if not self._visible(phone, purpose, actor_id, actor_epoch, actor_jti, allow_admin):
            return False
        del self.records[(phone, purpose)]
        return True


@pytest.fixture
def phone_service(monkeypatch):
    from app.api.v1.endpoints import phone_verification

    service = FakePhoneService()
    monkeypatch.setattr(phone_verification, "get_phone_verification_service", lambda: service)
    return service


@pytest.fixture
def patient(db_session):
    suffix = uuid4().hex
    user = User(username="SYNTHETIC_" + suffix, role="Patient", is_active=True,
                is_superuser=False, hashed_password="unused-synthetic")
    db_session.add(user)
    db_session.flush()
    profile = UserProfile(user_id=user.id, phone=OLD_PHONE, phone_verified=True)
    expires = datetime.now(UTC) + timedelta(hours=1)
    session = UserSession(user_id=user.id, refresh_token=uuid4().hex, expires_at=expires, revoked=False)
    refresh = RefreshToken(user_id=user.id, token=uuid4().hex, jti=uuid4().hex, expires_at=expires, revoked=False)
    reset = PasswordResetToken(user_id=user.id, token=uuid4().hex, expires_at=expires, used=False)
    db_session.add_all([profile, session, refresh, reset])
    db_session.commit()
    user_id = user.id
    token = create_access_token({"sub": str(user_id), "auth_epoch": user.auth_epoch})
    return {"id": user_id, "headers": {"Authorization": f"Bearer {token}"},
            "session": session.id, "refresh": refresh.id, "reset": reset.id}


def _send(client, patient, phone=NEW_PHONE, purpose="phone_change"):
    return client.post("/api/v1/phone-verification/send-code", headers=patient["headers"],
                       json={"phone": phone, "purpose": purpose})


def _state(db, patient):
    db.expire_all()
    return (db.query(User).filter_by(id=patient["id"]).one(),
            db.query(UserProfile).filter_by(user_id=patient["id"]).one(),
            db.get(UserSession, patient["session"]), db.get(RefreshToken, patient["refresh"]),
            db.get(PasswordResetToken, patient["reset"]))


def test_self_send_limits_purpose_and_rejects_custom_text(client, patient, phone_service):
    for purpose in ("password_reset", "registration", "unknown"):
        response = _send(client, patient, purpose=purpose)
        assert response.status_code == 422
    response = client.post("/api/v1/phone-verification/send-code", headers=patient["headers"],
                           json={"phone": NEW_PHONE, "custom_message": "synthetic"})
    assert response.status_code == 400
    assert not phone_service.records


def test_update_phone_is_verified_and_revokes_old_sessions(client, db_session, patient, phone_service):
    assert _send(client, patient).status_code == 200
    response = client.put("/api/v1/phone-verification/update-phone", headers=patient["headers"],
                          json={"new_phone": NEW_PHONE, "verification_code": SYNTHETIC_CODE})
    assert response.status_code == 200, response.text
    assert response.json()["sessions_revoked"] is True
    assert response.headers["cache-control"] == "no-store"
    user, profile, session, refresh, reset = _state(db_session, patient)
    assert user.auth_epoch == 1 and profile.phone == NEW_PHONE and profile.phone_verified
    assert session.revoked and refresh.revoked and reset.used
    assert (NEW_PHONE, "phone_change") not in phone_service.records


def test_same_phone_verification_keeps_session(client, db_session, patient, phone_service):
    assert _send(client, patient, phone=OLD_PHONE).status_code == 200
    response = client.put("/api/v1/phone-verification/update-phone", headers=patient["headers"],
                          json={"new_phone": OLD_PHONE, "verification_code": SYNTHETIC_CODE})
    assert response.status_code == 200, response.text
    assert response.json()["sessions_revoked"] is False
    user, profile, session, refresh, reset = _state(db_session, patient)
    assert user.auth_epoch == 0 and profile.phone == OLD_PHONE and profile.phone_verified
    assert not session.revoked and not refresh.revoked and not reset.used


def test_unbound_and_foreign_codes_are_not_visible_or_consumed(client, db_session, patient, phone_service):
    other = User(username="SYNTHETIC_" + uuid4().hex, role="Doctor", is_active=True,
                 is_superuser=False, hashed_password="unused-synthetic")
    db_session.add(other)
    db_session.commit()
    other_token = create_access_token({"sub": str(other.id), "auth_epoch": other.auth_epoch})
    headers = {"Authorization": f"Bearer {other_token}"}
    assert _send(client, patient).status_code == 200
    payload = {"phone": NEW_PHONE, "purpose": "phone_change"}
    assert client.post("/api/v1/phone-verification/status", headers=headers, json=payload).json() == {"exists": False, "verified": False}
    assert client.post("/api/v1/phone-verification/cancel", headers=headers, json=payload).status_code == 404
    assert client.post("/api/v1/phone-verification/verify-code", headers=headers,
                       json={**payload, "code": SYNTHETIC_CODE}).status_code == 404
    assert client.put("/api/v1/phone-verification/update-phone", headers=headers,
                      json={"new_phone": NEW_PHONE, "verification_code": SYNTHETIC_CODE}).status_code == 404
    assert (NEW_PHONE, "phone_change") in phone_service.records
    phone_service.records[(NEW_PHONE, "phone_change")] = None
    assert client.post("/api/v1/phone-verification/status", headers=headers, json=payload).json() == {"exists": False, "verified": False}
    assert client.post("/api/v1/phone-verification/cancel", headers=headers, json=payload).status_code == 404


def test_phone_is_never_required_in_url(client, patient, phone_service):
    assert _send(client, patient).status_code == 200
    payload = {"phone": NEW_PHONE, "purpose": "phone_change"}
    status = client.post("/api/v1/phone-verification/status", headers=patient["headers"], json=payload)
    assert status.status_code == 200 and status.json()["exists"] is True
    assert status.headers["cache-control"] == "no-store"
    assert client.get("/api/v1/phone-verification/status", headers=patient["headers"]).status_code == 405
    assert client.delete("/api/v1/phone-verification/cancel", headers=patient["headers"]).status_code == 405
    assert client.post("/api/v1/phone-verification/cancel", headers=patient["headers"], json=payload).status_code == 200


def test_same_user_different_session_cannot_consume_code(client, db_session, patient, phone_service):
    assert _send(client, patient).status_code == 200
    other_token = create_access_token({"sub": str(patient["id"]), "auth_epoch": 0})
    response = client.put("/api/v1/phone-verification/update-phone",
                          headers={"Authorization": f"Bearer {other_token}"},
                          json={"new_phone": NEW_PHONE, "verification_code": SYNTHETIC_CODE})
    assert response.status_code == 404
    assert (NEW_PHONE, "phone_change") in phone_service.records
    user, profile, session, refresh, reset = _state(db_session, patient)
    assert user.auth_epoch == 0 and profile.phone == OLD_PHONE
    assert not session.revoked and not refresh.revoked and not reset.used


@pytest.mark.parametrize("legacy_phone", [NEW_PHONE, "+998 (00) 000-00-02", "+٩٩٨ (00) 000-00-02"])
def test_verified_duplicate_rejected_after_proof_without_phone_oracle(client, db_session, patient, phone_service, legacy_phone):
    other = User(username="SYNTHETIC_" + uuid4().hex, role="Doctor", is_active=True,
                 is_superuser=False, hashed_password="unused-synthetic")
    db_session.add(other)
    db_session.flush()
    db_session.add(UserProfile(user_id=other.id, phone=legacy_phone, phone_verified=True))
    db_session.commit()
    assert _send(client, patient).status_code == 200
    invalid = client.put("/api/v1/phone-verification/update-phone", headers=patient["headers"],
                         json={"new_phone": NEW_PHONE, "verification_code": "999999"})
    assert invalid.status_code == 400
    assert (NEW_PHONE, "phone_change") in phone_service.records
    response = client.put("/api/v1/phone-verification/update-phone", headers=patient["headers"],
                          json={"new_phone": NEW_PHONE, "verification_code": SYNTHETIC_CODE})
    assert response.status_code == 409
    assert (NEW_PHONE, "phone_change") not in phone_service.records
    user, profile, session, refresh, reset = _state(db_session, patient)
    assert user.auth_epoch == 0 and profile.phone == OLD_PHONE
    assert not session.revoked and not refresh.revoked and not reset.used


@pytest.mark.parametrize("bad_phone", ["+٩٩٨000000002", "+998000000002x", "++998000000002"])
def test_non_ascii_or_malformed_phone_is_rejected(client, patient, phone_service, bad_phone):
    assert _send(client, patient, phone=bad_phone).status_code == 422
    assert not phone_service.records


@pytest.mark.parametrize("operation", ["status", "cancel", "verify-code", "update-phone"])
def test_store_outage_is_not_misreported_as_missing(client, patient, phone_service, monkeypatch, operation):
    from app.services.phone_verification_store import PhoneStoreUnavailable

    def unavailable(*args, **kwargs):
        raise PhoneStoreUnavailable("synthetic")

    method = {"status": "get_verification_status", "cancel": "cancel_verification",
              "verify-code": "verify_code", "update-phone": "verify_code"}[operation]
    monkeypatch.setattr(phone_service, method, unavailable)
    if operation == "update-phone":
        response = client.put("/api/v1/phone-verification/update-phone", headers=patient["headers"],
                              json={"new_phone": NEW_PHONE, "verification_code": SYNTHETIC_CODE})
    else:
        payload = {"phone": NEW_PHONE, "purpose": "phone_change"}
        if operation == "verify-code":
            payload["code"] = SYNTHETIC_CODE
        response = client.post("/api/v1/phone-verification/" + operation, headers=patient["headers"], json=payload)
    assert response.status_code == 503
    assert response.headers["cache-control"] == "no-store"
    assert "synthetic" not in response.text


def test_admin_body_only_and_unbound_code_is_invisible_to_nonadmin(client, db_session, patient, phone_service):
    admin = User(username="SYNTHETIC_" + uuid4().hex, role="Admin", is_active=True,
                 is_superuser=False, hashed_password="unused-synthetic")
    db_session.add(admin)
    db_session.commit()
    token = create_access_token({"sub": str(admin.id), "auth_epoch": admin.auth_epoch})
    admin_headers = {"Authorization": f"Bearer {token}"}
    data = {"phone": NEW_PHONE, "purpose": "verification", "message": "SYNTHETIC {code}"}
    assert client.post("/api/v1/phone-verification/admin/send-code", headers=patient["headers"], json=data).status_code == 403
    response = client.post("/api/v1/phone-verification/admin/send-code", headers=admin_headers, json=data)
    assert response.status_code == 200, response.text
    assert response.headers["cache-control"] == "no-store"
    assert response.json()["expires_in_seconds"] == 299
    # A pre-existing admin-issued unbound record is never visible to a regular caller.
    phone_service.records[(NEW_PHONE, "verification")] = None
    scope = {"phone": NEW_PHONE, "purpose": "verification"}
    assert client.post("/api/v1/phone-verification/status", headers=patient["headers"], json=scope).json() == {"exists": False, "verified": False}
    assert client.post("/api/v1/phone-verification/cancel", headers=patient["headers"], json=scope).status_code == 404
    assert client.post("/api/v1/phone-verification/status", headers=admin_headers, json=scope).json()["exists"] is True
    assert client.post("/api/v1/phone-verification/cancel", headers=admin_headers, json=scope).status_code == 200


def test_admin_custom_message_requires_code_before_reservation_or_sms(client, db_session, monkeypatch):
    from app.api.v1.endpoints import phone_verification
    from app.services.phone_verification_service import PhoneVerificationService
    from app.services.phone_verification_store import MemoryPhoneStore
    from app.services.sms_providers import SMSManager, SMSProviderType, SMSResponse

    admin = User(username="SYNTHETIC_" + uuid4().hex, role="Admin", is_active=True,
                 is_superuser=False, hashed_password="unused-synthetic")
    db_session.add(admin)
    db_session.commit()
    token = create_access_token({"sub": str(admin.id), "auth_epoch": admin.auth_epoch})
    headers = {"Authorization": f"Bearer {token}"}
    delivered = []
    reservations = []

    class SyntheticProvider:
        async def send_sms(self, message):
            delivered.append(message)
            return SMSResponse(success=True, provider="synthetic", message_id="synthetic")

    manager = SMSManager()
    manager.providers = {SMSProviderType.MOCK: SyntheticProvider()}
    manager.default_provider = SMSProviderType.MOCK
    store = MemoryPhoneStore()
    reserve = store.reserve

    def capture_reserve(*args, **kwargs):
        reservations.append(True)
        return reserve(*args, **kwargs)

    monkeypatch.setattr(store, "reserve", capture_reserve)
    service = PhoneVerificationService(store)
    service.sms_manager = manager
    monkeypatch.setattr(service, "generate_verification_code", lambda: SYNTHETIC_CODE)
    monkeypatch.setattr(phone_verification, "get_phone_verification_service", lambda: service)
    path = "/api/v1/phone-verification/admin/send-code"
    for message in ("", "synthetic message without placeholder"):
        response = client.post(path, headers=headers, json={"phone": NEW_PHONE, "message": message})
        assert response.status_code == 400
        assert response.headers["cache-control"] == "no-store"
        assert not reservations and not delivered

    response = client.post(path, headers=headers, json={"phone": NEW_PHONE, "message": "Code: {code}"})
    assert response.status_code == 200, response.text
    assert response.headers["cache-control"] == "no-store"
    assert len(reservations) == len(delivered) == 1
    assert delivered[0].phone == NEW_PHONE and delivered[0].text == "Code: " + SYNTHETIC_CODE
