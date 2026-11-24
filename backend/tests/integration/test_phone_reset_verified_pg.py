"""PostgreSQL barriers for verified-phone password reset issuance."""
from __future__ import annotations

import asyncio
import os
import secrets
import time
from concurrent.futures import ThreadPoolExecutor
from queue import Queue
from types import SimpleNamespace
from urllib.parse import urlsplit
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models.authentication import PasswordResetToken
from app.models.user import User
from app.models.user_profile import UserProfile
from app.services.password_reset_service import _PHONE_RESET_TASKS, PasswordResetService
from app.services.patient_phone_scope import acquire_phone_scope_lock, phone_lock_key
from tests.integration.test_profile_contact_security_pg import pg_engine  # noqa: F401

pytestmark = pytest.mark.integration


def _owner(db, phone, *, active=True):
    user = User(
        username="SYNTHETIC_" + uuid4().hex,
        hashed_password="SYNTHETIC_NO_LOGIN",
        role="Patient",
        is_active=active,
        is_superuser=False,
    )
    db.add(user)
    db.flush()
    db.add(UserProfile(user_id=user.id, phone=phone, phone_verified=True))
    db.flush()
    return user.id


def _phone():
    return "+9989" + f"{secrets.randbelow(100_000_000):08d}"


class FakeProof:
    def __init__(self, binding, deadline=None):
        self.binding = binding
        self.deadline = deadline if deadline is not None else time.monotonic() + 300

    def verify_code(self, **kwargs):
        return {"success": True, "account_binding": self.binding, "expires_monotonic": self.deadline}


def _wait_until_blocked(engine, pid):
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        with engine.connect() as conn:
            if conn.execute(text("SELECT cardinality(pg_blocking_pids(:pid))"), {"pid": pid}).scalar_one():
                return
        time.sleep(.02)
    pytest.fail("reset-token issuer did not wait for the expected lock")


def _issue_in_thread(engine, user_id, phone, pids, deadline=None):
    # Keep one physical connection checked out while the service commits its
    # cleanup transaction, so the recorded PID remains the lock waiter's PID.
    with engine.connect() as connection:
        with Session(bind=connection) as db:
            pids.put(db.execute(text("SELECT pg_backend_pid()")).scalar_one())
            service = PasswordResetService()
            service.phone_verification = FakeProof((user_id, 0), deadline)
            return asyncio.run(service.verify_phone_and_get_token(db, phone, "SYNTHETIC"))


def test_reset_waiting_on_user_lock_rejects_revoked_epoch(pg_engine):
    phone, pids = _phone(), Queue()
    with Session(pg_engine) as db:
        user_id = _owner(db, phone)
        db.commit()
    with Session(pg_engine) as gate, ThreadPoolExecutor(max_workers=1) as pool:
        user = gate.query(User).filter_by(id=user_id).with_for_update(key_share=True).one()
        pending = pool.submit(_issue_in_thread, pg_engine, user_id, phone, pids)
        _wait_until_blocked(pg_engine, pids.get(timeout=10))
        user.auth_epoch += 1
        gate.commit()
        assert pending.result(timeout=15)["error_code"] == "CODE_NOT_FOUND"
    with Session(pg_engine) as db:
        assert db.query(PasswordResetToken).filter_by(user_id=user_id).count() == 0


@pytest.mark.parametrize("legacy_format", ["plain", "unicode", "separated"])
def test_duplicate_verified_owner_wins_phone_lock_before_reset_commit(pg_engine, legacy_format):
    phone, pids = _phone(), Queue()
    with Session(pg_engine) as db:
        user_id = _owner(db, phone)
        db.commit()
    with Session(pg_engine) as gate, ThreadPoolExecutor(max_workers=1) as pool:
        acquire_phone_scope_lock(gate, phone)
        pending = pool.submit(_issue_in_thread, pg_engine, user_id, phone, pids)
        _wait_until_blocked(pg_engine, pids.get(timeout=10))
        if legacy_format == "unicode":
            duplicate_phone = phone.translate(str.maketrans("0123456789", "٠١٢٣٤٥٦٧٨٩"))
        elif legacy_format == "separated":
            duplicate_phone = "+ 9 9 8 " + phone[4:]
        else:
            duplicate_phone = phone
        _owner(gate, duplicate_phone, active=False)
        gate.commit()
        assert pending.result(timeout=15)["error_code"] == "CODE_NOT_FOUND"
    with Session(pg_engine) as db:
        assert db.query(PasswordResetToken).filter_by(user_id=user_id).count() == 0


@pytest.mark.asyncio
async def test_sms_transport_holds_no_user_or_phone_lock(pg_engine):
    phone = _phone()
    with Session(pg_engine) as db:
        user_id = _owner(db, phone)
        db.commit()

    class CheckLocks:
        async def send_verification_code(self, **kwargs):
            with Session(pg_engine) as other:
                user = other.query(User).filter_by(id=user_id).with_for_update(nowait=True).one()
                assert user.id == user_id
                assert other.execute(
                    text("SELECT pg_try_advisory_xact_lock(:key)"),
                    {"key": phone_lock_key(phone)},
                ).scalar_one()
                other.rollback()
            return {"success": True}

    with Session(pg_engine) as db:
        service = PasswordResetService()
        service.phone_verification = CheckLocks()
        assert (await service.initiate_phone_reset(db, phone))["success"]
        if _PHONE_RESET_TASKS:
            await asyncio.gather(*tuple(_PHONE_RESET_TASKS))


@pytest.mark.asyncio
async def test_reset_sms_binding_and_single_use_across_redis_workers(pg_engine, monkeypatch):
    redis_url = os.getenv("PHONE_RESET_REDIS_URL")
    if not redis_url:
        pytest.skip("requires a disposable local Redis URL")
    parts = urlsplit(redis_url)
    if parts.scheme != "redis" or parts.hostname not in {"127.0.0.1", "localhost", "::1"}:
        pytest.fail("requires a local disposable Redis instance")
    from redis import Redis

    from app.services.phone_verification_service import PhoneVerificationService
    from app.services.phone_verification_store import RedisPhoneStore

    client = Redis.from_url(redis_url, decode_responses=True, socket_timeout=2)
    client.ping()
    phone, code = _phone(), f"{secrets.randbelow(1_000_000):06d}"
    with Session(pg_engine) as db:
        user_id = _owner(db, phone)
        db.commit()
    first = PhoneVerificationService(store=RedisPhoneStore(client))
    second = PhoneVerificationService(store=RedisPhoneStore(client))
    monkeypatch.setattr(first, "generate_verification_code", lambda: code)

    async def fake_send(**kwargs):
        return SimpleNamespace(success=True, provider="SYNTHETIC", message_id="SYNTHETIC")

    monkeypatch.setattr(first.sms_manager, "send_sms", fake_send)
    key = first._get_code_key(phone, "password_reset")
    try:
        with Session(pg_engine) as db:
            sender = PasswordResetService()
            sender.phone_verification = first
            assert (await sender.initiate_phone_reset(db, phone))["success"]
            if _PHONE_RESET_TASKS:
                await asyncio.gather(*tuple(_PHONE_RESET_TASKS))
        with Session(pg_engine) as db:
            receiver = PasswordResetService()
            receiver.phone_verification = second
            result = await receiver.verify_phone_and_get_token(db, phone, code)
            assert result["success"] and result["reset_token"]
            assert db.query(PasswordResetToken).filter_by(user_id=user_id, used=False).count() == 1
            assert not (await receiver.verify_phone_and_get_token(db, phone, code))["success"]
    finally:
        client.delete(*RedisPhoneStore._keys(key))
        client.close()


def test_reset_waiting_on_phone_lock_rejects_expired_consumed_otp(pg_engine):
    phone, pids = _phone(), Queue()
    with Session(pg_engine) as db:
        user_id = _owner(db, phone)
        db.commit()
    with Session(pg_engine) as gate, ThreadPoolExecutor(max_workers=1) as pool:
        acquire_phone_scope_lock(gate, phone)
        deadline = time.monotonic() + 3
        pending = pool.submit(_issue_in_thread, pg_engine, user_id, phone, pids, deadline)
        _wait_until_blocked(pg_engine, pids.get(timeout=10))
        # The barrier proves consume completed while the proof was live.
        assert time.monotonic() < deadline
        while time.monotonic() <= deadline:
            time.sleep(.02)
        gate.commit()
        assert pending.result(timeout=15)["error_code"] == "CODE_NOT_FOUND"
    with Session(pg_engine) as db:
        assert db.query(PasswordResetToken).filter_by(user_id=user_id).count() == 0
