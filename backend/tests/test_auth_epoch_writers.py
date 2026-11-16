"""Account security writers must revoke credentials in the same transaction."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from app.core.security import get_password_hash, verify_password
from app.models.authentication import PasswordResetToken, RefreshToken, UserSession
from app.models.user import User
from app.schemas.user_management import UserBulkActionRequest, UserUpdateRequest
from app.services.authentication_service import AuthenticationService
from app.services.password_reset_service import PasswordResetService
from app.services.user_management_service import UserManagementService


def _user(db, *, active=True):
    user = User(
        username=f"synthetic-{uuid4().hex[:16]}",
        email=f"synthetic-{uuid4().hex[:16]}@example.test",
        hashed_password=get_password_hash("Synthetic-Old-Password-1"),
        role="Nurse",
        is_active=active,
        is_superuser=False,
    )
    db.add(user)
    db.flush()
    return user


def _credentials(db, user):
    session = UserSession(
        user_id=user.id,
        refresh_token=f"synthetic-session-{uuid4().hex}",
        expires_at=datetime.now(UTC) + timedelta(hours=1),
        revoked=False,
    )
    token = RefreshToken(
        user_id=user.id,
        token=f"synthetic-refresh-{uuid4().hex}",
        jti=str(uuid4()),
        expires_at=datetime.now(UTC) + timedelta(hours=1),
        revoked=False,
    )
    db.add_all([session, token])
    db.commit()
    return session, token


def _assert_revoked(db, user, session, token):
    for item in (user, session, token):
        db.refresh(item)
    assert user.auth_epoch == 1
    assert session.revoked is True
    assert token.revoked is True
    assert token.revoked_at is not None


def test_change_password_revokes_all_credentials_atomically(db_session):
    user = _user(db_session)
    session, token = _credentials(db_session, user)
    result = AuthenticationService().change_password(
        db_session, user.id, "Synthetic-Old-Password-1", "Synthetic-New-Password-2"
    )
    assert result["success"] is True
    _assert_revoked(db_session, user, session, token)
    assert verify_password("Synthetic-New-Password-2", user.hashed_password)


def test_change_password_wrong_password_keeps_credentials(db_session):
    user = _user(db_session)
    session, token = _credentials(db_session, user)
    result = AuthenticationService().change_password(
        db_session, user.id, "Synthetic-Wrong-Password", "Synthetic-New-Password-2"
    )
    assert result["success"] is False
    for item in (user, session, token):
        db_session.refresh(item)
    assert user.auth_epoch == 0
    assert session.revoked is False
    assert token.revoked is False


def test_password_change_checks_bearer_expiry_after_hash(db_session, monkeypatch):
    from app.services.profile_contact_security import (
        ProfileBearerContext,
        ProfileBearerInvalid,
    )

    user = _user(db_session)
    session, refresh = _credentials(db_session, user)
    old_hash = user.hashed_password
    context = ProfileBearerContext(user.id, user.auth_epoch, None, 101, None)
    clock = {"now": 100}
    monkeypatch.setattr("app.services.profile_contact_security.time.time", lambda: clock["now"])

    def finish_after_expiry(_password):
        clock["now"] = 102
        return "synthetic-hash"

    monkeypatch.setattr("app.services.auth_svc._auth.get_password_hash", finish_after_expiry)
    with pytest.raises(ProfileBearerInvalid):
        AuthenticationService().change_password(
            db_session, user.id, "Synthetic-Old-Password-1", "Synthetic-New-Password-2",
            bearer_context=context,
        )
    for item in (user, session, refresh):
        db_session.refresh(item)
    assert user.hashed_password == old_hash and user.auth_epoch == 0
    assert not session.revoked and not refresh.revoked


def test_password_change_rechecks_patient_scope_binding(db_session):
    from app.services.profile_contact_security import (
        ProfileBearerContext,
        ProfileBearerInvalid,
    )

    user = _user(db_session)
    user.role = "Patient"
    session, refresh = _credentials(db_session, user)
    context = ProfileBearerContext(user.id, user.auth_epoch, None, None, 999999)
    with pytest.raises(ProfileBearerInvalid):
        AuthenticationService().change_password(
            db_session, user.id, "Synthetic-Old-Password-1", "Synthetic-New-Password-2",
            bearer_context=context,
        )
    for item in (user, session, refresh):
        db_session.refresh(item)
    assert user.auth_epoch == 0 and not session.revoked and not refresh.revoked


@pytest.mark.asyncio
async def test_password_change_endpoint_rejects_invalid_bearer_signature(db_session):
    from fastapi import HTTPException
    from starlette.requests import Request

    from app.api.v1.endpoints.authentication import change_password
    from app.schemas.authentication import PasswordChangeRequest

    user = _user(db_session)
    db_session.commit()
    request = Request({"type": "http", "method": "POST", "path": "/", "headers": [(b"authorization", b"Bearer invalid.jwt.signature")]})
    with pytest.raises(HTTPException) as denied:
        await change_password(
            request, PasswordChangeRequest(current_password="Synthetic-Old-Password-1", new_password="Synthetic-New-Password-2"),
            db=db_session, current_user=user,
        )
    assert denied.value.status_code == 401


@pytest.mark.parametrize("kind", ["mounted", "authentication"])
def test_reset_token_is_consumed_with_password_and_revocations(db_session, kind):
    user = _user(db_session)
    session, refresh = _credentials(db_session, user)
    raw_token = f"synthetic-reset-{uuid4().hex}"
    service = PasswordResetService()
    stored_token = service._hash_token(raw_token) if kind == "mounted" else raw_token
    reset = PasswordResetToken(
        user_id=user.id,
        token=stored_token,
        expires_at=datetime.now(UTC) + timedelta(hours=1),
        used=False,
    )
    db_session.add(reset)
    db_session.commit()
    if kind == "mounted":
        result = service.reset_password_with_token(db_session, raw_token, "Synthetic-New-Password-2")
        replay = service.reset_password_with_token(db_session, raw_token, "Synthetic-Another-Password-3")
    else:
        result = AuthenticationService().reset_password(db_session, raw_token, "Synthetic-New-Password-2")
        replay = AuthenticationService().reset_password(db_session, raw_token, "Synthetic-Another-Password-3")
    assert result["success"] is True
    assert replay["success"] is False
    _assert_revoked(db_session, user, session, refresh)
    db_session.refresh(reset)
    assert reset.used is True
    assert verify_password("Synthetic-New-Password-2", user.hashed_password)


@pytest.mark.parametrize("kind", ["mounted", "authentication"])
def test_reset_rolls_back_everything_on_revocation_failure(db_session, monkeypatch, caplog, kind):
    from sqlalchemy.exc import StatementError

    user = _user(db_session)
    session, refresh = _credentials(db_session, user)
    raw_token = f"synthetic-reset-{uuid4().hex}"
    service = PasswordResetService()
    stored_token = service._hash_token(raw_token) if kind == "mounted" else raw_token
    reset = PasswordResetToken(user_id=user.id, token=stored_token, expires_at=datetime.now(UTC) + timedelta(hours=1), used=False)
    db_session.add(reset)
    db_session.commit()
    old_hash = user.hashed_password

    def fail_after_mutation(db, locked_user, **_kwargs):
        locked_user.auth_epoch += 1
        session.revoked = True
        db.flush()
        raise StatementError(
            "synthetic failure", "INSERT", {"token": "SYNTHETIC_SECRET_DO_NOT_LOG"}, RuntimeError()
        )

    if kind == "mounted":
        monkeypatch.setattr("app.services.password_reset_service.revoke_account_sessions_locked", fail_after_mutation)
        result = service.reset_password_with_token(db_session, raw_token, "Synthetic-New-Password-2")
    else:
        monkeypatch.setattr("app.services.token_blacklist_service.revoke_account_sessions_locked", fail_after_mutation)
        result = AuthenticationService().reset_password(db_session, raw_token, "Synthetic-New-Password-2")
    assert result["success"] is False
    assert "SYNTHETIC_SECRET_DO_NOT_LOG" not in caplog.text
    assert "SYNTHETIC_SECRET_DO_NOT_LOG" not in str(result)
    for item in (user, session, refresh, reset):
        db_session.refresh(item)
    assert user.auth_epoch == 0
    assert user.hashed_password == old_hash
    assert session.revoked is False
    assert refresh.revoked is False
    assert reset.used is False


@pytest.mark.parametrize("kind", ["mounted", "authentication"])
def test_reset_expiring_during_hash_rolls_back(db_session, monkeypatch, kind):
    user = _user(db_session)
    session, refresh = _credentials(db_session, user)
    raw = f"synthetic-reset-{uuid4().hex}"
    service = PasswordResetService()
    reset = PasswordResetToken(
        user_id=user.id, token=service._hash_token(raw) if kind == "mounted" else raw,
        expires_at=datetime.now(UTC) + timedelta(hours=1), used=False,
    )
    db_session.add(reset)
    db_session.commit()
    old_hash = user.hashed_password

    class TestClock(datetime):
        expired = False

        @classmethod
        def now(cls, tz=None):
            return datetime.now(tz) + (timedelta(hours=2) if cls.expired else timedelta())

    def hash_after_expiry(_password):
        TestClock.expired = True
        return "synthetic-hash"

    if kind == "mounted":
        monkeypatch.setattr("app.services.password_reset_service.datetime", TestClock)
        monkeypatch.setattr("app.services.password_reset_service.get_password_hash", hash_after_expiry)
        result = service.reset_password_with_token(db_session, raw, "Synthetic-New-Password-2")
    else:
        monkeypatch.setattr("app.services.auth_svc._auth.datetime", TestClock)
        monkeypatch.setattr("app.services.auth_svc._auth.get_password_hash", hash_after_expiry)
        result = AuthenticationService().reset_password(db_session, raw, "Synthetic-New-Password-2")
    assert result["success"] is False
    for item in (user, session, refresh, reset):
        db_session.refresh(item)
    assert user.auth_epoch == 0 and user.hashed_password == old_hash
    assert not session.revoked and not refresh.revoked and not reset.used


def test_login_audit_failure_does_not_log_sql_bind_values(db_session, monkeypatch, caplog):
    from sqlalchemy.exc import StatementError

    def fail_add(_record):
        raise StatementError(
            "synthetic failure", "INSERT", {"user_agent": "SYNTHETIC_SECRET_DO_NOT_LOG"}, RuntimeError()
        )

    monkeypatch.setattr(db_session, "add", fail_add)
    AuthenticationService()._log_login_attempt(
        db_session, None, "SYNTHETIC-user", None, None, False, "invalid"
    )
    assert "SYNTHETIC_SECRET_DO_NOT_LOG" not in caplog.text


def test_deactivate_then_reactivate_does_not_revive_credentials(db_session):
    user = _user(db_session)
    actor = _user(db_session)
    session, token = _credentials(db_session, user)
    service = UserManagementService()
    ok, _ = service.update_user(db_session, user.id, UserUpdateRequest(is_active=False), actor.id)
    assert ok
    _assert_revoked(db_session, user, session, token)
    assert user.is_active is False
    ok, _ = service.update_user(db_session, user.id, UserUpdateRequest(is_active=True), actor.id)
    assert ok
    _assert_revoked(db_session, user, session, token)
    assert user.is_active is True


def test_non_deactivation_user_update_does_not_revoke(db_session):
    user = _user(db_session)
    actor = _user(db_session)
    session, token = _credentials(db_session, user)
    ok, _ = UserManagementService().update_user(
        db_session, user.id, UserUpdateRequest(full_name="Synthetic Updated"), actor.id
    )
    assert ok
    for item in (user, session, token):
        db_session.refresh(item)
    assert user.auth_epoch == 0
    assert session.revoked is False
    assert token.revoked is False


@pytest.mark.parametrize("kind", ["mounted", "authentication"])
def test_deactivation_invalidates_reset_before_reactivation(db_session, kind):
    user, actor = _user(db_session), _user(db_session)
    service = PasswordResetService()
    raw = f"synthetic-reset-{uuid4().hex}"
    reset = PasswordResetToken(
        user_id=user.id, token=service._hash_token(raw) if kind == "mounted" else raw,
        expires_at=datetime.now(UTC) + timedelta(hours=1), used=False,
    )
    db_session.add(reset)
    db_session.commit()
    management = UserManagementService()
    assert management.update_user(db_session, user.id, UserUpdateRequest(is_active=False), actor.id)[0]
    assert management.update_user(db_session, user.id, UserUpdateRequest(is_active=True), actor.id)[0]
    db_session.refresh(reset)
    assert reset.used is True
    result = (service.reset_password_with_token(db_session, raw, "Synthetic-New-Password-2")
              if kind == "mounted" else
              AuthenticationService().reset_password(db_session, raw, "Synthetic-New-Password-2"))
    assert result["success"] is False
    db_session.refresh(user)
    assert verify_password("Synthetic-Old-Password-1", user.hashed_password)


@pytest.mark.parametrize("kind", ["mounted", "authentication"])
def test_inactive_user_cannot_consume_existing_reset_token(db_session, kind):
    user = _user(db_session, active=False)
    service = PasswordResetService()
    raw = f"synthetic-reset-{uuid4().hex}"
    reset = PasswordResetToken(
        user_id=user.id, token=service._hash_token(raw) if kind == "mounted" else raw,
        expires_at=datetime.now(UTC) + timedelta(hours=1), used=False,
    )
    db_session.add(reset)
    db_session.commit()
    result = (service.reset_password_with_token(db_session, raw, "Synthetic-New-Password-2")
              if kind == "mounted" else
              AuthenticationService().reset_password(db_session, raw, "Synthetic-New-Password-2"))
    assert result["success"] is False
    db_session.refresh(reset)
    db_session.refresh(user)
    assert not reset.used and user.auth_epoch == 0
    assert verify_password("Synthetic-Old-Password-1", user.hashed_password)


def test_username_change_revokes_but_noop_does_not(db_session):
    user, actor = _user(db_session), _user(db_session)
    session, token = _credentials(db_session, user)
    management = UserManagementService()
    assert management.update_user(db_session, user.id, UserUpdateRequest(username=user.username), actor.id)[0]
    db_session.refresh(user)
    assert user.auth_epoch == 0
    assert management.update_user(db_session, user.id, UserUpdateRequest(username=f"renamed-{uuid4().hex[:12]}"), actor.id)[0]
    _assert_revoked(db_session, user, session, token)


@pytest.mark.parametrize("contact", ["email", "phone"])
def test_staff_contact_changes_revoke_credentials_but_noop_does_not(db_session, contact):
    from app.models.user_profile import UserProfile

    user, actor = _user(db_session), _user(db_session)
    profile = UserProfile(user_id=user.id, phone="+998900000120", phone_verified=True, email_verified=True)
    db_session.add(profile)
    session, refresh = _credentials(db_session, user)
    old_value = user.email if contact == "email" else profile.phone
    new_value = f"changed-{uuid4().hex}@example.test" if contact == "email" else "+998900000121"
    management = UserManagementService()
    assert management.update_user(db_session, user.id, UserUpdateRequest(**{contact: old_value}), actor.id)[0]
    db_session.refresh(user)
    assert user.auth_epoch == 0
    assert management.update_user(db_session, user.id, UserUpdateRequest(**{contact: new_value}), actor.id)[0]
    _assert_revoked(db_session, user, session, refresh)
    db_session.refresh(profile)
    assert not (profile.email_verified if contact == "email" else profile.phone_verified)


def test_email_verification_uses_current_contact_and_profile_only(db_session):
    user, actor = _user(db_session), _user(db_session)
    db_session.commit()
    auth = AuthenticationService()
    old = auth.create_email_verification_token(db_session, user.id)["token"]
    assert len(old) <= 64
    assert auth.get_user_profile(db_session, user.id)["email_verified"] is False
    assert UserManagementService().update_user(
        db_session, user.id, UserUpdateRequest(email=f"changed-{uuid4().hex}@example.test"), actor.id
    )[0]
    assert auth.verify_email(db_session, old)["success"] is False
    fresh = auth.create_email_verification_token(db_session, user.id)["token"]
    assert auth.get_user_profile(db_session, user.id)["email_verified"] is False
    assert auth.verify_email(db_session, fresh)["success"] is True
    assert auth.get_user_profile(db_session, user.id)["email_verified"] is True
    assert auth.verify_email(db_session, fresh)["success"] is False


def test_email_verification_request_rejects_stale_session_snapshot(db_session):
    user = _user(db_session)
    db_session.commit()
    epoch, email = user.auth_epoch, user.email
    user.auth_epoch += 1
    db_session.commit()
    result = AuthenticationService().create_email_verification_token(
        db_session, user.id, expected_auth_epoch=epoch, expected_email=email
    )
    assert result["success"] is False


def test_legacy_and_rotated_key_email_verification_tokens_fail_closed(db_session, monkeypatch):
    from app.core.config import settings
    from app.models.authentication import EmailVerificationToken

    user = _user(db_session)
    db_session.commit()
    db_session.add(EmailVerificationToken(
        user_id=user.id, token="synthetic-legacy-token",
        expires_at=datetime.now(UTC) + timedelta(hours=1), verified=False,
    ))
    db_session.commit()
    auth = AuthenticationService()
    assert auth.verify_email(db_session, "synthetic-legacy-token")["success"] is False
    fresh = auth.create_email_verification_token(db_session, user.id)["token"]
    monkeypatch.setattr(settings, "SECRET_KEY", settings.SECRET_KEY + "-rotated")
    assert auth.verify_email(db_session, fresh)["success"] is False
    assert auth.get_user_profile(db_session, user.id)["email_verified"] is False


@pytest.mark.asyncio
async def test_phone_reset_code_is_bound_to_account_epoch(db_session, monkeypatch):
    from types import SimpleNamespace

    from app.models.user_profile import UserProfile
    from app.services.phone_verification_service import PhoneVerificationService

    user, actor = _user(db_session), _user(db_session)
    phone = "+998900000123"
    db_session.add(UserProfile(user_id=user.id, phone=phone))
    db_session.commit()
    service = PasswordResetService()
    service.phone_verification = PhoneVerificationService()
    monkeypatch.setattr(service.phone_verification, "generate_verification_code", lambda: "123456")

    async def send_sms(**kwargs):
        return SimpleNamespace(success=True, message_id="synthetic", provider="synthetic")

    monkeypatch.setattr(service.phone_verification.sms_manager, "send_sms", send_sms)
    assert (await service.initiate_phone_reset(db_session, phone))["success"]
    management = UserManagementService()
    assert management.update_user(db_session, user.id, UserUpdateRequest(is_active=False), actor.id)[0]
    assert management.update_user(db_session, user.id, UserUpdateRequest(is_active=True), actor.id)[0]
    result = await service.verify_phone_and_get_token(db_session, phone, "123456")
    assert result["success"] is False
    assert "reset_token" not in result
    assert db_session.query(PasswordResetToken).filter_by(user_id=user.id, used=False).count() == 0

    # A newly issued code for the live epoch still works once.
    service.phone_verification.verification_codes.clear()
    assert (await service.initiate_phone_reset(db_session, phone))["success"]
    result = await service.verify_phone_and_get_token(db_session, phone, "123456")
    assert result["success"] is True and result["reset_token"]
    assert (await service.verify_phone_and_get_token(db_session, phone, "123456"))["success"] is False


def test_phone_code_can_be_consumed_only_once_across_threads():
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    from app.services.phone_verification_service import PhoneVerificationService

    service = PhoneVerificationService()
    phone = "+998900000124"
    key = service._get_code_key(phone, "password_reset")
    service.verification_codes[key] = {
        "code": "123456", "expires_at": datetime.now() + timedelta(minutes=5),
        "attempts": 0, "account_binding": (42, 1),
    }
    barrier = Barrier(2)

    def verify():
        barrier.wait(timeout=5)
        return service.verify_code(phone, "123456", "password_reset", include_account_binding=True)

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = [future.result(timeout=5) for future in (pool.submit(verify), pool.submit(verify))]
    assert sum(result["success"] is True for result in results) == 1


@pytest.mark.parametrize(
    ("initial_role", "initial_superuser", "update"),
    [
        ("Nurse", False, {"role": "Registrar"}),
        ("Registrar", False, {"role": "Nurse"}),
        ("Nurse", False, {"is_superuser": True}),
        ("Nurse", True, {"is_superuser": False}),
    ],
)
def test_privilege_change_revokes_existing_and_pending_credentials(
    db_session, initial_role, initial_superuser, update
):
    import asyncio

    from fastapi import HTTPException

    from app.api.deps import create_access_token, get_current_user

    user = _user(db_session)
    user.role = initial_role
    user.is_superuser = initial_superuser
    actor = _user(db_session)
    pending, refresh = _credentials(db_session, user)
    pending.session_kind = "pending_2fa"
    db_session.commit()
    stale_bearer = create_access_token({"sub": str(user.id)})
    assert asyncio.run(get_current_user(token=stale_bearer, db=db_session)).id == user.id

    ok, _ = UserManagementService().update_user(
        db_session, user.id, UserUpdateRequest(**update), actor.id
    )
    assert ok
    _assert_revoked(db_session, user, pending, refresh)
    with pytest.raises(HTTPException) as denied:
        asyncio.run(get_current_user(token=stale_bearer, db=db_session))
    assert denied.value.status_code == 401
    fresh_bearer = create_access_token({"sub": str(user.id), "auth_epoch": user.auth_epoch})
    assert asyncio.run(get_current_user(token=fresh_bearer, db=db_session)).id == user.id


def test_unchanged_privilege_does_not_revoke(db_session):
    user, actor = _user(db_session), _user(db_session)
    session, token = _credentials(db_session, user)
    ok, _ = UserManagementService().update_user(
        db_session, user.id, UserUpdateRequest(role="Nurse", is_superuser=False), actor.id
    )
    assert ok
    for item in (user, session, token):
        db_session.refresh(item)
    assert user.auth_epoch == 0
    assert session.revoked is False and token.revoked is False


def test_bulk_role_change_revokes_only_changed_users(db_session):
    first, unchanged, actor = _user(db_session), _user(db_session), _user(db_session)
    unchanged.role = "Registrar"
    s1, r1 = _credentials(db_session, first)
    s2, r2 = _credentials(db_session, unchanged)
    ok, _, result = UserManagementService().bulk_action_users(
        db_session,
        UserBulkActionRequest(user_ids=[first.id, unchanged.id], action="change_role", role="Registrar"),
        actor.id,
    )
    assert ok and result["processed_count"] == 2 and result["failed_count"] == 0
    _assert_revoked(db_session, first, s1, r1)
    for item in (unchanged, s2, r2):
        db_session.refresh(item)
    assert unchanged.auth_epoch == 0
    assert s2.revoked is False and r2.revoked is False


def test_bulk_failure_rolls_back_one_user_without_losing_other_success(db_session, monkeypatch):
    first, second, actor = _user(db_session), _user(db_session), _user(db_session)
    s1, r1 = _credentials(db_session, first)
    s2, r2 = _credentials(db_session, second)
    service = UserManagementService()
    original = service._sync_doctor_active

    def fail_second(db, user_id, *args, **kwargs):
        if user_id == second.id:
            raise ValueError("synthetic mirror failure")
        return original(db, user_id, *args, **kwargs)

    monkeypatch.setattr(service, "_sync_doctor_active", fail_second)
    ok, _, result = service.bulk_action_users(
        db_session,
        UserBulkActionRequest(user_ids=[first.id, second.id], action="deactivate"),
        actor.id,
    )
    assert ok and result["processed_count"] == 1 and result["failed_count"] == 1
    _assert_revoked(db_session, first, s1, r1)
    for item in (second, s2, r2):
        db_session.refresh(item)
    assert second.is_active is True and second.auth_epoch == 0
    assert s2.revoked is False and r2.revoked is False
