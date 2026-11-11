"""Cross-PR end-to-end in-process queue WebSocket admission and handshake.

Exercises real signed synthetic JWT parsing, production TESTING hardening,
Doctor-to-User room ownership, and browser subprotocol negotiation together.
Only the DB, resolver and WS manager are faked. No clinical data or Redis.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import jwt
import pytest
from fastapi import WebSocketDisconnect, status

from app.core.config import settings
from app.ws import queue_ws


class _DoctorQuery:
    def __init__(self, doctor_id: int | None, user_id: int) -> None:
        self.doctor_id = doctor_id
        self.user_id = user_id

    def filter(self, *_criteria):
        return self

    def first(self):
        if self.doctor_id is None:
            return None
        return SimpleNamespace(
            id=self.doctor_id, user_id=self.user_id, active=True
        )


class _Db:
    def __init__(self, doctor_id: int | None, user_id: int) -> None:
        self.doctor_id = doctor_id
        self.user_id = user_id
        self.closed = False

    def query(self, _model):
        return _DoctorQuery(self.doctor_id, self.user_id)

    def close(self):
        self.closed = True


class _WebSocket:
    def __init__(self, signed_jwt: str | None) -> None:
        self.headers = {"origin": "http://localhost:5173"}
        if signed_jwt:
            self.headers["sec-websocket-protocol"] = f"bearer.{signed_jwt}"
        self.query_params = {}
        self.url = SimpleNamespace(path="/ws/queue", query="")
        self.accepted_protocol = "NOT_ACCEPTED"
        self.sent = []
        self.closed = []

    async def accept(self, subprotocol=None):
        self.accepted_protocol = subprotocol

    async def send_json(self, payload):
        self.sent.append(payload)

    async def receive_text(self):
        raise WebSocketDisconnect(code=1000)

    async def close(self, code):
        self.closed.append(code)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("role", "own_doctor", "selected_doctor", "allowed"),
    [
        ("Doctor", 501, 501, True),
        ("Doctor", 501, 502, False),
        ("Patient", None, 501, False),
        ("Registrar", None, 502, True),
    ],
)
async def test_production_handshake_and_room_permissions_together(
    monkeypatch, role, own_doctor, selected_doctor, allowed
):
    monkeypatch.setenv("ENV", "production")
    monkeypatch.setenv("TESTING", "1")
    monkeypatch.setenv("CORS_DISABLE", "0")
    monkeypatch.setenv("CORS_ORIGINS", "http://localhost:5173")
    user = SimpleNamespace(
        id=19, username="synthetic-queue-user", role=role,
        is_active=True, is_superuser=False
    )
    sessions = []

    def session_factory():
        session = _Db(own_doctor, user.id)
        sessions.append(session)
        return session

    monkeypatch.setattr("app.db.session.SessionLocal", session_factory)
    resolver = Mock(return_value=user)
    monkeypatch.setattr(
        "app.api.v1.endpoints.websocket_auth._resolve_websocket_user",
        resolver,
    )
    blacklist = Mock(return_value=False)
    monkeypatch.setattr(
        "app.services.token_blacklist_service.TokenBlacklistService.is_token_blacklisted",
        blacklist,
    )
    manager = SimpleNamespace(connect=AsyncMock(), disconnect=Mock())
    monkeypatch.setattr(queue_ws, "ws_manager", manager)
    token = jwt.encode(
        {
            "sub": user.username,
            "jti": "synthetic-queue-ws-integrated",
            "exp": datetime.now(UTC) + timedelta(minutes=10),
        },
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM,
    )
    ws = _WebSocket(token)

    await asyncio.wait_for(
        queue_ws.ws_queue(
            ws, f"specialist_{selected_doctor}", "2026-11-11"
        ),
        timeout=2,
    )

    assert len(sessions) == 3
    assert all(session.closed for session in sessions)
    assert resolver.call_count == 3
    assert blacklist.call_count == 3
    assert all(
        call.kwargs == {"user_id": user.id}
        for call in blacklist.call_args_list
    )
    if allowed:
        assert ws.accepted_protocol == f"bearer.{token}"
        assert ws.sent == [
            {
                "type": "queue.connected",
                "room": f"specialist_{selected_doctor}::2026-11-11",
            }
        ]
        assert ws.closed == []
        manager.connect.assert_awaited_once()
        manager.disconnect.assert_called_once()
    else:
        assert ws.sent == [
            {"type": "error", "reason": "queue room access denied"}
        ]
        assert ws.closed == [status.WS_1008_POLICY_VIOLATION]
        manager.connect.assert_not_awaited()
        manager.disconnect.assert_not_called()


@pytest.mark.asyncio
async def test_testing_cannot_skip_production_jwt_before_room_check(
    monkeypatch,
):
    monkeypatch.setenv("ENV", "production")
    monkeypatch.setenv("TESTING", "1")
    monkeypatch.setenv("CORS_DISABLE", "0")
    monkeypatch.setenv("CORS_ORIGINS", "http://localhost:5173")
    no_db = Mock(side_effect=AssertionError("invalid JWT reached auth DB"))
    monkeypatch.setattr("app.db.session.SessionLocal", no_db)
    manager = SimpleNamespace(connect=AsyncMock(), disconnect=Mock())
    monkeypatch.setattr(queue_ws, "ws_manager", manager)
    ws = _WebSocket(None)

    await queue_ws.ws_queue(ws, "specialist_501", "2026-11-11")

    assert ws.sent == [
        {"type": "error", "reason": "Authentication required in production"}
    ]
    assert ws.closed == [status.WS_1008_POLICY_VIOLATION]
    manager.connect.assert_not_awaited()
    no_db.assert_not_called()
