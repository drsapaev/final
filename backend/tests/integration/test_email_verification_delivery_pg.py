"""Email delivery is serialized with revocation without holding locks over SMTP."""
import asyncio
import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from urllib.parse import parse_qs, urlsplit

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.deps import create_access_token
from app.core.config import settings
from app.db.session import get_db
from app.main import app
from app.models.authentication import EmailVerificationToken
from app.models.user import User
from app.services.email_verification_delivery import (
    VerificationExpired,
    VerificationRateLimited,
    activate_verification,
    reserve_verification,
)
from app.services.profile_contact_security import ProfileBearerContext
from app.services.token_blacklist_service import revoke_account_sessions_locked
from tests.integration.test_profile_contact_security_pg import account, pg_engine  # noqa: F401

pytestmark = pytest.mark.integration


def test_no_lock_during_smtp_and_logout_invalidates_delivered_link(pg_engine, account, monkeypatch):
    import app.api.v1.endpoints.authentication as endpoint
    started, release = threading.Event(), threading.Event()
    delivered = []
    class BlockingMail:
        async def send_email_enhanced(self, **message):
            delivered.append(message)
            started.set()
            if not await asyncio.to_thread(release.wait, 15):
                raise TimeoutError("delivery barrier")
            return True, "sent"
    def get_session():
        with Session(pg_engine, autoflush=False) as db:
            yield db
    with Session(pg_engine) as db:
        user = db.get(User, account)
        bearer = create_access_token({"sub": str(user.id), "auth_epoch": user.auth_epoch})
    app.dependency_overrides[get_db] = get_session
    monkeypatch.setattr(endpoint, "get_email_sms_enhanced_service", lambda: BlockingMail())
    monkeypatch.setattr(settings, "FRONTEND_URL", "https://frontend.example")
    try:
        with TestClient(app) as client, ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(client.post, "/api/v1/authentication/email-verification", headers={"Authorization": f"Bearer {bearer}"})
            assert started.wait(15)
            try:
                # NOWAIT proves the request released its User lock before SMTP.
                with Session(pg_engine) as db:
                    user = db.query(User).filter_by(id=account).with_for_update(key_share=True, nowait=True).one()
                    revoke_account_sessions_locked(db, user, revoke_password_resets=True)
                    db.commit()
            finally:
                release.set()
            response = future.result(timeout=15)
            assert response.status_code == 401
            token = parse_qs(urlsplit(delivered[0]["text_content"].splitlines()[1]).fragment)["token"][0]
            assert client.post("/api/v1/authentication/email-verification/confirm", json={"token": token}).status_code == 400
    finally:
        release.set()
        app.dependency_overrides.pop(get_db, None)
    with Session(pg_engine) as db:
        assert db.query(EmailVerificationToken).filter_by(user_id=account).one().verified


def test_parallel_reservations_enforce_one_account_limit(pg_engine, account):
    context = ProfileBearerContext(account, 0, None, None, None)
    barrier = threading.Barrier(6)
    def reserve():
        with Session(pg_engine, autoflush=False) as db:
            barrier.wait(timeout=10)
            try:
                reserve_verification(db, context, None, None)
                return True
            except VerificationRateLimited:
                return False
    with ThreadPoolExecutor(max_workers=6) as pool:
        assert sum(pool.map(lambda _: reserve(), range(6))) == 3
    with Session(pg_engine) as db:
        assert db.query(EmailVerificationToken).filter_by(user_id=account).count() == 3


def test_expired_or_superseded_reservation_never_revokes_newer_link(pg_engine, account):
    context = ProfileBearerContext(account, 0, None, None, None)
    with Session(pg_engine, autoflush=False) as db:
        first = reserve_verification(db, context, None, None)
        second = reserve_verification(db, context, None, None)
        activate_verification(db, context, second)
        with pytest.raises(VerificationExpired):
            activate_verification(db, context, first)
        with pytest.raises(VerificationExpired):
            activate_verification(db, context, replace(first, expires_at=datetime.now(UTC) - timedelta(seconds=1)))
        third = reserve_verification(db, context, None, None)
        db.query(EmailVerificationToken).filter_by(id=third.id).update({"expires_at": datetime.now(UTC) - timedelta(seconds=1)})
        db.commit()
        with pytest.raises(VerificationExpired):
            activate_verification(db, context, third)
        live = db.query(EmailVerificationToken).filter_by(user_id=account, verified=False).one()
        assert live.id == second.id


def test_slow_older_delivery_cannot_revive_after_newer_link_confirmed(pg_engine, account):
    from app.services.authentication_service import AuthenticationService
    context = ProfileBearerContext(account, 0, None, None, None)
    reserved, complete_delivery = threading.Event(), threading.Event()
    def slow_request():
        with Session(pg_engine, autoflush=False) as db:
            older = reserve_verification(db, context, None, None)
            reserved.set()
            if not complete_delivery.wait(15):
                raise TimeoutError("synthetic SMTP barrier")
            with pytest.raises(VerificationExpired):
                activate_verification(db, context, older)
            return older.id
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(slow_request)
        assert reserved.wait(15)
        try:
            with Session(pg_engine, autoflush=False) as db:
                newer = reserve_verification(db, context, None, None)
                activate_verification(db, context, newer)
                assert AuthenticationService().verify_email(db, newer.token)["success"]
        finally:
            complete_delivery.set()
        older_id = future.result(timeout=15)
    with Session(pg_engine) as db:
        assert db.query(EmailVerificationToken).filter_by(user_id=account, verified=False).count() == 0
        older = db.get(EmailVerificationToken, older_id)
        assert older.verified and older.verified_at is None


def test_newer_failed_delivery_does_not_invalidate_older_link(pg_engine, account):
    context = ProfileBearerContext(account, 0, None, None, None)
    with Session(pg_engine, autoflush=False) as db:
        older = reserve_verification(db, context, None, None)
        newer = reserve_verification(db, context, None, None)
        # The newer reservation simulates an SMTP failure and stays pending.
        activate_verification(db, context, older)
        assert db.get(EmailVerificationToken, older.id).verified is False
        assert db.get(EmailVerificationToken, newer.id).verified is True
        assert db.get(EmailVerificationToken, newer.id).verified_at is None


def test_single_logout_and_expired_bearer_cannot_activate_pending_link(pg_engine, account):
    from uuid import uuid4

    from app.models.authentication import TokenBlacklist
    from app.services.profile_contact_security import ProfileBearerInvalid

    context = ProfileBearerContext(account, 0, str(uuid4()), int((datetime.now(UTC) + timedelta(hours=1)).timestamp()), None)
    with Session(pg_engine) as db:
        pending = reserve_verification(db, context, None, None)
    with Session(pg_engine) as db:
        db.query(User).filter_by(id=account).with_for_update(key_share=True).one()
        db.add(TokenBlacklist(user_id=account, jti=context.jti, expires_at=datetime.now(UTC) + timedelta(hours=1)))
        db.commit()
    with Session(pg_engine) as db:
        with pytest.raises(ProfileBearerInvalid):
            activate_verification(db, context, pending)
        assert db.get(EmailVerificationToken, pending.id).verified is True
    with Session(pg_engine) as db:
        expired = replace(context, jti=str(uuid4()), expires_at=int((datetime.now(UTC) - timedelta(seconds=1)).timestamp()))
        with pytest.raises(ProfileBearerInvalid):
            activate_verification(db, expired, pending)
