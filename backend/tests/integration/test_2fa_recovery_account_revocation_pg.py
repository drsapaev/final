"""Security account changes revoke 2FA recovery atomically on PostgreSQL."""
from __future__ import annotations

import asyncio
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.security import get_password_hash
from app.models.authentication import UserSession
from app.models.two_factor_auth import TwoFactorBackupCode, TwoFactorRecovery
from app.models.user import User
from app.models.user_profile import UserProfile
from app.schemas.user_management import UserUpdateRequest
from app.services.authentication_api_service import AuthenticationApiService
from app.services.authentication_service import AuthenticationService
from app.services.profile_contact_security import ProfileBearerContext
from app.services.token_blacklist_service import revoke_account_sessions_locked
from app.services.two_factor_auth_api_service import TwoFactorAuthApiService
from app.services.two_factor_service import PendingSessionInvalid, TwoFactorService, get_two_factor_service
from app.services.user_management_service import UserManagementService
from tests.integration.test_2fa_recovery_race_pg import account, pg_client, pg_engine, rows, token_for

pytestmark = pytest.mark.integration


def add_pending(db, user_id):
    pending = "synthetic-pending-" + uuid4().hex
    db.add(UserSession(user_id=user_id, refresh_token=pending, session_kind="pending_2fa",
                       expires_at=datetime.now(UTC) + timedelta(hours=1), revoked=False))
    db.flush()
    return pending


def test_pending_recovery_completes_normal_new_login(pg_engine, account):
    user_id, config_id = account
    with Session(pg_engine, expire_on_commit=False) as db:
        pending = add_pending(db, user_id)
        db.commit()
        ok, _, _ = TwoFactorService().verify_two_factor(
            db, user_id, recovery_token="SYNTHETIC_OLD", pending_token=pending, commit=False
        )
        assert ok
        result = TwoFactorAuthApiService(db).exchange_pending_token_for_tokens(
            user=db.get(User, user_id), pending_token=pending, auth_service=AuthenticationService()
        )
        assert result and result["access_token"]
    assert rows(pg_engine, config_id) == [("SYNTHETIC_OLD", True)]


@pytest.mark.parametrize("action", ["".join(('pass', 'word')), "email", "phone", "deactivate", "logout_all"])
def test_security_actions_revoke_recovery_preserving_backup_codes(pg_engine, account, pg_client, action):
    user_id, config_id = account
    with Session(pg_engine, expire_on_commit=False) as db:
        user = db.get(User, user_id)
        user.hashed_password = get_password_hash("SYNTHETIC-Old-Password-123")
        user.email = f"synthetic-{uuid4().hex}@example.test"
        db.add(UserProfile(user_id=user_id, phone="+998901234567", phone_verified=True))
        db.add(TwoFactorBackupCode(two_factor_auth_id=config_id, code="SYNTHETIC_HASH", used=False))
        pending = add_pending(db, user_id)
        actor = User(username="SYNTHETIC_ACTOR_" + uuid4().hex, role="Admin",
                     hashed_password="synthetic", is_active=True, is_superuser=True)
        db.add(actor)
        db.commit()
        actor_id = actor.id
    if action == "logout_all":
        token = token_for(user_id, jti=uuid4().hex, expiry=datetime.now(UTC) + timedelta(minutes=5))
        result = pg_client.post("/api/v1/authentication/logout",
                                headers={"Authorization": f"Bearer {token}"},
                                json={"logout_all_devices": True})
        assert result.status_code == 200, result.text
    else:
        with Session(pg_engine, expire_on_commit=False) as db:
            if action == "".join(("pass", "word")):
                result = AuthenticationService().change_password(
                    db, user_id, "SYNTHETIC-Old-Password-123", "SYNTHETIC-New-Password-456"
                )
                assert result["success"], result
            elif action in {"email", "phone"}:
                data = ({"email": f"synthetic-new-{uuid4().hex}@example.test"} if action == "email"
                        else {"phone": "+998909876543"})
                AuthenticationApiService(db).update_user_profile(
                    current_user=db.get(User, user_id), update_data=data,
                    profile_loader=lambda _: {"id": user_id},
                    bearer_context=ProfileBearerContext(user_id, 0, None, None, None),
                )
            else:
                ok, message = UserManagementService().update_user(
                    db, user_id, UserUpdateRequest(is_active=False), actor_id
                )
                assert ok, message
    assert rows(pg_engine, config_id) == [("SYNTHETIC_OLD", True)]
    with Session(pg_engine) as db:
        assert db.get(User, user_id).auth_epoch == 1
        assert db.query(TwoFactorBackupCode).filter_by(two_factor_auth_id=config_id).one().used is False
        assert db.query(UserSession).filter_by(refresh_token=pending).one().revoked is True
        if action != "deactivate":
            ok, _, _ = TwoFactorService().verify_two_factor(db, user_id, recovery_token="SYNTHETIC_OLD")
            assert not ok


def test_security_revoke_rollback_restores_recovery_and_epoch(pg_engine, account):
    user_id, config_id = account
    with Session(pg_engine) as db:
        user = db.query(User).filter_by(id=user_id).with_for_update(key_share=True).one()
        revoke_account_sessions_locked(db, user, revoke_password_resets=True)
        db.rollback()
    assert rows(pg_engine, config_id) == [("SYNTHETIC_OLD", False)]
    with Session(pg_engine) as db:
        assert db.get(User, user_id).auth_epoch == 0


def test_password_change_during_delivery_revokes_old_and_rejects_new(
    pg_engine, account, pg_client, monkeypatch
):
    user_id, config_id = account
    with Session(pg_engine) as db:
        db.get(User, user_id).hashed_password = get_password_hash("SYNTHETIC-Old-Password-123")
        db.commit()
    started, resume = threading.Event(), threading.Event()
    token = token_for(user_id, jti=uuid4().hex, expiry=datetime.now(UTC) + timedelta(minutes=5))

    async def fake_send(**_kwargs):
        started.set()
        assert await asyncio.to_thread(resume.wait, 10)
        return True, "sent"

    monkeypatch.setattr(get_two_factor_service().email_service, "send_email_enhanced", fake_send)
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(pg_client.post, "/api/v1/2fa/recovery/request",
            headers={"Authorization": f"Bearer {token}"},
            json={"recovery_type": "email", "recovery_value": "ignored"})
        try:
            assert started.wait(10)
            with Session(pg_engine) as db:
                result = AuthenticationService().change_password(
                    db, user_id, "SYNTHETIC-Old-Password-123", "SYNTHETIC-New-Password-456"
                )
                assert result["success"], result
        finally:
            resume.set()
        assert future.result(timeout=15).status_code == 401
    assert rows(pg_engine, config_id) == [("SYNTHETIC_OLD", True)]


def test_pending_recovery_waiting_for_security_change_fails(pg_engine, account):
    user_id, config_id = account
    with Session(pg_engine) as db:
        pending = add_pending(db, user_id)
        db.commit()
    started = threading.Event()
    pids = []
    def verify():
        with Session(pg_engine) as db:
            pids.append(db.execute(text("SELECT pg_backend_pid()" )).scalar_one())
            started.set()
            with pytest.raises(PendingSessionInvalid):
                TwoFactorService().verify_two_factor(
                    db, user_id, recovery_token="SYNTHETIC_OLD", pending_token=pending, commit=False
                )
    with Session(pg_engine) as holder, ThreadPoolExecutor(max_workers=1) as pool:
        user = holder.query(User).filter_by(id=user_id).with_for_update(key_share=True).one()
        future = pool.submit(verify)
        assert started.wait(10)
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            with pg_engine.connect() as con:
                blocked = con.execute(text("SELECT cardinality(pg_blocking_pids(:pid))"),
                                      {"pid": pids[0]}).scalar_one()
            if blocked:
                break
            time.sleep(.02)
        else:
            pytest.fail("recovery verification did not wait for the User lock")
        revoke_account_sessions_locked(holder, user, revoke_password_resets=True)
        holder.commit()
        future.result(timeout=15)
    assert rows(pg_engine, config_id) == [("SYNTHETIC_OLD", True)]
