"""PostgreSQL proof that concurrent 2FA failures serialize per account."""

from __future__ import annotations

import os
import threading
from time import time
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.schema import CreateSchema, DropSchema

from app.db.base_class import Base
from app.models.two_factor_auth import TwoFactorAuth
from app.models.user import User
from app.services.two_factor_service import TwoFactorService

pytestmark = pytest.mark.integration

TOTP_SECRET = "JBSWY3DPEHPK3PXP"
CONCURRENT_ATTEMPTS = 8


@pytest.fixture(scope="module")
def pg_2fa_engine():
    is_ci = os.environ.get("CI", "").lower() == "true"
    raw_url = os.environ.get("DATABASE_URL", "").strip()
    if not raw_url:
        if is_ci:
            pytest.fail("CI must provide PostgreSQL DATABASE_URL for 2FA lockout proof")
        pytest.skip("2FA lockout concurrency proof requires PostgreSQL DATABASE_URL")
    url = make_url(raw_url)
    if url.get_backend_name() != "postgresql":
        if is_ci:
            pytest.fail("CI must run 2FA lockout concurrency proof against PostgreSQL")
        pytest.skip("2FA lockout concurrency proof requires PostgreSQL")
    if not is_ci and not (url.database or "").startswith("clinic_test"):
        pytest.skip("use CI or an explicitly disposable clinic_test database")

    schema = "test_2fa_lockout_" + uuid4().hex
    admin_engine = create_engine(url, pool_pre_ping=True)
    try:
        with admin_engine.begin() as connection:
            connection.execute(CreateSchema(schema))
    except Exception as exc:  # noqa: BLE001 - environmental skip only
        admin_engine.dispose()
        if is_ci:
            pytest.fail(f"CI disposable PostgreSQL schema unavailable: {exc}")
        pytest.skip(f"disposable PostgreSQL schema unavailable: {exc}")

    engine = create_engine(
        url,
        pool_pre_ping=True,
        pool_size=CONCURRENT_ATTEMPTS,
        max_overflow=0,
        connect_args={
            "options": (
                f"-csearch_path={schema} "
                "-cstatement_timeout=10000 -clock_timeout=10000"
            )
        },
    )
    try:
        # The test owns a uniquely named disposable schema; it never mutates
        # the shared/public schema or applies DDL to application data.
        import app.db.base  # noqa: F401 - register all model metadata

        Base.metadata.create_all(engine)
        yield engine
    finally:
        engine.dispose()
        with admin_engine.begin() as connection:
            connection.execute(DropSchema(schema, cascade=True))
        admin_engine.dispose()


@pytest.mark.parametrize("code_kind", ["totp", "backup", "recovery"])
def test_concurrent_wrong_codes_increment_one_account_counter_serially(
    pg_2fa_engine, code_kind
):
    session_factory = sessionmaker(bind=pg_2fa_engine, expire_on_commit=False)
    service = TwoFactorService()
    user_id: int

    with Session(pg_2fa_engine) as db:
        user = User(
            username=f"2fa-lock-{uuid4().hex[:16]}",
            email=f"2fa-lock-{uuid4().hex[:16]}@example.test",
            hashed_password="synthetic-unused-password-hash",
        )
        db.add(user)
        db.flush()
        db.add(
            TwoFactorAuth(
                user_id=user.id,
                totp_secret=TOTP_SECRET,
                totp_enabled=True,
                totp_verified=True,
            )
        )
        db.commit()
        user_id = user.id

    now = int(time())
    valid_codes = {
        service.generate_totp_code(TOTP_SECRET, now + offset * 30)
        for offset in (-1, 0, 1)
    }
    wrong_code = service.generate_totp_code(TOTP_SECRET, now - 3600)
    while wrong_code in valid_codes:
        wrong_code = f"{(int(wrong_code) + 1) % 1_000_000:06d}"
    invalid_code_arguments = {
        "totp": {"totp_code": wrong_code},
        "backup": {"backup_code": "synthetic-invalid-backup-code"},
        "recovery": {"recovery_token": "synthetic-invalid-recovery-token"},
    }

    all_selects_started = threading.Barrier(CONCURRENT_ATTEMPTS)
    unprotected_reads_finished = threading.Barrier(CONCURRENT_ATTEMPTS)
    observed_selects = 0
    observed_selects_lock = threading.Lock()

    def is_auth_read(statement: str) -> bool:
        normalized = statement.lower()
        return normalized.lstrip().startswith("select") and (
            "from two_factor_auth" in normalized
        )

    def before_cursor_execute(
        _connection, _cursor, statement, _parameters, _context, _executemany
    ):
        nonlocal observed_selects
        if is_auth_read(statement):
            with observed_selects_lock:
                observed_selects += 1

    def after_cursor_execute(
        _connection, _cursor, statement, _parameters, _context, _executemany
    ):
        # On the vulnerable implementation this holds every independent
        # transaction after reading the same old counter and before service
        # code can update it. With SELECT FOR UPDATE the database itself
        # serializes these reads, so the extra barrier must not apply.
        if is_auth_read(statement) and "for update" not in statement.lower():
            unprotected_reads_finished.wait(timeout=10)

    event.listen(pg_2fa_engine, "before_cursor_execute", before_cursor_execute)
    event.listen(pg_2fa_engine, "after_cursor_execute", after_cursor_execute)

    def attempt() -> tuple[bool, str]:
        with session_factory() as db:
            # All workers start together before the shared User lock. Waiting
            # at the later 2FA query would deadlock the correctly serialized
            # implementation, which now locks User before TwoFactorAuth.
            all_selects_started.wait(timeout=10)
            success, message, _ = service.verify_two_factor(
                db, user_id, **invalid_code_arguments[code_kind]
            )
            return success, message

    try:
        from concurrent.futures import ThreadPoolExecutor

        with ThreadPoolExecutor(max_workers=CONCURRENT_ATTEMPTS) as executor:
            results = list(
                executor.map(lambda _: attempt(), range(CONCURRENT_ATTEMPTS))
            )
    finally:
        event.remove(pg_2fa_engine, "before_cursor_execute", before_cursor_execute)
        event.remove(pg_2fa_engine, "after_cursor_execute", after_cursor_execute)

    assert observed_selects == CONCURRENT_ATTEMPTS
    assert all(not success for success, _ in results)
    assert all(not message.startswith("Verification error:") for _, message in results)

    with Session(pg_2fa_engine) as db:
        stored = db.query(TwoFactorAuth).filter_by(user_id=user_id).one()
        assert stored.failed_attempts == service.max_verify_attempts
        assert stored.locked_until is not None

    assert any("temporarily locked" in message for _, message in results)
