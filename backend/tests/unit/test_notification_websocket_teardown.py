"""Synthetic regression tests for notification WebSocket registration teardown.

No database, network, JWT, patient records or Redis service is used. The
endpoint's manager and session are fakes; the real route coroutine executes.
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest
from fastapi import WebSocketDisconnect, status

from app.api.v1.endpoints import notification_websocket as endpoint


class FakeSession:
    def __init__(self) -> None:
        self.close_calls = 0

    def close(self) -> None:
        self.close_calls += 1


class FakeSocket:
    def __init__(self, messages=(), slow_first_receive: bool = False) -> None:
        self.messages = list(messages)
        self.slow_first_receive = slow_first_receive
        self.closed: list[int] = []
        self.sent: list[dict] = []

    async def receive_text(self) -> str:
        if self.slow_first_receive:
            self.slow_first_receive = False
            # Force the periodic-recheck timeout path deterministically:
            # the receive blocks longer than the patched recheck interval.
            await asyncio.sleep(0.05)
        if self.messages:
            item = self.messages.pop(0)
            if isinstance(item, BaseException):
                raise item
            return item
        raise WebSocketDisconnect(code=1000)

    async def send_json(self, data: dict) -> None:
        self.sent.append(data)

    async def close(self, code: int, reason: str = "") -> None:
        self.closed.append(code)


class FakeManager:
    def __init__(self, *, fail_during_connect: bool = False) -> None:
        self.active: dict[int, FakeSocket] = {}
        self.connect_calls = 0
        self.disconnect_calls: list[tuple[FakeSocket, int]] = []
        self.fail_during_connect = fail_during_connect

    async def connect(self, socket: FakeSocket, user_id: int) -> None:
        self.connect_calls += 1
        self.active[user_id] = socket
        if self.fail_during_connect:
            raise RuntimeError("synthetic partial registration failure")

    def disconnect(self, socket: FakeSocket, user_id: int) -> None:
        self.disconnect_calls.append((socket, user_id))
        if self.active.get(user_id) is socket:
            del self.active[user_id]


class FakePlatform:
    def __init__(self, *, fail_counts: bool = False) -> None:
        self.fail_counts = fail_counts

    def get_unread_counts(self, *, current_user):
        if self.fail_counts:
            raise RuntimeError("synthetic unread database failure")
        return {"total": 0}

    def resolve_panel_role_for_user(self, user):
        return "doctor"

    def get_inbox(self, **_kwargs):
        return {"items": [], "unread_count": 0}


def wire_endpoint(
    monkeypatch: pytest.MonkeyPatch,
    *,
    authorized: bool = True,
    fail_during_connect: bool = False,
    fail_counts: bool = False,
    auth_results=None,
):
    db = FakeSession()
    manager = FakeManager(fail_during_connect=fail_during_connect)
    user = SimpleNamespace(id=41, username="synthetic-registrar")
    platform = FakePlatform(fail_counts=fail_counts)

    async def authenticate(_token, _db):
        if auth_results is not None:
            return auth_results.pop(0) if auth_results else None
        return user if authorized else None

    def resolve_sync(_token, _db):
        # NOTIFYLIVEAUTH-BE-001: the periodic re-check uses the synchronous
        # canonical resolver; the shared auth_results sequence keeps the
        # handshake -> recheck ordering deterministic.
        if auth_results is not None:
            return auth_results.pop(0) if auth_results else None
        return user if authorized else None

    monkeypatch.setattr(endpoint, "SessionLocal", lambda: db)
    monkeypatch.setattr(endpoint, "extract_ws_token", lambda _socket: "synthetic-jwt")
    monkeypatch.setattr(endpoint, "authenticate_websocket_token", authenticate)
    monkeypatch.setattr(endpoint, "resolve_websocket_token_user", resolve_sync)
    monkeypatch.setattr(endpoint, "get_notification_ws_manager", lambda: manager)
    monkeypatch.setattr(
        endpoint, "get_notification_platform_service", lambda _db: platform
    )
    return db, manager, user


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("message", "expected_code"),
    [
        (None, None),
        ("[]", status.WS_1011_INTERNAL_ERROR),
    ],
)
async def test_registered_socket_removed_on_disconnect_and_unexpected_errors(
    monkeypatch, message, expected_code
):
    db, manager, user = wire_endpoint(monkeypatch)
    socket = FakeSocket([] if message is None else [message])

    await endpoint.websocket_notifications(socket)

    assert manager.connect_calls == 1
    assert manager.disconnect_calls == [(socket, user.id)]
    assert manager.active == {}
    assert db.close_calls == 1
    assert socket.closed == ([] if expected_code is None else [expected_code])


@pytest.mark.asyncio
async def test_post_connect_database_failure_removes_socket(monkeypatch):
    db, manager, user = wire_endpoint(monkeypatch, fail_counts=True)
    socket = FakeSocket()

    await endpoint.websocket_notifications(socket)

    assert manager.disconnect_calls == [(socket, user.id)]
    assert manager.active == {}
    assert db.close_calls == 1
    assert socket.closed == [status.WS_1011_INTERNAL_ERROR]


@pytest.mark.asyncio
async def test_partial_manager_registration_failure_still_disconnects(monkeypatch):
    db, manager, user = wire_endpoint(monkeypatch, fail_during_connect=True)
    socket = FakeSocket()

    await endpoint.websocket_notifications(socket)

    assert manager.connect_calls == 1
    assert manager.disconnect_calls == [(socket, user.id)]
    assert manager.active == {}
    assert db.close_calls == 1
    assert socket.closed == [status.WS_1011_INTERNAL_ERROR]


@pytest.mark.asyncio
async def test_cancelled_receive_still_disconnects_and_closes_session(monkeypatch):
    db, manager, user = wire_endpoint(monkeypatch)
    socket = FakeSocket([asyncio.CancelledError()])

    with pytest.raises(asyncio.CancelledError):
        await endpoint.websocket_notifications(socket)

    assert manager.disconnect_calls == [(socket, user.id)]
    assert manager.active == {}
    assert db.close_calls == 1


@pytest.mark.asyncio
async def test_disconnect_failure_still_closes_database_session(monkeypatch):
    db, manager, _user = wire_endpoint(monkeypatch)
    socket = FakeSocket()

    def failing_disconnect(_socket, _user_id):
        raise RuntimeError("synthetic unsubscribe failure")

    manager.disconnect = failing_disconnect

    with pytest.raises(RuntimeError, match="synthetic unsubscribe failure"):
        await endpoint.websocket_notifications(socket)

    assert db.close_calls == 1


@pytest.mark.asyncio
async def test_invalid_token_never_registers_or_disconnects_socket(monkeypatch):
    db, manager, _user = wire_endpoint(monkeypatch, authorized=False)
    socket = FakeSocket()

    await endpoint.websocket_notifications(socket)

    assert manager.connect_calls == 0
    assert manager.disconnect_calls == []
    assert db.close_calls == 1
    assert socket.closed == [status.WS_1008_POLICY_VIOLATION]


# ---------------------------------------------------------------------------
# NOTIFYLIVEAUTH-BE-001 — periodic live re-authorization of an ACCEPTED
# personal-notification socket (round 40, P1 conditional).
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_established_notification_socket_closes_when_authorization_is_revoked(
    monkeypatch,
):
    """A socket accepted at handshake must close once its principal/token
    is revoked mid-session (NOTIFYLIVEAUTH-BE-001).

    The endpoint authenticated once and never re-checked JWT exp, per-JTI
    revocation, the ``all_user_tokens`` bulk sentinel or ``User.is_active``
    during the receive loop, so a socket connected before a revoke kept
    receiving user-scoped broadcasts. The periodic re-check reuses the
    handshake's canonical ``authenticate_websocket_token`` resolver (which
    covers all four revocation sources) on the SAME session — no extra DB
    checkout per idle socket.
    """
    principal = SimpleNamespace(id=41, username="synthetic-registrar")
    db, manager, user = wire_endpoint(monkeypatch, auth_results=[principal, None])
    monkeypatch.setattr(endpoint, "NOTIFICATION_WS_AUTH_RECHECK_SECONDS", 0.001, raising=False)
    socket = FakeSocket(slow_first_receive=True)

    await endpoint.websocket_notifications(socket)

    assert manager.connect_calls == 1
    assert manager.disconnect_calls == [(socket, user.id)]
    assert manager.active == {}
    assert socket.closed == [status.WS_1008_POLICY_VIOLATION]
    assert db.close_calls == 1


@pytest.mark.asyncio
async def test_notification_socket_survives_valid_periodic_recheck(monkeypatch):
    """Positive control: a still-valid principal must keep receiving and
    processing messages across periodic re-checks, and the socket must end
    with the normal client-disconnect teardown (no policy close)."""
    principal = SimpleNamespace(id=41, username="synthetic-registrar")
    db, manager, user = wire_endpoint(monkeypatch, auth_results=[principal, principal, principal])
    monkeypatch.setattr(endpoint, "NOTIFICATION_WS_AUTH_RECHECK_SECONDS", 0.001, raising=False)
    socket = FakeSocket(
        messages=['{"type": "notification_sync", "cursor": null, "limit": 50}'],
        slow_first_receive=True,
    )

    await endpoint.websocket_notifications(socket)

    assert socket.closed == []
    assert manager.disconnect_calls == [(socket, user.id)]
    assert socket.sent[0]["type"] == "connection_established"
    assert any(
        message.get("type") == "notification_sync_response" for message in socket.sent
    )
    assert db.close_calls == 1
