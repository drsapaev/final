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

    def lock(db, patient_id, user_id, **kwargs):
        result = original(db, patient_id, user_id, **kwargs)
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

    def lock(db, patient_id, **kwargs):
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


@pytest.mark.parametrize("revoke", ["epoch", "jti", "relink"])
def test_revocation_preceding_management_lock_rejects_mutation(pg_engine, revoke):
    from datetime import UTC, datetime, timedelta

    from app.models.authentication import TokenBlacklist

    suffix = uuid4().hex
    with Session(pg_engine) as db:
        user = User(
            username=f"synthetic-{suffix}",
            role="Patient",
            is_active=True,
            is_superuser=False,
            hashed_password="synthetic",
            auth_epoch=4,
        )
        replacement = User(
            username=f"replacement-{suffix}",
            role="Patient",
            is_active=True,
            is_superuser=False,
            hashed_password="synthetic",
        )
        db.add_all([user, replacement])
        db.flush()
        patient = Patient(user_id=user.id, first_name="Synthetic", last_name="Patient")
        db.add(patient)
        db.flush()
        keys = [
            PasskeyCredential(
                patient_id=patient.id,
                owner_user_id=user.id,
                credential_id=f"synthetic-{suffix}-{n}",
                public_key="cHVibGlj",
                active=True,
            )
            for n in range(2)
        ]
        db.add_all(keys)
        db.commit()
        user_id, patient_id, key_id, replacement_id = (
            user.id,
            patient.id,
            keys[0].id,
            replacement.id,
        )

    jti = str(uuid4())
    started, result = threading.Event(), {}
    with Session(pg_engine) as revoker:
        locked = (
            revoker.query(User)
            .filter_by(id=user_id)
            .with_for_update(key_share=True)
            .one()
        )
        if revoke == "epoch":
            locked.auth_epoch += 1
        elif revoke == "jti":
            revoker.add(
                TokenBlacklist(
                    jti=jti,
                    user_id=user_id,
                    reason="logout",
                    expires_at=datetime.now(UTC) + timedelta(hours=1),
                )
            )
        else:
            revoker.query(Patient).filter_by(
                id=patient_id
            ).with_for_update().one().user_id = replacement_id
        revoker.flush()

        def manage():
            with Session(pg_engine) as db:
                result["pid"] = db.scalar(text("SELECT pg_backend_pid()"))
                started.set()
                try:
                    result["outcome"] = ws.deactivate_passkey(
                        db,
                        patient_id,
                        key_id,
                        user_id=user_id,
                        expected_auth_epoch=4,
                        expected_jti=jti,
                        expected_exp=int(time.time()) + 120,
                    )
                except ws.WebAuthnBearerInvalid:
                    result["outcome"] = "revoked"

        thread = threading.Thread(target=manage)
        thread.start()
        assert started.wait(5)
        deadline = time.monotonic() + 5
        with pg_engine.connect() as conn:
            while time.monotonic() < deadline and not conn.scalar(
                text("SELECT cardinality(pg_blocking_pids(:pid))"),
                {"pid": result["pid"]},
            ):
                time.sleep(0.01)
            assert conn.scalar(
                text("SELECT cardinality(pg_blocking_pids(:pid))"),
                {"pid": result["pid"]},
            )
        revoker.commit()
        thread.join(10)
        assert not thread.is_alive()
    assert result["outcome"] == (False if revoke == "relink" else "revoked")
    with Session(pg_engine) as db:
        assert db.get(PasskeyCredential, key_id).active is True


def test_step_up_waits_for_phone_before_locking_patient(pg_engine):
    from app.services.patient_phone_scope import acquire_phone_scope_lock

    suffix, phone = uuid4().hex, "+998901234567"
    with Session(pg_engine) as db:
        user = User(
            username=f"synthetic-phone-{suffix}",
            role="Patient",
            is_active=True,
            is_superuser=False,
            hashed_password="synthetic",
            auth_epoch=2,
        )
        db.add(user)
        db.flush()
        patient = Patient(user_id=user.id, first_name="Synthetic", last_name="Patient")
        db.add(patient)
        db.flush()
        keys = [
            PasskeyCredential(
                patient_id=patient.id,
                owner_user_id=user.id,
                credential_id=f"phone-{suffix}-{n}",
                public_key="cHVibGlj",
                active=True,
            )
            for n in range(2)
        ]
        db.add_all(keys)
        db.commit()
        user_id, patient_id, key_id = user.id, patient.id, keys[0].id
    waiting, result = threading.Event(), {}
    with Session(pg_engine) as activation:
        acquire_phone_scope_lock(activation, phone)

        def manage():
            with Session(pg_engine) as db:
                result["pid"] = db.scalar(text("SELECT pg_backend_pid()"))

                def step_up():
                    waiting.set()
                    acquire_phone_scope_lock(db, phone)

                result["outcome"] = ws.deactivate_passkey(
                    db,
                    patient_id,
                    key_id,
                    user_id=user_id,
                    expected_auth_epoch=2,
                    expected_jti=str(uuid4()),
                    expected_exp=int(time.time()) + 120,
                    step_up=step_up,
                )

        thread = threading.Thread(target=manage)
        thread.start()
        assert waiting.wait(5)
        deadline = time.monotonic() + 5
        with pg_engine.connect() as conn:
            while time.monotonic() < deadline and not conn.scalar(
                text("SELECT cardinality(pg_blocking_pids(:pid))"),
                {"pid": result["pid"]},
            ):
                time.sleep(0.01)
            assert conn.scalar(
                text("SELECT cardinality(pg_blocking_pids(:pid))"),
                {"pid": result["pid"]},
            )
        # Activation takes Patient after phone. This must not wait on management.
        activation.execute(text("SET LOCAL lock_timeout = '500ms'"))
        activation.query(Patient).filter_by(id=patient_id).with_for_update().one()
        activation.commit()
        thread.join(10)
        assert not thread.is_alive()
    assert result["outcome"] is True


@pytest.mark.asyncio
@pytest.mark.parametrize("is_async", [False, True])
@pytest.mark.parametrize("revoke", [False, True])
async def test_fallback_login_uses_live_epoch_and_revoke_policy(
    pg_engine, monkeypatch, is_async, revoke
):
    import jwt
    from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

    from app.core.security import get_password_hash
    from app.services.auth_api_service import AuthApiService

    monkeypatch.setattr(settings, "REVOKE_SESSIONS_ON_NEW_LOGIN", revoke)
    username, password = "fallback-" + uuid4().hex, "synthetic-password-123"
    with Session(pg_engine) as setup:
        user = User(
            username=username,
            hashed_password=get_password_hash(password),
            role="Patient",
            is_active=True,
            is_superuser=False,
            auth_epoch=6,
        )
        setup.add(user)
        setup.commit()
        user_id = user.id
    if is_async:
        with pg_engine.connect() as conn:
            schema = conn.scalar(text("select current_schema()"))
        url = pg_engine.url.set(drivername="postgresql+psycopg")
        engine = create_async_engine(
            url, connect_args={"options": f"-csearch_path={schema}"}
        )
        try:
            async with AsyncSession(engine, expire_on_commit=False) as db:
                result = await AuthApiService(db).login_oauth_payload(
                    username=username, password=password
                )
        finally:
            await engine.dispose()
    else:
        with Session(pg_engine) as db:
            result = await AuthApiService(db).json_login_payload(
                username=username, password=password, remember_me=False
            )
    claims = jwt.decode(
        result["access_token"], settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
    )
    assert claims["sub"] == str(user_id)
    assert claims["auth_epoch"] == 6 + int(revoke)
    with Session(pg_engine) as db:
        assert db.get(User, user_id).auth_epoch == claims["auth_epoch"]


def test_identified_assertion_blocked_by_concurrent_epoch_revocation(
    pg_engine, monkeypatch
):
    from types import SimpleNamespace

    monkeypatch.setattr(settings, "TESTING", True)
    monkeypatch.setattr(settings, "FRONTEND_URL", "https://clinic.example")
    monkeypatch.setattr(
        ws,
        "generate_authentication_options",
        lambda **kw: SimpleNamespace(challenge=b"synthetic-challenge"),
    )
    called = []
    monkeypatch.setattr(
        ws, "verify_authentication_response", lambda **kw: called.append(True)
    )
    suffix = uuid4().hex
    credential_id = ws._b64url(uuid4().bytes)
    stored_credential_id = credential_id + "=" * (-len(credential_id) % 4)
    with Session(pg_engine) as db:
        user = User(
            username=f"epoch-{suffix}",
            role="Patient",
            is_active=True,
            is_superuser=False,
            hashed_password="synthetic",
            auth_epoch=3,
        )
        db.add(user)
        db.flush()
        patient = Patient(user_id=user.id, first_name="Synthetic", last_name="Patient")
        db.add(patient)
        db.flush()
        db.add(
            PasskeyCredential(
                patient_id=patient.id,
                owner_user_id=user.id,
                credential_id=stored_credential_id,
                public_key="cHVibGlj",
                active=True,
            )
        )
        db.commit()
        patient_id, user_id = patient.id, user.id
        options = ws.begin_passkey_authentication(db, patient_id)
    ready, result = threading.Event(), {}
    with Session(pg_engine) as revoker:
        user = (
            revoker.query(User)
            .filter_by(id=user_id)
            .with_for_update(key_share=True)
            .one()
        )
        user.auth_epoch += 1
        revoker.flush()

        def complete():
            with Session(pg_engine) as db:
                result["pid"] = db.scalar(text("select pg_backend_pid()"))
                ready.set()
                try:
                    result["value"] = ws.finish_passkey_authentication(
                        db,
                        patient_id,
                        ceremony_id=options["ceremony_id"],
                        assertion_response={
                            "id": credential_id,
                            "rawId": credential_id,
                        },
                    )
                except ValueError:
                    result["value"] = "rejected"

        thread = threading.Thread(target=complete)
        thread.start()
        assert ready.wait(5)
        deadline = time.monotonic() + 5
        with pg_engine.connect() as conn:
            while time.monotonic() < deadline and not conn.scalar(
                text("SELECT cardinality(pg_blocking_pids(:pid))"),
                {"pid": result["pid"]},
            ):
                time.sleep(0.01)
            assert conn.scalar(
                text("SELECT cardinality(pg_blocking_pids(:pid))"),
                {"pid": result["pid"]},
            )
        revoker.commit()
        thread.join(10)
        assert not thread.is_alive()
    assert result["value"] == "rejected"
    assert not called


def test_discoverable_second_assertion_waits_for_epoch_revocation(
    pg_engine, monkeypatch
):
    import redis

    redis_url = os.environ.get("WEBAUTHN_TEST_REDIS_URL")
    if not redis_url:
        pytest.skip("provide disposable Redis")
    store = redis.Redis.from_url(redis_url, decode_responses=True)
    prefix = f"synthetic:{{discoverable}}:{uuid4().hex}:"
    monkeypatch.setattr(ws, "_DISCOVERABLE_PREFIX", prefix)
    monkeypatch.setattr(ws, "_discoverable_store", lambda: store)
    monkeypatch.setattr(settings, "FRONTEND_URL", "https://clinic.example")
    verified = []
    monkeypatch.setattr(
        ws, "verify_authentication_response", lambda **kw: verified.append(True)
    )
    credential_id = ws._b64url(uuid4().bytes)
    stored_credential_id = credential_id + "=" * (-len(credential_id) % 4)
    with Session(pg_engine) as db:
        user = User(
            username="step-two-" + uuid4().hex,
            role="Patient",
            is_active=True,
            is_superuser=False,
            hashed_password="synthetic",
            auth_epoch=4,
        )
        db.add(user)
        db.flush()
        patient = Patient(user_id=user.id, first_name="Synthetic", last_name="Patient")
        db.add(patient)
        db.flush()
        db.add(
            PasskeyCredential(
                patient_id=patient.id,
                owner_user_id=user.id,
                credential_id=stored_credential_id,
                public_key="cHVibGlj",
                active=True,
            )
        )
        db.commit()
        user_id, patient_id = user.id, patient.id
    ceremony = ws.secrets.token_urlsafe(32)
    ws._store_bounded_ceremony(
        store,
        "discoverable_second",
        ceremony,
        "synthetic-client",
        {
            "purpose": "discoverable_second",
            "challenge": ws._b64url(b"synthetic"),
            "user_id": user_id,
            "patient_id": patient_id,
            "auth_epoch": 4,
            "credential_id": stored_credential_id,
        },
    )
    ready, result = threading.Event(), {}
    try:
        with Session(pg_engine) as revoker:
            user = (
                revoker.query(User)
                .filter_by(id=user_id)
                .with_for_update(key_share=True)
                .one()
            )
            user.auth_epoch += 1
            revoker.flush()

            def complete():
                with Session(pg_engine) as db:
                    result["pid"] = db.scalar(text("select pg_backend_pid()"))
                    ready.set()
                    try:
                        result["value"] = ws.complete_discoverable_authentication(
                            db,
                            client_ip="synthetic-client",
                            ceremony_id=ceremony,
                            assertion_response={
                                "id": credential_id,
                                "rawId": credential_id,
                            },
                        )
                    except ValueError:
                        result["value"] = "rejected"

            thread = threading.Thread(target=complete)
            thread.start()
            assert ready.wait(5)
            deadline = time.monotonic() + 5
            with pg_engine.connect() as conn:
                while time.monotonic() < deadline and not conn.scalar(
                    text("SELECT cardinality(pg_blocking_pids(:pid))"),
                    {"pid": result["pid"]},
                ):
                    time.sleep(0.01)
                assert conn.scalar(
                    text("SELECT cardinality(pg_blocking_pids(:pid))"),
                    {"pid": result["pid"]},
                )
            revoker.commit()
            thread.join(10)
            assert not thread.is_alive()
        assert result["value"] == "rejected"
        assert not verified
    finally:
        keys = list(store.scan_iter(prefix + "*"))
        if keys:
            store.delete(*keys)
        store.close()


@pytest.mark.parametrize("revoke_between_password_and_lock", [False, True])
def test_mobile_api_login_pg_checks_live_epoch(
    pg_engine, monkeypatch, revoke_between_password_and_lock
):
    import jwt
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from app.api.v1.endpoints import mobile_api
    from app.core.security import get_password_hash

    monkeypatch.setattr(settings, "REVOKE_SESSIONS_ON_NEW_LOGIN", False)
    phone, password = (
        "+998" + str(int(uuid4().hex[:8], 16)).zfill(10),
        "synthetic-password-123",
    )
    with Session(pg_engine) as db:
        user = User(
            username="mobile-" + uuid4().hex,
            role="Patient",
            is_active=True,
            is_superuser=False,
            hashed_password=get_password_hash(password),
            auth_epoch=8,
        )
        db.add(user)
        db.flush()
        db.add(
            Patient(
                user_id=user.id,
                first_name="Synthetic",
                last_name="Patient",
                phone=phone,
            )
        )
        db.commit()
        user_id = user.id
    application = FastAPI()
    application.include_router(mobile_api.router)

    def get_test_db():
        with Session(pg_engine) as db:
            yield db

    application.dependency_overrides[mobile_api.get_db] = get_test_db
    verified, release = threading.Event(), threading.Event()
    original = mobile_api.crud_user.verify_password

    def verify(password_value, password_hash):
        result = original(password_value, password_hash)
        if revoke_between_password_and_lock:
            verified.set()
            assert release.wait(8)
        return result

    monkeypatch.setattr(mobile_api.crud_user, "verify_password", verify)
    result = {}

    def run():
        with TestClient(application) as client:
            result["response"] = client.post(
                "/auth/login", json={"phone": phone, "".join(('pass', 'word')): password}
            )

    thread = threading.Thread(target=run)
    thread.start()
    if revoke_between_password_and_lock:
        try:
            assert verified.wait(8)
            with Session(pg_engine) as revoker:
                user = (
                    revoker.query(User)
                    .filter_by(id=user_id)
                    .with_for_update(key_share=True)
                    .one()
                )
                user.auth_epoch += 1
                revoker.commit()
        finally:
            release.set()
    thread.join(15)
    assert not thread.is_alive()
    response = result["response"]
    if revoke_between_password_and_lock:
        assert response.status_code == 401, response.text
        assert "access_token" not in response.text
    else:
        assert response.status_code == 200, response.text
        claims = jwt.decode(
            response.json()["access_token"],
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM],
        )
        assert claims["sub"] == str(user_id) and claims["auth_epoch"] == 8


def test_passkey_login_observes_2fa_enrollment_before_user_lock(pg_engine, monkeypatch):
    from types import SimpleNamespace

    from app.models.authentication import UserSession
    from app.models.two_factor_auth import TwoFactorAuth

    monkeypatch.setattr(settings, "TESTING", True)
    monkeypatch.setattr(settings, "FRONTEND_URL", "https://clinic.example")
    monkeypatch.setattr(
        ws,
        "generate_authentication_options",
        lambda **kw: SimpleNamespace(challenge=b"synthetic"),
    )
    monkeypatch.setattr(
        ws,
        "verify_authentication_response",
        lambda **kw: SimpleNamespace(new_sign_count=1),
    )
    credential_id = ws._b64url(uuid4().bytes)
    stored_credential_id = credential_id + "=" * (-len(credential_id) % 4)
    with Session(pg_engine) as db:
        user = User(
            username="factor-race-" + uuid4().hex,
            role="Patient",
            is_active=True,
            is_superuser=False,
            hashed_password="synthetic",
            auth_epoch=5,
        )
        db.add(user)
        db.flush()
        patient = Patient(user_id=user.id, first_name="Synthetic", last_name="Patient")
        db.add(patient)
        db.flush()
        db.add(
            PasskeyCredential(
                patient_id=patient.id,
                owner_user_id=user.id,
                credential_id=stored_credential_id,
                public_key="cHVibGlj",
                active=True,
            )
        )
        db.commit()
        user_id, patient_id = user.id, patient.id
        options = ws.begin_passkey_authentication(db, patient_id)
    ready, result = threading.Event(), {}
    with Session(pg_engine) as enroller:
        enroller.query(User).filter_by(id=user_id).with_for_update(key_share=True).one()
        enroller.add(
            TwoFactorAuth(
                user_id=user_id,
                totp_enabled=True,
                totp_verified=True,
                totp_secret="SYNTHETIC",
            )
        )
        enroller.flush()

        def finish():
            with Session(pg_engine) as db:
                result["pid"] = db.scalar(text("select pg_backend_pid()"))
                ready.set()
                result["value"] = ws.finish_passkey_authentication(
                    db,
                    patient_id,
                    ceremony_id=options["ceremony_id"],
                    assertion_response={"id": credential_id, "rawId": credential_id},
                )

        thread = threading.Thread(target=finish)
        thread.start()
        assert ready.wait(5)
        deadline = time.monotonic() + 5
        with pg_engine.connect() as conn:
            while time.monotonic() < deadline and not conn.scalar(
                text("SELECT cardinality(pg_blocking_pids(:pid))"),
                {"pid": result["pid"]},
            ):
                time.sleep(0.01)
            assert conn.scalar(
                text("SELECT cardinality(pg_blocking_pids(:pid))"),
                {"pid": result["pid"]},
            )
        enroller.commit()
        thread.join(10)
        assert not thread.is_alive()
    challenge = result["value"]
    assert challenge["requires_2fa"] is True
    assert "access_token" not in challenge and "refresh_token" not in challenge
    with Session(pg_engine) as db:
        session = (
            db.query(UserSession)
            .filter_by(refresh_token=challenge["pending_2fa_token"])
            .one()
        )
        assert session.session_kind.startswith("p2fa_pk:")
        assert db.get(User, user_id).auth_epoch == 5
        assert (
            db.query(PasskeyCredential)
            .filter_by(patient_id=patient_id)
            .one()
            .sign_count
            == 1
        )
