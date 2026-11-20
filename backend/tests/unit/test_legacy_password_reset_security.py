"""Canonical and legacy reset paths share safe issuance and redemption."""
from __future__ import annotations

import asyncio
import secrets
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.api.v1.endpoints import authentication, password_reset
from app.core.rate_limiter import limiter
from app.core.security import verify_password
from app.db.session import get_db
from app.models.authentication import PasswordResetToken
from app.services import password_reset_service as reset_module
from app.services.authentication_service import AuthenticationService


def _row(db, user, token):
    row = PasswordResetToken(user_id=user.id, token=token, used=False,
        expires_at=datetime.now(UTC) + timedelta(hours=1))
    db.add(row)
    db.commit()
    return row


def test_both_http_initiators_are_uniform_and_preserve_existing_reset(
    client, db_session, admin_user, monkeypatch
):
    scheduled = []
    def schedule(email, binding):
        scheduled.append((email, binding))
        return True
    monkeypatch.setattr(authentication, "schedule_email_reset", schedule)
    monkeypatch.setattr(password_reset, "schedule_email_reset", schedule)
    svc = reset_module.get_password_reset_service()
    old_raw = secrets.token_urlsafe(32)
    old = _row(db_session, admin_user, svc._hash_token(old_raw))
    for path in ("/api/v1/authentication/password-reset", "/api/v1/password-reset/initiate"):
        known = client.post(path, json={"email": admin_user.email})
        unknown = client.post(path, json={"email": "nobody@example.com"})
        assert known.status_code == unknown.status_code == 200
        assert known.json() == unknown.json()
    assert [email for email, _ in scheduled] == [admin_user.email, "nobody@example.com"] * 2
    assert [binding is not None for _, binding in scheduled] == [True, False] * 2
    db_session.refresh(old)
    assert not old.used
    assert svc.validate_reset_token(db_session, old_raw)["valid"]

    # Actually run the canonical delivery operation using a synthetic provider.
    sent = []
    async def fake_send(**kwargs):
        sent.append(kwargs)
        return True, "synthetic"
    monkeypatch.setattr(svc.email_service, "send_email_enhanced", fake_send)
    result = asyncio.run(svc.initiate_email_reset(db_session, admin_user.email))
    assert result["success"] is True and len(sent) == 1
    db_session.refresh(old)
    assert not old.used and svc.validate_reset_token(db_session, old_raw)["valid"]
    assert "/reset-password#token=" in sent[0]["text_content"]


@pytest.mark.parametrize("canonical", [True, False])
def test_legacy_confirm_rejects_database_hash_and_accepts_issued_token(
    client, db_session, admin_user, canonical
):
    svc = reset_module.get_password_reset_service()
    raw = secrets.token_urlsafe(32)
    stored = svc._hash_token(raw) if canonical else raw
    row = _row(db_session, admin_user, stored)
    if canonical:
        rejected = client.post("/api/v1/authentication/password-reset/confirm", json={
            "token": stored, "new_password": "Synthetic-New-Password-2"})
        assert rejected.status_code == 400
        db_session.refresh(row)
        assert not row.used
        assert not AuthenticationService().reset_password(db_session, stored, "Synthetic-New-Password-2")["success"]
    response = client.post("/api/v1/authentication/password-reset/confirm", json={
        "token": raw, "new_password": "Synthetic-New-Password-2"})
    assert response.status_code == 200, response.text
    replay = client.post("/api/v1/authentication/password-reset/confirm", json={
        "token": raw, "new_password": "Synthetic-Another-Password-3"})
    assert replay.status_code == 400
    db_session.refresh(row)
    db_session.refresh(admin_user)
    assert row.used and verify_password("Synthetic-New-Password-2", admin_user.hashed_password)


def test_shared_initiation_limit_across_both_real_routes(monkeypatch):
    monkeypatch.setattr(authentication, "schedule_email_reset", lambda email, binding: True)
    monkeypatch.setattr(password_reset, "schedule_email_reset", lambda email, binding: True)
    monkeypatch.setattr(reset_module.get_password_reset_service(), "snapshot_email_binding", lambda db, email: None)
    app = FastAPI()
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.dependency_overrides[get_db] = lambda: None
    app.include_router(authentication.router, prefix="/authentication")
    app.include_router(password_reset.router, prefix="/password-reset")
    limiter._storage.reset()
    monkeypatch.setattr(limiter, "enabled", True)
    try:
        with TestClient(app) as client:
            for path in ("/authentication/password-reset", "/password-reset/initiate", "/authentication/password-reset"):
                assert client.post(path, json={"email": "synthetic@example.com"}).status_code == 200
            assert client.post("/password-reset/initiate", json={"email": "synthetic@example.com"}).status_code == 429
    finally:
        limiter._storage.reset()


def test_outstanding_worker_keeps_its_slot_until_completion(monkeypatch):
    started, release = threading.Event(), threading.Event()
    calls = []
    def blocked(email, binding):
        calls.append(email)
        started.set()
        assert release.wait(5)
    slots = threading.BoundedSemaphore(1)
    monkeypatch.setattr(reset_module, "_EMAIL_RESET_PENDING", slots)
    monkeypatch.setattr(reset_module, "_dispatch_email_reset", blocked)
    with ThreadPoolExecutor(max_workers=1) as executor:
        monkeypatch.setattr(reset_module, "_EMAIL_RESET_EXECUTOR", executor)
        try:
            assert reset_module.schedule_email_reset("first@example.test", None)
            assert started.wait(5)
            assert not reset_module.schedule_email_reset("second@example.test", None)
            assert calls == ["first@example.test"]
        finally:
            release.set()
    assert slots.acquire(blocking=False)
    slots.release()


def test_worker_owns_and_closes_its_session(monkeypatch):
    from app.db import session as session_module
    calls = []
    class FakeSession:
        def __enter__(self):
            calls.append("open")
            return self
        def __exit__(self, *_):
            calls.append("close")
    class FakeService:
        async def initiate_email_reset(self, db, email, *, expected_binding):
            assert isinstance(db, FakeSession)
            calls.append(email)
            raise RuntimeError("synthetic-email-and-secret-must-not-log")
    monkeypatch.setattr(session_module, "SessionLocal", FakeSession)
    monkeypatch.setattr(reset_module, "get_password_reset_service", lambda: FakeService())
    reset_module._dispatch_email_reset("synthetic@example.com", (1, 1))
    assert calls == ["open", "synthetic@example.com", "close"]


@pytest.fixture
def isolated_reset_app(tmp_path, monkeypatch):
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from app.core.security import get_password_hash
    from app.db import session as session_module
    from app.db.base_class import Base
    from app.models.user import User

    engine = create_engine(f"sqlite:///{tmp_path / 'reset.sqlite'}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory() as db:
        user = User(username="SYNTHETIC_reset", email="synthetic-reset@example.com",
            hashed_password=get_password_hash("Synthetic-Old-Password-1"),
            role="Patient", is_active=True, is_superuser=False)
        db.add(user)
        db.commit()
        user_id = user.id
    monkeypatch.setattr(session_module, "SessionLocal", factory)
    app = FastAPI()
    app.include_router(authentication.router, prefix="/authentication")
    app.include_router(password_reset.router, prefix="/password-reset")
    def own_db():
        with factory() as db:
            yield db
    app.dependency_overrides[get_db] = own_db
    try:
        yield app, factory, user_id
    finally:
        engine.dispose()


def test_http_real_dispatch_preserves_existing_links_and_issued_token_works(
    isolated_reset_app, monkeypatch
):
    import re
    app, factory, user_id = isolated_reset_app
    svc = reset_module.get_password_reset_service()
    old_email, old_phone = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
    with factory() as db:
        for raw in (old_email, old_phone):
            db.add(PasswordResetToken(user_id=user_id, token=svc._hash_token(raw), used=False,
                expires_at=datetime.now(UTC) + timedelta(hours=1)))
        db.commit()
    deliveries, futures = [], []
    async def fake_send(**kwargs):
        deliveries.append(kwargs)
        return True, "synthetic"
    monkeypatch.setattr(svc.email_service, "send_email_enhanced", fake_send)
    with ThreadPoolExecutor(max_workers=2) as executor:
        submit = executor.submit
        def track(*args, **kwargs):
            future = submit(*args, **kwargs)
            futures.append(future)
            return future
        monkeypatch.setattr(executor, "submit", track)
        monkeypatch.setattr(reset_module, "_EMAIL_RESET_EXECUTOR", executor)
        monkeypatch.setattr(reset_module, "_EMAIL_RESET_PENDING", threading.BoundedSemaphore(4))
        with TestClient(app) as client:
            for route in ("/authentication/password-reset", "/password-reset/initiate"):
                response = client.post(route, json={"email": "synthetic-reset@example.com"})
                assert response.status_code == 200, response.text
            for future in futures:
                future.result(timeout=10)
            assert len(deliveries) == 2
            with factory() as db:
                assert svc.validate_reset_token(db, old_email)["valid"]
                assert svc.validate_reset_token(db, old_phone)["valid"]
            issued = re.search(r"/reset-password#token=([A-Za-z0-9_-]+)", deliveries[0]["text_content"]).group(1)
            confirm = client.post("/authentication/password-reset/confirm", json={
                "token": issued, "new_password": "Synthetic-New-Password-2"})
            assert confirm.status_code == 200, confirm.text
            assert client.post("/authentication/password-reset/confirm", json={
                "token": issued, "new_password": "Synthetic-New-Password-2"}).status_code == 400


@pytest.mark.parametrize("route", ["/authentication/password-reset", "/password-reset/initiate"])
def test_queued_reset_is_invalidated_by_auth_epoch_change(isolated_reset_app, monkeypatch, route):
    from app.models.user import User
    app, factory, user_id = isolated_reset_app
    svc = reset_module.get_password_reset_service()
    deliveries, futures = [], []
    async def fake_send(**kwargs):
        deliveries.append(kwargs)
        return True, "synthetic"
    monkeypatch.setattr(svc.email_service, "send_email_enhanced", fake_send)
    started, release = threading.Event(), threading.Event()
    def block():
        started.set()
        assert release.wait(10)
    with ThreadPoolExecutor(max_workers=1) as executor:
        blocker = executor.submit(block)
        assert started.wait(5)
        submit = executor.submit
        def track(*args, **kwargs):
            future = submit(*args, **kwargs)
            futures.append(future)
            return future
        monkeypatch.setattr(executor, "submit", track)
        monkeypatch.setattr(reset_module, "_EMAIL_RESET_EXECUTOR", executor)
        monkeypatch.setattr(reset_module, "_EMAIL_RESET_PENDING", threading.BoundedSemaphore(2))
        try:
            with TestClient(app) as client:
                response = client.post(route, json={"email": "synthetic-reset@example.com"})
                assert response.status_code == 200, response.text
            with factory() as db:
                user = db.get(User, user_id)
                user.auth_epoch += 1
                db.commit()
        finally:
            release.set()
        blocker.result(timeout=10)
        for future in futures:
            future.result(timeout=10)
    assert not deliveries
    with factory() as db:
        assert db.query(PasswordResetToken).filter_by(user_id=user_id).count() == 0


@pytest.mark.parametrize("route", ["/authentication/password-reset", "/password-reset/initiate"])
@pytest.mark.parametrize("failure", ["full", "lookup", "submission"])
def test_unavailable_is_uniform_for_known_and_unknown(client, db_session, admin_user, monkeypatch, route, failure):
    svc = reset_module.get_password_reset_service()
    if failure == "lookup":
        def unavailable(*_):
            raise reset_module.EmailResetUnavailable()
        monkeypatch.setattr(svc, "snapshot_email_binding", unavailable)
    elif failure == "full":
        monkeypatch.setattr(authentication, "schedule_email_reset", lambda *_: False)
        monkeypatch.setattr(password_reset, "schedule_email_reset", lambda *_: False)
    else:
        class BrokenExecutor:
            def submit(self, *_):
                raise RuntimeError("synthetic dispatch failure")
        monkeypatch.setattr(reset_module, "_EMAIL_RESET_EXECUTOR", BrokenExecutor())
        monkeypatch.setattr(reset_module, "_EMAIL_RESET_PENDING", threading.BoundedSemaphore(1))
    known = client.post("/api/v1" + route, json={"email": admin_user.email})
    unknown = client.post("/api/v1" + route, json={"email": "nobody@example.com"})
    assert known.status_code == unknown.status_code == 503
    assert known.json() == unknown.json()
    assert known.headers["retry-after"] == unknown.headers["retry-after"] == "60"
