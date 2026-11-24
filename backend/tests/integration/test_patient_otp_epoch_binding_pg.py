"""Patient OTP revocation across real PostgreSQL and Redis transactions."""

from __future__ import annotations

import asyncio
import os
import re
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session
from sqlalchemy.schema import CreateSchema, DropSchema

from app.db.base_class import Base
from app.models.authentication import RefreshToken, TokenBlacklist, UserSession
from app.models.patient import Patient
from app.models.two_factor_auth import (
    TwoFactorAuth,
    TwoFactorBackupCode,
    TwoFactorRecovery,
)
from app.models.user import User
from app.models.user_profile import UserProfile
from app.services.patient_otp_service import (
    PatientOtpError,
    PatientOtpService,
    _RedisBackend,
)


@pytest.fixture
def pg_otp(monkeypatch):
    url = os.getenv("PATIENT_OTP_TEST_POSTGRES_URL", "").strip()
    redis_url = (
        os.getenv("PATIENT_OTP_TEST_REDIS_URL") or os.getenv("ARQ_REDIS_URL") or ""
    ).strip()
    if not url and os.getenv("CI", "").lower() == "true":
        from tests._pg_admin_guard import is_local_admin_dsn

        candidate = os.getenv("DATABASE_URL", "").strip()
        if (
            candidate
            and is_local_admin_dsn(candidate)
            and make_url(candidate).database == "clinicdb"
        ):
            url = candidate
    if not url or not redis_url:
        if os.getenv("CI"):
            pytest.fail("patient OTP generation tests require PostgreSQL and Redis")
        pytest.skip("set PATIENT_OTP_TEST_POSTGRES_URL and PATIENT_OTP_TEST_REDIS_URL")
    if make_url(url).get_backend_name() != "postgresql":
        pytest.fail("patient OTP generation tests require PostgreSQL")
    schema = f"test_patient_otp_{uuid4().hex}"
    admin = create_engine(url)
    with admin.begin() as conn:
        conn.execute(CreateSchema(schema))
    engine = create_engine(
        url,
        connect_args={
            "options": f"-csearch_path={schema} -cstatement_timeout=15000 -clock_timeout=10000"
        },
    )
    import redis

    import app.db.base  # noqa: F401

    Base.metadata.create_all(
        engine,
        tables=[
            User.__table__,
            UserProfile.__table__,
            TwoFactorAuth.__table__,
            TwoFactorBackupCode.__table__,
            TwoFactorRecovery.__table__,
            Patient.__table__,
            TokenBlacklist.__table__,
            UserSession.__table__,
            RefreshToken.__table__,
        ],
    )
    backend = _RedisBackend.__new__(_RedisBackend)
    backend._client = redis.Redis.from_url(
        redis_url, decode_responses=True, socket_connect_timeout=2
    )
    backend.last_sent_code = {}
    backend._client.ping()
    service = PatientOtpService()
    service._backend = backend
    from app.services import patient_otp_service as otp_module

    prefix = f"test:patient-otp-epoch:{uuid4().hex}"
    monkeypatch.setattr(otp_module, "_PREFIX", prefix)
    monkeypatch.setattr(otp_module, "_NS_LOGIN", prefix)
    monkeypatch.setattr(
        otp_module, "_OTP_NAMESPACES", (prefix, otp_module._NS_ACTIVATION)
    )
    monkeypatch.setattr(
        "app.services.patient_otp_service.settings.SMS_DEFAULT_PROVIDER", "mock"
    )
    captured = []

    async def send_sms(**kwargs):
        captured.append(re.search(r"\b\d{6}\b", kwargs["text"]).group())
        return SimpleNamespace(success=True, provider="mock")

    monkeypatch.setattr(
        "app.services.patient_otp_service.get_sms_manager",
        lambda: SimpleNamespace(send_sms=send_sms),
    )
    # Each test uses its own test-only Redis database.
    try:
        yield engine, service, backend, captured
    finally:
        for key in backend._client.scan_iter(f"{prefix}:*"):
            backend._client.delete(key)
        for key in backend._client.scan_iter(f"meta:{prefix}:*"):
            backend._client.delete(key)
        backend._client.close()
        engine.dispose()
        with admin.begin() as conn:
            conn.execute(DropSchema(schema, cascade=True))
        admin.dispose()


def _patient(engine, phone):
    with Session(engine) as db:
        user = User(
            username=f"SYNTHETIC_{uuid4().hex}",
            hashed_password="synthetic",
            role="Patient",
            is_active=True,
            is_superuser=False,
        )
        db.add(user)
        db.flush()
        db.add(UserProfile(user_id=user.id, phone=phone, phone_verified=True))
        db.commit()
        return user.id


def _change_epoch(engine, user_id, *, deactivate=False):
    with Session(engine) as db:
        user = db.query(User).filter_by(id=user_id).with_for_update().one()
        user.auth_epoch += 1
        if deactivate:
            user.is_active = False
        db.commit()
    if deactivate:
        with Session(engine) as db:
            user = db.query(User).filter_by(id=user_id).with_for_update().one()
            user.is_active = True
            db.commit()


@pytest.mark.parametrize("deactivate", [False, True])
@pytest.mark.parametrize("event_stage", ["sms", "grant"])
def test_revocation_invalidates_issued_code_and_grant(pg_otp, deactivate, event_stage):
    engine, service, backend, sent = pg_otp
    phone = "+998900000001"
    user_id = _patient(engine, phone)
    with Session(engine) as db:
        binding = service.binding_for_phone(db, phone)
    asyncio.run(service.send_login_otp(phone, binding=binding))
    if event_stage == "sms":
        _change_epoch(engine, user_id, deactivate=deactivate)
    with Session(engine) as db:
        grant = service.verify_login_otp(phone, sent[-1], db=db)["verification_grant"]
    step_up_grant = "synthetic-step-up-grant-" + uuid4().hex
    from app.services import patient_otp_service as otp_module

    backend.set(
        f"{otp_module._PREFIX}:grant:{step_up_grant}",
        backend.get(f"{otp_module._PREFIX}:grant:{grant}"),
        60,
    )
    if event_stage == "grant":
        _change_epoch(engine, user_id, deactivate=deactivate)
    with Session(engine) as db:
        with pytest.raises(PatientOtpError) as error:
            service.login_with_grant(db, phone, grant)
        assert error.value.status_code == 401
    # Same public verification result but unusable for step-up, too.
    with Session(engine) as db:
        assert not service.consume_bound_grant(db, user_id, phone, step_up_grant)
    backend.delete(f"{otp_module._PREFIX}:cd:{phone}")
    with Session(engine) as db:
        fresh = service.binding_for_phone(db, phone)
    asyncio.run(service.send_login_otp(phone, binding=fresh))
    with Session(engine) as db:
        new_grant = service.verify_login_otp(phone, sent[-1], db=db)[
            "verification_grant"
        ]
    with Session(engine) as db:
        assert service.login_with_grant(db, phone, new_grant)["user"]["id"] == user_id


def test_revocation_during_sms_send_keeps_original_snapshot(pg_otp, monkeypatch):
    engine, service, _, sent = pg_otp
    phone = "+998900000001"
    user_id = _patient(engine, phone)
    with Session(engine) as db:
        binding = service.binding_for_phone(db, phone)

    async def send_sms(**kwargs):
        sent.append(re.search(r"\b\d{6}\b", kwargs["text"]).group())
        _change_epoch(engine, user_id)
        return SimpleNamespace(success=True, provider="mock")

    monkeypatch.setattr(
        "app.services.patient_otp_service.get_sms_manager",
        lambda: SimpleNamespace(send_sms=send_sms),
    )
    asyncio.run(service.send_login_otp(phone, binding=binding))
    with Session(engine) as db:
        grant = service.verify_login_otp(phone, sent[-1], db=db)["verification_grant"]
    with Session(engine) as db:
        with pytest.raises(PatientOtpError):
            service.login_with_grant(db, phone, grant)


def test_step_up_and_revocation_serialize_on_user_lock(pg_otp):
    engine, service, _, sent = pg_otp
    phone = "+998900000001"
    user_id = _patient(engine, phone)
    with Session(engine) as db:
        binding = service.binding_for_phone(db, phone)
    asyncio.run(service.send_login_otp(phone, binding=binding))
    with Session(engine) as db:
        grant = service.verify_login_otp(phone, sent[-1], db=db)["verification_grant"]
    writer_started, writer_finished = Event(), Event()

    def revoke():
        writer_started.set()
        _change_epoch(engine, user_id)
        writer_finished.set()

    with Session(engine) as db, ThreadPoolExecutor(max_workers=1) as pool:
        assert service.consume_bound_grant(db, user_id, phone, grant)
        pending = pool.submit(revoke)
        assert writer_started.wait(5)
        assert not writer_finished.wait(0.3)
        db.commit()
        pending.result(timeout=10)
        assert writer_finished.is_set()
