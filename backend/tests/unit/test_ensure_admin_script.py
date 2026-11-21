from __future__ import annotations

import pytest

from app.models.clinic import Branch, ClinicSettings


class _SessionContext:
    def __init__(self, session):
        self.session = session

    def __enter__(self):
        return self.session

    def __exit__(self, exc_type, exc, tb):
        return False


def test_ensure_admin_skips_initialized_instance_without_override(
    db_session,
    admin_user,
    monkeypatch,
):
    from app.scripts import ensure_admin as ensure_admin_module

    db_session.add(
        ClinicSettings(
            key="clinic_name",
            value="Initialized Clinic",
            category="clinic",
        )
    )
    db_session.add(
        Branch(
            name="Main Branch",
            code="main",
            timezone="Asia/Tashkent",
            capacity=50,
        )
    )
    db_session.commit()

    monkeypatch.setenv("ADMIN_USERNAME", "admin")
    monkeypatch.setenv("ADMIN_EMAIL", "ops@example.com")
    monkeypatch.setenv("ADMIN_FULL_NAME", "Ops Admin")
    monkeypatch.delenv("ENSURE_ADMIN_ALLOW_INITIALIZED", raising=False)
    monkeypatch.setattr(
        ensure_admin_module,
        "SessionLocal",
        lambda: _SessionContext(db_session),
    )

    result = ensure_admin_module.ensure_admin()

    assert result["skipped"] is True
    assert "explicit_ops_override" in result["reason"]


def test_ensure_admin_requires_explicit_admin_username(monkeypatch):
    from app.scripts import ensure_admin as ensure_admin_module

    monkeypatch.delenv("ADMIN_USERNAME", raising=False)

    with pytest.raises(RuntimeError, match="ADMIN_USERNAME must be set"):
        ensure_admin_module._required_admin_username()


def test_recovery_revokes_existing_credentials_only_for_security_changes(db_session, admin_user, monkeypatch):
    from datetime import UTC, datetime, timedelta
    from uuid import uuid4

    from app.models.authentication import PasswordResetToken, RefreshToken, UserSession
    from app.models.user_profile import UserProfile
    from app.scripts import ensure_admin as script

    expiry = datetime.now(UTC) + timedelta(hours=1)
    session = UserSession(user_id=admin_user.id, refresh_token=uuid4().hex, expires_at=expiry, revoked=False)
    refresh = RefreshToken(user_id=admin_user.id, token=uuid4().hex, jti=uuid4().hex, expires_at=expiry, revoked=False)
    reset = PasswordResetToken(user_id=admin_user.id, token=uuid4().hex, expires_at=expiry, used=False)
    profile = db_session.query(UserProfile).filter_by(user_id=admin_user.id).first()
    if profile is None:
        profile = UserProfile(user_id=admin_user.id)
        db_session.add(profile)
    profile.email_verified = True
    db_session.add_all([session, refresh, reset])
    db_session.commit()
    monkeypatch.setattr(script, "SessionLocal", lambda: _SessionContext(db_session))
    monkeypatch.setenv("ADMIN_USERNAME", admin_user.username)
    monkeypatch.setenv("ADMIN_EMAIL", admin_user.email)
    monkeypatch.setenv("ADMIN_FULL_NAME", "Changed name")
    monkeypatch.setenv("ENSURE_ADMIN_ALLOW_INITIALIZED", "1")
    monkeypatch.setenv("ENSURE_ADMIN_CONFIRM_INITIALIZED_OVERRIDE", "1")
    monkeypatch.delenv("ADMIN_RESET_PASSWORD", raising=False)

    script.ensure_admin()
    db_session.expire_all()
    assert admin_user.auth_epoch == 0
    assert not session.revoked and not refresh.revoked and not reset.used
    assert profile.email_verified is True

    monkeypatch.setenv("ADMIN_EMAIL", "recovery@example.com")
    script.ensure_admin()
    db_session.expire_all()
    assert admin_user.auth_epoch == 1
    assert admin_user.email == "recovery@example.com"
    assert session.revoked and refresh.revoked and reset.used
    assert profile.email_verified is False


def test_recovery_failure_rolls_back_revocation(db_session, admin_user, monkeypatch):
    from app.scripts import ensure_admin as script

    old_email = admin_user.email
    monkeypatch.setattr(script, "SessionLocal", lambda: _SessionContext(db_session))
    monkeypatch.setenv("ADMIN_USERNAME", admin_user.username)
    monkeypatch.setenv("ADMIN_EMAIL", "new-ops@example.com")
    monkeypatch.setenv("ENSURE_ADMIN_ALLOW_INITIALIZED", "1")
    monkeypatch.setenv("ENSURE_ADMIN_CONFIRM_INITIALIZED_OVERRIDE", "1")
    original = script.revoke_account_sessions_locked
    def fail_after_revoke(*args, **kwargs):
        original(*args, **kwargs)
        raise RuntimeError("synthetic failure")
    monkeypatch.setattr(script, "revoke_account_sessions_locked", fail_after_revoke)
    with pytest.raises(RuntimeError):
        script.ensure_admin()
    db_session.rollback()
    db_session.expire_all()
    assert admin_user.email == old_email and admin_user.auth_epoch == 0
