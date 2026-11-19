"""Operational writers interleave safely with account revocation in PostgreSQL."""
import sqlite3
import time
from concurrent.futures import ThreadPoolExecutor
from queue import Queue

import pytest
from sqlalchemy import event, text
from sqlalchemy.orm import Session

from app.models.authentication import PasswordResetToken, RefreshToken, UserSession
from app.models.user import User
from app.models.user_profile import UserProfile
from app.services.token_blacklist_service import revoke_account_sessions_locked
from tests.integration.test_profile_contact_security_pg import account, pg_engine  # noqa: F401
from tests.unit.test_migrate_users_to_postgres import _create_source_db


def wait_blocked(engine, pid):
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        with engine.connect() as con:
            if con.execute(text("select cardinality(pg_blocking_pids(:pid))"), {"pid": pid}).scalar_one():
                return
        time.sleep(.02)
    raise AssertionError("worker did not wait for User lock")


def source_for_account(tmp_path, engine, user_id):
    source = tmp_path / "synthetic.db"
    _create_source_db(source)
    with Session(engine) as db:
        user = db.get(User, user_id)
        username, email = user.username, user.email
    with sqlite3.connect(source) as sqlite:
        sqlite.execute("DELETE FROM users WHERE id=21")
        sqlite.execute("UPDATE users SET username=?, email=?, role='Doctor', hashed_password='synthetic-changed' WHERE id=20", (username, email))
    return source


def test_migration_waits_for_revoke_and_rechecks_live_epoch(pg_engine, account, tmp_path):
    from app.scripts.migrate_users_to_postgres import migrate_users
    source = source_for_account(tmp_path, pg_engine, account)
    pids = Queue()
    def capture(conn, cursor, statement, parameters, context, executemany):
        if statement.startswith("SELECT id, username, email, hashed_password"):
            cursor.execute("select pg_backend_pid()")
            pids.put(cursor.fetchone()[0])
    event.listen(pg_engine, "before_cursor_execute", capture)
    try:
        with Session(pg_engine) as gate, ThreadPoolExecutor(max_workers=1) as pool:
            user = gate.query(User).filter_by(id=account).with_for_update(key_share=True).one()
            future = pool.submit(migrate_users, source_sqlite_path=source, target_engine=pg_engine)
            wait_blocked(pg_engine, pids.get(timeout=10))
            revoke_account_sessions_locked(gate, user, revoke_password_resets=True)
            gate.commit()
            assert future.result(timeout=15).updated_count == 1
        with Session(pg_engine) as db:
            user = db.get(User, account)
            assert user.auth_epoch == 2 and user.role == "Doctor"
    finally:
        event.remove(pg_engine, "before_cursor_execute", capture)


def test_migration_rolls_back_everything_on_write_failure(pg_engine, account, tmp_path):
    from app.scripts.migrate_users_to_postgres import migrate_users
    source = source_for_account(tmp_path, pg_engine, account)
    def fail(conn, cursor, statement, parameters, context, executemany):
        if statement.startswith("UPDATE password_reset_tokens SET"):
            raise RuntimeError("synthetic failure")
    event.listen(pg_engine, "before_cursor_execute", fail)
    try:
        with pytest.raises(RuntimeError, match="synthetic failure"):
            migrate_users(source_sqlite_path=source, target_engine=pg_engine)
    finally:
        event.remove(pg_engine, "before_cursor_execute", fail)
    with Session(pg_engine) as db:
        assert db.get(User, account).auth_epoch == 0 and db.get(User, account).role == "Patient"
        assert db.query(UserProfile).filter_by(user_id=account).one().phone_verified
        assert not db.query(UserSession).filter_by(user_id=account).one().revoked
        assert not db.query(RefreshToken).filter_by(user_id=account).one().revoked
        assert not db.query(PasswordResetToken).filter_by(user_id=account).one().used


@pytest.mark.parametrize("writer", ["roles", "smoke"])
def test_provisioning_waits_for_revoke(pg_engine, account, monkeypatch, writer):
    from app.db import session as db_module
    from app.scripts import ensure_roles, ensure_smoke_users

    pids = Queue()
    class RecordingSession(Session):
        def execute(self, *args, **kwargs):
            if not hasattr(self, "reported_pid"):
                self.reported_pid = True
                pids.put(self.connection().exec_driver_sql("select pg_backend_pid()").scalar_one())
            return super().execute(*args, **kwargs)
    with Session(pg_engine) as db:
        user = db.get(User, account)
        username, email = user.username, user.email
    def factory():
        return RecordingSession(pg_engine)
    if writer == "roles":
        monkeypatch.setattr(db_module, "SessionLocal", factory)
        monkeypatch.setattr(ensure_roles, "USERS", [(username, "Registrar", email)])
        monkeypatch.setenv("CONFIRM_ENSURE_ROLES", "1")
        monkeypatch.delenv(f"ENSURE_ROLES_{username.upper()}_PASSWORD", raising=False)
        run = ensure_roles.upsert_users
    else:
        monkeypatch.setattr(ensure_smoke_users, "SessionLocal", factory)
        monkeypatch.setattr(ensure_smoke_users, "SMOKE_USERS", [(username, "Registrar", email)])
        monkeypatch.setattr(ensure_smoke_users, "RETIRED_SMOKE_USERNAMES", ())
        monkeypatch.setenv("SMOKE_USER_PASSWORD", "SYNTHETIC-test-password")
        run = ensure_smoke_users.ensure_smoke_users
    with Session(pg_engine) as gate, ThreadPoolExecutor(max_workers=1) as pool:
        user = gate.query(User).filter_by(id=account).with_for_update(key_share=True).one()
        future = pool.submit(run)
        wait_blocked(pg_engine, pids.get(timeout=10))
        revoke_account_sessions_locked(gate, user, revoke_password_resets=True)
        gate.commit()
        future.result(timeout=15)
    with Session(pg_engine) as db:
        user = db.get(User, account)
        assert user.auth_epoch == 2 and user.role == "Registrar"
