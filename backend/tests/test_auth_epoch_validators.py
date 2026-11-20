"""User-generation revocation across HTTP, idempotency and WebSocket."""

from __future__ import annotations

import asyncio
import threading
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import jwt
import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_user_from_token, validate_token
from app.api.v1.endpoints.websocket_auth import (
    _resolve_websocket_user,
    resolve_websocket_token_user,
)
from app.core.config import settings
from app.core.user_token_claims import parse_user_auth_epoch, user_auth_epoch_matches
from app.db.base_class import Base
from app.middleware.idempotency_middleware import (
    IdempotencyMiddleware,
    _user_authorized_in_db,
    _user_id_from_principal,
)
from app.models.authentication import (
    PasswordResetToken,
    RefreshToken,
    TokenBlacklist,
    UserSession,
)
from app.models.two_factor_auth import TwoFactorAuth, TwoFactorRecovery
from app.models.user import User
from app.services.token_blacklist_service import (
    TokenBlacklistService,
    bump_user_auth_epoch,
    revoke_account_sessions_locked,
)


def _token(user_id: int, *, epoch=..., jti: str | None = None) -> str:
    payload = {
        "sub": str(user_id),
        "exp": datetime.now(UTC) + timedelta(minutes=5),
        "jti": jti or str(uuid4()),
    }
    if epoch is not ...:
        payload["auth_epoch"] = epoch
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


@pytest.mark.parametrize("bad", [None, True, False, -1, 1 << 63, "0", 0.0, [], {}])
def test_malformed_epoch_is_not_a_valid_user_generation(bad):
    assert parse_user_auth_epoch({"auth_epoch": bad}) is None
    assert not user_auth_epoch_matches({"auth_epoch": bad}, 0)


def test_legacy_sentinel_never_revives_old_tokens_and_allows_fresh_login(
    db_session, admin_user
):
    user_id = admin_user.id
    old = _token(user_id)
    db_session.add(
        TokenBlacklist(
            jti=f"sentinel-{uuid4()}",
            user_id=user_id,
            reason="all_user_tokens:synthetic",
            expires_at=datetime.now(UTC) + timedelta(minutes=5),
        )
    )
    db_session.flush()

    with pytest.raises(HTTPException) as failure:
        asyncio.run(get_current_user(token=old, db=db_session))
    assert failure.value.status_code == 401
    assert not _user_authorized_in_db(db_session, user_id, None, None)[0]
    assert resolve_websocket_token_user(old, db_session) is None

    # Model the migration's active-sentinel backfill using the database, not
    # the identity-map instance held by the request.
    db_session.execute(text("UPDATE users SET auth_epoch = 1 WHERE id = :id"), {"id": user_id})
    fresh = _token(user_id, epoch=1)
    with pytest.raises(HTTPException):
        asyncio.run(get_current_user(token=old, db=db_session))
    assert asyncio.run(get_current_user(token=fresh, db=db_session)).id == user_id
    assert _user_authorized_in_db(db_session, user_id, None, None, token_epoch=1)[0]
    assert resolve_websocket_token_user(fresh, db_session).id == user_id

    db_session.execute(text("UPDATE users SET auth_epoch = 2 WHERE id = :id"), {"id": user_id})
    with pytest.raises(HTTPException):
        asyncio.run(get_current_user(token=fresh, db=db_session))
    assert not _user_authorized_in_db(db_session, user_id, None, None, token_epoch=1)[0]
    assert resolve_websocket_token_user(fresh, db_session) is None


def test_matching_epoch_never_bypasses_individual_jti_revocation(db_session, admin_user):
    admin_user.auth_epoch = 1
    db_session.flush()
    jti = str(uuid4())
    db_session.add(
        TokenBlacklist(
            jti=jti,
            user_id=admin_user.id,
            reason="synthetic",
            expires_at=datetime.now(UTC) + timedelta(minutes=5),
        )
    )
    db_session.flush()
    token = _token(admin_user.id, epoch=1, jti=jti)
    assert TokenBlacklistService.is_token_blacklisted(
        db_session, jti, user_id=admin_user.id, auth_epoch=1
    )
    with pytest.raises(HTTPException):
        asyncio.run(get_current_user(token=token, db=db_session))
    assert not _user_authorized_in_db(db_session, admin_user.id, None, jti, token_epoch=1)[0]
    assert resolve_websocket_token_user(token, db_session) is None


def test_synchronous_token_helpers_check_live_authentication_state(db_session, admin_user):
    user_id = admin_user.id
    jti = str(uuid4())
    token = _token(user_id, jti=jti)
    assert validate_token(token, db_session) is not None
    assert get_user_from_token(token, db_session).id == user_id

    db_session.add(TokenBlacklist(
        jti=jti, user_id=user_id, reason="synthetic",
        expires_at=datetime.now(UTC) + timedelta(minutes=5),
    ))
    db_session.flush()
    assert validate_token(token, db_session) is None
    assert get_user_from_token(token, db_session) is None

    fresh = _token(user_id)
    db_session.execute(text("UPDATE users SET auth_epoch = 1 WHERE id = :id"), {"id": user_id})
    assert validate_token(fresh, db_session) is None
    assert get_user_from_token(fresh, db_session) is None
    active = _token(user_id, epoch=1)
    assert get_user_from_token(active, db_session).id == user_id
    db_session.execute(text("UPDATE users SET is_active = false WHERE id = :id"), {"id": user_id})
    assert validate_token(active, db_session) is None
    assert get_user_from_token(active, db_session) is None


def test_unknown_websocket_subject_is_not_logged(db_session, caplog):
    subject = f"SYNTHETIC_PRIVATE_{uuid4().hex}@example.invalid"
    assert _resolve_websocket_user({"sub": subject}, db_session) is None
    assert "no user matched" in caplog.text
    assert subject not in caplog.text


def test_signed_subject_cannot_switch_accounts_after_username_reuse(db_session, admin_user):
    old_name = admin_user.username
    user_id = admin_user.id
    payload = {
        "sub": str(user_id), "username": old_name, "auth_epoch": 0,
        "jti": str(uuid4()), "exp": datetime.now(UTC) + timedelta(minutes=5),
    }
    token = jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    admin_user.username = f"SYNTHETIC_renamed_{uuid4().hex}"
    db_session.flush()
    second = User(username=old_name, hashed_password="synthetic", role="Doctor", is_active=True)
    db_session.add(second)
    db_session.flush()
    assert second.id != user_id and second.auth_epoch == 0

    assert asyncio.run(get_current_user(token=token, db=db_session)).id == user_id
    assert get_user_from_token(token, db_session).id == user_id
    assert resolve_websocket_token_user(token, db_session).id == user_id
    request = SimpleNamespace(headers={"Authorization": f"Bearer {token}"})
    principal = IdempotencyMiddleware._verified_principal(None, request)
    assert _user_id_from_principal(principal) == (user_id, None)
    assert _user_authorized_in_db(db_session, user_id, None, payload["jti"])[0]

    legacy = jwt.encode({**payload, "sub": old_name}, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    with pytest.raises(HTTPException):
        asyncio.run(get_current_user(token=legacy, db=db_session))
    assert get_user_from_token(legacy, db_session) is None
    assert resolve_websocket_token_user(legacy, db_session) is None
    request.headers["Authorization"] = f"Bearer {legacy}"
    assert IdempotencyMiddleware._verified_principal(None, request) is None


def test_push_throttle_bucket_uses_only_stable_numeric_subject():
    from app.api.v1.endpoints.push_devices import _user_throttle_key

    def bucket(sub, username):
        token = jwt.encode(
            {"sub": sub, "username": username, "exp": datetime.now(UTC) + timedelta(minutes=5)},
            settings.SECRET_KEY, algorithm=settings.ALGORITHM,
        )
        return _user_throttle_key(SimpleNamespace(headers={"Authorization": f"Bearer {token}"}))

    assert bucket("42", "SYNTHETIC_old") == bucket("00042", "SYNTHETIC_new") == "push-user:42"
    assert bucket("43", "SYNTHETIC_old") == "push-user:43"


@pytest.mark.parametrize("endpoint", ["ws_queue_authenticated", "ws_queue_optional_auth"])
def test_queue_closes_during_continuous_traffic_when_database_stalls(monkeypatch, endpoint):
    from app.api.v1.endpoints import websocket_auth

    release = threading.Event()
    calls = 0
    user = SimpleNamespace(username="SYNTHETIC_user", role="Admin", id=42)

    def authorization(_token, _department):
        nonlocal calls
        calls += 1
        if calls == 1:
            return user
        release.wait(2)
        return user

    class Socket:
        client = SimpleNamespace(host="127.0.0.1")
        close = AsyncMock()
        send_json = AsyncMock()

        async def receive_text(self):
            await asyncio.sleep(0.001)
            return '{"type":"ping"}'

    socket = Socket()
    manager = SimpleNamespace(connect=AsyncMock(), disconnect=Mock())
    monkeypatch.setattr(websocket_auth, "reauthorize_queue_websocket", authorization)
    monkeypatch.setattr(websocket_auth, "QUEUE_WS_AUTH_RECHECK_SECONDS", 0.02)
    monkeypatch.setattr(websocket_auth, "QUEUE_WS_AUTH_TIMEOUT_SECONDS", 0.02)
    monkeypatch.setattr(websocket_auth, "ws_manager", manager)
    monkeypatch.setattr(websocket_auth, "_handle_authenticated_message", AsyncMock())
    monkeypatch.setattr(websocket_auth.websocket_rate_limiter, "check_rate_limit", lambda _ip: (True, ""))
    monkeypatch.setattr(websocket_auth.websocket_rate_limiter, "record_connection", lambda _ip: None)
    monkeypatch.setattr(websocket_auth.websocket_rate_limiter, "remove_connection", lambda _ip: None)
    monkeypatch.setattr("app.api.v1.endpoints.ws_token.extract_ws_token", lambda _socket: "synthetic")
    monkeypatch.setattr("app.api.v1.endpoints.ws_token.accept_echoing_subprotocol", AsyncMock())

    async def run():
        try:
            await asyncio.wait_for(
                getattr(websocket_auth, endpoint)(socket, "synthetic", "2026-01-01"), 0.5
            )
        finally:
            release.set()

    asyncio.run(run())
    assert calls >= 2
    socket.close.assert_awaited_once()
    manager.disconnect.assert_called_once_with(socket, "synthetic::2026-01-01")


def test_mounted_queue_closes_during_continuous_traffic_when_database_stalls(monkeypatch):
    from app.api.v1.endpoints import websocket_auth
    from app.ws import queue_ws

    release = threading.Event()
    calls = 0
    user = SimpleNamespace(username="SYNTHETIC_user", role="Admin", id=42)

    def stalled_database(_headers, _token):
        nonlocal calls
        calls += 1
        if calls == 1:
            return user
        release.wait(2)
        return user

    class Socket:
        headers = {"origin": "http://localhost:5173"}
        url = SimpleNamespace(path="/ws/queue")
        close = AsyncMock()
        send_json = AsyncMock()

        async def receive_text(self):
            await asyncio.sleep(0.001)
            return '{"type":"pong"}'

    socket = Socket()
    manager = SimpleNamespace(connect=AsyncMock(), disconnect=Mock())
    monkeypatch.setenv("CORS_DISABLE", "0")
    monkeypatch.setenv("CORS_ORIGINS", "http://localhost:5173")
    monkeypatch.setattr(queue_ws, "_resolve_ws_auth", stalled_database)
    monkeypatch.setattr(websocket_auth, "_has_department_access", lambda _user, _department: True)
    monkeypatch.setattr(websocket_auth, "QUEUE_WS_AUTH_RECHECK_SECONDS", 0.02)
    monkeypatch.setattr(queue_ws, "QUEUE_AUTH_TIMEOUT_SECONDS", 0.02)
    monkeypatch.setattr(queue_ws, "ws_manager", manager)
    monkeypatch.setattr("app.api.v1.endpoints.ws_token.extract_ws_token", lambda _socket: "synthetic")
    monkeypatch.setattr("app.api.v1.endpoints.ws_token.accept_echoing_subprotocol", AsyncMock())

    # Exercise the endpoint object actually registered for the mounted route.
    endpoint = next(route.endpoint for route in queue_ws.router.routes if route.path == "/ws/queue")

    async def run():
        try:
            await asyncio.wait_for(endpoint(socket, "synthetic", "2026-01-01"), 0.5)
        finally:
            release.set()

    asyncio.run(run())
    assert calls >= 2
    socket.close.assert_awaited_once()
    manager.disconnect.assert_called_once_with(socket, "synthetic::2026-01-01")


def test_mounted_queue_route_rejects_stalled_recheck_with_live_client(monkeypatch):
    from fastapi import FastAPI, WebSocketDisconnect
    from fastapi.testclient import TestClient

    from app.api.v1.endpoints import websocket_auth
    from app.ws import queue_ws

    release = threading.Event()
    calls = 0
    user = SimpleNamespace(username="SYNTHETIC_user", role="Admin", id=42)

    def stalled_database(_headers, _token):
        nonlocal calls
        calls += 1
        if calls == 1:
            return user
        release.wait(2)
        return user

    manager = SimpleNamespace(connect=AsyncMock(), disconnect=Mock())
    monkeypatch.setenv("CORS_ORIGINS", "http://localhost:5173")
    monkeypatch.setenv("CORS_DISABLE", "0")
    monkeypatch.setattr(queue_ws, "_resolve_ws_auth", stalled_database)
    monkeypatch.setattr(websocket_auth, "_has_department_access", lambda _user, _department: True)
    monkeypatch.setattr(websocket_auth, "QUEUE_WS_AUTH_RECHECK_SECONDS", 0.02)
    monkeypatch.setattr(queue_ws, "QUEUE_AUTH_TIMEOUT_SECONDS", 0.02)
    monkeypatch.setattr(queue_ws, "ws_manager", manager)
    app = FastAPI()
    app.include_router(queue_ws.router)
    try:
        with TestClient(app) as client:
            with client.websocket_connect(
                "/ws/queue?department=synthetic&date=2026-01-01",
                headers={"origin": "http://localhost:5173", "authorization": "Bearer synthetic"},
            ) as socket:
                assert socket.receive_json()["type"] == "queue.connected"
                for _ in range(30):
                    socket.send_text('{"type":"pong"}')
                    threading.Event().wait(0.002)
                with pytest.raises(WebSocketDisconnect) as closed:
                    socket.receive_json()
                assert closed.value.code == 1008
                release.set()
    finally:
        release.set()
    assert calls >= 2
    manager.disconnect.assert_called_once()


def test_blacklist_database_failure_is_fail_closed():
    class BrokenDatabase:
        def query(self, *_args, **_kwargs):
            raise RuntimeError("synthetic database failure")

    assert TokenBlacklistService.is_token_blacklisted(BrokenDatabase(), "synthetic")
    assert TokenBlacklistService.is_token_blacklisted(
        BrokenDatabase(), "synthetic", user_id=1, auth_epoch=1
    )


def test_epoch_helper_rejects_dirty_user_without_discarding_changes(db_session, admin_user):
    original_password = admin_user.hashed_password
    admin_user.hashed_password = "SYNTHETIC-pending-password"
    with pytest.raises(ValueError):
        bump_user_auth_epoch(db_session, admin_user.id)
    assert admin_user.hashed_password == "SYNTHETIC-pending-password"
    assert admin_user.hashed_password != original_password
    assert admin_user.auth_epoch == 0


def test_account_revocation_is_caller_owned_and_rolls_back_as_one_transaction():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(
        engine,
        tables=[User.__table__, TokenBlacklist.__table__, UserSession.__table__, RefreshToken.__table__, PasswordResetToken.__table__, TwoFactorAuth.__table__, TwoFactorRecovery.__table__],
    )
    db_session = Session(engine, autoflush=False, expire_on_commit=False)
    admin_user = User(username=f"SYNTHETIC_{uuid4().hex}", hashed_password="synthetic", is_active=True)
    db_session.add(admin_user)
    db_session.flush()
    now = datetime.now(UTC)
    session = UserSession(
        user_id=admin_user.id,
        refresh_token=f"synthetic-{uuid4()}",
        expires_at=now + timedelta(hours=1),
        revoked=False,
    )
    refresh = RefreshToken(
        user_id=admin_user.id,
        token=f"synthetic-{uuid4()}",
        jti=str(uuid4()),
        expires_at=now + timedelta(hours=1),
        revoked=False,
    )
    db_session.add_all([session, refresh])
    reset = PasswordResetToken(user_id=admin_user.id, token=uuid4().hex, expires_at=now + timedelta(hours=1), used=False)
    db_session.add(reset)
    two_factor = TwoFactorAuth(user_id=admin_user.id)
    db_session.add(two_factor)
    db_session.flush()
    recovery = TwoFactorRecovery(
        two_factor_auth_id=two_factor.id, recovery_type="email",
        recovery_value="synthetic@example.invalid", verified=False,
    )
    db_session.add(recovery)
    db_session.flush()
    try:
        with db_session.begin_nested() as transaction:
            locked_user = (
                db_session.query(type(admin_user))
                .filter_by(id=admin_user.id)
                .with_for_update(key_share=True)
                .populate_existing()
                .one()
            )
            assert revoke_account_sessions_locked(db_session, locked_user, revoke_password_resets=True) == 1
            assert locked_user.auth_epoch == 1
            assert session.revoked is True
            assert refresh.revoked is True
            assert reset.used is True
            db_session.refresh(recovery)
            assert recovery.verified is True
            transaction.rollback()
        db_session.refresh(admin_user)
        db_session.refresh(session)
        db_session.refresh(refresh)
        db_session.refresh(reset)
        db_session.refresh(recovery)
        assert admin_user.auth_epoch == 0
        assert session.revoked is False
        assert refresh.revoked is False
        assert reset.used is False
        assert recovery.verified is False
    finally:
        db_session.close()
        engine.dispose()


def test_cashier_socket_closes_and_unregisters_after_live_revocation(monkeypatch):
    from app.ws import cashier_ws

    checks = iter([None, 4401])
    monkeypatch.setattr(cashier_ws, "_cashier_token_close_code", lambda _token: next(checks))
    monkeypatch.setattr(cashier_ws, "CASHIER_WS_AUTH_RECHECK_SECONDS", 0.01)
    monkeypatch.setattr("app.api.v1.endpoints.ws_token.extract_ws_token", lambda _ws: "synthetic")

    class Socket:
        accept = AsyncMock()
        close = AsyncMock()
        send_json = AsyncMock()

        async def receive_text(self):
            await asyncio.sleep(60)

    websocket = Socket()
    asyncio.run(cashier_ws.cashier_websocket(websocket))
    websocket.close.assert_awaited_once_with(code=4401)
    assert websocket not in cashier_ws.cashier_ws_manager.connections
