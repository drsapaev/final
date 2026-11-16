"""Real PostgreSQL and Redis concurrency proofs for passkey login."""

import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor
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


def test_deactivations_serialize_on_patient_row(pg_engine, monkeypatch, caplog):
    with Session(pg_engine) as db:
        user = User(
            username="synthetic-management-race",
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
        credentials = [
            PasskeyCredential(
                patient_id=patient.id,
                owner_user_id=user.id,
                credential_id=value,
                public_key="cHVibGlj",
                sign_count=0,
                active=True,
            )
            for value in ("cmFjZS0x", "cmFjZS0y")
        ]
        db.add_all(credentials)
        db.commit()
        patient_id, user_id, ids = patient.id, user.id, [c.id for c in credentials]

    first_locked, release, second_ready = (
        threading.Event(),
        threading.Event(),
        threading.Event(),
    )
    original = ws._lock_patient_identity
    results = {}

    def lock(db, patient_id, user_id):
        result = original(db, patient_id, user_id)
        if threading.current_thread().name == "management-first":
            first_locked.set()
            assert release.wait(8)
        return result

    monkeypatch.setattr(ws, "_lock_patient_identity", lock)

    def run(index):
        with Session(pg_engine) as db:
            if index == 1:
                results["pid"] = db.scalar(text("SELECT pg_backend_pid()"))
                second_ready.set()
            try:
                results[index] = ws.deactivate_passkey(
                    db, patient_id, ids[index], user_id=user_id
                )
            except ValueError as exc:
                results[index] = str(exc)

    first = threading.Thread(target=run, args=(0,), name="management-first")
    second = threading.Thread(target=run, args=(1,), name="management-second")
    first.start()
    try:
        assert first_locked.wait(5)
        second.start()
        assert second_ready.wait(5)
        deadline = time.monotonic() + 5
        blocked = False
        with pg_engine.connect() as conn:
            while time.monotonic() < deadline:
                if conn.scalar(
                    text("SELECT cardinality(pg_blocking_pids(:pid))"),
                    {"pid": results["pid"]},
                ):
                    blocked = True
                    break
                time.sleep(0.01)
        assert blocked, results
    finally:
        release.set()
        first.join(10)
        if second.ident:
            second.join(10)
    assert results[0] is True
    assert results[1] == "last_active_credential"
    with Session(pg_engine) as db:
        assert (
            db.query(PasskeyCredential)
            .filter_by(patient_id=patient_id, active=True)
            .count()
            == 1
        )
    deactivation_logs = [
        record for record in caplog.records if record.name == ws.logger.name
    ]
    assert len(deactivation_logs) == 1
    assert deactivation_logs[0].getMessage() == "Passkey deactivated"
    assert not deactivation_logs[0].args


def test_registration_redis_getdel_is_atomic(monkeypatch):
    import redis

    url = os.environ.get("WEBAUTHN_TEST_REDIS_URL") or os.environ.get("ARQ_REDIS_URL")
    if not url:
        if os.environ.get("CI") == "true":
            pytest.fail("CI Redis is required")
        pytest.skip("supply WEBAUTHN_TEST_REDIS_URL")
    client = redis.Redis.from_url(url, decode_responses=True)
    client.ping()
    monkeypatch.setattr(settings, "TESTING", False)
    monkeypatch.setenv("REDIS_URL", url)
    ceremony_id = ws.secrets.token_urlsafe(32)
    key = f"webauthn:registration:{ceremony_id}"
    try:
        ws._store_registration_ceremony(
            client, ceremony_id, 71, 12, "synthetic-session", b"binary\xff"
        )
        assert 0 < client.ttl(key) <= 300

        def consume(_):
            try:
                return ws._consume_registration_ceremony(
                    ceremony_id, 71, 12, "synthetic-session"
                )
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


def test_simultaneous_registration_begins_reuse_one_handle(pg_engine, monkeypatch):
    monkeypatch.setattr(settings, "TESTING", True)
    monkeypatch.setattr(settings, "FRONTEND_URL", "https://clinic.example")
    with Session(pg_engine) as db:
        user = User(
            username="synthetic-concurrent-begin",
            role="Patient",
            is_active=True,
            is_superuser=False,
            hashed_password="synthetic",
        )
        db.add(user)
        db.flush()
        patient = Patient(user_id=user.id, first_name="Synthetic", last_name="Patient")
        db.add(patient)
        db.commit()
        patient_id, user_id = patient.id, user.id
    acquired, release, second_ready = (
        threading.Event(),
        threading.Event(),
        threading.Event(),
    )
    original = ws._lock_current_patient_identity
    results = {}

    def lock(db, patient_id):
        user = original(db, patient_id)
        if threading.current_thread().name == "registration-first":
            acquired.set()
            assert release.wait(8)
        return user

    monkeypatch.setattr(ws, "_lock_current_patient_identity", lock)

    def run(index):
        try:
            with Session(pg_engine) as db:
                if index == 1:
                    results["pid"] = db.scalar(text("SELECT pg_backend_pid()"))
                    second_ready.set()
                results[index] = ws.begin_passkey_registration(
                    db,
                    patient_id,
                    user_id,
                    "synthetic-session",
                    rp_name="Synthetic Clinic",
                )
        except Exception as exc:
            results[f"error-{index}"] = repr(exc)

    first = threading.Thread(target=run, args=(0,), name="registration-first")
    second = threading.Thread(target=run, args=(1,), name="registration-second")
    first.start()
    try:
        assert acquired.wait(5)
        second.start()
        assert second_ready.wait(5)
        deadline = time.monotonic() + 5
        blocked = False
        with pg_engine.connect() as conn:
            while time.monotonic() < deadline:
                if conn.scalar(
                    text("SELECT cardinality(pg_blocking_pids(:pid))"),
                    {"pid": results["pid"]},
                ):
                    blocked = True
                    break
                time.sleep(0.01)
        assert blocked, results
    finally:
        release.set()
        first.join(10)
        if second.ident:
            second.join(10)
    assert not [key for key in results if str(key).startswith("error-")], results
    assert results[0]["user"]["id"] == results[1]["user"]["id"]
    assert results[0]["ceremony_id"] != results[1]["ceremony_id"]
    with Session(pg_engine) as db:
        assert db.get(User, user_id).passkey_user_handle == results[0]["user"]["id"]
