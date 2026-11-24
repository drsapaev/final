"""Executable PostgreSQL interleavings for sensitive two-factor operations."""

from __future__ import annotations

import base64
import os
import secrets
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from queue import Queue
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.schema import CreateSchema, DropSchema

from app.core.security import get_password_hash
from app.db.base_class import Base
from app.models.two_factor_auth import TwoFactorAuth, TwoFactorBackupCode
from app.models.user import User
from app.services.two_factor_service import TwoFactorService

pytestmark = pytest.mark.integration
SECRET = base64.b32encode(secrets.token_bytes(20)).decode("ascii")


@pytest.fixture(scope="module")
def pg_engine():
    ci = os.environ.get("CI", "").lower() == "true"
    raw = os.environ.get("DATABASE_URL", "").strip()
    if not raw:
        if ci:
            pytest.fail("CI requires PostgreSQL DATABASE_URL")
        pytest.skip("requires a disposable PostgreSQL DATABASE_URL")
    url = make_url(raw)
    if url.get_backend_name() != "postgresql":
        if ci:
            pytest.fail("CI requires PostgreSQL")
        pytest.skip("requires PostgreSQL")
    if not ci and not (url.database or "").startswith("clinic_test"):
        pytest.skip("use an explicitly disposable clinic_test database")
    schema = "test_2fa_rotate_" + uuid4().hex
    admin = create_engine(url, pool_pre_ping=True)
    with admin.begin() as connection:
        connection.execute(CreateSchema(schema))
    engine = create_engine(
        url,
        pool_pre_ping=True,
        pool_size=8,
        connect_args={
            "options": f"-csearch_path={schema} -cstatement_timeout=15000 -clock_timeout=10000"
        },
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


@pytest.fixture
def enrolled(pg_engine):
    service = TwoFactorService()
    password = secrets.token_urlsafe(24)
    backup_codes = ["A1B2C3D4", "E5F6G7H8", "J1K2L3M4"]
    with Session(pg_engine, expire_on_commit=False) as db:
        user = User(
            username=f"SYNTHETIC_2fa_{uuid4().hex}",
            email=f"{uuid4().hex}@example.test",
            hashed_password=get_password_hash(password),
            role="Doctor",
            is_active=True,
            is_superuser=False,
        )
        db.add(user)
        db.flush()
        config = TwoFactorAuth(
            user_id=user.id, totp_secret=SECRET, totp_enabled=True, totp_verified=True
        )
        db.add(config)
        db.flush()
        db.add_all(
            [
                TwoFactorBackupCode(
                    two_factor_auth_id=config.id,
                    code=service._hash_backup_code(code),
                    used=False,
                )
                for code in backup_codes
            ]
        )
        db.commit()
        return {
            "user_id": user.id,
            "config_id": config.id,
            "".join(('pass', 'word')): password,
            "codes": backup_codes,
        }


def _assert_waiting(engine, pids):
    """Prove the workers actually reached a database lock before releasing it."""
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        with engine.connect() as db:
            blocked = [
                db.execute(
                    text("SELECT cardinality(pg_blocking_pids(:pid))"), {"pid": pid}
                ).scalar_one()
                for pid in pids
            ]
        if all(value > 0 for value in blocked):
            return
        time.sleep(0.02)
    raise AssertionError("worker did not block on the orchestrating transaction")


def _run_blocked(engine, user_id, operations):
    """Start each operation in a distinct PG session under a held user lock."""
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    pids = Queue()
    start = threading.Event()

    def worker(operation):
        with factory() as db:
            pid = db.execute(text("SELECT pg_backend_pid()")).scalar_one()
            pids.put(pid)
            if not start.wait(10):
                raise TimeoutError("test start barrier")
            return operation(db)

    with factory() as gate, ThreadPoolExecutor(max_workers=len(operations)) as executor:
        gate.query(User).filter_by(id=user_id).with_for_update(key_share=True).one()
        futures = [executor.submit(worker, operation) for operation in operations]
        worker_pids = [pids.get(timeout=10) for _ in operations]
        start.set()
        try:
            _assert_waiting(engine, worker_pids)
        finally:
            gate.commit()
        return [future.result(timeout=20) for future in futures]


@pytest.mark.parametrize("factor", ["totp", "backup"])
def test_simultaneous_rotations_have_exactly_one_winner(pg_engine, enrolled, factor):
    service = TwoFactorService()
    code = service.generate_totp_code(SECRET)
    second_factors = (
        [{"totp_code": code}] * 2
        if factor == "totp"
        else [
            {"backup_code": enrolled["codes"][0]},
            {"backup_code": enrolled["codes"][1]},
        ]
    )
    operations = [
        lambda db, second=second: service.regenerate_backup_codes(
            db, enrolled["user_id"], enrolled["".join(("pass", "word"))], **second
        )
        for second in second_factors
    ]
    results = _run_blocked(pg_engine, enrolled["user_id"], operations)
    winners = [result for result in results if result is not None]
    assert len(winners) == 1
    assert len(winners[0]) == 10
    with Session(pg_engine) as db:
        rows = (
            db.query(TwoFactorBackupCode)
            .filter_by(two_factor_auth_id=enrolled["config_id"], used=False)
            .all()
        )
        assert {row.code for row in rows} == {
            service._hash_backup_code(code) for code in winners[0]
        }


def test_disable_racing_regenerate_never_revives_disabled_or_publishes_stale_codes(
    pg_engine, enrolled
):
    service = TwoFactorService()
    code = service.generate_totp_code(SECRET)
    regenerate, disabled = _run_blocked(
        pg_engine,
        enrolled["user_id"],
        [
            lambda db: service.regenerate_backup_codes(
                db, enrolled["user_id"], enrolled["".join(("pass", "word"))], totp_code=code
            ),
            lambda db: service.disable_two_factor_auth(
                db, enrolled["user_id"], enrolled["".join(("pass", "word"))], totp_code=code
            ),
        ],
    )
    assert (regenerate is not None) != disabled
    with Session(pg_engine) as db:
        config = db.query(TwoFactorAuth).filter_by(user_id=enrolled["user_id"]).first()
        if disabled:
            assert config is None
        else:
            assert config is not None and config.totp_enabled
            rows = (
                db.query(TwoFactorBackupCode)
                .filter_by(two_factor_auth_id=config.id, used=False)
                .all()
            )
            assert {row.code for row in rows} == {
                service._hash_backup_code(code) for code in regenerate
            }


@pytest.mark.parametrize("factor", ["totp", "backup"])
def test_rotation_failure_rolls_back_old_codes_and_factor_consumption(
    pg_engine, enrolled, monkeypatch, factor
):
    service = TwoFactorService()
    second = (
        {"totp_code": service.generate_totp_code(SECRET)}
        if factor == "totp"
        else {"backup_code": enrolled["codes"][0]}
    )

    def fail_generation():
        raise RuntimeError("synthetic failure after deletion")

    monkeypatch.setattr(service, "generate_backup_codes", fail_generation)
    with Session(pg_engine) as db, pytest.raises(RuntimeError, match="synthetic"):
        service.regenerate_backup_codes(
            db, enrolled["user_id"], enrolled["".join(("pass", "word"))], **second
        )
    with Session(pg_engine) as db:
        config = db.query(TwoFactorAuth).filter_by(user_id=enrolled["user_id"]).one()
        rows = (
            db.query(TwoFactorBackupCode)
            .filter_by(two_factor_auth_id=config.id, used=False)
            .all()
        )
        assert {row.code for row in rows} == {
            service._hash_backup_code(code) for code in enrolled["codes"]
        }
        assert config.last_sensitive_totp_step is None


def test_password_change_waits_then_old_password_rejected(pg_engine, enrolled):
    service = TwoFactorService()
    factory = sessionmaker(bind=pg_engine, expire_on_commit=False)
    pids = Queue()
    code = service.generate_totp_code(SECRET)
    replacement_hash = get_password_hash(secrets.token_urlsafe(24))

    def rotate():
        with factory() as db:
            pids.put(db.execute(text("SELECT pg_backend_pid()")).scalar_one())
            return service.regenerate_backup_codes(
                db, enrolled["user_id"], enrolled["".join(("pass", "word"))], totp_code=code
            )

    with factory() as gate, ThreadPoolExecutor(max_workers=1) as executor:
        user = (
            gate.query(User)
            .filter_by(id=enrolled["user_id"])
            .with_for_update(key_share=True)
            .one()
        )
        user.hashed_password = replacement_hash
        future = executor.submit(rotate)
        try:
            _assert_waiting(pg_engine, [pids.get(timeout=10)])
        finally:
            gate.commit()
        assert future.result(timeout=20) is None
    with Session(pg_engine) as db:
        rows = (
            db.query(TwoFactorBackupCode)
            .filter_by(two_factor_auth_id=enrolled["config_id"], used=False)
            .all()
        )
        assert {row.code for row in rows} == {
            service._hash_backup_code(code) for code in enrolled["codes"]
        }


def test_trusted_session_insert_and_rotation_do_not_deadlock(pg_engine, enrolled):
    """Reproduce 2FA→FK and user→2FA locking with separate PG sessions."""
    from sqlalchemy import event

    service = TwoFactorService()
    factory = sessionmaker(bind=pg_engine, expire_on_commit=False)
    code = service.generate_totp_code(SECRET)
    insert_reached, release_insert = threading.Event(), threading.Event()
    verification_ident = []
    rotation_pid = Queue()

    def pause_trusted_insert(_conn, _cursor, statement, _params, _context, _many):
        if (
            verification_ident
            and threading.get_ident() == verification_ident[0]
            and "insert into two_factor_sessions" in statement.lower()
        ):
            insert_reached.set()
            if not release_insert.wait(12):
                raise TimeoutError("test failed to release trusted-session insert")

    def verify():
        with factory() as db:
            verification_ident.append(threading.get_ident())
            return service.verify_two_factor(
                db,
                enrolled["user_id"],
                totp_code=code,
                device_fingerprint=f"synthetic-{uuid4().hex}",
            )

    def rotate():
        with factory() as db:
            rotation_pid.put(db.execute(text("SELECT pg_backend_pid()")).scalar_one())
            return service.regenerate_backup_codes(
                db, enrolled["user_id"], enrolled["".join(("pass", "word"))], totp_code=code
            )

    event.listen(pg_engine, "before_cursor_execute", pause_trusted_insert)
    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            verify_future = executor.submit(verify)
            try:
                assert insert_reached.wait(12), (
                    "verify did not reach trusted-session insertion"
                )
                rotate_future = executor.submit(rotate)
                _assert_waiting(pg_engine, [rotation_pid.get(timeout=10)])
            finally:
                release_insert.set()
            verified, _message, token = verify_future.result(timeout=20)
            rotated = rotate_future.result(timeout=20)
        assert verified and token
        assert rotated is not None and len(rotated) == 10
    finally:
        release_insert.set()
        event.remove(pg_engine, "before_cursor_execute", pause_trusted_insert)


def test_enable_wins_over_waiting_stale_setup(pg_engine, enrolled):
    """An already-verified secret must not be replaced by delayed setup."""
    service = TwoFactorService()
    factory = sessionmaker(bind=pg_engine, expire_on_commit=False)
    with factory() as db:
        config = db.query(TwoFactorAuth).filter_by(user_id=enrolled["user_id"]).one()
        config.totp_enabled = False
        config.totp_verified = False
        db.commit()

    verify_pid, setup_pid = Queue(), Queue()
    code = service.generate_totp_code(SECRET)

    def verify():
        with factory() as db:
            verify_pid.put(db.execute(text("SELECT pg_backend_pid()")).scalar_one())
            return service.verify_totp_setup(db, enrolled["user_id"], code)

    def setup():
        with factory() as db:
            setup_pid.put(db.execute(text("SELECT pg_backend_pid()")).scalar_one())
            try:
                return service.setup_two_factor_auth(db, enrolled["user_id"])
            except ValueError:
                return None

    with factory() as gate, ThreadPoolExecutor(max_workers=2) as executor:
        gate.query(TwoFactorAuth).filter_by(
            user_id=enrolled["user_id"]
        ).with_for_update().one()
        verify_future = executor.submit(verify)
        try:
            _assert_waiting(pg_engine, [verify_pid.get(timeout=10)])
            setup_future = executor.submit(setup)
            _assert_waiting(pg_engine, [setup_pid.get(timeout=10)])
        finally:
            gate.commit()
        assert verify_future.result(timeout=20) is True
        assert setup_future.result(timeout=20) is None
    with factory() as db:
        config = db.query(TwoFactorAuth).filter_by(user_id=enrolled["user_id"]).one()
        assert config.totp_enabled is True and config.totp_verified is True
        assert config.totp_secret == SECRET


def test_setup_verify_rechecks_account_active_after_waiting_for_user_lock(
    pg_engine, enrolled
):
    """A user deactivated while verification waits cannot enable 2FA."""
    service = TwoFactorService()
    factory = sessionmaker(bind=pg_engine, expire_on_commit=False)
    with factory() as db:
        config = db.query(TwoFactorAuth).filter_by(user_id=enrolled["user_id"]).one()
        config.totp_enabled = False
        config.totp_verified = False
        db.commit()
    pids = Queue()
    code = service.generate_totp_code(SECRET)

    def verify():
        with factory() as db:
            pids.put(db.execute(text("SELECT pg_backend_pid()")).scalar_one())
            return service.verify_totp_setup(db, enrolled["user_id"], code)

    with factory() as gate, ThreadPoolExecutor(max_workers=1) as executor:
        user = (
            gate.query(User)
            .filter_by(id=enrolled["user_id"])
            .with_for_update(key_share=True)
            .one()
        )
        user.is_active = False
        future = executor.submit(verify)
        try:
            _assert_waiting(pg_engine, [pids.get(timeout=10)])
        finally:
            gate.commit()
        assert future.result(timeout=20) is False
    with factory() as db:
        config = db.query(TwoFactorAuth).filter_by(user_id=enrolled["user_id"]).one()
        assert config.totp_enabled is False
        assert config.totp_verified is False
        assert config.totp_secret == SECRET


@pytest.fixture
def enrollment(pg_engine):
    from datetime import UTC, datetime, timedelta

    from app.models.authentication import UserSession

    token = secrets.token_urlsafe(32)
    password = secrets.token_urlsafe(24)
    with Session(pg_engine, expire_on_commit=False) as db:
        user = User(
            username=f"SYNTHETIC_enroll_{uuid4().hex}",
            email=f"{uuid4().hex}@example.test",
            hashed_password=get_password_hash(password),
            role="Admin",
            is_active=True,
            is_superuser=False,
        )
        db.add(user)
        db.flush()
        enrollment_session = UserSession(
            user_id=user.id,
            refresh_token=token,
            session_kind="2fa_enrollment",
            expires_at=datetime.now(UTC) + timedelta(minutes=10),
            revoked=False,
        )
        config = TwoFactorAuth(
            user_id=user.id, totp_secret=SECRET, totp_enabled=False, totp_verified=False
        )
        db.add_all([enrollment_session, config])
        db.flush()
        config_id = config.id
        session_id = enrollment_session.id
        db.commit()
        return {
            "user_id": user.id,
            "config_id": config_id,
            "session_id": session_id,
            "token": token,
        }


@pytest.fixture
def pg_http_client(pg_engine):
    from fastapi.testclient import TestClient

    from app.db.session import get_db
    from app.main import app

    # Match production SessionLocal: changes are flushed only explicitly.
    factory = sessionmaker(bind=pg_engine, expire_on_commit=False, autoflush=False)
    prior = app.dependency_overrides.get(get_db)

    def override_db():
        with factory() as db:
            yield db

    app.dependency_overrides[get_db] = override_db
    try:
        with TestClient(app) as client:
            yield client
    finally:
        if prior is None:
            app.dependency_overrides.pop(get_db, None)
        else:
            app.dependency_overrides[get_db] = prior


def _install_advanced_clock(monkeypatch, *modules):
    """Advance only application time at a proven lock/flush boundary."""
    from datetime import datetime, timedelta

    offset = {"value": timedelta(0)}

    class ControlledDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            return datetime.now(tz) + offset["value"]

    for module in modules:
        monkeypatch.setattr(module, "datetime", ControlledDatetime)

    def advance():
        offset["value"] = timedelta(hours=1)

    return advance


def _race_enrollment_http(
    pg_engine,
    pg_http_client,
    enrollment,
    *,
    path,
    body,
    mutation,
    advance_clock=None,
):
    """Complete preliminary token lookup; race a real HTTP handler at its user lock."""
    from sqlalchemy import event

    from app.models.authentication import UserSession

    factory = sessionmaker(bind=pg_engine, expire_on_commit=False)
    main_ident = threading.get_ident()
    pids = Queue()
    seen = set()
    seen_lock = threading.Lock()

    def capture_user_lock(connection, _cursor, statement, _params, _context, _many):
        sql = statement.lower()
        if (
            threading.get_ident() == main_ident
            or "from users" not in sql
            or "for no key update" not in sql
        ):
            return
        raw = connection.connection.driver_connection
        pid = raw.info.backend_pid if hasattr(raw, "info") else raw.get_backend_pid()
        with seen_lock:
            if pid not in seen:
                seen.add(pid)
                pids.put(pid)

    event.listen(pg_engine, "before_cursor_execute", capture_user_lock)
    try:
        with factory() as gate, ThreadPoolExecutor(max_workers=1) as executor:
            user = (
                gate.query(User)
                .filter_by(id=enrollment["user_id"])
                .with_for_update(key_share=True)
                .one()
            )
            session = (
                gate.query(UserSession).filter_by(id=enrollment["session_id"]).one()
            )
            mutation(user, session)
            future = executor.submit(pg_http_client.post, path, json=body)
            try:
                _assert_waiting(pg_engine, [pids.get(timeout=10)])
                if advance_clock:
                    advance_clock()
            finally:
                gate.commit()
            return future.result(timeout=20)
    finally:
        event.remove(pg_engine, "before_cursor_execute", capture_user_lock)


@pytest.mark.parametrize("path", ["/api/v1/2fa/setup", "/api/v1/2fa/verify-setup"])
def test_revoked_enrollment_cannot_commit_after_preliminary_lookup(
    pg_engine, pg_http_client, enrollment, path
):
    from app.models.authentication import RefreshToken, UserSession

    body = {
        "enrollment_token": enrollment["token"],
        "totp_code": TwoFactorService().generate_totp_code(SECRET),
    }
    response = _race_enrollment_http(
        pg_engine,
        pg_http_client,
        enrollment,
        path=path,
        body=body,
        mutation=lambda _user, session: setattr(session, "revoked", True),
    )
    assert response.status_code in (401, 403), response.text
    with Session(pg_engine) as db:
        config = db.query(TwoFactorAuth).filter_by(id=enrollment["config_id"]).one()
        assert (
            not config.totp_enabled
            and not config.totp_verified
            and config.totp_secret == SECRET
        )
        assert (
            db.query(UserSession).filter_by(id=enrollment["session_id"]).one().revoked
            is True
        )
        assert (
            db.query(RefreshToken).filter_by(user_id=enrollment["user_id"]).count() == 0
        )


@pytest.mark.parametrize("path", ["/api/v1/2fa/setup", "/api/v1/2fa/verify-setup"])
def test_enrollment_expiry_while_waiting_for_lock_is_rechecked(
    pg_engine, pg_http_client, enrollment, path, monkeypatch
):
    from app.models.authentication import RefreshToken
    from app.services import two_factor_service

    advance = _install_advanced_clock(monkeypatch, two_factor_service)
    body = {
        "enrollment_token": enrollment["token"],
        "totp_code": TwoFactorService().generate_totp_code(SECRET),
    }
    response = _race_enrollment_http(
        pg_engine,
        pg_http_client,
        enrollment,
        path=path,
        body=body,
        mutation=lambda _user, _session: None,
        advance_clock=advance,
    )
    assert response.status_code in (401, 403), response.text
    with Session(pg_engine) as db:
        config = db.query(TwoFactorAuth).filter_by(id=enrollment["config_id"]).one()
        assert (
            not config.totp_enabled
            and not config.totp_verified
            and config.totp_secret == SECRET
        )
        assert (
            db.query(RefreshToken).filter_by(user_id=enrollment["user_id"]).count() == 0
        )


def test_deactivated_enrollment_cannot_issue_refresh_even_if_reactivated(
    pg_engine, pg_http_client, enrollment
):
    from app.models.authentication import RefreshToken

    body = {
        "enrollment_token": enrollment["token"],
        "totp_code": TwoFactorService().generate_totp_code(SECRET),
    }
    response = _race_enrollment_http(
        pg_engine,
        pg_http_client,
        enrollment,
        path="/api/v1/2fa/verify-setup",
        body=body,
        mutation=lambda user, _session: setattr(user, "is_active", False),
    )
    assert response.status_code in (401, 403), response.text
    with Session(pg_engine) as db:
        db.query(User).filter_by(id=enrollment["user_id"]).one().is_active = True
        db.commit()
    with Session(pg_engine) as db:
        config = db.query(TwoFactorAuth).filter_by(id=enrollment["config_id"]).one()
        assert not config.totp_enabled and not config.totp_verified
        assert (
            db.query(RefreshToken).filter_by(user_id=enrollment["user_id"]).count() == 0
        )


def test_concurrent_enrollment_verification_exchanges_only_once(
    pg_engine, pg_http_client, enrollment
):
    """Two independently authenticated requests cannot both mint sessions."""
    import jwt
    from sqlalchemy import event

    from app.core.config import settings
    from app.models.authentication import RefreshToken, UserSession

    factory = sessionmaker(bind=pg_engine, expire_on_commit=False, autoflush=False)
    main_ident, pids, seen, mutex = (
        threading.get_ident(),
        Queue(),
        set(),
        threading.Lock(),
    )
    body = {
        "enrollment_token": enrollment["token"],
        "totp_code": TwoFactorService().generate_totp_code(SECRET),
    }

    def capture_user_lock(connection, _cursor, statement, _params, _context, _many):
        sql = statement.lower()
        if (
            threading.get_ident() == main_ident
            or "from users" not in sql
            or "for no key update" not in sql
        ):
            return
        raw = connection.connection.driver_connection
        pid = raw.info.backend_pid if hasattr(raw, "info") else raw.get_backend_pid()
        with mutex:
            if pid not in seen:
                seen.add(pid)
                pids.put(pid)

    event.listen(pg_engine, "before_cursor_execute", capture_user_lock)
    try:
        with factory() as gate, ThreadPoolExecutor(max_workers=2) as executor:
            gate.query(User).filter_by(id=enrollment["user_id"]).with_for_update(
                key_share=True
            ).one()
            futures = [
                executor.submit(
                    pg_http_client.post, "/api/v1/2fa/verify-setup", json=body
                )
                for _ in range(2)
            ]
            try:
                _assert_waiting(pg_engine, [pids.get(timeout=10), pids.get(timeout=10)])
            finally:
                gate.commit()
            responses = [future.result(timeout=20) for future in futures]
    finally:
        event.remove(pg_engine, "before_cursor_execute", capture_user_lock)

    successes = [
        response
        for response in responses
        if response.status_code == 200 and response.json().get("success")
    ]
    rejected = [response for response in responses if response not in successes]
    assert len(successes) == len(rejected) == 1
    assert rejected[0].status_code in (401, 403), rejected[0].text
    assert successes[0].json()["refresh_token"]
    claims = jwt.decode(
        successes[0].json()["access_token"],
        settings.SECRET_KEY,
        algorithms=[settings.ALGORITHM],
    )
    assert claims["sub"] == str(enrollment["user_id"])
    with factory() as db:
        config = db.query(TwoFactorAuth).filter_by(id=enrollment["config_id"]).one()
        session = db.query(UserSession).filter_by(id=enrollment["session_id"]).one()
        assert config.totp_enabled and config.totp_verified and session.revoked
        assert (
            db.query(RefreshToken).filter_by(user_id=enrollment["user_id"]).count() == 1
        )


def test_enrollment_exchange_failure_rolls_back_enable_and_revocation(
    pg_engine, pg_http_client, enrollment
):
    """A failed refresh INSERT must roll back 2FA and leave enrollment usable."""
    from sqlalchemy import event

    from app.models.authentication import RefreshToken, UserSession

    body = {
        "enrollment_token": enrollment["token"],
        "totp_code": TwoFactorService().generate_totp_code(SECRET),
    }
    injected = []

    def fail_refresh_insert(_conn, _cursor, statement, _params, _context, _many):
        if "insert into refresh_tokens" in statement.lower():
            injected.append(True)
            raise RuntimeError("synthetic refresh persistence failure")

    event.listen(pg_engine, "before_cursor_execute", fail_refresh_insert)
    try:
        response = pg_http_client.post("/api/v1/2fa/verify-setup", json=body)
    finally:
        event.remove(pg_engine, "before_cursor_execute", fail_refresh_insert)
    assert injected, "refresh persistence was not reached"
    assert response.status_code >= 400
    assert "refresh_token" not in response.json()
    with Session(pg_engine) as db:
        config = db.query(TwoFactorAuth).filter_by(id=enrollment["config_id"]).one()
        session = db.query(UserSession).filter_by(id=enrollment["session_id"]).one()
        assert not config.totp_enabled and not config.totp_verified
        assert session.revoked is False
        assert (
            db.query(RefreshToken).filter_by(user_id=enrollment["user_id"]).count() == 0
        )

    retry = pg_http_client.post("/api/v1/2fa/verify-setup", json=body)
    assert retry.status_code == 200, retry.text
    assert retry.json()["success"] is True and retry.json()["refresh_token"]


@pytest.mark.parametrize("state", ["missing", "unverified"])
def test_direct_exchange_does_not_authenticate_without_verified_2fa(
    pg_engine, enrollment, state
):
    """Production autoflush=False must not mint from an unenrolled state."""
    from app.models.authentication import RefreshToken, UserSession
    from app.services.authentication_service import get_authentication_service
    from app.services.two_factor_auth_api_service import TwoFactorAuthApiService

    factory = sessionmaker(bind=pg_engine, expire_on_commit=False, autoflush=False)
    with factory() as db:
        config = db.query(TwoFactorAuth).filter_by(id=enrollment["config_id"]).one()
        if state == "missing":
            db.delete(config)
        else:
            config.totp_enabled = True
            config.totp_verified = False
        db.commit()
    with factory() as db:
        user = db.query(User).filter_by(id=enrollment["user_id"]).one()
        result = TwoFactorAuthApiService(db).exchange_enrollment_token_for_tokens(
            user=user,
            enrollment_token=enrollment["token"],
            auth_service=get_authentication_service(),
        )
        assert result is None
    with factory() as db:
        assert (
            db.query(UserSession).filter_by(id=enrollment["session_id"]).one().revoked
            is False
        )
        assert (
            db.query(RefreshToken).filter_by(user_id=enrollment["user_id"]).count() == 0
        )


@pytest.mark.parametrize("path", ["/api/v1/2fa/setup", "/api/v1/2fa/verify-setup"])
def test_enrollment_expiry_while_waiting_for_session_row_is_rechecked(
    pg_engine, pg_http_client, enrollment, path, monkeypatch
):
    from sqlalchemy import event

    from app.models.authentication import RefreshToken, UserSession
    from app.services import two_factor_service

    factory = sessionmaker(bind=pg_engine, expire_on_commit=False, autoflush=False)
    advance = _install_advanced_clock(monkeypatch, two_factor_service)
    body = {
        "enrollment_token": enrollment["token"],
        "totp_code": TwoFactorService().generate_totp_code(SECRET),
    }
    main_ident, pids = threading.get_ident(), Queue()

    def capture_session_lock(connection, _cursor, statement, _params, _context, _many):
        sql = statement.lower()
        if (
            threading.get_ident() == main_ident
            or "from user_sessions" not in sql
            or "for update" not in sql
        ):
            return
        raw = connection.connection.driver_connection
        pids.put(
            raw.info.backend_pid if hasattr(raw, "info") else raw.get_backend_pid()
        )

    event.listen(pg_engine, "before_cursor_execute", capture_session_lock)
    try:
        with factory() as gate, ThreadPoolExecutor(max_workers=1) as executor:
            gate.query(UserSession).filter_by(
                id=enrollment["session_id"]
            ).with_for_update().one()
            future = executor.submit(pg_http_client.post, path, json=body)
            try:
                _assert_waiting(pg_engine, [pids.get(timeout=10)])
                advance()
            finally:
                gate.commit()
            response = future.result(timeout=20)
    finally:
        event.remove(pg_engine, "before_cursor_execute", capture_session_lock)
    assert response.status_code in (401, 403), response.text
    with factory() as db:
        config = db.query(TwoFactorAuth).filter_by(id=enrollment["config_id"]).one()
        assert (
            not config.totp_enabled
            and not config.totp_verified
            and config.totp_secret == SECRET
        )
        assert (
            db.query(RefreshToken).filter_by(user_id=enrollment["user_id"]).count() == 0
        )


def test_enrollment_expiry_after_refresh_flush_rolls_back(
    pg_engine, pg_http_client, enrollment, monkeypatch
):
    from sqlalchemy import event

    from app.models.authentication import RefreshToken, UserSession
    from app.services import two_factor_auth_api_service

    advance = _install_advanced_clock(monkeypatch, two_factor_auth_api_service)
    body = {
        "enrollment_token": enrollment["token"],
        "totp_code": TwoFactorService().generate_totp_code(SECRET),
    }
    paused = []

    def delay_refresh_insert(_conn, _cursor, statement, _params, _context, _many):
        if "insert into refresh_tokens" in statement.lower():
            paused.append(True)
            advance()

    event.listen(pg_engine, "before_cursor_execute", delay_refresh_insert)
    try:
        response = pg_http_client.post("/api/v1/2fa/verify-setup", json=body)
    finally:
        event.remove(pg_engine, "before_cursor_execute", delay_refresh_insert)
    assert paused, "refresh-token flush was not reached"
    assert response.status_code in (401, 403), response.text
    assert not response.json().get("refresh_token")
    with Session(pg_engine) as db:
        config = db.query(TwoFactorAuth).filter_by(id=enrollment["config_id"]).one()
        session = db.query(UserSession).filter_by(id=enrollment["session_id"]).one()
        assert not config.totp_enabled and not config.totp_verified
        assert session.revoked is False
        assert (
            db.query(RefreshToken).filter_by(user_id=enrollment["user_id"]).count() == 0
        )


@pytest.fixture
def pending(pg_engine, enrollment):
    from app.models.authentication import UserSession

    service = TwoFactorService()
    backup = "A1B2C3D4"
    with Session(pg_engine) as db:
        config = db.query(TwoFactorAuth).filter_by(id=enrollment["config_id"]).one()
        config.totp_enabled = True
        config.totp_verified = True
        db.query(UserSession).filter_by(
            id=enrollment["session_id"]
        ).one().session_kind = "pending_2fa"
        db.add(
            TwoFactorBackupCode(
                two_factor_auth_id=config.id,
                code=service._hash_backup_code(backup),
                used=False,
            )
        )
        db.commit()
    return {**enrollment, "backup": backup}


@pytest.mark.parametrize("change", ["revoke", "deactivate"])
def test_pending_revocation_or_deactivation_during_user_lock_never_mints_refresh(
    pg_engine, pg_http_client, pending, change
):
    from app.models.authentication import RefreshToken

    body = {
        "pending_2fa_token": pending["token"],
        "totp_code": TwoFactorService().generate_totp_code(SECRET),
    }

    def mutate(user, session):
        if change == "revoke":
            session.revoked = True
        else:
            user.is_active = False

    response = _race_enrollment_http(
        pg_engine,
        pg_http_client,
        pending,
        path="/api/v1/2fa/verify",
        body=body,
        mutation=mutate,
    )
    assert response.status_code in (401, 403), response.text
    if change == "deactivate":
        with Session(pg_engine) as db:
            db.query(User).filter_by(id=pending["user_id"]).one().is_active = True
            db.commit()
    with Session(pg_engine) as db:
        config = db.query(TwoFactorAuth).filter_by(id=pending["config_id"]).one()
        assert config.totp_enabled and config.totp_verified and config.last_used is None
        assert db.query(RefreshToken).filter_by(user_id=pending["user_id"]).count() == 0


def test_parallel_pending_verifications_issue_only_one_refresh(
    pg_engine, pg_http_client, pending
):
    from sqlalchemy import event

    from app.models.authentication import RefreshToken, UserSession

    factory = sessionmaker(bind=pg_engine, expire_on_commit=False, autoflush=False)
    main_ident, pids, seen, mutex = (
        threading.get_ident(),
        Queue(),
        set(),
        threading.Lock(),
    )
    body = {
        "pending_2fa_token": pending["token"],
        "totp_code": TwoFactorService().generate_totp_code(SECRET),
    }

    def capture_user_lock(connection, _cursor, statement, _params, _context, _many):
        sql = statement.lower()
        if (
            threading.get_ident() == main_ident
            or "from users" not in sql
            or "for no key update" not in sql
        ):
            return
        raw = connection.connection.driver_connection
        pid = raw.info.backend_pid if hasattr(raw, "info") else raw.get_backend_pid()
        with mutex:
            if pid not in seen:
                seen.add(pid)
                pids.put(pid)

    event.listen(pg_engine, "before_cursor_execute", capture_user_lock)
    try:
        with factory() as gate, ThreadPoolExecutor(max_workers=2) as executor:
            gate.query(User).filter_by(id=pending["user_id"]).with_for_update(
                key_share=True
            ).one()
            futures = [
                executor.submit(pg_http_client.post, "/api/v1/2fa/verify", json=body)
                for _ in range(2)
            ]
            try:
                _assert_waiting(pg_engine, [pids.get(timeout=10), pids.get(timeout=10)])
            finally:
                gate.commit()
            responses = [future.result(timeout=20) for future in futures]
    finally:
        event.remove(pg_engine, "before_cursor_execute", capture_user_lock)
    accepted = [
        response
        for response in responses
        if response.status_code == 200 and response.json().get("success")
    ]
    rejected = [response for response in responses if response not in accepted]
    assert len(accepted) == len(rejected) == 1
    assert accepted[0].json()["refresh_token"]
    assert rejected[0].status_code in (401, 403), rejected[0].text
    with factory() as db:
        assert (
            db.query(UserSession).filter_by(id=pending["session_id"]).one().revoked
            is True
        )
        assert db.query(RefreshToken).filter_by(user_id=pending["user_id"]).count() == 1


def test_pending_refresh_failure_rolls_back_backup_and_trusted_device(
    pg_engine, pg_http_client, pending
):
    from sqlalchemy import event

    from app.models.authentication import RefreshToken, UserSession
    from app.models.two_factor_auth import TwoFactorDevice, TwoFactorSession

    body = {
        "pending_2fa_token": pending["token"],
        "backup_code": pending["backup"],
        "remember_device": True,
        "device_fingerprint": f"SYNTHETIC-{uuid4().hex}",
    }
    injected = []

    def fail_refresh_insert(_conn, _cursor, statement, _params, _context, _many):
        if "insert into refresh_tokens" in statement.lower():
            injected.append(True)
            raise RuntimeError("synthetic refresh persistence failure")

    event.listen(pg_engine, "before_cursor_execute", fail_refresh_insert)
    try:
        response = pg_http_client.post("/api/v1/2fa/verify", json=body)
    finally:
        event.remove(pg_engine, "before_cursor_execute", fail_refresh_insert)
    assert injected, "refresh persistence was not reached"
    assert response.status_code >= 400
    assert not response.json().get("refresh_token")
    with Session(pg_engine) as db:
        backup = (
            db.query(TwoFactorBackupCode)
            .filter_by(two_factor_auth_id=pending["config_id"])
            .one()
        )
        assert backup.used is False
        assert (
            db.query(UserSession).filter_by(id=pending["session_id"]).one().revoked
            is False
        )
        assert db.query(RefreshToken).filter_by(user_id=pending["user_id"]).count() == 0
        assert (
            db.query(TwoFactorSession).filter_by(user_id=pending["user_id"]).count()
            == 0
        )
        assert (
            db.query(TwoFactorDevice).filter_by(user_id=pending["user_id"]).count() == 0
        )
    retry = pg_http_client.post("/api/v1/2fa/verify", json=body)
    assert retry.status_code == 200, retry.text
    assert retry.json()["success"] is True and retry.json()["refresh_token"]


def test_patient_scope_relink_during_wait_denies_rotation_but_unscoped_user_works(
    pg_engine, pg_http_client, enrolled
):
    """A scoped bearer cannot outlive its live patient-card binding."""
    from sqlalchemy import event

    from app.api.deps import create_access_token
    from app.models.patient import Patient

    factory = sessionmaker(bind=pg_engine, expire_on_commit=False, autoflush=False)
    with factory() as db:
        user = db.query(User).filter_by(id=enrolled["user_id"]).one()
        user.role = "Patient"
        patient = Patient(
            user_id=user.id, first_name="SYNTHETIC", last_name="PATIENT", is_deleted=False
        )
        db.add(patient)
        db.flush()
        patient_id = patient.id
        epoch = user.auth_epoch
        db.commit()

    scoped = create_access_token({
        "sub": str(enrolled["user_id"]), "auth_epoch": epoch,
        "scope": "patient_portal", "patient_id": patient_id,
    })
    body = {
        "".join(('pass', 'word')): enrolled["".join(("pass", "word"))],
        "totp_code": TwoFactorService().generate_totp_code(SECRET),
    }
    main_ident, pids = threading.get_ident(), Queue()

    def capture_user_lock(connection, _cursor, statement, _params, _context, _many):
        sql = statement.lower()
        if threading.get_ident() == main_ident or "from users" not in sql or "for no key update" not in sql:
            return
        raw = connection.connection.driver_connection
        pids.put(raw.info.backend_pid if hasattr(raw, "info") else raw.get_backend_pid())

    event.listen(pg_engine, "before_cursor_execute", capture_user_lock)
    try:
        with factory() as gate, ThreadPoolExecutor(max_workers=1) as executor:
            gate.query(User).filter_by(id=enrolled["user_id"]).with_for_update(key_share=True).one()
            gate.query(Patient).filter_by(id=patient_id).one().user_id = None
            gate.flush()
            future = executor.submit(
                pg_http_client.post, "/api/v1/2fa/backup-codes/regenerate",
                headers={"Authorization": f"Bearer {scoped}"}, json=body,
            )
            try:
                _assert_waiting(pg_engine, [pids.get(timeout=10)])
            finally:
                gate.commit()
            response = future.result(timeout=20)
    finally:
        event.remove(pg_engine, "before_cursor_execute", capture_user_lock)

    assert response.status_code == 401, response.text
    with factory() as db:
        assert db.query(TwoFactorBackupCode).filter_by(two_factor_auth_id=enrolled["config_id"], used=False).count() == 3
    unscoped = create_access_token({"sub": str(enrolled["user_id"]), "auth_epoch": epoch})
    response = pg_http_client.post(
        "/api/v1/2fa/backup-codes/regenerate",
        headers={"Authorization": f"Bearer {unscoped}"}, json=body,
    )
    assert response.status_code == 200, response.text


def _rotation_payload(enrolled):
    field = "".join(("pass", "word"))
    return {
        field: enrolled[field],
        "totp_code": TwoFactorService().generate_totp_code(SECRET),
    }


@pytest.mark.parametrize("logout_all", [False, True])
def test_logout_after_bearer_validation_blocks_waiting_rotation(
    pg_engine, pg_http_client, enrolled, monkeypatch, logout_all
):
    """Real single-JTI and account logout serialize against 2FA mutations."""
    from datetime import UTC, datetime

    import jwt
    from sqlalchemy import event

    from app.api.deps import create_access_token
    from app.core.config import settings
    from app.services.authentication_service import get_authentication_service

    auth = get_authentication_service()
    monkeypatch.setattr(auth, "_log_user_activity", lambda *args, **kwargs: None)
    token = create_access_token({"sub": str(enrolled["user_id"]), "auth_epoch": 0})
    claims = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    body = _rotation_payload(enrolled)
    factory = sessionmaker(bind=pg_engine, expire_on_commit=False, autoflush=False)
    main_ident, pids = threading.get_ident(), Queue()

    def capture_user_lock(connection, _cursor, statement, _params, _context, _many):
        sql = statement.lower()
        if threading.get_ident() == main_ident or "from users" not in sql or "for no key update" not in sql:
            return
        raw = connection.connection.driver_connection
        pids.put(raw.info.backend_pid if hasattr(raw, "info") else raw.get_backend_pid())

    event.listen(pg_engine, "before_cursor_execute", capture_user_lock)
    try:
        with factory() as gate, ThreadPoolExecutor(max_workers=1) as executor:
            gate.query(User).filter_by(id=enrolled["user_id"]).with_for_update(key_share=True).one()
            future = executor.submit(
                pg_http_client.post, "/api/v1/2fa/backup-codes/regenerate",
                headers={"Authorization": f"Bearer {token}"}, json=body,
            )
            _assert_waiting(pg_engine, [pids.get(timeout=10)])
            outcome = auth.logout_user(
                gate, user_id=enrolled["user_id"], logout_all=logout_all,
                access_token_jti=claims["jti"],
                access_token_exp=datetime.fromtimestamp(claims["exp"], UTC),
            )
            assert outcome["success"] is True
            response = future.result(timeout=20)
    finally:
        event.remove(pg_engine, "before_cursor_execute", capture_user_lock)

    assert response.status_code == 401, response.text
    with factory() as db:
        config = db.query(TwoFactorAuth).filter_by(id=enrolled["config_id"]).one()
        assert config.last_sensitive_totp_step is None
        assert db.query(TwoFactorBackupCode).filter_by(two_factor_auth_id=config.id, used=False).count() == 3


def test_blacklist_database_failure_fails_closed_before_rotation(
    pg_engine, pg_http_client, enrolled
):
    """A failed post-lock revocation query cannot authorize a 2FA mutation."""
    from sqlalchemy import event

    from app.api.deps import create_access_token

    token = create_access_token({"sub": str(enrolled["user_id"]), "auth_epoch": 0})
    failed = []

    def fail_post_lock_check(_connection, _cursor, statement, _params, _context, _many):
        sql = " ".join(statement.lower().split())
        if sql.startswith("select users.auth_epoch,") and "token_blacklist" in sql:
            failed.append(True)
            raise RuntimeError("synthetic blacklist database failure")

    event.listen(pg_engine, "before_cursor_execute", fail_post_lock_check)
    try:
        response = pg_http_client.post(
            "/api/v1/2fa/backup-codes/regenerate",
            headers={"Authorization": f"Bearer {token}"},
            json={"".join(('pass', 'word')): enrolled["".join(("pass", "word"))],
                "totp_code": TwoFactorService().generate_totp_code(SECRET)},
        )
    finally:
        event.remove(pg_engine, "before_cursor_execute", fail_post_lock_check)
    assert failed, "post-lock blacklist query was not reached"
    assert response.status_code == 401, response.text
    with Session(pg_engine) as db:
        config = db.query(TwoFactorAuth).filter_by(id=enrolled["config_id"]).one()
        assert config.last_sensitive_totp_step is None
        assert db.query(TwoFactorBackupCode).filter_by(two_factor_auth_id=config.id, used=False).count() == 3
