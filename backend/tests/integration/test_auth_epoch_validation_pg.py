"""PostgreSQL proof of fresh user-generation checks and serialized revocation."""

from __future__ import annotations

import asyncio
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from queue import Queue
from uuid import uuid4

import jwt
import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session
from sqlalchemy.schema import CreateSchema, DropSchema

from app.api.deps import get_current_user
from app.api.v1.endpoints.websocket_auth import resolve_websocket_token_user
from app.core.config import settings
from app.db.base_class import Base
from app.models.authentication import RefreshToken, TokenBlacklist, UserSession
from app.models.user import User
from app.services.token_blacklist_service import (
    TokenBlacklistService,
    bump_user_auth_epoch,
)

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def epoch_pg_engine():
    url = os.getenv("AUTH_EPOCH_VALIDATION_TEST_URL", "").strip()
    ci = os.getenv("CI", "").lower() == "true"
    if not url and ci:
        from tests._pg_admin_guard import is_local_admin_dsn

        candidate = os.getenv("DATABASE_URL", "").strip()
        if candidate and is_local_admin_dsn(candidate) and make_url(candidate).database == "clinicdb":
            url = candidate
    if not url:
        if ci:
            pytest.fail("CI requires an isolated PostgreSQL auth-generation test")
        pytest.skip("set AUTH_EPOCH_VALIDATION_TEST_URL to a disposable PostgreSQL database")
    if make_url(url).get_backend_name() != "postgresql":
        pytest.fail("auth-generation integration test requires PostgreSQL")

    schema = f"test_auth_epoch_{uuid4().hex}"
    admin_engine = create_engine(url, pool_pre_ping=True)
    with admin_engine.begin() as connection:
        connection.execute(CreateSchema(schema))
    engine = create_engine(
        url,
        pool_pre_ping=True,
        connect_args={"options": f"-csearch_path={schema} -cstatement_timeout=15000 -clock_timeout=10000"},
    )
    try:
        import app.db.base  # noqa: F401

        Base.metadata.create_all(
            engine,
            tables=[User.__table__, TokenBlacklist.__table__, UserSession.__table__, RefreshToken.__table__],
        )
        yield engine
    finally:
        engine.dispose()
        with admin_engine.begin() as connection:
            connection.execute(DropSchema(schema, cascade=True))
        admin_engine.dispose()


def _token(user_id: int, epoch: int) -> str:
    return jwt.encode(
        {
            "sub": str(user_id),
            "jti": str(uuid4()),
            "auth_epoch": epoch,
            "exp": datetime.now(UTC) + timedelta(minutes=5),
        },
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM,
    )


def test_recheck_observes_committed_epoch_in_a_reused_session(epoch_pg_engine):
    username = f"SYNTHETIC_epoch_{uuid4().hex}"
    with Session(epoch_pg_engine, expire_on_commit=False) as setup:
        user = User(username=username, hashed_password="synthetic", role="Doctor", is_active=True)
        setup.add(user)
        setup.commit()
        user_id = user.id
    token = _token(user_id, 0)
    with Session(epoch_pg_engine, expire_on_commit=False) as held:
        assert asyncio.run(get_current_user(token=token, db=held)).id == user_id
        assert resolve_websocket_token_user(token, held).id == user_id
        with Session(epoch_pg_engine) as writer:
            assert bump_user_auth_epoch(writer, user_id) == 1
            writer.commit()
        with pytest.raises(HTTPException):
            asyncio.run(get_current_user(token=token, db=held))
        assert resolve_websocket_token_user(token, held) is None
        assert asyncio.run(get_current_user(token=_token(user_id, 1), db=held)).id == user_id


def test_epoch_bump_waits_for_account_lock_and_uses_latest_committed_value(epoch_pg_engine):
    with Session(epoch_pg_engine, expire_on_commit=False) as setup:
        user = User(username=f"SYNTHETIC_lock_{uuid4().hex}", hashed_password="synthetic", is_active=True)
        setup.add(user)
        setup.commit()
        user_id = user.id

    pids: Queue[int] = Queue()
    start = threading.Event()

    def bump():
        with Session(epoch_pg_engine) as worker:
            pids.put(worker.execute(text("SELECT pg_backend_pid()")).scalar_one())
            assert start.wait(10)
            result = bump_user_auth_epoch(worker, user_id)
            worker.commit()
            return result

    with Session(epoch_pg_engine) as holder, ThreadPoolExecutor(max_workers=1) as executor:
        locked = holder.query(User).filter_by(id=user_id).with_for_update(key_share=True).one()
        future = executor.submit(bump)
        pid = pids.get(timeout=10)
        start.set()
        deadline = time.monotonic() + 10
        try:
            while time.monotonic() < deadline:
                with epoch_pg_engine.connect() as observer:
                    if observer.execute(text("SELECT cardinality(pg_blocking_pids(:pid))"), {"pid": pid}).scalar_one():
                        break
                time.sleep(0.02)
            else:
                pytest.fail("epoch bump did not wait for the account row lock")
            locked.auth_epoch = 1
            holder.commit()
        finally:
            holder.rollback()
        assert future.result(timeout=15) == 2

    with Session(epoch_pg_engine) as check:
        assert check.query(User.auth_epoch).filter_by(id=user_id).scalar() == 2


def test_individual_token_revocation_waits_for_account_lock(epoch_pg_engine):
    with Session(epoch_pg_engine, expire_on_commit=False) as setup:
        user = User(username=f"SYNTHETIC_jti_{uuid4().hex}", hashed_password="synthetic", is_active=True)
        setup.add(user)
        setup.commit()
        user_id = user.id

    jti = str(uuid4())
    pids: Queue[int] = Queue()
    start = threading.Event()

    def revoke():
        with Session(epoch_pg_engine) as worker:
            pids.put(worker.execute(text("SELECT pg_backend_pid()")).scalar_one())
            assert start.wait(10)
            return TokenBlacklistService.blacklist_token(
                worker, jti, datetime.now(UTC) + timedelta(minutes=5), user_id=user_id
            )

    with Session(epoch_pg_engine) as holder, ThreadPoolExecutor(max_workers=1) as executor:
        holder.query(User).filter_by(id=user_id).with_for_update(key_share=True).one()
        future = executor.submit(revoke)
        pid = pids.get(timeout=10)
        start.set()
        deadline = time.monotonic() + 10
        try:
            while time.monotonic() < deadline:
                with epoch_pg_engine.connect() as observer:
                    if observer.execute(text("SELECT cardinality(pg_blocking_pids(:pid))"), {"pid": pid}).scalar_one():
                        break
                time.sleep(0.02)
            else:
                pytest.fail("individual revocation did not wait for the account row lock")
            holder.commit()
        finally:
            holder.rollback()
        assert future.result(timeout=15)

    with Session(epoch_pg_engine) as check:
        assert TokenBlacklistService.is_token_blacklisted(check, jti, user_id=user_id)
