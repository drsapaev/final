"""Transaction boundaries for verified phone changes on PostgreSQL."""

from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor
from queue import Queue
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.v1.endpoints import phone_verification as endpoint
from app.models.user import User
from app.models.user_profile import UserProfile
from app.services.patient_phone_scope import PatientPhoneScopeConflict
from app.services.profile_contact_security import (
    ProfileBearerContext,
    ProfileBearerInvalid,
)
from app.services.token_blacklist_service import revoke_account_sessions_locked
from tests.integration.test_profile_contact_security_pg import pg_engine  # noqa: F401

PHONE_A = "+998000000011"
PHONE_B = "+998000000012"
PHONE_NEW = "+998000000013"


class ProofService:
    def __init__(self):
        self.consumed = 0

    def verify_code(self, **kwargs):
        self.consumed += 1
        return {"success": True, "verified_at": "synthetic"}


@pytest.fixture
def users(pg_engine):
    ids = []
    with Session(pg_engine, expire_on_commit=False) as db:
        for phone in (PHONE_A, PHONE_B):
            user = User(username="SYNTHETIC_" + uuid4().hex, role="Patient", is_active=True,
                        is_superuser=False, hashed_password="synthetic-unused")
            db.add(user)
            db.flush()
            db.add(UserProfile(user_id=user.id, phone=phone, phone_verified=True))
            ids.append(user.id)
        db.commit()
    yield ids
    with Session(pg_engine) as db:
        db.query(User).filter(User.id.in_(ids)).delete(synchronize_session=False)
        db.commit()


def _context(user_id):
    return ProfileBearerContext(user_id, 0, "SYNTHETIC-" + uuid4().hex,
                                int(time.time()) + 120, None)


def _wait_blocked(engine, pid):
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        with engine.connect() as conn:
            if conn.execute(text("select cardinality(pg_blocking_pids(:pid))"), {"pid": pid}).scalar_one():
                return
        time.sleep(.02)
    raise AssertionError("request did not wait for a PostgreSQL lock")


def test_phone_update_waits_for_revoke_and_does_not_consume(pg_engine, users, monkeypatch):
    service = ProofService()
    monkeypatch.setattr(endpoint, "get_phone_verification_service", lambda: service)
    context = _context(users[0])
    pids = Queue()

    def worker():
        with Session(pg_engine, autoflush=False) as db:
            pids.put(db.execute(text("select pg_backend_pid()")).scalar_one())
            with pytest.raises(ProfileBearerInvalid):
                endpoint._phone_update(db, context, PHONE_NEW, "012345")

    with Session(pg_engine) as gate, ThreadPoolExecutor(max_workers=1) as pool:
        actor = gate.query(User).filter_by(id=users[0]).with_for_update(key_share=True).one()
        future = pool.submit(worker)
        _wait_blocked(pg_engine, pids.get(timeout=10))
        revoke_account_sessions_locked(gate, actor, revoke_password_resets=True)
        gate.commit()
        future.result(timeout=20)
    assert service.consumed == 0
    with Session(pg_engine) as db:
        assert db.query(UserProfile).filter_by(user_id=users[0]).one().phone == PHONE_A


def test_concurrent_verified_phone_claim_has_one_winner(pg_engine, users, monkeypatch):
    service = ProofService()
    monkeypatch.setattr(endpoint, "get_phone_verification_service", lambda: service)
    pids = Queue()

    def worker(user_id):
        with Session(pg_engine, autoflush=False) as db:
            pids.put(db.execute(text("select pg_backend_pid()")).scalar_one())
            try:
                endpoint._phone_update(db, _context(user_id), PHONE_NEW, "012345")
                return "success"
            except PatientPhoneScopeConflict:
                return "conflict"

    from app.services.patient_phone_scope import acquire_phone_scope_lock

    with Session(pg_engine) as gate, ThreadPoolExecutor(max_workers=2) as pool:
        acquire_phone_scope_lock(gate, PHONE_NEW)
        futures = [pool.submit(worker, user_id) for user_id in users]
        for _ in users:
            _wait_blocked(pg_engine, pids.get(timeout=10))
        gate.commit()
        assert sorted(f.result(timeout=20) for f in futures) == ["conflict", "success"]
    # Both callers must prove possession before learning whether a verified
    # account already holds the number; the losing proof is not revived.
    assert service.consumed == 2
    with Session(pg_engine) as db:
        assert db.query(UserProfile).filter_by(phone=PHONE_NEW, phone_verified=True).count() == 1


def test_db_failure_rolls_back_phone_and_epoch_without_reviving_proof(pg_engine, users, monkeypatch):
    service = ProofService()
    monkeypatch.setattr(endpoint, "get_phone_verification_service", lambda: service)
    original = endpoint.revoke_account_sessions_locked

    def fail_after_revoke(db, user, **kwargs):
        original(db, user, **kwargs)
        raise RuntimeError("synthetic failure")

    monkeypatch.setattr(endpoint, "revoke_account_sessions_locked", fail_after_revoke)
    with Session(pg_engine, autoflush=False) as db:
        with pytest.raises(RuntimeError, match="synthetic failure"):
            endpoint._phone_update(db, _context(users[0]), PHONE_NEW, "012345")
    assert service.consumed == 1
    with Session(pg_engine) as db:
        assert db.get(User, users[0]).auth_epoch == 0
        profile = db.query(UserProfile).filter_by(user_id=users[0]).one()
        assert profile.phone == PHONE_A and profile.phone_verified


def test_legacy_unicode_verified_phone_is_a_conflict(pg_engine, users, monkeypatch):
    service = ProofService()
    monkeypatch.setattr(endpoint, "get_phone_verification_service", lambda: service)
    with Session(pg_engine) as db:
        profile = db.query(UserProfile).filter_by(user_id=users[1]).one()
        profile.phone = "+٩٩٨ (00) 000-00-13"
        db.commit()
    with Session(pg_engine, autoflush=False) as db:
        with pytest.raises(PatientPhoneScopeConflict):
            endpoint._phone_update(db, _context(users[0]), PHONE_NEW, "012345")
    assert service.consumed == 1
    with Session(pg_engine) as db:
        assert db.get(User, users[0]).auth_epoch == 0
        assert db.query(UserProfile).filter_by(user_id=users[0]).one().phone == PHONE_A


def test_real_http_phone_change_uses_redis_and_revokes_bearer(pg_engine, users, monkeypatch):
    """Exercise the actual HTTP, SMS manager, Redis and PostgreSQL path."""
    import os
    import secrets
    from urllib.parse import urlparse

    import redis
    from fastapi.testclient import TestClient
    from sqlalchemy.orm import sessionmaker

    from app.db.session import get_db
    from app.main import app
    from app.services.authentication_service import authentication_service
    from app.services.phone_verification_service import PhoneVerificationService
    from app.services.phone_verification_store import RedisPhoneStore
    from app.services.sms_providers import SMSManager, SMSProviderType, SMSResponse

    url = os.getenv("PHONE_VERIFICATION_REDIS_TEST_URL")
    # The backend-tests GitHub Actions job provisions a local Redis service
    # as ARQ_REDIS_URL. Never infer a Redis server outside that CI job.
    if not url and os.getenv("CI", "").lower() == "true" and os.getenv("GITHUB_ACTIONS") == "true":
        url = os.getenv("REDIS_URL") or os.getenv("ARQ_REDIS_URL")
        if not url:
            pytest.fail("CI requires a local Redis URL for the phone verification integration test")
    if not url:
        pytest.skip("PHONE_VERIFICATION_REDIS_TEST_URL is required")
    if urlparse(url).hostname not in {"localhost", "127.0.0.1", "::1"}:
        pytest.fail("Redis integration test requires a local disposable server")
    client = redis.Redis.from_url(url, decode_responses=True, socket_connect_timeout=2, socket_timeout=2)
    client.ping()
    phone = "+998" + "".join(str(secrets.randbelow(10)) for _ in range(9))
    messages = []

    class SyntheticProvider:
        async def send_sms(self, message):
            messages.append(message)
            return SMSResponse(success=True, provider="synthetic", message_id="synthetic")

    # Exercise SMSManager while ensuring no configured external provider is used.
    manager = SMSManager()
    manager.providers = {SMSProviderType.MOCK: SyntheticProvider()}
    manager.default_provider = SMSProviderType.MOCK
    service = PhoneVerificationService(RedisPhoneStore(client))
    service.sms_manager = manager
    service.generate_verification_code = lambda: "012345"
    monkeypatch.setattr(endpoint, "get_phone_verification_service", lambda: service)
    key = service._get_code_key(phone, "phone_change")
    factory = sessionmaker(bind=pg_engine, expire_on_commit=False, autoflush=False)
    previous = app.dependency_overrides.get(get_db)

    def override_db():
        with factory() as db:
            yield db

    with Session(pg_engine) as db:
        user = db.get(User, users[0])
        token = authentication_service.create_access_token({
            "sub": str(user.id), "username": user.username, "role": user.role,
            "is_active": True, "is_superuser": False, "auth_epoch": user.auth_epoch,
        })
    headers = {"Authorization": f"Bearer {token}"}
    app.dependency_overrides[get_db] = override_db
    try:
        with TestClient(app) as http:
            sent = http.post("/api/v1/phone-verification/send-code", headers=headers,
                             json={"phone": phone, "purpose": "phone_change"})
            assert sent.status_code == 200, sent.text
            assert sent.json()["expires_in_seconds"] > 0
            assert sent.headers["cache-control"] == "no-store"
            assert phone not in str(sent.request.url)
            assert len(messages) == 1 and messages[0].phone == phone and "012345" in messages[0].text
            raw = client.get(RedisPhoneStore._keys(key)[0])
            assert raw and phone not in raw and "012345" not in raw
            changed = http.put("/api/v1/phone-verification/update-phone", headers=headers,
                               json={"new_phone": phone, "verification_code": "012345"})
            assert changed.status_code == 200, changed.text
            assert changed.json()["sessions_revoked"] is True
            assert changed.headers["cache-control"] == "no-store"
            assert phone not in str(changed.request.url)
            assert not client.exists(RedisPhoneStore._keys(key)[0])
            stale = http.post("/api/v1/phone-verification/status", headers=headers,
                              json={"phone": phone, "purpose": "phone_change"})
            assert stale.status_code == 401
            assert phone not in str(stale.request.url)
        with Session(pg_engine) as db:
            profile = db.query(UserProfile).filter_by(user_id=users[0]).one()
            assert profile.phone == phone and profile.phone_verified
            assert db.get(User, users[0]).auth_epoch == 1
    finally:
        client.delete(*RedisPhoneStore._keys(key))
        if previous is None:
            app.dependency_overrides.pop(get_db, None)
        else:
            app.dependency_overrides[get_db] = previous


def test_opposite_formatted_phone_changes_take_locks_in_canonical_order(pg_engine):
    """Two reverse changes cannot ABBA when legacy digits change sort order."""
    from app.services.patient_phone_scope import acquire_phone_scope_lock
    from app.services.profile_contact_security import prepare_phone_change

    phone_a, phone_b = "+998000000001", "+998000000002"
    unicode_a, unicode_b = "+99800000000١", "+99800000000٢"
    pids = Queue()

    def worker(old, new):
        with Session(pg_engine) as db:
            pids.put(db.execute(text("select pg_backend_pid()")).scalar_one())
            profile = UserProfile(phone=old, phone_verified=True)
            assert prepare_phone_change(db, profile, {"phone": new})
            db.commit()
            return True

    with Session(pg_engine) as gate, ThreadPoolExecutor(max_workers=2) as pool:
        acquire_phone_scope_lock(gate, phone_a)
        futures = [pool.submit(worker, phone_a, unicode_b), pool.submit(worker, phone_b, unicode_a)]
        for _ in futures:
            _wait_blocked(pg_engine, pids.get(timeout=10))
        gate.commit()
        assert all(f.result(timeout=15) for f in futures)


@pytest.mark.asyncio
async def test_unicode_activation_and_ascii_verified_change_serialize(pg_engine, users, monkeypatch):
    """Activation and self-service proof cannot create equivalent owners."""
    from app.models.patient import Patient
    from app.services.patient_activation_service import (
        ActivationError,
        PatientActivationService,
    )
    from app.services.patient_otp_service import get_patient_otp_service
    from app.services.patient_phone_scope import acquire_phone_scope_lock

    unicode_phone = "+998٠٠٠٠٠٠٠١٣"
    assert len(unicode_phone) == len(PHONE_NEW)
    monkeypatch.setattr("app.services.patient_otp_service.settings.SMS_DEFAULT_PROVIDER", "mock")
    service = ProofService()
    monkeypatch.setattr(endpoint, "get_phone_verification_service", lambda: service)
    activation = PatientActivationService()
    otp = get_patient_otp_service()
    otp._reset_backend_for_tests()
    try:
        with Session(pg_engine, expire_on_commit=False) as db:
            patient = Patient(first_name="SYNTHETIC", last_name="Race", phone=unicode_phone)
            db.add(patient)
            db.commit()
            token = activation.issue_activation_token(db, patient.id)["activation_token"]
            await activation.request_activation_otp(db, token)
            code = otp.get_backend().last_sent_code[f"patact:{unicode_phone}"]
        pids = Queue()

        def activate():
            with Session(pg_engine) as db:
                pids.put(db.execute(text("select pg_backend_pid()")).scalar_one())
                try:
                    activation.activate(db, token, code)
                    return "activation"
                except ActivationError as exc:
                    assert exc.status_code == 409
                    return "activation-conflict"

        def update():
            with Session(pg_engine, autoflush=False) as db:
                pids.put(db.execute(text("select pg_backend_pid()")).scalar_one())
                try:
                    endpoint._phone_update(db, _context(users[0]), PHONE_NEW, "012345")
                    return "update"
                except PatientPhoneScopeConflict:
                    return "update-conflict"

        with Session(pg_engine) as gate, ThreadPoolExecutor(max_workers=2) as pool:
            acquire_phone_scope_lock(gate, PHONE_NEW)
            futures = [pool.submit(activate), pool.submit(update)]
            for _ in futures:
                _wait_blocked(pg_engine, pids.get(timeout=10))
            gate.commit()
            outcome = {f.result(timeout=20) for f in futures}
        assert outcome in ({"activation", "update-conflict"}, {"activation-conflict", "update"})
    finally:
        otp._reset_backend_for_tests()
