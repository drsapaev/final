"""Real PostgreSQL and Redis concurrency proofs for passkey login."""

import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session
from sqlalchemy.schema import CreateSchema, DropSchema

from app.core.config import settings
from app.db.base_class import Base
from app.models.passkey_credential import PasskeyCredential
from app.models.patient import Patient
from app.models.user import User
from app.services import webauthn_service as ws

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def pg_engine():
    raw_url = os.environ.get("DATABASE_URL", "").strip()
    if not raw_url or make_url(raw_url).get_backend_name() != "postgresql":
        if os.environ.get("CI") == "true":
            pytest.fail("CI PostgreSQL is required for WebAuthn concurrency")
        pytest.skip("WebAuthn concurrency requires disposable PostgreSQL")
    url = make_url(raw_url)
    if os.environ.get("CI") != "true" and not (url.database or "").startswith(
        "clinic_test"
    ):
        pytest.skip("use an explicitly disposable clinic_test database")
    schema = "test_webauthn_lock_" + uuid4().hex
    admin = create_engine(url, pool_pre_ping=True)
    try:
        with admin.begin() as conn:
            conn.execute(CreateSchema(schema))
    except Exception as exc:
        admin.dispose()
        if os.environ.get("CI") == "true":
            pytest.fail(f"CI disposable PostgreSQL unavailable: {exc}")
        pytest.skip(f"disposable PostgreSQL unavailable: {exc}")
    engine = create_engine(
        url,
        pool_pre_ping=True,
        connect_args={
            "options": f"-csearch_path={schema} -cstatement_timeout=10000 -clock_timeout=10000"
        },
    )
    try:
        import app.db.base  # noqa: F401 - register all models

        Base.metadata.create_all(engine)
        yield engine
    finally:
        engine.dispose()
        with admin.begin() as conn:
            conn.execute(DropSchema(schema, cascade=True))
        admin.dispose()


def test_distinct_ceremonies_serialize_credential_sign_count(pg_engine, monkeypatch):
    monkeypatch.setattr(settings, "TESTING", True)
    monkeypatch.setattr(settings, "FRONTEND_URL", "https://clinic.example")
    monkeypatch.setattr(ws, "WEBAUTHN_AVAILABLE", True)
    monkeypatch.setattr(
        ws,
        "generate_authentication_options",
        lambda **_: SimpleNamespace(challenge=b"\xff\x00challenge"),
        raising=False,
    )
    with Session(pg_engine) as db:
        user = User(
            username="passkey-lock-patient",
            role="Patient",
            is_active=True,
            is_superuser=False,
            hashed_password="synthetic",
        )
        db.add(user)
        db.flush()
        patient = Patient(user_id=user.id, first_name="Synthetic", last_name="Patient")
        db.add(patient)
        db.flush()
        db.add(
            PasskeyCredential(
                patient_id=patient.id,
                credential_id="Zmlyc3Q=",
                public_key="cHVibGlj",
                sign_count=0,
                active=True,
            )
        )
        db.commit()
        patient_id = patient.id
        first_id = ws.begin_passkey_authentication(db, patient_id)["ceremony_id"]
        second_id = ws.begin_passkey_authentication(db, patient_id)["ceremony_id"]

    first_entered = threading.Event()
    second_ready = threading.Event()
    second_finished = threading.Event()
    release = threading.Event()
    counts = []
    data = {}

    def verify(**kwargs):
        count = kwargs["credential_current_sign_count"]
        counts.append(count)
        if count == 0:
            first_entered.set()
            if not release.wait(8):
                raise AssertionError("first verifier was not released")
        return SimpleNamespace(new_sign_count=count + 1)

    monkeypatch.setattr(ws, "verify_authentication_response", verify, raising=False)

    def finish(ceremony_id, label):
        try:
            with Session(pg_engine) as db:
                if label == "second":
                    data["pid"] = db.scalar(text("SELECT pg_backend_pid()"))
                    second_ready.set()
                data[label] = ws.finish_passkey_authentication(
                    db,
                    patient_id,
                    assertion_response={"id": "Zmlyc3Q"},
                    ceremony_id=ceremony_id,
                )
        except Exception as exc:
            data[label + "_error"] = repr(exc)
        finally:
            if label == "second":
                second_finished.set()

    first = threading.Thread(target=finish, args=(first_id, "first"), daemon=True)
    second = threading.Thread(target=finish, args=(second_id, "second"), daemon=True)
    first.start()
    try:
        assert first_entered.wait(5), data
        second.start()
        assert second_ready.wait(5), data
        blocked = False
        deadline = time.monotonic() + 5
        with pg_engine.connect() as connection:
            while time.monotonic() < deadline:
                if connection.scalar(
                    text("SELECT cardinality(pg_blocking_pids(:pid))"),
                    {"pid": data["pid"]},
                ):
                    blocked = True
                    break
                if second_finished.wait(0.01):
                    break
        release.set()
        first.join(timeout=10)
        second.join(timeout=10)
        assert blocked, data
        assert not first.is_alive() and not second.is_alive(), data
        assert "first_error" not in data and "second_error" not in data, data
        assert counts == [0, 1]
        assert (
            data["first"]["user"]["role"] == data["second"]["user"]["role"] == "Patient"
        )
    finally:
        release.set()
        first.join(timeout=10)
        if second.ident:
            second.join(timeout=10)


def test_redis_getdel_consumes_once_across_connections(monkeypatch):
    import redis

    url = os.environ.get("WEBAUTHN_TEST_REDIS_URL") or os.environ.get("ARQ_REDIS_URL")
    if not url:
        if os.environ.get("CI") == "true":
            pytest.fail("CI Redis is required for WebAuthn concurrency")
        pytest.skip("supply WEBAUTHN_TEST_REDIS_URL for disposable Redis")
    client = redis.Redis.from_url(
        url, decode_responses=True, socket_connect_timeout=2, socket_timeout=2
    )
    try:
        client.ping()
    except redis.RedisError as exc:
        if os.environ.get("CI") == "true":
            pytest.fail(f"CI Redis unavailable: {exc}")
        pytest.skip(f"disposable Redis unavailable: {exc}")
    monkeypatch.setattr(settings, "TESTING", False)
    monkeypatch.setenv("REDIS_URL", url)
    ceremony_id = ws.secrets.token_urlsafe(32)
    key = f"webauthn:login:{ceremony_id}"
    try:
        ws._store_ceremony(client, ceremony_id, 71, b"binary\xff")
        assert 0 < client.ttl(key) <= 300

        def consume(_):
            try:
                return ws._consume_ceremony(ceremony_id, 71)
            except ValueError:
                return None

        with ThreadPoolExecutor(max_workers=8) as executor:
            results = list(executor.map(consume, range(8)))
        assert results.count(b"binary\xff") == 1
        assert results.count(None) == 7
        assert not client.exists(key)
    finally:
        client.delete(key)
        client.close()
