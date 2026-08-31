"""Cross-loop WebSocket delivery for NotificationWebSocketManager.

Codex follow-up on #2874: background schedulers (lab notifications) run on
worker-thread loops. A WebSocket lives on Uvicorn's application loop, so a
direct ``await connection.send_json(...)`` from a foreign loop fails with
"attached to a different loop" and the notification is dropped. The manager
must marshal such sends back onto the connection's home loop.

Run:
    pytest backend/tests/unit/test_notification_ws_cross_loop.py -v
"""

from __future__ import annotations

import asyncio
import threading

import pytest

from app.services.notification_websocket import NotificationWebSocketManager


class _FakeWebSocket:
    def __init__(self, name: str) -> None:
        self.name = name
        self.sent: list[dict] = []
        self.seen_loops: list[int] = []

    async def send_json(self, data: dict) -> None:
        self.seen_loops.append(id(asyncio.get_running_loop()))
        self.sent.append(data)


async def _wait_until(predicate, timeout: float = 5.0) -> None:
    deadline = asyncio.get_running_loop().time() + timeout
    while not predicate():
        if asyncio.get_running_loop().time() > deadline:
            pytest.fail("condition not reached in time")
        await asyncio.sleep(0.02)


@pytest.mark.asyncio
async def test_send_json_from_foreign_loop_is_marshalled_to_home_loop() -> None:
    manager = NotificationWebSocketManager()
    ws = _FakeWebSocket("w1")
    home_loop = asyncio.get_running_loop()

    # Register exactly as connect() would, without a real handshake.
    manager.active_connections[7] = [ws]
    manager._connection_loops[id(ws)] = home_loop

    foreign_loop_id: list[int] = []

    def foreign_thread() -> None:
        async def go() -> None:
            foreign_loop_id.append(id(asyncio.get_running_loop()))
            await manager.send_json({"alert": "lab-ready"}, 7)

        asyncio.run(go())

    worker = threading.Thread(target=foreign_thread, daemon=True)
    worker.start()
    worker.join(timeout=5)
    assert not worker.is_alive()

    # The payload must arrive asynchronously on the HOME loop.
    await _wait_until(lambda: bool(ws.sent))
    assert ws.sent == [{"alert": "lab-ready"}]
    assert ws.seen_loops == [id(home_loop)], "delivery ran on the wrong loop"
    assert foreign_loop_id[0] != id(home_loop), "precondition: foreign loop"


@pytest.mark.asyncio
async def test_send_json_on_home_loop_still_works_directly() -> None:
    manager = NotificationWebSocketManager()
    ws = _FakeWebSocket("w2")
    manager.active_connections[8] = [ws]
    manager._connection_loops[id(ws)] = asyncio.get_running_loop()

    await manager.send_json({"alert": "direct"}, 8)

    assert ws.sent == [{"alert": "direct"}]
    assert ws.seen_loops == [id(asyncio.get_running_loop())]


@pytest.mark.asyncio
async def test_disconnect_cleans_up_home_loop_mapping() -> None:
    manager = NotificationWebSocketManager()
    ws = _FakeWebSocket("w3")
    manager.active_connections[9] = [ws]
    manager._connection_loops[id(ws)] = asyncio.get_running_loop()

    manager.disconnect(ws, 9)

    assert ws not in manager.active_connections.get(9, [])
    assert id(ws) not in manager._connection_loops
