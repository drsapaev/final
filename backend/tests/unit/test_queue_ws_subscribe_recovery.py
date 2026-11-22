"""Queue WS Redis SUBSCRIBE truthfulness and reconnect race regressions.

QUEUEWS-POST4008-SUBSCRIBE-01 (audit #3961). All data and sockets are synthetic;
no real Redis, patient records, or network calls. Tests were staged before
the implementation and must be run with the repo's mandatory gate.
"""

from __future__ import annotations

import asyncio
from collections import defaultdict

import pytest

from app.ws import queue_ws


ROOM = "specialist_71::2026-11-11"
CHANNEL = f"room:{ROOM}"


class _Socket:
    def __init__(self) -> None:
        self.received: list[dict] = []

    async def send_json(self, message: dict) -> None:
        self.received.append(message)


class _Bridge:
    """Fake bridge mirrors the real bridge retaining handlers on readiness failure."""

    def __init__(self, *, first_failure: str | None = None) -> None:
        self.first_failure = first_failure
        self.handlers: dict[str, set] = defaultdict(set)
        self.subscribe_calls: list[str] = []
        self.unsubscribe_calls: list[str] = []
        self.subscribe_entered = asyncio.Event()
        self.release_subscribe = asyncio.Event()
        self.block_subscribe = False
        self.unsubscribe_entered = asyncio.Event()
        self.release_unsubscribe = asyncio.Event()
        self.block_unsubscribe = False

    async def subscribe(self, channel: str, handler) -> bool:
        self.subscribe_calls.append(channel)
        # _ensure_ready() in RedisPubSubBridge adds to _handlers BEFORE it
        # discovers that Redis is unavailable. A manager must clean this up.
        self.handlers[channel].add(handler)
        if self.first_failure is not None:
            failure = self.first_failure
            self.first_failure = None
            if failure == "false":
                return False
            raise RuntimeError("synthetic Redis SUBSCRIBE failure")
        if self.block_subscribe:
            self.subscribe_entered.set()
            await self.release_subscribe.wait()
        return True

    async def unsubscribe(self, channel: str, handler) -> None:
        self.unsubscribe_calls.append(channel)
        if self.block_unsubscribe:
            self.unsubscribe_entered.set()
            await self.release_unsubscribe.wait()
        self.handlers[channel].discard(handler)
        if not self.handlers[channel]:
            self.handlers.pop(channel, None)

    async def publish(self, channel: str, payload: dict) -> bool:
        return True

    async def deliver(self, channel: str, data: dict) -> None:
        for handler in list(self.handlers.get(channel, ())):
            await handler({"data": data})


@pytest.fixture
def manager(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(queue_ws.WSManager, "_instance", None)
    instance = queue_ws.WSManager()
    bridge = _Bridge()
    instance._pubsub = bridge
    return instance, bridge


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["false", "raise"])
async def test_failed_subscribe_is_not_cached_and_next_live_connection_retries(
    manager, failure: str
) -> None:
    mgr, bridge = manager
    bridge.first_failure = failure
    first, second = _Socket(), _Socket()

    await mgr.connect(first, ROOM)
    assert ROOM in mgr.rooms  # Local socket remains connected.
    assert ROOM not in mgr._redis_handlers
    assert CHANNEL not in bridge.handlers
    assert bridge.unsubscribe_calls == [CHANNEL]

    await mgr.connect(second, ROOM)
    assert bridge.subscribe_calls == [CHANNEL, CHANNEL]
    assert len(bridge.handlers[CHANNEL]) == 1
    assert bridge.handlers[CHANNEL] == {mgr._redis_handlers[ROOM]}

    message = {"type": "queue_update", "synthetic": 71}
    await bridge.deliver(CHANNEL, message)
    assert first.received == [message]
    assert second.received == [message]


@pytest.mark.asyncio
async def test_concurrent_first_connections_share_one_confirmed_subscription(
    manager,
) -> None:
    mgr, bridge = manager
    bridge.block_subscribe = True
    first, second = _Socket(), _Socket()

    task_a = asyncio.create_task(mgr.connect(first, ROOM))
    await asyncio.wait_for(bridge.subscribe_entered.wait(), timeout=1)
    task_b = asyncio.create_task(mgr.connect(second, ROOM))
    await asyncio.sleep(0)
    assert bridge.subscribe_calls == [CHANNEL]
    assert not task_b.done()

    bridge.release_subscribe.set()
    await asyncio.wait_for(asyncio.gather(task_a, task_b), timeout=1)
    assert bridge.subscribe_calls == [CHANNEL]
    assert len(bridge.handlers[CHANNEL]) == 1
    assert bridge.handlers[CHANNEL] == {mgr._redis_handlers[ROOM]}


@pytest.mark.asyncio
async def test_queued_unsubscribe_cannot_remove_a_fast_reconnect(manager) -> None:
    mgr, bridge = manager
    first, second = _Socket(), _Socket()
    await mgr.connect(first, ROOM)

    mgr.disconnect(first, ROOM)  # Async cleanup is queued, not yet executed.
    await mgr.connect(second, ROOM)
    for _ in range(4):
        await asyncio.sleep(0)

    assert second in mgr.rooms[ROOM]
    assert bridge.unsubscribe_calls == []
    assert bridge.handlers[CHANNEL] == {mgr._redis_handlers[ROOM]}


@pytest.mark.asyncio
async def test_reconnect_waits_for_an_inflight_unsubscribe(manager) -> None:
    mgr, bridge = manager
    first, second = _Socket(), _Socket()
    await mgr.connect(first, ROOM)

    bridge.block_unsubscribe = True
    mgr.disconnect(first, ROOM)
    await asyncio.wait_for(bridge.unsubscribe_entered.wait(), timeout=1)

    reconnect = asyncio.create_task(mgr.connect(second, ROOM))
    await asyncio.sleep(0)
    assert not reconnect.done()

    bridge.release_unsubscribe.set()
    await asyncio.wait_for(reconnect, timeout=1)
    assert bridge.subscribe_calls == [CHANNEL, CHANNEL]
    assert bridge.unsubscribe_calls == [CHANNEL]
    assert bridge.handlers[CHANNEL] == {mgr._redis_handlers[ROOM]}


@pytest.mark.asyncio
async def test_last_socket_removal_unsubscribes_but_live_peer_does_not(
    manager,
) -> None:
    mgr, bridge = manager
    first, second = _Socket(), _Socket()
    await mgr.connect(first, ROOM)
    await mgr.connect(second, ROOM)

    mgr.disconnect(first, ROOM)
    await asyncio.sleep(0)
    assert bridge.unsubscribe_calls == []
    assert CHANNEL in bridge.handlers

    mgr.disconnect(second, ROOM)
    for _ in range(12):
        if bridge.unsubscribe_calls:
            break
        await asyncio.sleep(0)
    assert bridge.unsubscribe_calls == [CHANNEL]
    assert CHANNEL not in bridge.handlers
    assert ROOM not in mgr._redis_handlers
