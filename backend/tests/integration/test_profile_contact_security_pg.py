"""PostgreSQL races for contact changes and revoked bearers."""
from __future__ import annotations

import os
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from queue import Queue
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session
from sqlalchemy.schema import CreateSchema, DropSchema

from app.db.base_class import Base
from app.models.authentication import PasswordResetToken, RefreshToken, UserSession
from app.models.user import User
from app.models.user_profile import UserProfile
from app.services.authentication_api_service import AuthenticationApiService
from app.services.profile_contact_security import (
    ProfileBearerContext,
    ProfileBearerInvalid,
)
from app.services.token_blacklist_service import revoke_account_sessions_locked

pytestmark = pytest.mark.integration


def _safe_test_database(url, *, ci: bool) -> bool:
    if url is None or url.get_backend_name() != "postgresql":
        return False
    if url.host not in {"localhost", "127.0.0.1", "::1"}:
        return False
    database = url.database or ""
    return database.startswith("clinic_test") or (ci and database == "clinicdb")


@pytest.fixture(scope="module")
def pg_engine():
    raw = os.environ.get("DATABASE_URL", "")
    url = make_url(raw) if raw else None
    ci = os.environ.get("CI", "").lower() == "true"
    if not _safe_test_database(url, ci=ci):
        if ci:
            pytest.fail("requires a disposable PostgreSQL database")
        pytest.skip("requires a local disposable clinic_test PostgreSQL database")
    schema = "test_contact_" + uuid4().hex
    admin = create_engine(url)
    with admin.begin() as con:
        con.execute(CreateSchema(schema))
    engine = create_engine(url, connect_args={"options": f"-csearch_path={schema} -cstatement_timeout=15000 -clock_timeout=10000"})
    try:
        import app.db.base  # noqa: F401
        Base.metadata.create_all(engine)
        yield engine
    finally:
        engine.dispose()
        with admin.begin() as con:
            con.execute(DropSchema(schema, cascade=True))
        admin.dispose()


@pytest.fixture
def account(pg_engine):
    with Session(pg_engine, expire_on_commit=False) as db:
        user = User(username="SYNTHETIC_" + uuid4().hex, email=uuid4().hex + "@example.com", hashed_password="synthetic", role="Patient", is_active=True, is_superuser=False)
        db.add(user)
        db.flush()
        expiry = datetime.now(UTC) + timedelta(hours=1)
        db.add_all([UserProfile(user_id=user.id, phone="+998901234567", phone_verified=True), UserSession(user_id=user.id, refresh_token=uuid4().hex, expires_at=expiry, revoked=False), RefreshToken(user_id=user.id, token=uuid4().hex, jti=uuid4().hex, expires_at=expiry, revoked=False), PasswordResetToken(user_id=user.id, token=uuid4().hex, expires_at=expiry, used=False)])
        db.commit()
        return user.id


def update(db, user_id, body):
    user = db.get(User, user_id)
    return AuthenticationApiService(db).update_user_profile(current_user=user, update_data=body, profile_loader=lambda _: {"id": user_id}, bearer_context=ProfileBearerContext(user_id, 0, None, None, None))


def test_stale_contact_update_waits_for_revocation_and_fails(pg_engine, account):
    pids = Queue()
    def worker():
        with Session(pg_engine) as db:
            pids.put(db.execute(text("select pg_backend_pid()")).scalar_one())
            with pytest.raises(ProfileBearerInvalid):
                update(db, account, {"phone": "+998909876543"})
            db.rollback()
    with Session(pg_engine) as gate, ThreadPoolExecutor(max_workers=1) as pool:
        user = gate.query(User).filter_by(id=account).with_for_update(key_share=True).one()
        future = pool.submit(worker)
        pid = pids.get(timeout=10)
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            with pg_engine.connect() as con:
                if con.execute(text("select cardinality(pg_blocking_pids(:pid))"), {"pid": pid}).scalar_one():
                    break
            time.sleep(.02)
        else:
            pytest.fail("contact update did not wait for User lock")
        revoke_account_sessions_locked(gate, user, revoke_password_resets=True)
        gate.commit()
        future.result(timeout=15)
    with Session(pg_engine) as db:
        profile = db.query(UserProfile).filter_by(user_id=account).one()
        assert profile.phone == "+998901234567" and profile.phone_verified
        assert db.get(User, account).auth_epoch == 1


def test_contact_failure_rolls_back_revocation_and_contact(pg_engine, account, monkeypatch):
    import app.services.authentication_api_service as module
    original = module.revoke_account_sessions_locked
    def fail_after_revoke(*args, **kwargs):
        original(*args, **kwargs)
        raise RuntimeError("synthetic failure")
    monkeypatch.setattr(module, "revoke_account_sessions_locked", fail_after_revoke)
    with Session(pg_engine) as db:
        with pytest.raises(RuntimeError):
            update(db, account, {"phone": "+998909876543"})
        db.rollback()
    with Session(pg_engine) as db:
        assert db.get(User, account).auth_epoch == 0
        profile = db.query(UserProfile).filter_by(user_id=account).one()
        assert profile.phone == "+998901234567" and profile.phone_verified
        assert not db.query(UserSession).filter_by(user_id=account).one().revoked
        assert not db.query(RefreshToken).filter_by(user_id=account).one().revoked
        assert not db.query(PasswordResetToken).filter_by(user_id=account).one().used


def test_phone_change_invalidates_otp_issued_before_wait(pg_engine, account):
    from app.services.patient_otp_service import (
        PatientOtpBinding,
        PatientOtpGrant,
        PatientOtpService,
    )

    pids = Queue()
    proof = PatientOtpGrant("+998901234567", PatientOtpBinding(account, 0))
    def worker():
        with Session(pg_engine) as db:
            pids.put(db.execute(text("select pg_backend_pid()")).scalar_one())
            return PatientOtpService()._locked_grant_user(db, proof.phone, proof)
    with Session(pg_engine) as gate, ThreadPoolExecutor(max_workers=1) as pool:
        gate.query(User).filter_by(id=account).with_for_update(key_share=True).one()
        future = pool.submit(worker)
        pid = pids.get(timeout=10)
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            with pg_engine.connect() as con:
                if con.execute(text("select cardinality(pg_blocking_pids(:pid))"), {"pid": pid}).scalar_one():
                    break
            time.sleep(.02)
        else:
            pytest.fail("OTP verification did not wait for User lock")
        update(gate, account, {"phone": "+998909876543"})
        assert future.result(timeout=15) is None
    with Session(pg_engine) as db:
        assert db.query(UserProfile).filter_by(user_id=account).one().phone == "+998909876543"
