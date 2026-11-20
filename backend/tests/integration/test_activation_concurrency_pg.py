"""Real PostgreSQL activation serialization and public status contract."""
from __future__ import annotations

import os
import secrets
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import pytest
from fastapi import HTTPException, Request
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session
from sqlalchemy.schema import CreateSchema, DropSchema

from app.api.deps import get_db
from app.core import activation as activation_core
from app.core import activation_rate_limit as budget
from app.core.security import get_password_hash
from app.db.base_class import Base
from app.main import app
from app.models.activation import Activation, ActivationStatus
from app.models.user import User
from tests.conftest import mint_access_token
from tests.integration.test_setup_api import build_payload

pytestmark = pytest.mark.integration


@pytest.fixture
def pg_engine():
    raw = os.getenv("DATABASE_URL", "").strip()
    ci = os.getenv("CI", "").lower() == "true"
    if not raw or make_url(raw).get_backend_name() != "postgresql":
        if ci:
            pytest.fail("CI requires PostgreSQL DATABASE_URL")
        pytest.skip("requires a disposable PostgreSQL DATABASE_URL")
    url = make_url(raw)
    if not ci and not (url.database or "").startswith("clinic_test"):
        pytest.skip("requires explicitly disposable clinic_test database")
    schema = "test_activation_" + uuid4().hex
    admin = create_engine(url, pool_pre_ping=True)
    with admin.begin() as connection:
        connection.execute(CreateSchema(schema))
    engine = create_engine(
        url, pool_pre_ping=True, pool_size=6,
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


def test_budget_is_atomic_shared_and_not_refunded_by_rejected_attempts(pg_engine, monkeypatch):
    monkeypatch.setattr(budget, "_testing_bypass", lambda: False)
    scope = {"type": "http", "method": "POST", "path": "/", "headers": [],
             "client": ("192.0.2.1", 123), "server": ("testserver", 80), "scheme": "http"}
    def attempt(_):
        with Session(pg_engine) as db:
            try:
                budget.enforce_activation_budget(Request(scope), db)
                db.rollback()  # The independently committed budget must survive.
                return 200
            except HTTPException as exc:
                return exc.status_code
    with ThreadPoolExecutor(max_workers=20) as pool:
        results = list(pool.map(attempt, range(20)))
    assert results.count(200) == 5 and results.count(429) == 15
    with pg_engine.connect() as conn:
        rows = conn.execute(text("SELECT scope, attempts FROM activation_rate_budgets")).all()
    assert sorted(row.attempts for row in rows) == [5, 5]
    assert "192.0.2.1" not in repr(rows)
    second = {**scope, "client": ("192.0.2.2", 123)}
    with Session(pg_engine) as db:
        budget.enforce_activation_budget(Request(second), db)
    with pg_engine.connect() as conn:
        assert conn.execute(text("SELECT attempts FROM activation_rate_budgets WHERE scope = 'global'")).scalar_one() == 6


def test_expired_budget_is_pruned(pg_engine, monkeypatch):
    monkeypatch.setattr(budget, "_testing_bypass", lambda: False)
    scope = {"type": "http", "method": "POST", "path": "/", "headers": [],
             "client": ("192.0.2.3", 123), "server": ("testserver", 80), "scheme": "http"}
    with pg_engine.begin() as conn:
        conn.execute(text("INSERT INTO activation_rate_budgets (scope,attempts,expires_at) "
                          "VALUES ('client:obsolete', 5, clock_timestamp() - interval '1 second')"))
    with Session(pg_engine) as db:
        budget.enforce_activation_budget(Request(scope), db)
    with pg_engine.connect() as conn:
        rows = conn.execute(text("SELECT scope FROM activation_rate_budgets")).scalars().all()
    assert len(rows) == 2 and "client:obsolete" not in rows


def test_global_limit_bounds_the_number_of_client_rows(pg_engine, monkeypatch):
    monkeypatch.setattr(budget, "_testing_bypass", lambda: False)
    monkeypatch.setattr(budget, "_GLOBAL_LIMIT", 3)
    for index in range(1, 15):
        scope = {"type": "http", "method": "POST", "path": "/", "headers": [],
                 "client": (f"192.0.2.{index}", 123), "server": ("testserver", 80), "scheme": "http"}
        with Session(pg_engine) as db:
            if index <= 3:
                budget.enforce_activation_budget(Request(scope), db)
            else:
                with pytest.raises(HTTPException) as exc:
                    budget.enforce_activation_budget(Request(scope), db)
                assert exc.value.status_code == 429
    with pg_engine.connect() as conn:
        assert conn.execute(text("SELECT count(*) FROM activation_rate_budgets")).scalar_one() == 4


def test_missing_budget_table_fails_closed(pg_engine, monkeypatch):
    monkeypatch.setattr(budget, "_testing_bypass", lambda: False)
    with pg_engine.begin() as conn:
        conn.execute(text("DROP TABLE activation_rate_budgets"))
    scope = {"type": "http", "method": "POST", "path": "/", "headers": [],
             "client": ("192.0.2.5", 123), "server": ("testserver", 80), "scheme": "http"}
    with Session(pg_engine) as db:
        with pytest.raises(HTTPException) as exc:
            budget.enforce_activation_budget(Request(scope), db)
    assert exc.value.status_code == 503


def test_both_http_paths_share_budget_across_failed_setup_rollback(pg_engine, monkeypatch):
    monkeypatch.setattr(budget, "_testing_bypass", lambda: False)
    def override_db():
        with Session(pg_engine) as db:
            yield db
    app.dependency_overrides[get_db] = override_db
    key = "SYNTHETIC-" + secrets.token_hex(12)
    try:
        with TestClient(app) as client:
            for index in range(5):
                if index % 2:
                    response = client.post("/api/v1/setup/initialize", json=build_payload(activation_key=key))
                    assert response.status_code == 400
                else:
                    response = client.post("/api/v1/activation/activate", json={"key": key})
                    assert response.status_code == 200 and not response.json()["ok"]
            assert client.post("/api/v1/activation/activate", json={"key": key}).status_code == 429
            assert client.post("/api/v1/setup/initialize", json=build_payload(activation_key=key)).status_code == 429
            assert client.post("/api/v1/setup/initialize", json=build_payload()).status_code == 200
        with pg_engine.connect() as conn:
            assert conn.execute(text("SELECT attempts FROM activation_rate_budgets WHERE scope = 'global'")).scalar_one() == 5
    finally:
        app.dependency_overrides.pop(get_db, None)


def test_real_http_issue_activate_status_masks_public_values(pg_engine, monkeypatch, caplog):
    machine = "SYNTHETIC-MACHINE-" + secrets.token_hex(12)
    monkeypatch.setattr(activation_core, "server_machine_hash", lambda: machine)
    with Session(pg_engine, expire_on_commit=False) as db:
        admin = User(username="SYNTHETIC_" + secrets.token_hex(8), role="Admin",
                     hashed_password=get_password_hash(secrets.token_urlsafe(24)),
                     is_active=True, is_superuser=True)
        db.add(admin)
        db.commit()
        authorization = f"Bearer {mint_access_token(admin)}"

    def override_db():
        with Session(pg_engine) as db:
            yield db
    app.dependency_overrides[get_db] = override_db
    try:
        with TestClient(app) as client, caplog.at_level("INFO"):
            issue = client.post("/api/v1/activation/issue", json={"days": 1},
                                headers={"Authorization": authorization})
            assert issue.status_code == 200, issue.text
            key = issue.json()["key"]
            activated = client.post("/api/v1/activation/activate", json={"key": key})
            assert activated.status_code == 200 and activated.json()["ok"]
            status = client.get("/api/v1/activation/status")
            assert status.status_code == 200 and status.json()["ok"]
            assert status.json()["key"] == "****" + key[-4:]
            assert status.json()["machine_hash"] == "****" + machine[-4:]
            assert key not in status.text and machine not in status.text
            assert key not in caplog.text
    finally:
        app.dependency_overrides.pop(get_db, None)


def test_concurrent_activation_waits_for_lock_and_refuses_rebinding(pg_engine, monkeypatch):
    key = "SYNTHETIC-" + secrets.token_hex(12)
    first_machine = "FIRST-" + secrets.token_hex(12)
    second_machine = "SECOND-" + secrets.token_hex(12)
    with Session(pg_engine) as db:
        db.add(Activation(key=key, status=ActivationStatus.ISSUED))
        db.commit()
    monkeypatch.setattr(activation_core, "server_machine_hash", lambda: second_machine)
    started = threading.Event()
    pid = []

    def contender():
        with Session(pg_engine) as db:
            pid.append(db.execute(text("SELECT pg_backend_pid()")).scalar_one())
            started.set()
            return activation_core.activate_key(db, key=key)

    with Session(pg_engine) as winner:
        row = winner.execute(select(Activation).where(Activation.key == key).with_for_update()).scalar_one()
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(contender)
            assert started.wait(5)
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline:
                with pg_engine.connect() as conn:
                    blocked = conn.execute(text("SELECT cardinality(pg_blocking_pids(:pid))"), {"pid": pid[0]}).scalar_one()
                if blocked:
                    break
                time.sleep(0.02)
            else:
                pytest.fail("contender did not wait for activation row lock")
            row.machine_hash = first_machine
            row.status = ActivationStatus.ACTIVE
            winner.commit()
            result = future.result(timeout=5)
    assert not result.ok and result.reason == "KEY_IN_USE"
    assert result.machine_hash is None
    with Session(pg_engine) as db:
        assert db.execute(select(Activation.machine_hash).where(Activation.key == key)).scalar_one() == first_machine
