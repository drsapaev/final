"""Recovery dispatch must revalidate authority after the SMTP await (PostgreSQL)."""
from __future__ import annotations

import asyncio
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import jwt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session
from sqlalchemy.schema import CreateSchema, DropSchema

from app.core.config import settings
from app.db.base_class import Base
from app.db.session import get_db
from app.main import app
from app.models.two_factor_auth import TwoFactorAuth, TwoFactorRecovery
from app.models.user import User
from app.services.token_blacklist_service import token_blacklist_service
from app.services.two_factor_service import get_two_factor_service

pytestmark = pytest.mark.integration
REQUEST = "/api/v1/2fa/recovery/request"


@pytest.fixture(scope="module")
def pg_engine():
    raw = os.environ.get("DATABASE_URL", "")
    if not raw or make_url(raw).get_backend_name() != "postgresql":
        if os.environ.get("CI", "").lower() == "true":
            pytest.fail("CI requires PostgreSQL DATABASE_URL")
        pytest.skip("requires disposable PostgreSQL")
    url = make_url(raw)
    if os.environ.get("CI", "").lower() != "true" and not (url.database or "").startswith("clinic_test"):
        pytest.skip("requires disposable clinic_test database")
    schema = "test_recovery_race_" + uuid4().hex
    admin = create_engine(url)
    with admin.begin() as connection:
        connection.execute(CreateSchema(schema))
    engine = create_engine(url, pool_size=8, connect_args={
        "options": f"-csearch_path={schema} -cstatement_timeout=15000 -clock_timeout=10000"
    })
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
def account(pg_engine):
    with Session(pg_engine, expire_on_commit=False) as db:
        user = User(username="SYNTHETIC_" + uuid4().hex, role="Doctor", is_active=True,
                    is_superuser=False, hashed_password="synthetic")
        db.add(user)
        db.flush()
        config = TwoFactorAuth(user_id=user.id, totp_secret="SYNTHETIC",
            totp_enabled=True, totp_verified=True, recovery_enabled=True,
            recovery_email="synthetic@example.test")
        db.add(config)
        db.flush()
        old = TwoFactorRecovery(two_factor_auth_id=config.id, recovery_type="email",
            recovery_value="synthetic@example.test", recovery_token="SYNTHETIC_OLD",
            verified=False, expires_at=datetime.now(UTC) + timedelta(hours=1))
        db.add(old)
        db.commit()
        return user.id, config.id


@pytest.fixture
def pg_client(pg_engine):
    def override_db():
        with Session(pg_engine, expire_on_commit=False) as db:
            yield db
    app.dependency_overrides[get_db] = override_db
    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides.pop(get_db, None)


def token_for(user_id, *, jti, expiry):
    return jwt.encode({"sub": str(user_id), "type": "access", "auth_epoch": 0,
                       "jti": jti, "exp": expiry}, settings.SECRET_KEY,
                      algorithm=settings.ALGORITHM)


def post(client, token):
    return client.post(REQUEST, headers={"Authorization": f"Bearer {token}"},
                       json={"recovery_type": "email", "recovery_value": "ignored"})


def rows(engine, config_id):
    with Session(engine) as db:
        return [(row.recovery_token, row.verified) for row in db.query(TwoFactorRecovery)
                .filter_by(two_factor_auth_id=config_id).order_by(TwoFactorRecovery.id)]


@pytest.mark.parametrize("change", ["epoch", "deactivated", "logout", "contact", "expiry"])
def test_revocation_during_delivery_does_not_mutate_recovery(
    pg_engine, account, pg_client, monkeypatch, change
):
    user_id, config_id = account
    started, resume = threading.Event(), threading.Event()
    sent = []
    expiry = datetime.now(UTC) + timedelta(seconds=3 if change == "expiry" else 300)
    jti = uuid4().hex
    token = token_for(user_id, jti=jti, expiry=expiry)

    async def fake_send(**kwargs):
        sent.append(kwargs["text_content"].split("восстановления: ")[-1].split()[0])
        started.set()
        assert await asyncio.to_thread(resume.wait, 10)
        return True, "sent"

    monkeypatch.setattr(get_two_factor_service().email_service, "send_email_enhanced", fake_send)
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(post, pg_client, token)
        try:
            assert started.wait(10)
            with Session(pg_engine) as db:
                # This update/blacklist must complete while SMTP is stalled.
                if change == "logout":
                    assert token_blacklist_service.blacklist_token(db, jti, expiry, user_id)
                elif change == "epoch":
                    db.query(User).filter_by(id=user_id).update({"auth_epoch": 1})
                    db.commit()
                elif change == "deactivated":
                    db.query(User).filter_by(id=user_id).update({"is_active": False})
                    db.commit()
                elif change == "contact":
                    db.query(TwoFactorAuth).filter_by(id=config_id).update(
                        {"recovery_email": "changed@example.test"})
                    db.commit()
                else:
                    while datetime.now(UTC) < expiry + timedelta(seconds=1):
                        time.sleep(0.05)
        finally:
            resume.set()
        response = future.result(timeout=15)
    assert response.status_code == (400 if change == "contact" else 401), response.text
    assert rows(pg_engine, config_id) == [("SYNTHETIC_OLD", False)]
    assert sent[0] not in response.text


def test_database_lock_wait_rechecks_epoch(pg_engine, account, pg_client, monkeypatch):
    user_id, config_id = account
    started, resume, locking = threading.Event(), threading.Event(), threading.Event()
    worker_pid = []
    token = token_for(user_id, jti=uuid4().hex, expiry=datetime.now(UTC) + timedelta(minutes=5))

    async def fake_send(**_kwargs):
        started.set()
        assert await asyncio.to_thread(resume.wait, 10)
        return True, "sent"

    def inspect_query(conn, cursor, statement, parameters, context, executemany):
        if "FOR NO KEY UPDATE" in statement and "users" in statement:
            worker_pid.append(conn.connection.driver_connection.info.backend_pid)
            locking.set()

    monkeypatch.setattr(get_two_factor_service().email_service, "send_email_enhanced", fake_send)
    try:
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(post, pg_client, token)
            assert started.wait(10)
            with Session(pg_engine) as gate:
                user = gate.query(User).filter_by(id=user_id).with_for_update(key_share=True).one()
                event.listen(pg_engine, "before_cursor_execute", inspect_query)
                resume.set()
                assert locking.wait(10)
                deadline = time.monotonic() + 10
                while time.monotonic() < deadline:
                    with pg_engine.connect() as check:
                        blocked = check.execute(text("SELECT cardinality(pg_blocking_pids(:pid))"),
                                                {"pid": worker_pid[0]}).scalar_one()
                    if blocked:
                        break
                    time.sleep(0.02)
                assert blocked, "request must wait on the user's row lock"
                user.auth_epoch = 1
                gate.commit()
            response = future.result(timeout=15)
        assert response.status_code == 401
        assert rows(pg_engine, config_id) == [("SYNTHETIC_OLD", False)]
    finally:
        resume.set()
        event.remove(pg_engine, "before_cursor_execute", inspect_query)
