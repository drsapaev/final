from __future__ import annotations

import pytest

from app.ws.chat_ws import chat_manager


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
    assert replacement.accepted is True
    assert chat_manager.active_connections[42] is replacement
