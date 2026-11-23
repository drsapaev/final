"""Operational account writers revoke credentials only on real changes."""
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from app.core.security import get_password_hash
from app.models.authentication import PasswordResetToken, RefreshToken, UserSession
from app.models.user import User
from app.models.user_profile import UserProfile


class SessionProxy:
    def __init__(self, db):
        self.db = db
    def __enter__(self):
        return self.db
    def __exit__(self, *args):
        return False
    def __getattr__(self, name):
        return getattr(self.db, name)
    def close(self):
        pass


@pytest.mark.parametrize("writer", ["roles", "smoke"])
def test_writer_noop_and_security_change(db_session, monkeypatch, writer):
    from app.db import session as db_module
    from app.scripts import ensure_roles, ensure_smoke_users

    password = "SYNTHETIC-Password-1!"
    user = User(username="SYNTHETIC_test", email="synthetic@example.com", role="Registrar", is_active=True, is_superuser=False, hashed_password=get_password_hash(password))
    db_session.add(user)
    db_session.flush()
    db_session.add(UserProfile(user_id=user.id, email_verified=True))
    expiry = datetime.now(UTC) + timedelta(hours=1)
    session = UserSession(user_id=user.id, refresh_token=uuid4().hex, expires_at=expiry, revoked=False)
    refresh = RefreshToken(user_id=user.id, token=uuid4().hex, jti=uuid4().hex, expires_at=expiry, revoked=False)
    reset = PasswordResetToken(user_id=user.id, token=uuid4().hex, expires_at=expiry, used=False)
    db_session.add_all([session, refresh, reset])
    db_session.commit()
    def proxy():
        return SessionProxy(db_session)
    if writer == "roles":
        monkeypatch.setattr(db_module, "SessionLocal", proxy)
        monkeypatch.setattr(ensure_roles, "USERS", [(user.username, "Registrar", user.email)])
        monkeypatch.setenv("CONFIRM_ENSURE_ROLES", "1")
        monkeypatch.setenv("ENSURE_ROLES_SYNTHETIC_TEST_PASSWORD", password)
        run = ensure_roles.upsert_users
    else:
        monkeypatch.setattr(ensure_smoke_users, "SessionLocal", proxy)
        monkeypatch.setattr(ensure_smoke_users, "SMOKE_USERS", [(user.username, "Registrar", user.email)])
        monkeypatch.setattr(ensure_smoke_users, "RETIRED_SMOKE_USERNAMES", ())
        monkeypatch.setenv("SMOKE_USER_PASSWORD", password)
        run = ensure_smoke_users.ensure_smoke_users
    run()
    db_session.expire_all()
    assert user.auth_epoch == 0 and not session.revoked and not refresh.revoked and not reset.used
    if writer == "roles":
        monkeypatch.setattr(ensure_roles, "USERS", [(user.username, "Registrar", "new@example.com")])
    else:
        monkeypatch.setenv("SMOKE_USER_PASSWORD", "SYNTHETIC-Password-2!")
    run()
    db_session.expire_all()
    assert user.auth_epoch == 1 and session.revoked and refresh.revoked and reset.used
    if writer == "roles":
        assert user.profile.email_verified is False


@pytest.mark.parametrize("writer", ["roles", "smoke"])
def test_writer_rolls_back_if_revocation_fails(db_session, monkeypatch, writer):
    from app.db import session as db_module
    from app.scripts import ensure_roles, ensure_smoke_users
    from app.services import token_blacklist_service as blacklist_module

    user = User(username="SYNTHETIC_rollback", email="synthetic@example.com", role="Doctor", is_active=True, is_superuser=False, hashed_password=get_password_hash("SYNTHETIC-previous"))
    db_session.add(user)
    db_session.commit()
    def proxy():
        return SessionProxy(db_session)
    original = blacklist_module.revoke_account_sessions_locked
    def fail_after_revoke(*args, **kwargs):
        original(*args, **kwargs)
        raise RuntimeError("synthetic failure")
    if writer == "roles":
        monkeypatch.setattr(db_module, "SessionLocal", proxy)
        monkeypatch.setattr(ensure_roles, "USERS", [(user.username, "Registrar", user.email)])
        monkeypatch.setenv("CONFIRM_ENSURE_ROLES", "1")
        monkeypatch.setattr(blacklist_module, "revoke_account_sessions_locked", fail_after_revoke)
        run = ensure_roles.upsert_users
    else:
        monkeypatch.setattr(ensure_smoke_users, "SessionLocal", proxy)
        monkeypatch.setattr(ensure_smoke_users, "SMOKE_USERS", [(user.username, "Registrar", user.email)])
        monkeypatch.setattr(ensure_smoke_users, "RETIRED_SMOKE_USERNAMES", ())
        monkeypatch.setenv("SMOKE_USER_PASSWORD", "SYNTHETIC-new-password")
        monkeypatch.setattr(ensure_smoke_users, "revoke_account_sessions_locked", fail_after_revoke)
        run = ensure_smoke_users.ensure_smoke_users
    with pytest.raises(RuntimeError, match="synthetic failure"):
        run()
    db_session.rollback()
    db_session.expire_all()
    assert user.auth_epoch == 0 and user.role == "Doctor"
