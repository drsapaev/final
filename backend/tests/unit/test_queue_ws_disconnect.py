"""Regression coverage for a closed queue WebSocket's receive loop."""

from __future__ import annotations

import asyncio
import logging
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from fastapi import WebSocketDisconnect

from app.ws import queue_ws

_TOKEN_CANARY = "SYNTHETIC-QUEUE-WS-TOKEN"
_ERROR_CANARY = "SYNTHETIC-RECEIVE-ERROR"


class _DisconnectingWebSocket:
    def __init__(self, receive_error: Exception) -> None:
        self.headers = {"origin": "http://localhost:5173"}
        self.url = SimpleNamespace(path="/ws/queue", query=f"token={_TOKEN_CANARY}")
        self.query_params = {"token": _TOKEN_CANARY}
        self.receive_error = receive_error
        self.receive_calls = 0
        self.sent: list[dict] = []
        self.accepted = False

    async def accept(self) -> None:
        self.accepted = True

    async def send_json(self, message: dict) -> None:
        self.sent.append(message)

    async def receive_text(self) -> str:
        self.receive_calls += 1
        if self.receive_calls > 1:
            # A regression that retries a dead socket waits here until the
            # outer timeout fails, without flooding logs or the test runner.
            await asyncio.Event().wait()
        raise self.receive_error


@pytest.mark.asyncio
@pytest.mark.parametrize("error_kind", ["disconnect", "unexpected"])
async def test_closed_queue_socket_exits_once_and_cleans_up(
    error_kind: str, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """A failed receive must end the stream, release its room and heartbeat."""
    monkeypatch.setenv("TESTING", "1")
    monkeypatch.setenv("ENV", "dev")
    monkeypatch.setenv("CORS_DISABLE", "0")
    monkeypatch.setenv("CORS_ORIGINS", "http://localhost:5173")
    receive_error = (
        WebSocketDisconnect(code=1000)
        if error_kind == "disconnect"
        else RuntimeError(_ERROR_CANARY)
    )
    websocket = _DisconnectingWebSocket(receive_error)
    manager = SimpleNamespace(connect=AsyncMock(), disconnect=Mock())
    monkeypatch.setattr(queue_ws, "ws_manager", manager)

    heartbeat_tasks: list[asyncio.Task] = []
    create_task = asyncio.create_task

    def track_heartbeat(coro):
        task = create_task(coro)
        if coro.__qualname__.endswith("send_heartbeat"):
            heartbeat_tasks.append(task)
        return task

    monkeypatch.setattr(queue_ws.asyncio, "create_task", track_heartbeat)

    with caplog.at_level(logging.INFO):
        await asyncio.wait_for(
            queue_ws.ws_queue(websocket, "specialist_1", "2026-09-24"),
            timeout=1,
        )

    room = "specialist_1::2026-09-24"
    assert websocket.accepted
    assert websocket.sent == [{"type": "queue.connected", "room": room}]
    assert websocket.receive_calls == 1
    manager.connect.assert_awaited_once_with(websocket, room)
    manager.disconnect.assert_called_once_with(websocket, room)
    assert len(heartbeat_tasks) == 1
    assert heartbeat_tasks[0].cancelled()
    logged = "\n".join(record.getMessage() for record in caplog.records)
    assert _TOKEN_CANARY not in logged
    assert _ERROR_CANARY not in logged
