"""Deterministic queue WS Redis subscribe/unsubscribe race regressions.

Uses WSManager and an in-memory bridge with explicit asyncio.Event barriers;
no real Redis, JWT, database, network, patient data, or timing sleeps.
"""

from __future__ import annotations

import asyncio

import pytest

from app.ws import queue_ws


class _FakeSocket:
    pass


class _BarrierPubSub:
    def __init__(self) -> None:
        self.active: dict[str, object] = {}
        self.subscribe_calls: list[str] = []
        self.unsubscribe_calls: list[str] = []
        self.block_unsubscribe_for: str | None = None
        self.unsubscribe_entered = asyncio.Event()
        self.allow_unsubscribe = asyncio.Event()

    async def subscribe(self, channel: str, handler: object) -> None:
        self.subscribe_calls.append(channel)
        self.active[channel] = handler

    async def unsubscribe(self, channel: str, handler: object) -> None:
        self.unsubscribe_calls.append(channel)
        if channel == self.block_unsubscribe_for:
            self.unsubscribe_entered.set()
            await self.allow_unsubscribe.wait()
        # The Redis unsubscribe acts on the channel, even if a new
        # subscribe was issued while the old unsubscribe was pending.
        self.active.pop(channel, None)

    async def publish(self, _channel: str, _payload: dict) -> bool:
        return True


def _new_manager(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(queue_ws.WSManager, "_instance", None)
    manager = queue_ws.WSManager()
    bridge = _BarrierPubSub()
    manager._pubsub = bridge
    return manager, bridge


@pytest.mark.asyncio
async def test_reconnect_before_queued_unsubscribe_preserves_subscription(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manager, bridge = _new_manager(monkeypatch)
    room = "specialist_91::2026-11-11"
    channel = f"room:{room}"
    old_socket = _FakeSocket()
    new_socket = _FakeSocket()

    await manager.connect(old_socket, room)
    manager.disconnect(old_socket, room)
    # Do not yield between disconnect and reconnect: the old
    # unsubscribe coroutine is queued but has not yet run.
    await manager.connect(new_socket, room)
    await asyncio.sleep(0)
    await asyncio.sleep(0)

    assert manager.rooms[room] == {new_socket}
    assert channel in bridge.active
    assert bridge.active[channel] is manager._redis_handlers[room]
    assert bridge.unsubscribe_calls == []

    manager.disconnect(new_socket, room)
    for _ in range(10):
        if bridge.unsubscribe_calls:
            break
        await asyncio.sleep(0)
    assert bridge.unsubscribe_calls == [channel]


@pytest.mark.asyncio
async def test_reconnect_during_unsubscribe_waits_then_resubscribes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manager, bridge = _new_manager(monkeypatch)
    room = "specialist_92::2026-11-11"
    channel = f"room:{room}"
    old_socket = _FakeSocket()
    new_socket = _FakeSocket()
    await manager.connect(old_socket, room)
    bridge.block_unsubscribe_for = channel

    manager.disconnect(old_socket, room)
    await asyncio.wait_for(bridge.unsubscribe_entered.wait(), timeout=1)

    reconnect = asyncio.create_task(manager.connect(new_socket, room))
    await asyncio.sleep(0)
    completed_before_unsubscribe = reconnect.done()
    bridge.allow_unsubscribe.set()
    await asyncio.wait_for(reconnect, timeout=1)

    assert not completed_before_unsubscribe
    assert bridge.subscribe_calls == [channel, channel]
    assert bridge.unsubscribe_calls == [channel]
    assert bridge.active[channel] is manager._redis_handlers[room]
    assert manager.rooms[room] == {new_socket}

    manager.disconnect(new_socket, room)
    for _ in range(10):
        if len(bridge.unsubscribe_calls) == 2:
            break
        await asyncio.sleep(0)
    assert bridge.unsubscribe_calls == [channel, channel]


@pytest.mark.asyncio
async def test_delayed_unsubscribe_does_not_block_unrelated_room(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manager, bridge = _new_manager(monkeypatch)
    room_a = "specialist_93::2026-11-11"
    room_b = "specialist_94::2026-11-11"
    old = _FakeSocket()
    peer = _FakeSocket()
    await manager.connect(old, room_a)
    bridge.block_unsubscribe_for = f"room:{room_a}"

    manager.disconnect(old, room_a)
    await asyncio.wait_for(bridge.unsubscribe_entered.wait(), timeout=1)

    await asyncio.wait_for(manager.connect(peer, room_b), timeout=1)
    assert f"room:{room_b}" in bridge.active
    assert peer in manager.rooms[room_b]

    bridge.allow_unsubscribe.set()
    manager.disconnect(peer, room_b)
    for _ in range(10):
        if f"room:{room_b}" in bridge.unsubscribe_calls:
            break
        await asyncio.sleep(0)
    assert f"room:{room_b}" in bridge.unsubscribe_calls


@pytest.mark.asyncio
async def test_rapid_disconnect_reconnect_has_one_valid_final_handler(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manager, bridge = _new_manager(monkeypatch)
    room = "specialist_95::2026-11-11"
    channel = f"room:{room}"
    socket = _FakeSocket()
    await manager.connect(socket, room)

    for _ in range(12):
        manager.disconnect(socket, room)
        # Let some but not all cleanup tasks advance unpredictably.
        await asyncio.sleep(0)
        await manager.connect(socket, room)
        await asyncio.sleep(0)

    assert manager.rooms[room] == {socket}
    assert bridge.active[channel] is manager._redis_handlers[room]

    manager.disconnect(socket, room)
    for _ in range(20):
        if channel not in bridge.active:
            break
        await asyncio.sleep(0)
    assert channel not in bridge.active
    assert room not in manager._redis_handlers


@pytest.mark.asyncio
async def test_disconnect_with_healthy_peer_does_not_unsubscribe(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manager, bridge = _new_manager(monkeypatch)
    room = "specialist_96::2026-11-11"
    channel = f"room:{room}"
    first = _FakeSocket()
    second = _FakeSocket()
    await manager.connect(first, room)
    await manager.connect(second, room)

    manager.disconnect(first, room)
    await asyncio.sleep(0)
    assert bridge.unsubscribe_calls == []
    assert bridge.active[channel] is manager._redis_handlers[room]

    manager.disconnect(second, room)
    for _ in range(10):
        if bridge.unsubscribe_calls:
            break
        await asyncio.sleep(0)
    assert bridge.unsubscribe_calls == [channel]
