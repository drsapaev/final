"""PostgreSQL proofs for account revocation and password-reset serialization."""

from __future__ import annotations

import os
import secrets
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session
from sqlalchemy.schema import CreateSchema, DropSchema

from app.core.security import get_password_hash, verify_password
from app.db.base_class import Base
from app.models.authentication import PasswordResetToken, RefreshToken, UserSession
from app.models.user import User
from app.schemas.user_management import UserUpdateRequest
from app.services.password_reset_service import PasswordResetService
from app.services.user_management_service import UserManagementService

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def epoch_pg_engine():
    ci = os.environ.get("CI", "").lower() == "true"
    raw = os.environ.get("DATABASE_URL", "").strip()
    if not raw:
        if ci:
            pytest.fail("CI requires PostgreSQL DATABASE_URL")
        pytest.skip("requires disposable PostgreSQL DATABASE_URL")
    url = make_url(raw)
    if url.get_backend_name() != "postgresql":
        if ci:
            pytest.fail("CI requires PostgreSQL")
        pytest.skip("requires PostgreSQL")
    if not ci and not (url.database or "").startswith("clinic_test"):
        pytest.skip("use an explicitly disposable clinic_test database")
    schema = "test_auth_epoch_writers_" + uuid4().hex
    admin = create_engine(url, pool_pre_ping=True)
    with admin.begin() as connection:
        connection.execute(CreateSchema(schema))
    engine = create_engine(
        url,
        pool_pre_ping=True,
        pool_size=8,
        connect_args={"options": f"-csearch_path={schema} -cstatement_timeout=15000 -clock_timeout=10000"},
    )
    try:
        import app.db.base  # noqa: F401

        Base.metadata.create_all(engine)
        yield engine
    finally:
        engine.dispose()
        with admin.begin() as connection:
            connection.execute(DropSchema(schema, cascade=True))
        admin.dispose()


def _seed_user(db):
    user = User(
        username=f"SYNTHETIC_epoch_{uuid4().hex[:16]}",
        email=f"synthetic-{uuid4().hex}@example.test",
        hashed_password=get_password_hash("Synthetic-Old-Password-1"),
        role="Nurse",
        is_active=True,
        is_superuser=False,
    )
    db.add(user)
    db.flush()
    return user


def _seed_credentials(db, user_id):
    db.add_all(
        [
            UserSession(
                user_id=user_id,
                refresh_token=f"synthetic-session-{uuid4().hex}",
                expires_at=datetime.now(UTC) + timedelta(hours=1),
                revoked=False,
            ),
            RefreshToken(
                user_id=user_id,
                token=f"synthetic-refresh-{uuid4().hex}",
                jti=str(uuid4()),
                expires_at=datetime.now(UTC) + timedelta(hours=1),
                revoked=False,
            ),
        ]
    )
    db.flush()


def _wait_for_user_lock(engine, pid):
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        with engine.connect() as connection:
            blockers = connection.execute(
                text("SELECT cardinality(pg_blocking_pids(:pid))"), {"pid": pid}
            ).scalar_one()
        if blockers:
            return
        time.sleep(0.02)
    pytest.fail("worker did not block on the held account lock")


def test_deactivation_serializes_with_inflight_session_mint(epoch_pg_engine):
    with Session(epoch_pg_engine, expire_on_commit=False) as db:
        user, actor = _seed_user(db), _seed_user(db)
        db.commit()
        user_id, actor_id = user.id, actor.id

    started = threading.Event()
    worker_pid = []

    def deactivate():
        with Session(epoch_pg_engine, autoflush=False) as db:
            worker_pid.append(db.execute(text("SELECT pg_backend_pid()" )).scalar_one())
            started.set()
            return UserManagementService().update_user(
                db, user_id, UserUpdateRequest(is_active=False), actor_id
            )

    # This transaction represents an already-authorized mint. The new
    # deactivation must wait for its User lock and then revoke that session.
    with Session(epoch_pg_engine, expire_on_commit=False) as holder:
        holder.query(User).filter(User.id == user_id).with_for_update(key_share=True).one()
        _seed_credentials(holder, user_id)
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(deactivate)
            assert started.wait(5)
            _wait_for_user_lock(epoch_pg_engine, worker_pid[0])
            holder.commit()
            ok, _ = future.result(timeout=15)
    assert ok
    with Session(epoch_pg_engine) as db:
        user = db.get(User, user_id)
        assert user.is_active is False and user.auth_epoch == 1
        assert db.query(UserSession).filter_by(user_id=user_id, revoked=False).count() == 0
        assert db.query(RefreshToken).filter_by(user_id=user_id, revoked=False).count() == 0


@pytest.mark.parametrize("kind", ["mounted", "authentication"])
def test_two_concurrent_password_resets_consume_one_token(epoch_pg_engine, kind):
    from app.services.authentication_service import AuthenticationService

    raw = secrets.token_urlsafe(32)
    reset_service = PasswordResetService()
    with Session(epoch_pg_engine, expire_on_commit=False) as db:
        user = _seed_user(db)
        _seed_credentials(db, user.id)
        reset = PasswordResetToken(
            user_id=user.id,
            token=reset_service._hash_token(raw) if kind == "mounted" else raw,
            expires_at=datetime.now(UTC) + timedelta(hours=1),
            used=False,
        )
        db.add(reset)
        db.commit()
        user_id, reset_id = user.id, reset.id

    started = [threading.Event(), threading.Event()]
    pids = [None, None]

    def reset_one(index):
        with Session(epoch_pg_engine, autoflush=False) as db:
            pids[index] = db.execute(text("SELECT pg_backend_pid()")).scalar_one()
            started[index].set()
            if kind == "mounted":
                return PasswordResetService().reset_password_with_token(
                    db, raw, f"Synthetic-New-Password-{index}-2"
                )
            return AuthenticationService().reset_password(
                db, raw, f"Synthetic-New-Password-{index}-2"
            )

    with Session(epoch_pg_engine, expire_on_commit=False) as holder:
        holder.query(User).filter(User.id == user_id).with_for_update(key_share=True).one()
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(reset_one, index) for index in range(2)]
            assert all(event.wait(5) for event in started)
            for pid in pids:
                _wait_for_user_lock(epoch_pg_engine, pid)
            holder.commit()
            results = [future.result(timeout=15) for future in futures]
    assert sum(result["success"] is True for result in results) == 1
    with Session(epoch_pg_engine) as db:
        user = db.get(User, user_id)
        assert user.auth_epoch == 1
        assert db.get(PasswordResetToken, reset_id).used is True
        assert any(
            verify_password(f"Synthetic-New-Password-{index}-2", user.hashed_password)
            for index in range(2)
        )
        assert db.query(UserSession).filter_by(user_id=user_id, revoked=False).count() == 0
        assert db.query(RefreshToken).filter_by(user_id=user_id, revoked=False).count() == 0


def test_reset_token_issue_waits_for_deactivation(epoch_pg_engine):
    with Session(epoch_pg_engine, expire_on_commit=False) as db:
        user = _seed_user(db)
        db.commit()
        user_id = user.id

    started = threading.Event()
    worker_pid = []

    def issue():
        # Pin the connection across the cleanup commit so the barrier observes
        # the backend PID that subsequently waits for the User lock.
        with epoch_pg_engine.connect() as connection, Session(connection, autoflush=False) as db:
            worker_pid.append(db.execute(text("SELECT pg_backend_pid()")).scalar_one())
            started.set()
            return PasswordResetService()._store_reset_token(db, "synthetic-reset-token", user_id)

    with Session(epoch_pg_engine, expire_on_commit=False) as holder:
        user = holder.query(User).filter_by(id=user_id).with_for_update(key_share=True).one()
        user.is_active = False
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(issue)
            assert started.wait(5)
            _wait_for_user_lock(epoch_pg_engine, worker_pid[0])
            holder.commit()
            assert future.result(timeout=15) is False
    with Session(epoch_pg_engine) as db:
        assert db.query(PasswordResetToken).filter_by(user_id=user_id, used=False).count() == 0


def test_delete_serializes_with_webauthn_identity_lock(epoch_pg_engine):
    from app.models.patient import Patient
    from app.services.webauthn_service import _lock_current_patient_identity

    with Session(epoch_pg_engine, expire_on_commit=False) as db:
        user, actor = _seed_user(db), _seed_user(db)
        user.role = "Patient"
        patient = Patient(user_id=user.id, first_name="Synthetic", last_name="Patient")
        db.add(patient)
        db.commit()
        user_id, actor_id, patient_id = user.id, actor.id, patient.id

    started = threading.Event()
    worker_pid = []

    def delete():
        with Session(epoch_pg_engine, autoflush=False) as db:
            worker_pid.append(db.execute(text("SELECT pg_backend_pid()")).scalar_one())
            started.set()
            return UserManagementService().delete_user(db, user_id, actor_id)

    # Exercise the same real identity-lock routine used by passkey registration
    # and completion; deletion must wait before touching Patient or children.
    with Session(epoch_pg_engine, expire_on_commit=False) as holder:
        assert _lock_current_patient_identity(holder, patient_id).id == user_id
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(delete)
            assert started.wait(5)
            _wait_for_user_lock(epoch_pg_engine, worker_pid[0])
            holder.commit()
            ok, message = future.result(timeout=15)
    assert ok, message
    with Session(epoch_pg_engine) as db:
        assert db.get(User, user_id) is None


def test_password_change_waits_for_inflight_mint_and_revokes_it(epoch_pg_engine):
    from app.services.authentication_service import AuthenticationService

    with Session(epoch_pg_engine, expire_on_commit=False) as db:
        user = _seed_user(db)
        db.commit()
        user_id = user.id
    started = threading.Event()
    worker_pid = []

    def change():
        with Session(epoch_pg_engine, autoflush=False) as db:
            worker_pid.append(db.execute(text("SELECT pg_backend_pid()")).scalar_one())
            started.set()
            return AuthenticationService().change_password(
                db, user_id, "Synthetic-Old-Password-1", "Synthetic-New-Password-2"
            )

    with Session(epoch_pg_engine, expire_on_commit=False) as holder:
        holder.query(User).filter_by(id=user_id).with_for_update(key_share=True).one()
        _seed_credentials(holder, user_id)
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(change)
            assert started.wait(5)
            _wait_for_user_lock(epoch_pg_engine, worker_pid[0])
            holder.commit()
            assert future.result(timeout=15)["success"]
    with Session(epoch_pg_engine) as db:
        assert db.get(User, user_id).auth_epoch == 1
        assert db.query(UserSession).filter_by(user_id=user_id, revoked=False).count() == 0
        assert db.query(RefreshToken).filter_by(user_id=user_id, revoked=False).count() == 0


def test_security_revoke_resets_and_rollback_are_atomic_on_postgres(epoch_pg_engine):
    from app.services.token_blacklist_service import revoke_account_sessions_locked

    with Session(epoch_pg_engine, expire_on_commit=False) as db:
        user = _seed_user(db)
        _seed_credentials(db, user.id)
        reset = PasswordResetToken(
            user_id=user.id, token=secrets.token_urlsafe(32),
            expires_at=datetime.now(UTC) + timedelta(hours=1), used=False,
        )
        db.add(reset)
        db.commit()
        user_id, reset_id = user.id, reset.id

    with Session(epoch_pg_engine) as db:
        user = db.query(User).filter_by(id=user_id).with_for_update(key_share=True).one()
        revoke_account_sessions_locked(db, user, revoke_password_resets=True)
        assert db.get(PasswordResetToken, reset_id).used
        assert db.query(UserSession).filter_by(user_id=user_id, revoked=False).count() == 0
        db.rollback()

    with Session(epoch_pg_engine) as db:
        assert db.get(User, user_id).auth_epoch == 0
        assert db.get(PasswordResetToken, reset_id).used is False
        assert db.query(UserSession).filter_by(user_id=user_id, revoked=False).count() == 1
        assert db.query(RefreshToken).filter_by(user_id=user_id, revoked=False).count() == 1


def test_reset_waiting_on_hard_delete_cannot_change_another_account(epoch_pg_engine):
    raw = secrets.token_urlsafe(32)
    reset_service = PasswordResetService()
    with Session(epoch_pg_engine, expire_on_commit=False) as db:
        user, actor = _seed_user(db), _seed_user(db)
        db.add(PasswordResetToken(
            user_id=user.id, token=reset_service._hash_token(raw),
            expires_at=datetime.now(UTC) + timedelta(hours=1), used=False,
        ))
        db.commit()
        user_id, actor_id = user.id, actor.id
    started = threading.Event()
    worker_pid = []

    def reset():
        with Session(epoch_pg_engine, autoflush=False) as db:
            worker_pid.append(db.execute(text("SELECT pg_backend_pid()")).scalar_one())
            started.set()
            return PasswordResetService().reset_password_with_token(
                db, raw, "Synthetic-New-Password-2"
            )

    with Session(epoch_pg_engine, expire_on_commit=False) as holder:
        holder.query(User).filter_by(id=user_id).with_for_update().one()
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(reset)
            assert started.wait(5)
            _wait_for_user_lock(epoch_pg_engine, worker_pid[0])
            ok, message = UserManagementService().delete_user(holder, user_id, actor_id)
            assert ok, message
            assert future.result(timeout=15)["success"] is False
    with Session(epoch_pg_engine) as db:
        assert db.get(User, user_id) is None
        actor = db.get(User, actor_id)
        assert actor.auth_epoch == 0
        assert verify_password("Synthetic-Old-Password-1", actor.hashed_password)


def test_email_reset_started_before_revoke_cannot_issue_afterward(epoch_pg_engine):
    import asyncio

    from app.services.token_blacklist_service import revoke_account_sessions_locked

    with Session(epoch_pg_engine, expire_on_commit=False) as db:
        user = _seed_user(db)
        db.commit()
        user_id, email = user.id, user.email
    started = threading.Event()
    worker_pid = []

    def issue():
        with epoch_pg_engine.connect() as connection, Session(connection, autoflush=False) as db:
            worker_pid.append(db.execute(text("SELECT pg_backend_pid()")).scalar_one())
            started.set()
            return asyncio.run(PasswordResetService().initiate_email_reset(db, email))

    with Session(epoch_pg_engine, expire_on_commit=False) as holder:
        user = holder.query(User).filter_by(id=user_id).with_for_update(key_share=True).one()
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(issue)
            assert started.wait(5)
            _wait_for_user_lock(epoch_pg_engine, worker_pid[0])
            revoke_account_sessions_locked(holder, user, revoke_password_resets=True)
            holder.commit()
            result = future.result(timeout=15)
    assert result["success"] is True  # anti-enumeration response is unchanged
    with Session(epoch_pg_engine) as db:
        assert db.query(PasswordResetToken).filter_by(user_id=user_id, used=False).count() == 0


def test_email_verification_waiting_for_contact_change_is_rejected(epoch_pg_engine):
    from app.models.user_profile import UserProfile
    from app.services.authentication_service import AuthenticationService
    from app.services.token_blacklist_service import revoke_account_sessions_locked

    with Session(epoch_pg_engine, expire_on_commit=False) as db:
        user = _seed_user(db)
        db.add(UserProfile(user_id=user.id, email_verified=False))
        db.commit()
        user_id = user.id
        token = AuthenticationService().create_email_verification_token(db, user_id)["token"]
    started = threading.Event()
    worker_pid = []

    def verify():
        with Session(epoch_pg_engine, autoflush=False) as db:
            worker_pid.append(db.execute(text("SELECT pg_backend_pid()")).scalar_one())
            started.set()
            return AuthenticationService().verify_email(db, token)

    with Session(epoch_pg_engine, expire_on_commit=False) as holder:
        user = holder.query(User).filter_by(id=user_id).with_for_update(key_share=True).one()
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(verify)
            assert started.wait(5)
            _wait_for_user_lock(epoch_pg_engine, worker_pid[0])
            revoke_account_sessions_locked(holder, user, revoke_password_resets=True)
            user.email = f"new-{uuid4().hex}@example.test"
            holder.commit()
            assert future.result(timeout=15)["success"] is False
    with Session(epoch_pg_engine) as db:
        assert db.query(UserProfile).filter_by(user_id=user_id).one().email_verified is False


def test_stale_email_verification_request_cannot_issue_after_logout(epoch_pg_engine):
    from app.models.authentication import EmailVerificationToken
    from app.services.authentication_service import AuthenticationService
    from app.services.token_blacklist_service import revoke_account_sessions_locked

    with Session(epoch_pg_engine, expire_on_commit=False) as db:
        user = _seed_user(db)
        db.commit()
        user_id, email, epoch = user.id, user.email, user.auth_epoch
    started = threading.Event()
    worker_pid = []

    def issue():
        with Session(epoch_pg_engine, autoflush=False) as db:
            worker_pid.append(db.execute(text("SELECT pg_backend_pid()")).scalar_one())
            started.set()
            return AuthenticationService().create_email_verification_token(
                db, user_id, expected_auth_epoch=epoch, expected_email=email
            )

    with Session(epoch_pg_engine, expire_on_commit=False) as holder:
        user = holder.query(User).filter_by(id=user_id).with_for_update(key_share=True).one()
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(issue)
            assert started.wait(5)
            _wait_for_user_lock(epoch_pg_engine, worker_pid[0])
            revoke_account_sessions_locked(holder, user, revoke_password_resets=True)
            holder.commit()
            assert future.result(timeout=15)["success"] is False
    with Session(epoch_pg_engine) as db:
        assert db.query(EmailVerificationToken).filter_by(user_id=user_id).count() == 0


@pytest.mark.parametrize("logout_all", [False, True])
def test_password_change_waiting_for_logout_rejects_bearer(epoch_pg_engine, logout_all):
    import asyncio

    import jwt
    from fastapi import HTTPException
    from starlette.requests import Request

    from app.api.deps import create_access_token
    from app.api.v1.endpoints.authentication import change_password
    from app.core.config import settings
    from app.schemas.authentication import PasswordChangeRequest
    from app.services.authentication_service import AuthenticationService

    with Session(epoch_pg_engine, expire_on_commit=False) as db:
        user = _seed_user(db)
        db.commit()
        user_id = user.id
        token = create_access_token({"sub": str(user.id), "auth_epoch": user.auth_epoch})
    payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    started = threading.Event()
    worker_pid = []

    def change():
        with Session(epoch_pg_engine, autoflush=False) as db:
            worker_pid.append(db.execute(text("SELECT pg_backend_pid()")).scalar_one())
            current_user = db.get(User, user_id)
            request = Request({"type": "http", "method": "POST", "path": "/", "headers": [(b"authorization", f"Bearer {token}".encode())]})
            started.set()
            try:
                asyncio.run(change_password(
                    request,
                    PasswordChangeRequest(current_password="Synthetic-Old-Password-1", new_password="Synthetic-New-Password-2"),
                    db=db, current_user=current_user,
                ))
            except HTTPException as exc:
                return exc.status_code
            return 200

    with Session(epoch_pg_engine, expire_on_commit=False) as holder:
        holder.query(User).filter_by(id=user_id).with_for_update(key_share=True).one()
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(change)
            assert started.wait(5)
            _wait_for_user_lock(epoch_pg_engine, worker_pid[0])
            result = AuthenticationService().logout_user(
                holder, user_id=user_id, logout_all=logout_all,
                access_token_jti=payload["jti"],
                access_token_exp=datetime.fromtimestamp(payload["exp"], UTC),
            )
            assert result["success"]
            assert future.result(timeout=15) == 401
    with Session(epoch_pg_engine) as db:
        user = db.get(User, user_id)
        assert verify_password("Synthetic-Old-Password-1", user.hashed_password)
        assert user.auth_epoch == (1 if logout_all else 0)
