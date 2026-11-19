"""Staging admin recovery serializes with account-wide revocation."""
import time
from concurrent.futures import ThreadPoolExecutor
from queue import Queue

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models.user import User
from app.services.token_blacklist_service import revoke_account_sessions_locked
from tests.integration.test_profile_contact_security_pg import account, pg_engine  # noqa: F401


def test_admin_recovery_waits_for_revocation(pg_engine, account, monkeypatch):
    from app.scripts import ensure_admin as script
    pids = Queue()
    class RecordingSession(Session):
        def __enter__(self):
            pids.put(self.execute(text("select pg_backend_pid()")).scalar_one())
            return self
    with Session(pg_engine) as db:
        username = db.get(User, account).username
    monkeypatch.setattr(script, "SessionLocal", lambda: RecordingSession(pg_engine))
    monkeypatch.setenv("ADMIN_USERNAME", username)
    monkeypatch.setenv("ADMIN_EMAIL", "recovery@example.com")
    monkeypatch.setenv("ENSURE_ADMIN_ALLOW_INITIALIZED", "1")
    monkeypatch.setenv("ENSURE_ADMIN_CONFIRM_INITIALIZED_OVERRIDE", "1")
    monkeypatch.delenv("ADMIN_RESET_PASSWORD", raising=False)
    with Session(pg_engine) as gate, ThreadPoolExecutor(max_workers=1) as pool:
        user = gate.query(User).filter_by(id=account).with_for_update(key_share=True).one()
        future = pool.submit(script.ensure_admin)
        pid = pids.get(timeout=10)
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            with pg_engine.connect() as con:
                if con.execute(text("select cardinality(pg_blocking_pids(:pid))"), {"pid": pid}).scalar_one():
                    break
            time.sleep(.02)
        else:
            raise AssertionError("admin recovery did not wait for User lock")
        revoke_account_sessions_locked(gate, user, revoke_password_resets=True)
        gate.commit()
        assert future.result(timeout=15)["updated"]
    with Session(pg_engine) as db:
        user = db.get(User, account)
        assert user.auth_epoch == 2 and user.email == "recovery@example.com" and user.role == "Admin"
