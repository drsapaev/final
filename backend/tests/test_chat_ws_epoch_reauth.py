"""Real JWT/DB regressions for chat WebSocket authorization and revocation."""
from __future__ import annotations

import asyncio
import json
import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock

import jwt
import pytest
from sqlalchemy.orm import sessionmaker

from app.api.deps import create_access_token
from app.api.v1.endpoints import ai_chat
from app.core.config import settings
from app.models.authentication import TokenBlacklist
from app.models.user import User
from app.services.ai_chat_api_service import AIChatApiService
from app.ws import chat_ws


@pytest.fixture
def ws_identity(test_db):
    sessions = sessionmaker(bind=test_db, expire_on_commit=False)
    with sessions() as db:
        user = User(
            username="SYNTHETIC-ws-" + uuid.uuid4().hex,
            hashed_password="not-a-password",
            role="Admin",
            is_active=True,
            is_superuser=False,
            auth_epoch=0,
        )
        db.add(user)
        db.commit()
        user_id = user.id
    token = create_access_token({"sub": str(user_id), "auth_epoch": 0})
    yield user_id, token, sessions
    with sessions() as db:
        db.query(TokenBlacklist).filter(TokenBlacklist.user_id == user_id).delete()
        user = db.get(User, user_id)
        if user is not None:
            db.delete(user)
        db.commit()


def _revoke(sessions, user_id, token, action):
    with sessions() as db:
        user = db.get(User, user_id)
        if action == "epoch":
            user.auth_epoch += 1
        elif action == "inactive":
            user.is_active = False
        elif action == "role":
            user.role = "SYNTHETIC-no-ai-permission"
        elif action == "blacklist":
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
            db.add(TokenBlacklist(jti=payload["jti"], user_id=user_id,
                                  expires_at=datetime.now(UTC) + timedelta(minutes=5), reason="logout"))
        db.commit()


def _ai_user(db, token):
    return AIChatApiService(db).authenticate_websocket_user(
        token=token, secret_key=settings.SECRET_KEY, algorithm=settings.ALGORITHM
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("action", ["epoch", "inactive", "blacklist"])
async def test_chat_and_ai_handshakes_reject_live_revocation(ws_identity, action):
    user_id, token, sessions = ws_identity
    with sessions() as db:
        assert (await chat_ws._authenticate_by_token(token, db)).id == user_id
        assert _ai_user(db, token).id == user_id
        _revoke(sessions, user_id, token, action)
        assert await chat_ws._authenticate_by_token(token, db) is None
        assert _ai_user(db, token) is None


@pytest.mark.asyncio
async def test_chat_and_ai_reject_expired_and_scoped_tokens(ws_identity):
    user_id, _, sessions = ws_identity
    expired = jwt.encode({"sub": str(user_id), "auth_epoch": 0,
                          "exp": datetime.now(UTC) - timedelta(seconds=1)},
                         settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    scoped = create_access_token({"sub": str(user_id), "scope": "patient_portal",
                                  "patient_id": 1, "auth_epoch": 0})
    with sessions() as db:
        for token in (expired, scoped):
            assert await chat_ws._authenticate_by_token(token, db) is None
            assert _ai_user(db, token) is None


@pytest.mark.asyncio
@pytest.mark.parametrize("epoch", [True, -1, "0", 2**63])
async def test_chat_and_ai_reject_malformed_epochs(ws_identity, epoch):
    user_id, _, sessions = ws_identity
    token = create_access_token({"sub": str(user_id), "auth_epoch": epoch})
    with sessions() as db:
        assert await chat_ws._authenticate_by_token(token, db) is None
        assert _ai_user(db, token) is None


@pytest.mark.asyncio
async def test_chat_and_ai_fail_closed_when_blacklist_query_fails(ws_identity, monkeypatch):
    _, token, sessions = ws_identity
    def fail(*_args, **_kwargs):
        raise RuntimeError("SYNTHETIC database failure")

    monkeypatch.setattr(
        "app.services.token_blacklist_service.TokenBlacklistService.is_token_blacklisted", fail
    )
    with sessions() as db:
        assert await chat_ws._authenticate_by_token(token, db) is None
        assert _ai_user(db, token) is None


@pytest.mark.asyncio
async def test_legacy_sentinel_never_revives_old_tokens_or_blocks_new_epoch(ws_identity):
    user_id, old_token, sessions = ws_identity
    with sessions() as db:
        db.add(TokenBlacklist(jti="synthetic-sentinel-" + uuid.uuid4().hex[:10],
                              user_id=user_id, reason="all_user_tokens:test",
                              expires_at=datetime.now(UTC) + timedelta(minutes=5)))
        db.commit()
        assert await chat_ws._authenticate_by_token(old_token, db) is None
        assert _ai_user(db, old_token) is None
        db.get(User, user_id).auth_epoch = 1
        db.commit()
        new_token = create_access_token({"sub": str(user_id), "auth_epoch": 1})
        assert await chat_ws._authenticate_by_token(old_token, db) is None
        assert _ai_user(db, old_token) is None
        assert (await chat_ws._authenticate_by_token(new_token, db)).id == user_id
        assert _ai_user(db, new_token).id == user_id


class _ChatSocket:
    def __init__(self, token):
        self.client = SimpleNamespace(host="127.0.0.1")
        self._auth = json.dumps({"type": "auth", "token": token})
        self.sent = []
        self.closed = []
        self.started = asyncio.Event()
        self.wait = asyncio.Event()

    async def accept(self):
        pass

    async def receive_text(self):
        if self._auth is not None:
            auth, self._auth = self._auth, None
            return auth
        await self.wait.wait()
        raise AssertionError("idle socket should be cancelled")

    async def send_json(self, payload):
        self.sent.append(payload)
        self.started.set()

    async def close(self, **kwargs):
        self.closed.append(kwargs)


@pytest.mark.asyncio
@pytest.mark.parametrize("action", ["epoch", "inactive", "blacklist"])
async def test_idle_chat_socket_is_closed_on_revocation(ws_identity, monkeypatch, action):
    user_id, token, sessions = ws_identity
    monkeypatch.setattr(chat_ws, "SessionLocal", sessions)
    monkeypatch.setattr(chat_ws, "WS_AUTH_RECHECK_SECONDS", 0.03)
    monkeypatch.setattr(chat_ws.chat_manager, "active_connections", {})
    monkeypatch.setattr(chat_ws.chat_manager, "_ensure_redis_bridge", AsyncMock())
    remove = []
    monkeypatch.setattr(chat_ws, "websocket_rate_limiter", SimpleNamespace(
        check_rate_limit=lambda _: (True, ""), record_connection=lambda _: None,
        remove_connection=lambda ip: remove.append(ip),
    ))
    ws = _ChatSocket(token)
    task = asyncio.create_task(chat_ws.chat_websocket_handler(ws))
    await asyncio.wait_for(ws.started.wait(), timeout=2)
    _revoke(sessions, user_id, token, action)
    await asyncio.wait_for(task, timeout=2)
    assert ws.closed == [{"code": 4001, "reason": "Authorization expired"}]
    assert user_id not in chat_ws.chat_manager.active_connections
    assert remove == ["127.0.0.1"]


@pytest.mark.asyncio
async def test_chat_watchdog_fails_closed_when_db_check_stalls(ws_identity, monkeypatch):
    import time

    user_id, token, sessions = ws_identity
    monkeypatch.setattr(chat_ws, "SessionLocal", sessions)
    monkeypatch.setattr(chat_ws, "WS_AUTH_RECHECK_SECONDS", 0.05)
    monkeypatch.setattr(chat_ws.chat_manager, "active_connections", {})
    monkeypatch.setattr(chat_ws.chat_manager, "_ensure_redis_bridge", AsyncMock())
    monkeypatch.setattr(chat_ws, "websocket_rate_limiter", SimpleNamespace(
        check_rate_limit=lambda _: (True, ""), record_connection=lambda _: None,
        remove_connection=lambda _: None,
    ))
    ws = _ChatSocket(token)
    task = asyncio.create_task(chat_ws.chat_websocket_handler(ws))
    await asyncio.wait_for(ws.started.wait(), timeout=2)
    monkeypatch.setattr(chat_ws, "WS_AUTH_DB_TIMEOUT_SECONDS", 0.03)
    monkeypatch.setattr(chat_ws, "_chat_session_is_current", lambda *_: time.sleep(0.2) or True)
    await asyncio.wait_for(task, timeout=1)
    assert ws.closed == [{"code": 4001, "reason": "Authorization expired"}]
    assert user_id not in chat_ws.chat_manager.active_connections


@pytest.mark.asyncio
async def test_idle_chat_socket_closes_when_token_expires(ws_identity, monkeypatch):
    user_id, _, sessions = ws_identity
    token = create_access_token({"sub": str(user_id), "auth_epoch": 0},
                                expires_delta=timedelta(seconds=2))
    monkeypatch.setattr(chat_ws, "SessionLocal", sessions)
    monkeypatch.setattr(chat_ws, "WS_AUTH_RECHECK_SECONDS", 0.03)
    monkeypatch.setattr(chat_ws.chat_manager, "active_connections", {})
    monkeypatch.setattr(chat_ws.chat_manager, "_ensure_redis_bridge", AsyncMock())
    monkeypatch.setattr(chat_ws, "websocket_rate_limiter", SimpleNamespace(
        check_rate_limit=lambda _: (True, ""), record_connection=lambda _: None,
        remove_connection=lambda _: None,
    ))
    ws = _ChatSocket(token)
    task = asyncio.create_task(chat_ws.chat_websocket_handler(ws))
    await asyncio.wait_for(ws.started.wait(), timeout=2)
    await asyncio.wait_for(task, timeout=4)
    assert ws.closed == [{"code": 4001, "reason": "Authorization expired"}]
    assert user_id not in chat_ws.chat_manager.active_connections


class _AISocket:
    def __init__(self, message=None):
        self.message = message
        self.closed = []
        self.sent = []
        self.started = asyncio.Event()
        self.wait = asyncio.Event()

    async def close(self, **kwargs):
        self.closed.append(kwargs)

    async def send_json(self, payload):
        self.sent.append(payload)

    async def iter_json(self):
        if self.message is not None:
            yield self.message
        self.started.set()
        await self.wait.wait()


@pytest.mark.asyncio
@pytest.mark.parametrize("action", ["epoch", "inactive", "blacklist", "role"])
async def test_idle_ai_socket_is_closed_on_revocation(ws_identity, monkeypatch, action):
    user_id, token, sessions = ws_identity
    import app.db.session as session_module

    monkeypatch.setattr(session_module, "SessionLocal", sessions)
    monkeypatch.setattr(chat_ws, "WS_AUTH_RECHECK_SECONDS", 0.03)
    monkeypatch.setattr(ai_chat, "accept_echoing_subprotocol", AsyncMock())
    monkeypatch.setattr(ai_chat, "extract_ws_token", lambda _: token)
    monkeypatch.setattr(ai_chat, "get_chat_service", lambda _: SimpleNamespace())
    ws = _AISocket()
    with sessions() as endpoint_db:
        task = asyncio.create_task(ai_chat.chat_websocket(ws, endpoint_db))
        await asyncio.wait_for(ws.started.wait(), timeout=2)
        _revoke(sessions, user_id, token, action)
        await asyncio.wait_for(task, timeout=2)
    assert ws.closed == [{"code": 4001, "reason": "Authorization expired"}]
    assert ws.sent == []


@pytest.mark.asyncio
async def test_ai_inflight_response_is_not_sent_after_logout(ws_identity, monkeypatch):
    user_id, token, sessions = ws_identity
    import app.db.session as session_module

    monkeypatch.setattr(session_module, "SessionLocal", sessions)
    monkeypatch.setattr(chat_ws, "WS_AUTH_RECHECK_SECONDS", 0.03)
    monkeypatch.setattr(ai_chat, "accept_echoing_subprotocol", AsyncMock())
    monkeypatch.setattr(ai_chat, "extract_ws_token", lambda _: token)
    entered = asyncio.Event()
    cancelled = asyncio.Event()

    async def send_message(**_kwargs):
        entered.set()
        try:
            await asyncio.Event().wait()
        finally:
            cancelled.set()

    monkeypatch.setattr(ai_chat, "get_chat_service", lambda _: SimpleNamespace(send_message=send_message))
    ws = _AISocket({"type": "message", "session_id": 1, "content": "SYNTHETIC"})
    with sessions() as endpoint_db:
        task = asyncio.create_task(ai_chat.chat_websocket(ws, endpoint_db))
        await asyncio.wait_for(entered.wait(), timeout=2)
        _revoke(sessions, user_id, token, "epoch")
        await asyncio.wait_for(task, timeout=2)
    assert cancelled.is_set()
    assert ws.closed == [{"code": 4001, "reason": "Authorization expired"}]
    assert ws.sent == []


def test_stale_disconnect_does_not_remove_replacement():
    manager = chat_ws.ChatConnectionManager()
    old, replacement = object(), object()
    manager.active_connections[7] = replacement
    manager.disconnect(7, old)
    assert manager.active_connections[7] is replacement


@pytest.mark.asyncio
async def test_ai_does_not_emit_result_when_revoked_during_blocking_service(ws_identity, monkeypatch):
    """A stalled legacy sync DB call may delay watchdog, not disclose its result."""
    import threading
    import time

    import app.db.session as session_module

    user_id, token, sessions = ws_identity
    monkeypatch.setattr(session_module, "SessionLocal", sessions)
    monkeypatch.setattr(chat_ws, "WS_AUTH_RECHECK_SECONDS", 0.03)
    monkeypatch.setattr(ai_chat, "accept_echoing_subprotocol", AsyncMock())
    monkeypatch.setattr(ai_chat, "extract_ws_token", lambda _: token)
    entered = threading.Event()
    writer_done = threading.Event()

    async def send_message(**_kwargs):
        entered.set()
        time.sleep(0.2)  # Model a pre-existing blocking sync database call.
        return SimpleNamespace(content="SYNTHETIC private result", id=1,
                               provider="synthetic", model="synthetic", tokens_used=1,
                               latency_ms=1, was_cached=False)

    def revoke_in_thread():
        if entered.wait(timeout=2):
            _revoke(sessions, user_id, token, "epoch")
        writer_done.set()

    monkeypatch.setattr(ai_chat, "get_chat_service", lambda _: SimpleNamespace(send_message=send_message))
    ws = _AISocket({"type": "message", "session_id": 1, "content": "SYNTHETIC"})
    writer = threading.Thread(target=revoke_in_thread)
    writer.start()
    with sessions() as endpoint_db:
        task = asyncio.create_task(ai_chat.chat_websocket(ws, endpoint_db))
        await asyncio.wait_for(task, timeout=3)
    writer.join(timeout=2)
    assert writer_done.is_set()
    assert ws.closed == [{"code": 4001, "reason": "Authorization expired"}]
    assert ws.sent == []


@pytest.mark.asyncio
@pytest.mark.parametrize("guard_allowed", [False, True])
async def test_concurrent_watchdog_and_ai_guard_close_socket_only_once(monkeypatch, guard_allowed):
    """A blocked close lets both guards observe revocation concurrently."""
    import threading
    from unittest.mock import Mock

    first_close = asyncio.Event()
    allow_close = asyncio.Event()
    checked = threading.Event()

    class BlockingCloseSocket:
        def __init__(self):
            self.closed = []

        async def close(self, **kwargs):
            self.closed.append(kwargs)
            if len(self.closed) == 1:
                first_close.set()
                await allow_close.wait()

    def check(*_args):
        checked.set()
        return guard_allowed

    monkeypatch.setattr(chat_ws, "WS_AUTH_RECHECK_SECONDS", 0.01)
    monkeypatch.setattr(ai_chat, "_ai_ws_session_is_current", check)
    websocket = BlockingCloseSocket()
    revoked = asyncio.Event()
    close_lock = asyncio.Lock()
    owner = SimpleNamespace(cancel=Mock())
    watchdog = asyncio.create_task(
        chat_ws.monitor_websocket_authorization(websocket, lambda: False, revoked, owner, close_lock)
    )
    await asyncio.wait_for(first_close.wait(), 2)
    sender = asyncio.create_task(ai_chat._ai_ws_authorized_or_close(websocket, "synthetic", 1, revoked, close_lock))
    assert await asyncio.to_thread(checked.wait, 2)
    await asyncio.sleep(0.03)
    allow_close.set()
    assert not await asyncio.wait_for(sender, 2)
    await asyncio.wait_for(watchdog, 2)
    assert websocket.closed == [{"code": 4001, "reason": "Authorization expired"}]
    owner.cancel.assert_called_once()


@pytest.mark.asyncio
async def test_ai_guard_closes_first_then_watchdog_does_not_close_again(monkeypatch):
    from unittest.mock import Mock

    first_close = asyncio.Event()
    allow_close = asyncio.Event()

    class BlockingCloseSocket:
        def __init__(self):
            self.closed = []

        async def close(self, **kwargs):
            self.closed.append(kwargs)
            first_close.set()
            await allow_close.wait()

    monkeypatch.setattr(chat_ws, "WS_AUTH_RECHECK_SECONDS", 0.01)
    monkeypatch.setattr(ai_chat, "_ai_ws_session_is_current", lambda *_: False)
    websocket = BlockingCloseSocket()
    revoked, close_lock = asyncio.Event(), asyncio.Lock()
    owner = SimpleNamespace(cancel=Mock())
    sender = asyncio.create_task(
        ai_chat._ai_ws_authorized_or_close(websocket, "synthetic", 1, revoked, close_lock)
    )
    await asyncio.wait_for(first_close.wait(), 2)
    watchdog = asyncio.create_task(
        chat_ws.monitor_websocket_authorization(websocket, lambda: False, revoked, owner, close_lock)
    )
    await asyncio.sleep(0.03)
    allow_close.set()
    assert not await asyncio.wait_for(sender, 2)
    await asyncio.wait_for(watchdog, 2)
    assert websocket.closed == [{"code": 4001, "reason": "Authorization expired"}]
    owner.cancel.assert_called_once()


@pytest.mark.asyncio
async def test_ai_successful_guard_cannot_send_after_watchdog_starts_close(monkeypatch):
    close_entered, release_close = asyncio.Event(), asyncio.Event()

    class Socket:
        def __init__(self):
            self.sent = []
            self.closed = []

        async def close(self, **kwargs):
            self.closed.append(kwargs)
            close_entered.set()
            await release_close.wait()

        async def send_json(self, payload):
            self.sent.append(payload)

    monkeypatch.setattr(ai_chat, "_ai_ws_session_is_current", lambda *_: True)
    ws = Socket()
    revoked, lock = asyncio.Event(), asyncio.Lock()
    assert await ai_chat._ai_ws_authorized_or_close(ws, "synthetic", 1, revoked, lock)
    closer = asyncio.create_task(chat_ws.close_revoked_websocket(ws, revoked, lock))
    await asyncio.wait_for(close_entered.wait(), 2)
    sender = asyncio.create_task(ai_chat._ai_ws_send(ws, {
        "type": "chunk", "content": "synthetic",
        "ai_safety_meta": {"requires_doctor_confirmation": True},
    }, revoked, lock))
    await asyncio.sleep(0)
    assert ws.sent == []
    release_close.set()
    await asyncio.wait_for(closer, 2)
    with pytest.raises(ai_chat._AIWebSocketRevoked):
        await asyncio.wait_for(sender, 2)
    assert ws.sent == []
    assert len(ws.closed) == 1


@pytest.mark.asyncio
async def test_ai_stream_stops_during_stalled_revocation_close(ws_identity, monkeypatch):
    import app.db.session as session_module

    user_id, token, sessions = ws_identity
    monkeypatch.setattr(session_module, "SessionLocal", sessions)
    monkeypatch.setattr(chat_ws, "WS_AUTH_RECHECK_SECONDS", 0.01)
    monkeypatch.setattr(ai_chat, "accept_echoing_subprotocol", AsyncMock())
    monkeypatch.setattr(ai_chat, "extract_ws_token", lambda _: token)
    async def send_message(**_kwargs):
        return SimpleNamespace(content="private " * 50, id=1, provider="synthetic",
                               model="synthetic", tokens_used=1, latency_ms=1, was_cached=False)
    monkeypatch.setattr(ai_chat, "get_chat_service", lambda _: SimpleNamespace(send_message=send_message))

    first_chunk = asyncio.Event()
    close_entered = asyncio.Event()
    next_send_started = asyncio.Event()
    release_close = asyncio.Event()
    send = ai_chat._ai_ws_send

    async def pause_after_first_chunk(websocket, payload, revoked, close_lock):
        if first_chunk.is_set():
            next_send_started.set()
            await send(websocket, payload, revoked, close_lock)
            return
        await send(websocket, payload, revoked, close_lock)
        first_chunk.set()
        # The send lock is free while the real watchdog marks revocation.
        await close_entered.wait()

    monkeypatch.setattr(ai_chat, "_ai_ws_send", pause_after_first_chunk)

    class Socket(_AISocket):
        async def close(self, **kwargs):
            self.closed.append(kwargs)
            close_entered.set()
            await release_close.wait()

    ws = Socket({"type": "message", "session_id": 1, "content": "synthetic"})
    with sessions() as endpoint_db:
        task = asyncio.create_task(ai_chat.chat_websocket(ws, endpoint_db))
        try:
            await asyncio.wait_for(first_chunk.wait(), 2)
            _revoke(sessions, user_id, token, "epoch")
            await asyncio.wait_for(close_entered.wait(), 2)
            await asyncio.wait_for(next_send_started.wait(), 2)
            assert len(ws.sent) == 1
        finally:
            release_close.set()
        await asyncio.wait_for(task, 2)
    assert len(ws.sent) == 1
    assert ws.sent[0]["type"] == "chunk"
    assert ws.closed == [{"code": 4001, "reason": "Authorization expired"}]


@pytest.mark.asyncio
async def test_stalled_ai_send_does_not_hold_revocation_lock_indefinitely(monkeypatch):
    entered = asyncio.Event()
    class Socket:
        def __init__(self):
            self.closed = []

        async def send_json(self, _payload):
            entered.set()
            await asyncio.Event().wait()

        async def close(self, **kwargs):
            self.closed.append(kwargs)

    monkeypatch.setattr(ai_chat, "AI_WS_SEND_TIMEOUT_SECONDS", 0.05)
    ws = Socket()
    revoked, lock = asyncio.Event(), asyncio.Lock()
    sender = asyncio.create_task(ai_chat._ai_ws_send(ws, {
        "type": "chunk", "ai_safety_meta": {"requires_doctor_confirmation": True},
    }, revoked, lock))
    await asyncio.wait_for(entered.wait(), 2)
    closer = asyncio.create_task(chat_ws.close_revoked_websocket(ws, revoked, lock))
    with pytest.raises(ai_chat._AIWebSocketRevoked):
        await asyncio.wait_for(sender, 2)
    await asyncio.wait_for(closer, 2)
    assert revoked.is_set()
    assert len(ws.closed) == 1
