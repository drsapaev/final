"""Synthetic demo users retain sessions on no-op and revoke on contact changes."""
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from app.core.security import get_password_hash
from app.models.authentication import PasswordResetToken, RefreshToken, UserSession
from app.models.user import User
from app.models.user_profile import UserProfile
from app.scripts import dev_seed


def test_seed_noop_then_phone_change_revokes_and_unverifies(db_session, monkeypatch):
    password = "SYNTHETIC-password"
    spec = dev_seed.DemoUserSpec("synthetic@example.com", "Registrar", "SYNTHETIC", "Registrar", "Reception", "+998901234567")
    user = User(username=spec.email, email=spec.email, full_name=spec.full_name, role=spec.role, is_active=True, is_superuser=False, must_change_password=False, hashed_password=get_password_hash(password))
    db_session.add(user)
    db_session.flush()
    profile = UserProfile(user_id=user.id, phone=spec.phone, phone_verified=True, email_verified=True)
    expiry = datetime.now(UTC) + timedelta(hours=1)
    session = UserSession(user_id=user.id, refresh_token=uuid4().hex, expires_at=expiry, revoked=False)
    refresh = RefreshToken(user_id=user.id, token=uuid4().hex, jti=uuid4().hex, expires_at=expiry, revoked=False)
    reset = PasswordResetToken(user_id=user.id, token=uuid4().hex, expires_at=expiry, used=False)
    db_session.add_all([profile, session, refresh, reset])
    db_session.commit()
    monkeypatch.setenv("DEV_DEMO_PASSCODE", password)
    monkeypatch.setattr(dev_seed, "DEMO_USERS", (spec,))
    dev_seed.upsert_demo_users(db_session)
    db_session.expire_all()
    assert user.auth_epoch == 0 and profile.phone_verified and profile.email_verified
    assert not session.revoked and not refresh.revoked and not reset.used
    monkeypatch.setattr(dev_seed, "DEMO_USERS", (replace(spec, phone="+998909876543"),))
    dev_seed.upsert_demo_users(db_session)
    db_session.expire_all()
    assert user.auth_epoch == 1 and not profile.phone_verified and profile.email_verified
    assert session.revoked and refresh.revoked and reset.used


def test_seed_new_account_preserves_verified_demo_contract(db_session, monkeypatch):
    spec = dev_seed.DemoUserSpec("synthetic-new@example.com", "Registrar", "SYNTHETIC", "Registrar", "Reception", "+998901234567")
    monkeypatch.setenv("DEV_DEMO_PASSCODE", "SYNTHETIC-password")
    monkeypatch.setattr(dev_seed, "DEMO_USERS", (spec,))
    user = dev_seed.upsert_demo_users(db_session)[spec.email]
    db_session.expire_all()
    assert user.auth_epoch == 0 and user.profile.email_verified


def test_seed_email_change_clears_verified(db_session, monkeypatch):
    password = "SYNTHETIC-password"
    spec = dev_seed.DemoUserSpec("synthetic-new@example.com", "Registrar", "SYNTHETIC", "Registrar", "Reception", "+998901234567")
    user = User(username=spec.email, email="synthetic-old@example.com", role=spec.role, is_active=True, is_superuser=False, must_change_password=False, hashed_password=get_password_hash(password))
    db_session.add(user)
    db_session.flush()
    profile = UserProfile(user_id=user.id, phone=spec.phone, phone_verified=True, email_verified=True)
    db_session.add(profile)
    db_session.commit()
    monkeypatch.setenv("DEV_DEMO_PASSCODE", password)
    monkeypatch.setattr(dev_seed, "DEMO_USERS", (spec,))
    dev_seed.upsert_demo_users(db_session)
    db_session.expire_all()
    assert user.auth_epoch == 1 and user.email == spec.email
    assert not profile.email_verified and profile.phone_verified
