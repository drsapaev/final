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
    def __init__(self, messages=()) -> None:
        self.messages = list(messages)
        self.closed: list[int] = []
        self.sent: list[dict] = []

    async def receive_text(self) -> str:
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
):
    db = FakeSession()
    manager = FakeManager(fail_during_connect=fail_during_connect)
    user = SimpleNamespace(id=41, username="synthetic-registrar")
    platform = FakePlatform(fail_counts=fail_counts)

    async def authenticate(_token, _db):
        return user if authorized else None

    monkeypatch.setattr(endpoint, "SessionLocal", lambda: db)
    monkeypatch.setattr(endpoint, "extract_ws_token", lambda _socket: "synthetic-jwt")
    monkeypatch.setattr(endpoint, "authenticate_websocket_token", authenticate)
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
