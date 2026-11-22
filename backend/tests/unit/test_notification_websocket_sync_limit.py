"""Contract tests for bounded notification_sync WebSocket pagination.

All identities, messages and state are synthetic. No real database, token,
network, Redis or patient data is used; the production endpoint coroutine runs
against fake dependencies.
"""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest
from fastapi import WebSocketDisconnect

from app.api.v1.endpoints import notification_websocket as endpoint


class FakeSession:
    def __init__(self):
        self.closed = 0

    def close(self):
        self.closed += 1


class FakeManager:
    def __init__(self):
        self.connections = []
        self.disconnections = []

    async def connect(self, socket, user_id):
        self.connections.append((socket, user_id))

    def disconnect(self, socket, user_id):
        self.disconnections.append((socket, user_id))


class FakePlatform:
    def __init__(self):
        self.inbox_calls = []

    def get_unread_counts(self, *, current_user):
        return {"total": 0}

    def resolve_panel_role_for_user(self, _user):
        return "doctor"

    def get_inbox(self, **kwargs):
        self.inbox_calls.append(kwargs)
        return {"items": [], "total": 0, "unread_count": 0, "next_cursor": None}


class FakeSocket:
    def __init__(self, messages):
        self.messages = [json.dumps(message) for message in messages]
        self.sent = []
        self.closed = []

    async def receive_text(self):
        if self.messages:
            return self.messages.pop(0)
        raise WebSocketDisconnect(code=1000)

    async def send_json(self, payload):
        self.sent.append(payload)

    async def close(self, *, code, reason=""):
        self.closed.append(code)


def wire(monkeypatch):
    user = SimpleNamespace(id=67, username="synthetic-user")
    db = FakeSession()
    manager = FakeManager()
    platform = FakePlatform()

    async def authenticate(_token, _db):
        return user

    monkeypatch.setattr(endpoint, "SessionLocal", lambda: db)
    monkeypatch.setattr(endpoint, "get_notification_ws_manager", lambda: manager)
    monkeypatch.setattr(endpoint, "extract_ws_token", lambda _ws: "synthetic-token")
    monkeypatch.setattr(endpoint, "authenticate_websocket_token", authenticate)
    monkeypatch.setattr(
        endpoint, "get_notification_platform_service", lambda _db: platform
    )
    return user, db, manager, platform


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("sync_request", "expected_limit"),
    [
        ({"type": "notification_sync"}, 50),
        ({"type": "notification_sync", "limit": None}, 50),
        ({"type": "notification_sync", "limit": 1}, 1),
        ({"type": "notification_sync", "limit": 200}, 200),
        ({"type": "notification_sync", "limit": "42"}, 42),
    ],
)
async def test_sync_accepts_rest_contract_limit_and_keeps_cursor(
    monkeypatch, sync_request, expected_limit
):
    user, db, manager, platform = wire(monkeypatch)
    socket = FakeSocket([{**sync_request, "cursor": "123"}])

    await endpoint.websocket_notifications(socket)

    assert len(platform.inbox_calls) == 1
    assert platform.inbox_calls[0]["current_user"] is user
    assert platform.inbox_calls[0]["cursor"] == 123
    assert platform.inbox_calls[0]["limit"] == expected_limit
    assert [msg["type"] for msg in socket.sent] == [
        "connection_established",
        "notification_sync_response",
    ]
    assert manager.connections == [(socket, user.id)]
    assert manager.disconnections == [(socket, user.id)]
    assert db.closed == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "invalid_limit",
    [0, -1, 201, 10**9, "not-a-number", "1.5", 5.5, True, [], {}],
)
async def test_sync_rejects_bad_limit_without_query_or_closing_socket(
    monkeypatch, invalid_limit
):
    user, db, manager, platform = wire(monkeypatch)
    socket = FakeSocket(
        [
            {"type": "notification_sync", "limit": invalid_limit},
            {"type": "notification_sync", "limit": 12},
        ]
    )

    await endpoint.websocket_notifications(socket)

    # Only the subsequent valid request is allowed to reach the query.
    assert len(platform.inbox_calls) == 1
    assert platform.inbox_calls[0]["limit"] == 12
    assert platform.inbox_calls[0]["current_user"] is user
    assert [msg["type"] for msg in socket.sent] == [
        "connection_established",
        "notification_error",
        "notification_sync_response",
    ]
    assert socket.sent[1]["field"] == "limit"
    assert socket.closed == []
    assert manager.disconnections == [(socket, user.id)]
    assert db.closed == 1
