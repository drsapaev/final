"""Contact changes revoke stale authentication state and preserve no-ops."""

from __future__ import annotations

import secrets
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from app.api.deps import create_access_token
from app.models.authentication import PasswordResetToken, RefreshToken, UserSession
from app.models.user import User
from app.models.user_profile import UserProfile


@pytest.fixture
def account(db_session):
    suffix = uuid4().hex
    user = User(
        username=f"SYNTHETIC_{suffix}", email=f"{suffix}@example.test",
        full_name="Synthetic Patient", role="Patient", is_active=True,
        is_superuser=False, hashed_password="synthetic-not-used",
    )
    db_session.add(user)
    db_session.flush()
    profile = UserProfile(
        user_id=user.id, phone="+998901234567", phone_verified=True,
        email_verified=True, full_name="Synthetic Patient",
    )
    db_session.add(profile)
    expires = datetime.now(UTC) + timedelta(hours=1)
    session = UserSession(user_id=user.id, refresh_token=secrets.token_urlsafe(24), expires_at=expires, revoked=False)
    refresh = RefreshToken(user_id=user.id, token=secrets.token_urlsafe(24), jti=str(uuid4()), expires_at=expires, revoked=False)
    reset = PasswordResetToken(user_id=user.id, token=secrets.token_hex(16), expires_at=expires, used=False)
    db_session.add_all([session, refresh, reset])
    db_session.commit()
    token = create_access_token({"sub": str(user.id), "auth_epoch": user.auth_epoch})
    return {"user_id": user.id, "profile_id": profile.id, "session_id": session.id,
            "refresh_id": refresh.id, "reset_id": reset.id,
            "headers": {"Authorization": f"Bearer {token}"}}


def _state(db, item):
    db.expire_all()
    return (
        db.query(User).filter_by(id=item["user_id"]).one(),
        db.query(UserProfile).filter_by(id=item["profile_id"]).one(),
        db.query(UserSession).filter_by(id=item["session_id"]).one(),
        db.query(RefreshToken).filter_by(id=item["refresh_id"]).one(),
        db.query(PasswordResetToken).filter_by(id=item["reset_id"]).one(),
    )


@pytest.mark.parametrize("body", [{"full_name": "Updated"}, {"phone": "+998 (90) 123-45-67"}])
def test_self_noncontact_or_normalized_same_phone_preserves_credentials(client, db_session, account, body):
    response = client.put("/api/v1/authentication/profile", headers=account["headers"], json=body)
    assert response.status_code == 200, response.text
    user, profile, session, refresh, reset = _state(db_session, account)
    assert user.auth_epoch == 0
    assert profile.phone == "+998901234567" and profile.phone_verified and profile.email_verified
    assert not session.revoked and not refresh.revoked and not reset.used


@pytest.mark.parametrize("body, field", [({"phone": "+998909876543"}, "phone"), ({"email": "new-contact@example.com"}, "email")])
def test_self_changed_contact_revokes_credentials_and_verification(client, db_session, account, body, field):
    response = client.put("/api/v1/authentication/profile", headers=account["headers"], json=body)
    assert response.status_code == 200, response.text
    user, profile, session, refresh, reset = _state(db_session, account)
    assert user.auth_epoch == 1
    assert session.revoked and refresh.revoked and reset.used
    assert (profile.phone_verified if field == "phone" else profile.email_verified) is False
    assert client.get("/api/v1/authentication/profile", headers=account["headers"]).status_code == 401


def test_staff_phone_change_revokes_target_not_acting_admin(client, db_session, account):
    from app.api.deps import require_staff

    suffix = uuid4().hex
    admin = User(username=f"SYNTHETIC_admin_{suffix}", email=f"{suffix}@example.test", role="Admin", is_active=True, is_superuser=True, hashed_password="synthetic-not-used")
    db_session.add(admin)
    db_session.commit()
    token = create_access_token({"sub": str(admin.id), "auth_epoch": admin.auth_epoch})
    # The test app's middleware uses its own session; keep this focused on the
    # endpoint's second, locked authorization check using the fixture database.
    client.app.dependency_overrides[require_staff] = lambda: admin
    response = client.put(
        f"/api/v1/users/users/{account['user_id']}/profile",
        headers={"Authorization": f"Bearer {token}"}, json={"phone": "+998909876543"},
    )
    assert response.status_code == 200, response.text
    user, profile, session, refresh, reset = _state(db_session, account)
    assert user.auth_epoch == 1 and not profile.phone_verified
    assert session.revoked and refresh.revoked and reset.used
    assert db_session.query(User).filter_by(id=admin.id).one().auth_epoch == 0


def test_bootstrap_and_revocation_roll_back_together(client, db_session, account, monkeypatch):
    import app.services.authentication_api_service as module
    from app.models.user_profile import UserNotificationSettings, UserPreferences

    original = module.revoke_account_sessions_locked
    def fail_after_revoke(*args, **kwargs):
        original(*args, **kwargs)
        raise RuntimeError("synthetic failure")
    monkeypatch.setattr(module, "revoke_account_sessions_locked", fail_after_revoke)
    response = client.put("/api/v1/authentication/profile", headers=account["headers"], json={"phone": "+998909876543"})
    assert response.status_code == 500
    user, profile, session, refresh, reset = _state(db_session, account)
    assert user.auth_epoch == 0 and profile.phone == "+998901234567" and profile.phone_verified
    assert not session.revoked and not refresh.revoked and not reset.used
    assert db_session.query(UserPreferences).filter_by(user_id=user.id).first() is None
    assert db_session.query(UserNotificationSettings).filter_by(user_id=user.id).first() is None
