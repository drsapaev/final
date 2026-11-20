"""PostgreSQL interleavings for refresh rotation and account-wide logout."""

from __future__ import annotations

import os
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from threading import Event
from urllib.parse import urlparse

import jwt
import pytest
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker

from app.models.authentication import (
    LoginAttempt,
    PasswordResetToken,
    RefreshToken,
    TokenBlacklist,
    UserActivity,
    UserSession,
)
from app.models.two_factor_auth import TwoFactorAuth, TwoFactorRecovery
from app.models.user import User
from app.services.auth_svc import AuthenticationService

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def pg_factory():
    url = os.getenv("REFRESH_RACE_TEST_URL", "").strip()
    if not url and os.getenv("CI", "").lower() == "true":
        candidate = os.getenv("DATABASE_URL", "").strip()
        parsed = urlparse(candidate.replace("postgresql+psycopg://", "postgresql://"))
        if (
            parsed.scheme == "postgresql"
            and parsed.hostname in {"localhost", "127.0.0.1"}
            and parsed.path == "/clinicdb"
        ):
            url = candidate
        else:
            pytest.fail(
                "CI requires a local disposable PostgreSQL URL for refresh race tests"
            )
    if not url:
        pytest.skip("REFRESH_RACE_TEST_URL must name a disposable PostgreSQL database")
    schema = f"test_refresh_{uuid.uuid4().hex}"
    admin = create_engine(url, future=True)
    with admin.begin() as conn:
        conn.execute(text(f'CREATE SCHEMA "{schema}"'))
    engine = create_engine(
        url, future=True, connect_args={"options": f"-csearch_path={schema}"}
    )
    try:
        for table in (
            User.__table__,
            TwoFactorAuth.__table__,
            TwoFactorRecovery.__table__,
            UserSession.__table__,
            RefreshToken.__table__,
            TokenBlacklist.__table__,
            LoginAttempt.__table__,
            UserActivity.__table__,
            PasswordResetToken.__table__,
        ):
            table.create(engine, checkfirst=True)
        yield sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    finally:
        engine.dispose()
        with admin.begin() as conn:
            conn.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        admin.dispose()


def seed(factory, *, linked=True):
    service = AuthenticationService()
    with factory() as db:
        user = User(
            username=f"SYNTHETIC-{uuid.uuid4().hex}",
            hashed_password="x",
            role="Doctor",
            is_active=True,
            auth_epoch=0,
        )
        db.add(user)
        db.flush()
        user_id = user.id
        jti = str(uuid.uuid4())
        token = service.create_refresh_token(user_id, jti, auth_epoch=0)
        db.add(
            RefreshToken(
                user_id=user_id,
                token=token,
                jti=jti,
                expires_at=datetime.now(UTC) + timedelta(days=1),
            )
        )
        if linked:
            db.add(
                UserSession(
                    user_id=user_id,
                    refresh_token=token,
                    expires_at=datetime.now(UTC) + timedelta(days=1),
                    revoked=False,
                )
            )
        db.commit()
    return user_id, token


def wait_blocked(factory, pid):
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        with factory() as db:
            blocked = db.execute(
                text("SELECT pg_blocking_pids(:pid)"), {"pid": pid}
            ).scalar_one()
        if blocked:
            return
        time.sleep(0.05)
    pytest.fail("expected PostgreSQL row-lock wait did not occur")


class HeldAccountService(AuthenticationService):
    def __init__(self, acquired, release):
        super().__init__()
        self.acquired = acquired
        self.release = release

    def _lock_auth_user(self, db, user_id):
        user = super()._lock_auth_user(db, user_id)
        self.acquired.set()
        if not self.release.wait(timeout=15):
            raise RuntimeError("synthetic lock barrier timed out")
        return user


def test_concurrent_refresh_reuse_serializes_and_revokes_winner(pg_factory):
    user_id, token = seed(pg_factory)
    acquired, release = Event(), Event()
    pid_ready = Event()
    contender = {}

    def first():
        with pg_factory() as db:
            return HeldAccountService(acquired, release).refresh_access_token(db, token)

    def second():
        with pg_factory() as db:
            contender["pid"] = db.execute(text("SELECT pg_backend_pid()")).scalar_one()
            pid_ready.set()
            return AuthenticationService().refresh_access_token(db, token)

    with ThreadPoolExecutor(max_workers=2) as pool:
        a = pool.submit(first)
        assert acquired.wait(10)
        b = pool.submit(second)
        assert pid_ready.wait(10)
        try:
            wait_blocked(pg_factory, contender["pid"])
        finally:
            release.set()
        first_result, second_result = a.result(timeout=20), b.result(timeout=20)
    assert first_result["success"] is True
    assert second_result["success"] is False
    with pg_factory() as db:
        user = db.get(User, user_id)
        assert user.auth_epoch == 1
        assert (
            db.query(RefreshToken).filter_by(user_id=user_id, revoked=False).count()
            == 0
        )
        assert (
            db.query(UserSession).filter_by(user_id=user_id, revoked=False).count() == 0
        )
        assert (
            AuthenticationService().refresh_access_token(
                db, first_result["refresh_token"]
            )["success"]
            is False
        )


def test_logout_all_waits_for_refresh_and_revokes_its_new_token(pg_factory):
    user_id, token = seed(pg_factory)
    acquired, release, pid_ready = Event(), Event(), Event()
    contender = {}

    def first():
        with pg_factory() as db:
            return HeldAccountService(acquired, release).refresh_access_token(db, token)

    def logout():
        with pg_factory() as db:
            contender["pid"] = db.execute(text("SELECT pg_backend_pid()")).scalar_one()
            pid_ready.set()
            return AuthenticationService().logout_user(
                db, user_id=user_id, logout_all=True
            )

    with ThreadPoolExecutor(max_workers=2) as pool:
        a = pool.submit(first)
        assert acquired.wait(10)
        b = pool.submit(logout)
        assert pid_ready.wait(10)
        try:
            wait_blocked(pg_factory, contender["pid"])
        finally:
            release.set()
        first_result, logout_result = a.result(timeout=20), b.result(timeout=20)
    assert first_result["success"] is True and logout_result["success"] is True
    with pg_factory() as db:
        assert db.get(User, user_id).auth_epoch == 1
        assert (
            db.query(RefreshToken).filter_by(user_id=user_id, revoked=False).count()
            == 0
        )
        assert (
            AuthenticationService().refresh_access_token(
                db, first_result["refresh_token"]
            )["success"]
            is False
        )


def test_logout_before_refresh_rejects_old_epoch(pg_factory):
    user_id, token = seed(pg_factory)
    acquired, release, pid_ready = Event(), Event(), Event()
    contender = {}

    def logout():
        with pg_factory() as db:
            return HeldAccountService(acquired, release).logout_user(
                db, user_id=user_id, logout_all=True
            )

    def refresh():
        with pg_factory() as db:
            contender["pid"] = db.execute(text("SELECT pg_backend_pid()")).scalar_one()
            pid_ready.set()
            return AuthenticationService().refresh_access_token(db, token)

    with ThreadPoolExecutor(max_workers=2) as pool:
        a = pool.submit(logout)
        assert acquired.wait(10)
        b = pool.submit(refresh)
        assert pid_ready.wait(10)
        try:
            wait_blocked(pg_factory, contender["pid"])
        finally:
            release.set()
        logout_result, refresh_result = a.result(timeout=20), b.result(timeout=20)
    assert logout_result["success"] is True and refresh_result["success"] is False
    with pg_factory() as db:
        assert db.get(User, user_id).auth_epoch == 1
        assert (
            db.query(RefreshToken).filter_by(user_id=user_id, revoked=False).count()
            == 0
        )


@pytest.mark.parametrize("prior_revoke", ["account", "single"])
def test_stale_logout_waiting_for_account_lock_cannot_revoke_new_session(
    pg_factory, prior_revoke
):
    user_id, old_refresh = seed(pg_factory)
    service = AuthenticationService()
    old_access = service.create_access_token({"sub": str(user_id), "auth_epoch": 0})
    old_claims = service.verify_token(old_access)
    state, ready = {}, Event()

    def stale_logout():
        with pg_factory() as db:
            state["pid"] = db.execute(text("SELECT pg_backend_pid()")).scalar_one()
            ready.set()
            return AuthenticationService().logout_user(
                db, user_id=user_id, logout_all=True, access_token=old_access
            )

    with pg_factory() as holding, ThreadPoolExecutor(max_workers=1) as pool:
        user = (
            holding.query(User)
            .filter_by(id=user_id)
            .with_for_update(key_share=True)
            .one()
        )
        future = pool.submit(stale_logout)
        assert ready.wait(10)
        try:
            wait_blocked(pg_factory, state["pid"])
            if prior_revoke == "account":
                user.auth_epoch += 1
            else:
                holding.add(
                    TokenBlacklist(
                        jti=old_claims["jti"],
                        user_id=user_id,
                        expires_at=datetime.now(UTC) + timedelta(minutes=10),
                        reason="logout",
                    )
                )
            new_jti = str(uuid.uuid4())
            new_refresh = service.create_refresh_token(
                user_id, new_jti, auth_epoch=user.auth_epoch
            )
            holding.add(
                RefreshToken(
                    user_id=user_id,
                    token=new_refresh,
                    jti=new_jti,
                    expires_at=datetime.now(UTC) + timedelta(days=1),
                )
            )
            holding.commit()
        finally:
            holding.rollback()
        result = future.result(timeout=20)
    assert result["success"] is False
    with pg_factory() as db:
        assert (
            db.query(RefreshToken)
            .filter_by(user_id=user_id, token=new_refresh, revoked=False)
            .count()
            == 1
        )
        assert (
            AuthenticationService().refresh_access_token(db, new_refresh)["success"]
            is True
        )


@pytest.mark.parametrize("action", ["logout_all", "logout_single", "new_login"])
def test_logout_all_revokes_old_recovery_but_later_recovery_works(
    pg_factory, monkeypatch, action
):
    from app.core.config import settings
    from app.services.password_reset_service import PasswordResetService

    user_id, refresh = seed(pg_factory)
    reset_service = PasswordResetService()
    old_token, new_token = (
        f"SYNTHETIC-{uuid.uuid4().hex}",
        f"SYNTHETIC-{uuid.uuid4().hex}",
    )
    with pg_factory() as db:
        assert reset_service._store_reset_token(
            db, old_token, user_id, expected_epoch=0
        )
        assert reset_service.validate_reset_token(db, old_token)["valid"] is True
        auth = AuthenticationService()
        if action == "logout_all":
            assert auth.logout_user(db, user_id=user_id, logout_all=True)["success"]
        elif action == "logout_single":
            assert auth.logout_user(db, user_id=user_id, refresh_token=refresh)[
                "success"
            ]
        else:
            monkeypatch.setattr(settings, "REVOKE_SESSIONS_ON_NEW_LOGIN", True)
            user = auth._lock_auth_user(db, user_id)
            auth.revoke_all_for_new_login_locked(db, user)
            db.commit()
        assert reset_service.validate_reset_token(db, old_token)["valid"] is (
            action != "logout_all"
        )
        epoch = db.get(User, user_id).auth_epoch
        if action == "logout_all":
            assert not reset_service._store_reset_token(
                db, f"SYNTHETIC-{uuid.uuid4().hex}", user_id, expected_epoch=0
            )
        assert reset_service._store_reset_token(
            db, new_token, user_id, expected_epoch=epoch
        )
        assert reset_service.validate_reset_token(db, new_token)["valid"] is True


@pytest.fixture
def session_http_client(pg_factory):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from app.api.v1.endpoints.authentication import router
    from app.db.session import get_db

    app = FastAPI()
    app.include_router(router, prefix="/api/v1/authentication")

    def override_db():
        with pg_factory() as db:
            yield db

    app.dependency_overrides[get_db] = override_db
    with TestClient(app) as client:
        yield client


def test_session_api_refuses_partial_operations_without_mutation(
    pg_factory, session_http_client
):
    user_id, refresh = seed(pg_factory)
    service = AuthenticationService()
    access = service.create_access_token({"sub": str(user_id), "auth_epoch": 0})
    headers = {
        "Authorization": f"Bearer {access}",
        "User-Agent": "SYNTHETIC-shared-agent",
    }
    root = "/api/v1/authentication/sessions"
    with pg_factory() as db:
        session_id = db.query(UserSession).filter_by(user_id=user_id).one().id
    assert (
        session_http_client.get(f"{root}/current", headers=headers).status_code == 409
    )
    assert (
        session_http_client.post(f"{root}/revoke-all", headers=headers).status_code
        == 409
    )
    assert (
        session_http_client.post(
            f"{root}/{session_id}/revoke", headers=headers
        ).status_code
        == 409
    )
    assert (
        session_http_client.request(
            "DELETE",
            f"{root}/{session_id}",
            headers=headers,
            json={"session_id": session_id},
        ).status_code
        == 409
    )
    with pg_factory() as db:
        assert db.get(User, user_id).auth_epoch == 0
        assert (
            db.query(UserSession).filter_by(user_id=user_id, revoked=False).count() == 1
        )
        assert (
            AuthenticationService().refresh_access_token(db, refresh)["success"] is True
        )


def test_session_api_documents_temporary_409(session_http_client):
    paths = session_http_client.get("/openapi.json").json()["paths"]
    for suffix, method in (
        ("/current", "get"),
        ("/{session_id}", "delete"),
        ("/{session_id}/revoke", "post"),
        ("/revoke-all", "post"),
    ):
        assert (
            "409"
            in paths[f"/api/v1/authentication/sessions{suffix}"][method]["responses"]
        )


def test_session_api_all_devices_revokes_unlinked_refresh_and_access(
    pg_factory, session_http_client
):
    user_id, _ = seed(pg_factory, linked=False)
    service = AuthenticationService()
    access = service.create_access_token({"sub": str(user_id), "auth_epoch": 0})
    another_access = service.create_access_token({"sub": str(user_id), "auth_epoch": 0})
    headers = {"Authorization": f"Bearer {access}"}
    root = "/api/v1/authentication/sessions"
    assert session_http_client.post(
        f"{root}/revoke-all?except_current=false"
    ).status_code in (401, 403)
    expired = service.create_access_token(
        {"sub": str(user_id), "auth_epoch": 0}, expires_delta=timedelta(seconds=-1)
    )
    assert (
        session_http_client.post(
            f"{root}/revoke-all?except_current=false",
            headers={"Authorization": f"Bearer {expired}"},
        ).status_code
        == 401
    )
    result = session_http_client.post(
        f"{root}/revoke-all?except_current=false", headers=headers
    )
    assert result.status_code == 200
    assert result.json()["revoked_count"] is None
    assert (
        session_http_client.get(
            f"{root}/current", headers={"Authorization": f"Bearer {another_access}"}
        ).status_code
        == 401
    )
    assert (
        session_http_client.post(
            f"{root}/revoke-all?except_current=false", headers=headers
        ).status_code
        == 401
    )
    with pg_factory() as db:
        assert db.get(User, user_id).auth_epoch == 1
        assert (
            db.query(RefreshToken).filter_by(user_id=user_id, revoked=False).count()
            == 0
        )


def test_session_api_database_failure_cannot_report_success(
    pg_factory, session_http_client
):
    from sqlalchemy.exc import OperationalError

    user_id, _ = seed(pg_factory)
    access = AuthenticationService().create_access_token(
        {"sub": str(user_id), "auth_epoch": 0}
    )
    engine = pg_factory.kw["bind"]

    def fail_lock(conn, cursor, statement, parameters, context, executemany):
        if "FOR NO KEY UPDATE" in statement.upper() and "users" in statement.lower():
            raise OperationalError(
                "synthetic query", (), RuntimeError("synthetic outage")
            )

    event.listen(engine, "before_cursor_execute", fail_lock)
    try:
        response = session_http_client.post(
            "/api/v1/authentication/sessions/revoke-all?except_current=false",
            headers={"Authorization": f"Bearer {access}"},
        )
    finally:
        event.remove(engine, "before_cursor_execute", fail_lock)
    assert response.status_code != 200
    with pg_factory() as db:
        assert db.get(User, user_id).auth_epoch == 0
        assert (
            db.query(RefreshToken).filter_by(user_id=user_id, revoked=False).count()
            == 1
        )


def test_session_api_stale_request_cannot_revoke_new_login(
    pg_factory, session_http_client
):
    user_id, _ = seed(pg_factory)
    service = AuthenticationService()
    access = service.create_access_token({"sub": str(user_id), "auth_epoch": 0})
    state, blocked = {}, Event()
    engine = pg_factory.kw["bind"]

    def capture_lock(conn, cursor, statement, parameters, context, executemany):
        if "FOR NO KEY UPDATE" in statement.upper() and "users" in statement.lower():
            state["pid"] = conn.connection.driver_connection.info.backend_pid
            blocked.set()

    def request_logout():
        return session_http_client.post(
            "/api/v1/authentication/sessions/revoke-all?except_current=false",
            headers={"Authorization": f"Bearer {access}"},
        )

    with pg_factory() as holding, ThreadPoolExecutor(max_workers=1) as pool:
        user = (
            holding.query(User)
            .filter_by(id=user_id)
            .with_for_update(key_share=True)
            .one()
        )
        event.listen(engine, "before_cursor_execute", capture_lock)
        try:
            future = pool.submit(request_logout)
            assert blocked.wait(10)
            wait_blocked(pg_factory, state["pid"])
            user.auth_epoch += 1
            new_jti = str(uuid.uuid4())
            new_refresh = service.create_refresh_token(
                user_id, new_jti, auth_epoch=user.auth_epoch
            )
            holding.add(
                RefreshToken(
                    user_id=user_id,
                    token=new_refresh,
                    jti=new_jti,
                    expires_at=datetime.now(UTC) + timedelta(days=1),
                )
            )
            holding.commit()
            response = future.result(timeout=20)
        finally:
            holding.rollback()
            event.remove(engine, "before_cursor_execute", capture_lock)
    assert response.status_code == 401
    with pg_factory() as db:
        assert (
            AuthenticationService().refresh_access_token(db, new_refresh)["success"]
            is True
        )


@pytest.mark.parametrize("expiry_point", ["account_lock", "before_commit"])
def test_signed_refresh_expiry_is_rechecked_after_waits_and_before_commit(
    pg_factory, monkeypatch, expiry_point
):
    user_id, token = seed(pg_factory)
    expiration = jwt.decode(token, options={"verify_signature": False})["exp"]
    clock = {"now": datetime.fromtimestamp(expiration - 60, UTC)}

    class ControlledDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            now = clock["now"]
            return now.astimezone(tz) if tz else now.replace(tzinfo=None)

    monkeypatch.setattr(jwt.api_jwt, "datetime", ControlledDatetime)

    class ExpireBeforeCommitService(AuthenticationService):
        def create_refresh_token(self, *args, **kwargs):
            result = super().create_refresh_token(*args, **kwargs)
            clock["now"] = datetime.fromtimestamp(expiration + 1, UTC)
            return result

    def refresh():
        with pg_factory() as db:
            if expiry_point == "account_lock":
                state["pid"] = db.execute(text("SELECT pg_backend_pid()")).scalar_one()
                ready.set()
                service = AuthenticationService()
            else:
                service = ExpireBeforeCommitService()
            return service.refresh_access_token(db, token)

    state, ready = {}, Event()
    if expiry_point == "account_lock":
        with pg_factory() as holding, ThreadPoolExecutor(max_workers=1) as pool:
            holding.query(User).filter_by(id=user_id).with_for_update(
                key_share=True
            ).one()
            future = pool.submit(refresh)
            assert ready.wait(10)
            try:
                wait_blocked(pg_factory, state["pid"])
                clock["now"] = datetime.fromtimestamp(expiration + 1, UTC)
            finally:
                holding.rollback()
            result = future.result(timeout=20)
    else:
        result = refresh()

    assert result["success"] is False
    with pg_factory() as db:
        assert db.get(User, user_id).auth_epoch == 0
        assert (
            db.query(RefreshToken).filter_by(user_id=user_id, revoked=False).count()
            == 1
        )
        assert (
            db.query(UserSession)
            .filter_by(user_id=user_id, refresh_token=token, revoked=False)
            .count()
            == 1
        )


def test_login_authenticated_before_logout_cannot_create_late_pending_session(
    pg_factory,
):
    from app.core.security import get_password_hash

    with pg_factory() as db:
        user = User(
            username=f"SYNTHETIC-{uuid.uuid4().hex}",
            hashed_password=get_password_hash("synthetic-password"),
            role="Patient",
            is_active=True,
            auth_epoch=0,
        )
        db.add(user)
        db.flush()
        user_id, username = user.id, user.username
        db.add(
            TwoFactorAuth(
                user_id=user_id,
                totp_enabled=True,
                totp_verified=True,
                totp_secret="SYNTHETIC",
            )
        )
        db.commit()
    authenticated, release = Event(), Event()

    class PausedLoginService(AuthenticationService):
        def authenticate_user(self, *args, **kwargs):
            result = super().authenticate_user(*args, **kwargs)
            assert result[0] is not None, (
                "barrier must follow successful password verification"
            )
            assert getattr(result[0], "_password_auth_snapshot", None) is not None
            authenticated.set()
            if not release.wait(timeout=15):
                raise RuntimeError("synthetic login barrier timed out")
            return result

    def login():
        with pg_factory() as db:
            return PausedLoginService().login_user(
                db,
                username,
                "synthetic-password",
                ip_address="127.0.0.1",
                user_agent="SYNTHETIC-test",
            )

    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(login)
        assert authenticated.wait(10)
        try:
            with pg_factory() as db:
                assert (
                    AuthenticationService().logout_user(
                        db, user_id=user_id, logout_all=True
                    )["success"]
                    is True
                )
        finally:
            release.set()
        result = future.result(timeout=20)
    assert result["success"] is False
    with pg_factory() as db:
        assert db.get(User, user_id).auth_epoch == 1
        assert (
            db.query(UserSession).filter_by(user_id=user_id, revoked=False).count() == 0
        )
        assert (
            db.query(RefreshToken).filter_by(user_id=user_id, revoked=False).count()
            == 0
        )


def test_logout_all_waits_for_enrollment_mint_and_revokes_new_refresh(pg_factory):
    from app.repositories.two_factor_auth_api_repository import (
        TwoFactorAuthApiRepository,
    )
    from app.services.two_factor_auth_api_service import TwoFactorAuthApiService

    with pg_factory() as db:
        user = User(
            username=f"SYNTHETIC-{uuid.uuid4().hex}",
            hashed_password="x",
            role="Admin",
            is_active=True,
            auth_epoch=0,
        )
        db.add(user)
        db.flush()
        user_id = user.id
        db.add(
            TwoFactorAuth(
                user_id=user_id,
                totp_enabled=True,
                totp_verified=True,
                totp_secret="SYNTHETIC",
            )
        )
        enrollment = f"SYNTHETIC-{uuid.uuid4().hex}"
        db.add(
            UserSession(
                user_id=user_id,
                refresh_token=enrollment,
                session_kind="2fa_enrollment",
                expires_at=datetime.now(UTC) + timedelta(minutes=10),
                revoked=False,
            )
        )
        db.commit()
    acquired, release, pid_ready = Event(), Event(), Event()
    contender = {}

    class PausedRepository(TwoFactorAuthApiRepository):
        def get_user_for_update(self, uid):
            user = super().get_user_for_update(uid)
            acquired.set()
            if not release.wait(timeout=15):
                raise RuntimeError("synthetic enrollment barrier timed out")
            return user

    def exchange():
        with pg_factory() as db:
            user = db.get(User, user_id)
            return TwoFactorAuthApiService(
                db, repository=PausedRepository(db)
            ).exchange_enrollment_token_for_tokens(
                user=user,
                enrollment_token=enrollment,
                auth_service=AuthenticationService(),
            )

    def logout():
        with pg_factory() as db:
            contender["pid"] = db.execute(text("SELECT pg_backend_pid()")).scalar_one()
            pid_ready.set()
            return AuthenticationService().logout_user(
                db, user_id=user_id, logout_all=True
            )

    with ThreadPoolExecutor(max_workers=2) as pool:
        a = pool.submit(exchange)
        assert acquired.wait(10)
        b = pool.submit(logout)
        assert pid_ready.wait(10)
        try:
            wait_blocked(pg_factory, contender["pid"])
        finally:
            release.set()
        exchanged, logged_out = a.result(timeout=20), b.result(timeout=20)
    assert exchanged and logged_out["success"] is True
    with pg_factory() as db:
        assert (
            db.query(RefreshToken).filter_by(user_id=user_id, revoked=False).count()
            == 0
        )
        assert (
            AuthenticationService().refresh_access_token(
                db, exchanged["refresh_token"]
            )["success"]
            is False
        )
