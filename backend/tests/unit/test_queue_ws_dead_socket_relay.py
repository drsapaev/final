"""Queue WS Redis subscription lifecycle after send_json raises.

All sockets, channels and payloads are synthetic. These cases exercise the
real WSManager with a fake Redis bridge; no Redis service, JWT, database,
browser or patient records are involved.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable

import pytest

from app.ws import queue_ws


class _FakeRedisBridge:
    def __init__(self) -> None:
        self.handlers: dict[str, object] = {}
        self.subscribed: list[str] = []
        self.unsubscribed: list[str] = []
        self.published: list[tuple[str, dict]] = []

    async def subscribe(self, channel: str, handler: object) -> None:
        assert channel not in self.handlers
        self.handlers[channel] = handler
        self.subscribed.append(channel)

    async def unsubscribe(self, channel: str, handler: object) -> None:
        assert self.handlers.get(channel) is handler
        del self.handlers[channel]
        self.unsubscribed.append(channel)

    async def publish(self, channel: str, payload: dict) -> bool:
        self.published.append((channel, payload))
        return True


class _FakeSocket:
    def __init__(self, *, broken: bool = False) -> None:
        self.broken = broken
        self.attempts = 0
        self.sent: list[dict] = []

    async def send_json(self, payload: dict) -> None:
        self.attempts += 1
        if self.broken:
            raise RuntimeError("synthetic closed socket")
        self.sent.append(payload)


def _manager(monkeypatch: pytest.MonkeyPatch):
    # WSManager is a singleton in production. Isolate this test instance
    # without mutating the shared manager in other tests.
    monkeypatch.setattr(queue_ws.WSManager, "_instance", None)
    manager = queue_ws.WSManager()
    pubsub = _FakeRedisBridge()
    manager._pubsub = pubsub
    return manager, pubsub


async def _eventually(condition: Callable[[], bool]) -> None:
    # disconnect() schedules an async Redis unsubscribe on the running loop.
    for _ in range(30):
        if condition():
            return
        await asyncio.sleep(0)
    assert condition(), "scheduled Redis unsubscribe was not observed"


@pytest.mark.asyncio
async def test_failed_last_socket_unsubscribes_and_cleans_room(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manager, pubsub = _manager(monkeypatch)
    room = "specialist_81::2026-11-11"
    channel = f"room:{room}"
    dead = _FakeSocket(broken=True)
    await manager.connect(dead, room)
    assert pubsub.subscribed == [channel]

    await manager._broadcast_room(room, {"type": "queue_update"}, publish=False)
    await _eventually(lambda: pubsub.unsubscribed == [channel])

    assert dead.attempts == 1
    assert room not in manager.rooms
    assert room not in manager._redis_handlers
    assert pubsub.handlers == {}

    # Endpoint's later finally: disconnect must not unsubscribe twice.
    manager.disconnect(dead, room)
    await asyncio.sleep(0)
    assert pubsub.unsubscribed == [channel]


@pytest.mark.asyncio
async def test_broken_socket_does_not_evict_healthy_peer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manager, pubsub = _manager(monkeypatch)
    room = "specialist_82::2026-11-11"
    channel = f"room:{room}"
    bad = _FakeSocket(broken=True)
    good = _FakeSocket()
    await manager.connect(bad, room)
    await manager.connect(good, room)

    payload = {"type": "patient_called", "data": {"entry_id": 987}}
    await manager._broadcast_room(room, payload, publish=False)

    assert bad.attempts == 1
    assert good.sent == [payload]
    assert manager.rooms[room] == {good}
    assert room in manager._redis_handlers
    assert pubsub.unsubscribed == []

    await manager._broadcast_room(room, payload, publish=False)
    assert bad.attempts == 1
    assert good.sent == [payload, payload]

    manager.disconnect(good, room)
    await _eventually(lambda: pubsub.unsubscribed == [channel])
    assert room not in manager._redis_handlers
    assert room not in manager.rooms


@pytest.mark.asyncio
async def test_failed_socket_in_multiple_rooms_releases_both_subscriptions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manager, pubsub = _manager(monkeypatch)
    room1 = "specialist_83::2026-11-11"
    room2 = "specialist_84::2026-11-11"
    dead = _FakeSocket(broken=True)
    await manager.connect(dead, room1)
    await manager.connect(dead, room2)

    await manager._broadcast_room(room1, {"type": "queue_update"}, publish=False)
    await _eventually(lambda: len(pubsub.unsubscribed) == 2)

    assert dead.attempts == 1
    assert set(pubsub.unsubscribed) == {f"room:{room1}", f"room:{room2}"}
    assert manager._redis_handlers == {}
    assert not manager.rooms


@pytest.mark.asyncio
async def test_new_connection_resubscribes_after_failed_last_socket(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manager, pubsub = _manager(monkeypatch)
    room = "specialist_85::2026-11-11"
    channel = f"room:{room}"
    dead = _FakeSocket(broken=True)
    await manager.connect(dead, room)

    await manager._broadcast_room(room, {"type": "queue_update"}, publish=False)
    await _eventually(lambda: pubsub.unsubscribed == [channel])

    fresh = _FakeSocket()
    await manager.connect(fresh, room)
    assert pubsub.subscribed == [channel, channel]
    assert room in manager._redis_handlers

    payload = {"type": "queue_update", "data": {"action": "restore"}}
    await manager._broadcast_room(room, payload, publish=False)
    assert fresh.sent == [payload]

    manager.disconnect(fresh, room)
    await _eventually(lambda: pubsub.unsubscribed == [channel, channel])


@pytest.mark.asyncio
async def test_local_send_failure_still_publishes_one_event(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manager, pubsub = _manager(monkeypatch)
    room = "specialist_86::2026-11-11"
    dead = _FakeSocket(broken=True)
    await manager.connect(dead, room)
    payload = {"type": "queue_update", "data": {"entry_id": 123}}

    await manager._broadcast_room(room, payload, publish=True)
    await _eventually(lambda: len(pubsub.unsubscribed) == 1)

    assert dead.attempts == 1
    assert pubsub.published == [(f"room:{room}", {"data": payload})]
    assert room not in manager._redis_handlers
