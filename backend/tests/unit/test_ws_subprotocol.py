"""Unit tests for accept_echoing_subprotocol (RFC 6455 handshake echo).

Clinic clients pass the JWT as ``Sec-WebSocket-Protocol: bearer.<jwt>``.
The server MUST answer with one of the offered subprotocols — a bare
accept() makes browsers abort the handshake with
"Sent non-empty 'Sec-WebSocket-Protocol' header but no response was
received" (broke notifications / AI-chat / display-board WebSockets).
"""
from __future__ import annotations

import asyncio

from app.api.v1.endpoints.ws_token import accept_echoing_subprotocol


class FakeWebSocket:
    def __init__(self, offered: str | None):
        self.headers = {"sec-websocket-protocol": offered} if offered else {}
        self.accepted_subprotocol = "UNSET"

    async def accept(self, subprotocol: str | None = None) -> None:
        self.accepted_subprotocol = subprotocol


def _run(ws: FakeWebSocket) -> None:
    asyncio.get_event_loop().run_until_complete(accept_echoing_subprotocol(ws))


def test_echoes_bearer_subprotocol():
    ws = FakeWebSocket("bearer.eyJhbGciOiJIUzI1NiJ9")
    asyncio.run(accept_echoing_subprotocol(ws))
    assert ws.accepted_subprotocol == "bearer.eyJhbGciOiJIUzI1NiJ9"


def test_plain_accept_when_nothing_offered():
    ws = FakeWebSocket(None)
    asyncio.run(accept_echoing_subprotocol(ws))
    assert ws.accepted_subprotocol is None


def test_first_of_multiple_offered_protocols():
    ws = FakeWebSocket("bearer.jwt, json")
    asyncio.run(accept_echoing_subprotocol(ws))
    assert ws.accepted_subprotocol == "bearer.jwt"


def test_strips_whitespace():
    ws = FakeWebSocket("  bearer.jwt  ")
    asyncio.run(accept_echoing_subprotocol(ws))
    assert ws.accepted_subprotocol == "bearer.jwt"
