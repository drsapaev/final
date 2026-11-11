"""Queue WS handshake regressions for browser Sec-WebSocket-Protocol.

The standalone /ws/queue endpoint must echo an offered subprotocol after
origin and auth checks. All tokens, rooms and sockets here are synthetic.
No DB, Redis, real JWT, browser network, or patient records are used.
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from fastapi import WebSocketDisconnect, status

from app.ws import queue_ws


class _SyntheticWebSocket:
    def __init__(
        self,
        *,
        offered: str | None = None,
        origin: str = "http://localhost:5173",
        authorization: str | None = None,
    ) -> None:
        self.headers = {"origin": origin}
        if offered is not None:
            self.headers["sec-websocket-protocol"] = offered
        if authorization is not None:
            self.headers["authorization"] = authorization
        self.query_params = {}
        self.url = SimpleNamespace(path="/ws/queue", query="")
        self.accepted_subprotocol: str | None | object = "UNSET"
        self.sent: list[dict] = []
        self.closed: list[int] = []
        self.receive_calls = 0

    async def accept(self, subprotocol: str | None = None) -> None:
        self.accepted_subprotocol = subprotocol

    async def send_json(self, payload: dict) -> None:
        self.sent.append(payload)

    async def receive_text(self) -> str:
        self.receive_calls += 1
        raise WebSocketDisconnect(code=1000)

    async def close(self, code: int) -> None:
        self.closed.append(code)


def _setup(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("ENV", "production")
    monkeypatch.setenv("TESTING", "0")
    monkeypatch.setenv("CORS_DISABLE", "0")
    monkeypatch.setenv("CORS_ORIGINS", "http://localhost:5173")
    manager = SimpleNamespace(connect=AsyncMock(), disconnect=Mock())
    monkeypatch.setattr(queue_ws, "ws_manager", manager)
    checked_tokens: list[str | None] = []

    def check_auth(_headers, token: str | None) -> bool:
        checked_tokens.append(token)
        return token == "synthetic-jwt"

    monkeypatch.setattr(queue_ws, "_auth_ok", check_auth)
    # This file tests subprotocol negotiation. The combined RBAC gate has
    # its own tests; admit this synthetic, previously authorized room here.
    monkeypatch.setattr(
        queue_ws, "_queue_room_permitted", lambda *_args: True
    )
    return manager, checked_tokens


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("offered", "expected_echo"),
    [
        ("bearer.synthetic-jwt", "bearer.synthetic-jwt"),
        ("bearer.synthetic-jwt, json", "bearer.synthetic-jwt"),
        ("json, bearer.synthetic-jwt", "json"),
    ],
)
async def test_authorized_queue_ws_echoes_offered_browser_subprotocol(
    monkeypatch: pytest.MonkeyPatch, offered: str, expected_echo: str
) -> None:
    manager, checked = _setup(monkeypatch)
    ws = _SyntheticWebSocket(offered=offered)

    await asyncio.wait_for(
        queue_ws.ws_queue(ws, "specialist_9", "2026-11-10"), timeout=1
    )

    assert checked == ["synthetic-jwt", "synthetic-jwt"]
    assert ws.accepted_subprotocol == expected_echo
    assert ws.sent == [
        {"type": "queue.connected", "room": "specialist_9::2026-11-10"}
    ]
    assert ws.closed == []
    assert ws.receive_calls == 1
    manager.connect.assert_awaited_once_with(
        ws, "specialist_9::2026-11-10"
    )
    manager.disconnect.assert_called_once_with(
        ws, "specialist_9::2026-11-10"
    )


@pytest.mark.asyncio
async def test_legacy_authorization_header_preserves_plain_accept(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manager, checked = _setup(monkeypatch)
    ws = _SyntheticWebSocket(authorization="Bearer synthetic-jwt")

    await asyncio.wait_for(
        queue_ws.ws_queue(ws, "specialist_2", "2026-11-10"), timeout=1
    )

    assert checked == ["synthetic-jwt", "synthetic-jwt"]
    assert ws.accepted_subprotocol is None
    assert ws.sent[0]["type"] == "queue.connected"
    manager.connect.assert_awaited_once()
    manager.disconnect.assert_called_once()


@pytest.mark.asyncio
async def test_failed_auth_never_echoes_offered_subprotocol_or_joins_room(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manager, checked = _setup(monkeypatch)
    ws = _SyntheticWebSocket(offered="bearer.invalid-jwt")

    await asyncio.wait_for(
        queue_ws.ws_queue(ws, "specialist_9", "2026-11-10"), timeout=1
    )

    assert checked == ["invalid-jwt"]
    assert ws.accepted_subprotocol is None
    assert ws.sent[0]["type"] == "error"
    assert ws.closed == [status.WS_1008_POLICY_VIOLATION]
    manager.connect.assert_not_awaited()
    manager.disconnect.assert_not_called()


@pytest.mark.asyncio
async def test_disallowed_origin_never_echoes_or_joins_room(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manager, checked = _setup(monkeypatch)
    ws = _SyntheticWebSocket(
        offered="bearer.synthetic-jwt", origin="https://not-allowed.example"
    )

    await asyncio.wait_for(
        queue_ws.ws_queue(ws, "specialist_9", "2026-11-10"), timeout=1
    )

    assert checked == ["synthetic-jwt"]
    assert ws.accepted_subprotocol is None
    assert ws.sent == [{"type": "error", "reason": "origin not allowed"}]
    assert ws.closed == [status.WS_1008_POLICY_VIOLATION]
    manager.connect.assert_not_awaited()
    manager.disconnect.assert_not_called()
