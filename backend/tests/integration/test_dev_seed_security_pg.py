"""Development issuer and seed keep live PostgreSQL auth state consistent."""
import os
import time
from concurrent.futures import ThreadPoolExecutor
from queue import Queue

import jwt
import pytest
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.authentication import PasswordResetToken, RefreshToken, UserSession
from app.models.user import User
from app.models.user_profile import UserProfile
from app.scripts import dev_seed
from app.services.token_blacklist_service import revoke_account_sessions_locked
from tests.integration.test_profile_contact_security_pg import account, pg_engine  # noqa: F401


def wait_blocked(engine, pid):
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        with engine.connect() as con:
            if con.execute(text("select cardinality(pg_blocking_pids(:pid))"), {"pid": pid}).scalar_one():
                return
        time.sleep(.02)
    raise AssertionError("seed did not wait for the User lock")


def spec_for(engine, user_id):
    with Session(engine) as db:
        user = db.get(User, user_id)
        return dev_seed.DemoUserSpec(user.email, "Registrar", "SYNTHETIC", "Registrar", "Front Desk", "+998901234567")


def test_seed_waits_for_revocation(pg_engine, account, monkeypatch):
    spec = spec_for(pg_engine, account)
    monkeypatch.setattr(dev_seed, "DEMO_USERS", (spec,))
    monkeypatch.setenv("DEV_DEMO_PASSCODE", "SYNTHETIC-new-password")
    pids = Queue()
    def worker():
        with Session(pg_engine, autoflush=False) as db:
            pids.put(db.execute(text("select pg_backend_pid()")).scalar_one())
            dev_seed.upsert_demo_users(db)
    with Session(pg_engine) as gate, ThreadPoolExecutor(max_workers=1) as pool:
        user = gate.query(User).filter_by(id=account).with_for_update(key_share=True).one()
        future = pool.submit(worker)
        wait_blocked(pg_engine, pids.get(timeout=10))
        revoke_account_sessions_locked(gate, user, revoke_password_resets=True)
        gate.commit()
        future.result(timeout=20)
    with Session(pg_engine) as db:
        user = db.get(User, account)
        assert user.auth_epoch == 2 and user.role == "Registrar"


def test_seed_failure_rolls_back_auth_mutation(pg_engine, account, monkeypatch):
    from app.services import token_blacklist_service as service
    spec = spec_for(pg_engine, account)
    monkeypatch.setattr(dev_seed, "DEMO_USERS", (spec,))
    monkeypatch.setenv("DEV_DEMO_PASSCODE", "SYNTHETIC-new-password")
    original = service.revoke_account_sessions_locked
    def fail(*args, **kwargs):
        original(*args, **kwargs)
        raise RuntimeError("synthetic failure")
    monkeypatch.setattr(service, "revoke_account_sessions_locked", fail)
    with Session(pg_engine) as db:
        with pytest.raises(RuntimeError, match="synthetic failure"):
            dev_seed.upsert_demo_users(db)
        db.rollback()
    with Session(pg_engine) as db:
        assert db.get(User, account).auth_epoch == 0
        assert db.get(User, account).role == "Patient"
        assert db.query(UserProfile).filter_by(user_id=account).one().phone_verified
        assert not db.query(UserSession).filter_by(user_id=account).one().revoked
        assert not db.query(RefreshToken).filter_by(user_id=account).one().revoked
        assert not db.query(PasswordResetToken).filter_by(user_id=account).one().used


@pytest.mark.parametrize("by_id", [False, True])
def test_dev_token_uses_current_id_and_epoch(pg_engine, account, monkeypatch, capsys, by_id):
    from app.core.user_token_claims import (
        is_user_access_claims,
        user_auth_epoch_matches,
    )
    from app.scripts.mint_dev_token import mint_dev_token
    with Session(pg_engine) as db:
        user = db.get(User, account)
        user.auth_epoch = 7
        username = user.username
        db.commit()
        schema = db.execute(text("select current_schema()" )).scalar_one()
    url = make_url(os.environ["DATABASE_URL"]).update_query_dict({"options": f"-csearch_path={schema}"})
    monkeypatch.setenv("DATABASE_URL", url.render_as_string(hide_password=False))
    monkeypatch.setenv("ENV", "dev")
    monkeypatch.delenv("APP_ENV", raising=False)
    monkeypatch.delenv("ENVIRONMENT", raising=False)
    monkeypatch.setenv("CONFIRM_MINT_DEV_TOKEN", "1")
    monkeypatch.setenv("MINT_DEV_TOKEN_SUBJECT", str(account) if by_id else username)
    token = mint_dev_token()
    claims = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    assert claims["sub"] == str(account) and claims["auth_epoch"] == 7
    assert claims["jti"] and is_user_access_claims(claims)
    assert not capsys.readouterr().out
    with Session(pg_engine) as db:
        user = db.get(User, account)
        user.auth_epoch = 8
        user.is_active = False
        db.commit()
        assert not user_auth_epoch_matches(claims, user.auth_epoch)
    with pytest.raises(SystemExit):
        mint_dev_token()
    assert not capsys.readouterr().out
