from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock

import pytest

from app.ws import chat_ws
from app.ws.chat_ws import ChatConnectionManager, chat_manager


class FakeWebSocket:
    def __init__(self):
        self.sent = []
        self.closed = False
        self.accepted = False

    async def send_json(self, data):
        self.sent.append(data)

    async def accept(self):
        self.accepted = True

    async def close(self, *args, **kwargs):
        self.closed = True


@pytest.mark.asyncio
async def test_broadcast_typing_sends_versioned_event(monkeypatch):
    websocket = FakeWebSocket()
    monkeypatch.setattr(chat_manager, "active_connections", {3: websocket})

    await chat_manager.broadcast_typing(sender_id=1, recipient_id=3, is_typing=True)

    assert websocket.sent == [
        {
            "type": "typing",
            "contract_version": "2026-03",
            "sender_id": 1,
            "is_typing": True,
        }
    ]


@pytest.mark.asyncio
async def test_broadcast_event_wraps_new_message_payload(monkeypatch):
    websocket = FakeWebSocket()
    monkeypatch.setattr(chat_manager, "active_connections", {1: websocket})

    await chat_manager.broadcast_event(
        [1, 1],
        "new_message",
        {"id": 11, "content": "Привет"},
    )

    assert websocket.sent == [
        {
            "type": "new_message",
            "contract_version": "2026-03",
            "message": {
                "id": 11,
                "content": "Привет",
            },
        }
    ]


@pytest.mark.asyncio
async def test_notify_message_read_sends_read_event(monkeypatch):
    websocket = FakeWebSocket()
    monkeypatch.setattr(chat_manager, "active_connections", {7: websocket})

    await chat_manager.notify_message_read(sender_id=7, message_id=91)

    assert websocket.sent == [
        {
            "type": "message_read",
            "contract_version": "2026-03",
            "message_id": 91,
        }
    ]


@pytest.mark.asyncio
async def test_notify_messages_read_sends_batch_read_event(monkeypatch):
    websocket = FakeWebSocket()
    monkeypatch.setattr(chat_manager, "active_connections", {7: websocket})

    await chat_manager.notify_messages_read(sender_id=7, message_ids=[12, 13])

    assert websocket.sent == [
        {
            "type": "messages_read",
            "contract_version": "2026-03",
            "message_ids": [12, 13],
        }
    ]


@pytest.mark.asyncio
async def test_connect_replaces_existing_connection_and_closes_old_socket(monkeypatch):
    existing = FakeWebSocket()
    existing.accepted = True
    monkeypatch.setattr(chat_manager, "active_connections", {42: existing})

    replacement = FakeWebSocket()

    connected = await chat_manager.connect(42, replacement)

    assert connected is True
    assert existing.closed is True
    # ASGI-контракт: хендлер вызывает accept() ДО connect() — менеджер не
    # должен принимать хендшейк повторно (double accept = protocol error).
    assert replacement.accepted is False
    assert chat_manager.active_connections[42] is replacement


def isolated_manager():
    manager = ChatConnectionManager()
    manager._ensure_redis_bridge = AsyncMock()
    manager._publish_cross_instance = AsyncMock()
    return manager


@pytest.mark.asyncio
async def test_local_delivery_waiting_on_revocation_close_sends_nothing():
    close_entered, release_close = asyncio.Event(), asyncio.Event()

    class BlockingCloseSocket(FakeWebSocket):
        async def close(self, *args, **kwargs):
            close_entered.set()
            await release_close.wait()
            self.closed = True

    manager = isolated_manager()
    ws = BlockingCloseSocket()
    revoked, lock = asyncio.Event(), asyncio.Lock()
    assert await manager.connect(7, ws, revoked=revoked, close_lock=lock)
    closer = asyncio.create_task(chat_ws.close_revoked_websocket(ws, revoked, lock))
    await asyncio.wait_for(close_entered.wait(), 1)
    delivery = asyncio.create_task(manager._local_deliver(7, {"type": "new_message"}))
    await asyncio.sleep(0)
    assert not ws.sent
    release_close.set()
    await asyncio.wait_for(closer, 1)
    assert not await asyncio.wait_for(delivery, 1)
    assert not ws.sent
    assert ws.closed


@pytest.mark.asyncio
async def test_blocked_recipient_does_not_delay_other_broadcast_recipient():
    slow_entered, release_slow, fast_received = asyncio.Event(), asyncio.Event(), asyncio.Event()

    class SlowSocket(FakeWebSocket):
        async def send_json(self, data):
            slow_entered.set()
            await release_slow.wait()
            await super().send_json(data)

    class FastSocket(FakeWebSocket):
        async def send_json(self, data):
            await super().send_json(data)
            fast_received.set()

    manager = isolated_manager()
    slow, fast = SlowSocket(), FastSocket()
    assert await manager.connect(1, slow)
    assert await manager.connect(2, fast)
    broadcast = asyncio.create_task(manager.broadcast_event([1, 2], "new_message", {"id": 1}))
    try:
        await asyncio.wait_for(slow_entered.wait(), 1)
        await asyncio.wait_for(fast_received.wait(), 1)
        assert not broadcast.done()
    finally:
        release_slow.set()
        await asyncio.wait_for(broadcast, 1)
    assert len(slow.sent) == len(fast.sent) == 1


@pytest.mark.asyncio
async def test_stalled_local_send_fails_closed_and_releases_connection(monkeypatch):
    entered = asyncio.Event()

    class StalledSocket(FakeWebSocket):
        async def send_json(self, data):
            entered.set()
            await asyncio.Event().wait()

    monkeypatch.setattr(chat_ws, "WS_SEND_TIMEOUT_SECONDS", 0.05)
    manager = isolated_manager()
    ws = StalledSocket()
    revoked, lock = asyncio.Event(), asyncio.Lock()
    async def receive_forever():
        await asyncio.Event().wait()

    owner = asyncio.create_task(receive_forever())
    assert await manager.connect(7, ws, revoked=revoked, close_lock=lock, owner_task=owner)
    delivery = asyncio.create_task(manager._local_deliver(7, {"type": "new_message"}))
    await asyncio.wait_for(entered.wait(), 1)
    assert not await asyncio.wait_for(delivery, 1)
    assert revoked.is_set()
    assert ws.closed
    assert not ws.sent
    assert 7 not in manager.active_connections
    with pytest.raises(asyncio.CancelledError):
        await owner


@pytest.mark.asyncio
async def test_cancel_delivery_during_timeout_close_cleans_up_owner(monkeypatch):
    close_entered = asyncio.Event()

    class Socket(FakeWebSocket):
        async def send_json(self, data):
            await asyncio.Event().wait()

        async def close(self, *args, **kwargs):
            close_entered.set()
            await asyncio.Event().wait()

    async def receive_forever():
        await asyncio.Event().wait()

    monkeypatch.setattr(chat_ws, "WS_SEND_TIMEOUT_SECONDS", 0.02)
    manager = isolated_manager()
    ws = Socket()
    revoked, lock = asyncio.Event(), asyncio.Lock()
    owner = asyncio.create_task(receive_forever())
    assert await manager.connect(7, ws, revoked=revoked, close_lock=lock, owner_task=owner)
    delivery = asyncio.create_task(manager._local_deliver(7, {"type": "new_message"}))
    try:
        await asyncio.wait_for(close_entered.wait(), 1)
        delivery.cancel()
        with pytest.raises(asyncio.CancelledError):
            await delivery
        assert 7 not in manager.active_connections
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(owner, 1)
    finally:
        if not owner.done():
            owner.cancel()
        if not delivery.done():
            delivery.cancel()


@pytest.mark.asyncio
async def test_cancel_timeout_close_waiting_for_lock_cleans_up_owner(monkeypatch):
    async def receive_forever():
        await asyncio.Event().wait()

    monkeypatch.setattr(chat_ws, "WS_SEND_TIMEOUT_SECONDS", 0.02)
    manager = isolated_manager()
    ws = FakeWebSocket()
    revoked, lock = asyncio.Event(), asyncio.Lock()
    owner = asyncio.create_task(receive_forever())
    assert await manager.connect(7, ws, revoked=revoked, close_lock=lock, owner_task=owner)
    await lock.acquire()
    delivery = asyncio.create_task(manager._local_deliver(7, {"type": "new_message"}))
    with pytest.raises(asyncio.CancelledError):
        await asyncio.wait_for(owner, 1)
    try:
        assert 7 not in manager.active_connections
        assert revoked.is_set()  # Revocation is marked before waiting for close.
        delivery.cancel()
        with pytest.raises(asyncio.CancelledError):
            await delivery
    finally:
        lock.release()
        if not owner.done():
            owner.cancel()
        if not delivery.done():
            delivery.cancel()


@pytest.mark.asyncio
async def test_cancel_delivery_before_timeout_keeps_target_connected():
    started = asyncio.Event()

    class Socket(FakeWebSocket):
        async def send_json(self, data):
            started.set()
            await asyncio.Event().wait()

    async def receive_forever():
        await asyncio.Event().wait()

    manager = isolated_manager()
    ws = Socket()
    owner = asyncio.create_task(receive_forever())
    revoked = asyncio.Event()
    assert await manager.connect(7, ws, revoked=revoked, close_lock=asyncio.Lock(), owner_task=owner)
    delivery = asyncio.create_task(manager._local_deliver(7, {"type": "new_message"}))
    try:
        await asyncio.wait_for(started.wait(), 1)
        delivery.cancel()
        with pytest.raises(asyncio.CancelledError):
            await delivery
        assert manager.active_connections[7] is ws
        assert not revoked.is_set()
        assert not owner.done()
    finally:
        owner.cancel()
        with pytest.raises(asyncio.CancelledError):
            await owner


@pytest.mark.asyncio
async def test_delivery_queued_before_timeout_does_not_send_after_cleanup(monkeypatch):
    first_send_entered = asyncio.Event()

    class Socket(FakeWebSocket):
        async def send_json(self, data):
            if not first_send_entered.is_set():
                first_send_entered.set()
                await asyncio.Event().wait()
            await super().send_json(data)

    async def receive_forever():
        await asyncio.Event().wait()

    monkeypatch.setattr(chat_ws, "WS_SEND_TIMEOUT_SECONDS", 0.05)
    manager = isolated_manager()
    ws = Socket()
    owner = asyncio.create_task(receive_forever())
    assert await manager.connect(7, ws, revoked=asyncio.Event(), close_lock=asyncio.Lock(), owner_task=owner)
    first = asyncio.create_task(manager._local_deliver(7, {"type": "first"}))
    await asyncio.wait_for(first_send_entered.wait(), 1)
    second = asyncio.create_task(manager._local_deliver(7, {"type": "second"}))
    try:
        assert not await asyncio.wait_for(first, 1)
        assert not await asyncio.wait_for(second, 1)
        assert ws.sent == []
        assert 7 not in manager.active_connections
        with pytest.raises(asyncio.CancelledError):
            await owner
    finally:
        for task in (first, second, owner):
            if not task.done():
                task.cancel()


@pytest.mark.asyncio
async def test_stale_socket_disconnect_cannot_remove_or_revoke_replacement():
    manager = isolated_manager()
    old, replacement = FakeWebSocket(), FakeWebSocket()
    old_revoked, new_revoked = asyncio.Event(), asyncio.Event()
    assert await manager.connect(7, old, revoked=old_revoked, close_lock=asyncio.Lock())
    assert await manager.connect(7, replacement, revoked=new_revoked, close_lock=asyncio.Lock())
    manager.disconnect(7, old)
    assert manager.active_connections[7] is replacement
    assert old.closed
    assert not new_revoked.is_set()
    assert await manager._local_deliver(7, {"type": "new_message"})
    assert old.sent == []
    assert replacement.sent == [{"type": "new_message"}]


@pytest.mark.asyncio
async def test_cancelling_replacement_while_old_close_stalls_cancels_old_owner():
    owner_ready = asyncio.Event()
    continue_old = asyncio.Event()
    old_continued = asyncio.Event()
    close_entered = asyncio.Event()
    release_close = asyncio.Event()

    async def old_owner():
        owner_ready.set()
        await continue_old.wait()
        old_continued.set()

    class BlockingCloseSocket(FakeWebSocket):
        async def close(self, *args, **kwargs):
            close_entered.set()
            await release_close.wait()

    manager = isolated_manager()
    old = BlockingCloseSocket()
    owner = asyncio.create_task(old_owner())
    await asyncio.wait_for(owner_ready.wait(), 1)
    assert await manager.connect(7, old, revoked=asyncio.Event(), close_lock=asyncio.Lock(), owner_task=owner)
    replacement = asyncio.create_task(manager.connect(7, FakeWebSocket()))
    try:
        await asyncio.wait_for(close_entered.wait(), 1)
        replacement.cancel()
        with pytest.raises(asyncio.CancelledError):
            await replacement
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(owner, 1)
        continue_old.set()
        await asyncio.sleep(0)
        assert not old_continued.is_set()
    finally:
        release_close.set()
        if not replacement.done():
            replacement.cancel()
        if not owner.done():
            owner.cancel()
