import asyncio
import json
from collections import defaultdict
from unittest.mock import AsyncMock

import pytest

from app.schemas.misc_endpoints import DisplayTestAck
from app.services.display_websocket import DisplayWebSocketManager


class _FakePubSubBridge:
    enabled = True
    _subscribers: dict[str, list[tuple[str, object]]] = defaultdict(list)
    _seq = 0

    def __init__(self) -> None:
        type(self)._seq += 1
        self._id = f"instance-{type(self)._seq}"

    async def publish(self, logical_channel: str, payload: dict) -> bool:
        for instance_id, handler in list(self._subscribers.get(logical_channel, [])):
            if instance_id == self._id:
                continue
            await handler(payload)
        return True

    async def subscribe(self, logical_channel: str, handler) -> bool:
        self._subscribers[logical_channel].append((self._id, handler))
        return True

    async def unsubscribe(self, logical_channel: str, handler) -> None:
        current = self._subscribers.get(logical_channel, [])
        self._subscribers[logical_channel] = [
            (instance_id, h)
            for instance_id, h in current
            if not (instance_id == self._id and h == handler)
        ]


class _FakeWebSocket:
    def __init__(self) -> None:
        self.accepted = False
        self.messages: list[dict] = []
        self.received = asyncio.Event()

    async def accept(self, subprotocol: str | None = None) -> None:
        self.accepted = True

    async def send_text(self, data: str) -> None:
        self.messages.append(json.loads(data))
        self.received.set()


@pytest.mark.asyncio
async def test_display_manager_redis_pubsub_two_instance_propagation():
    bridge_1 = _FakePubSubBridge()
    bridge_2 = _FakePubSubBridge()

    manager_1 = DisplayWebSocketManager(pubsub=bridge_1)
    manager_2 = DisplayWebSocketManager(pubsub=bridge_2)

    async def _skip_initial_state(*args, **kwargs):
        return None

    manager_1._send_current_state = _skip_initial_state  # type: ignore[method-assign]
    manager_2._send_current_state = _skip_initial_state  # type: ignore[method-assign]

    ws_1 = _FakeWebSocket()
    ws_2 = _FakeWebSocket()
    board_id = "dept_cardiology"

    await manager_1.connect(ws_1, board_id)
    await manager_2.connect(ws_2, board_id)

    payload = {
        "type": "queue_event",
        "event": "queue.created",
        "data": {"queue_number": 7},
    }

    await manager_1.broadcast_to_board(board_id, payload)
    await asyncio.sleep(0)

    assert any(msg.get("event") == "queue.created" for msg in ws_2.messages)


@pytest.mark.asyncio
async def test_device_test_ack_crosses_workers_only_for_the_addressed_socket():
    sender = DisplayWebSocketManager(pubsub=_FakePubSubBridge())
    receiver = DisplayWebSocketManager(pubsub=_FakePubSubBridge())
    receiver._send_current_state = AsyncMock()
    addressed, other, staff = _FakeWebSocket(), _FakeWebSocket(), _FakeWebSocket()
    board_name = "synthetic-device-board"

    await receiver.connect(addressed, board_name, device_id=101)
    await receiver.connect(other, board_name, device_id=102)
    await receiver.connect(staff, board_name)

    test = asyncio.create_task(sender.test_device(board_name, 101, "call"))
    await asyncio.wait_for(addressed.received.wait(), timeout=1)
    assert not other.messages
    assert not staff.messages
    message = addressed.messages[0]
    assert message["type"] == "display_test"
    assert message["data"]["queue_number"] == "T007"
    assert "patient_name" not in message["data"]
    ack = DisplayTestAck(test_id=message["data"]["test_id"], status="displayed", audio_status="blocked")
    await receiver.acknowledge_display_test(other, board_name, 102, ack)
    assert not test.done()
    await receiver.acknowledge_display_test(addressed, board_name, 101, ack)
    result = await asyncio.wait_for(test, timeout=1)
    assert result.test_id == ack.test_id
    assert result.status == "displayed"
    assert result.audio_status == "blocked"
    assert receiver.board_states.get(board_name) is None


@pytest.mark.asyncio
async def test_diagnostic_distinguishes_no_acknowledgment_from_relay_failure(monkeypatch):
    monkeypatch.setattr("app.services.display_websocket.DISPLAY_TEST_TIMEOUT_SECONDS", 0.05)
    bridge = _FakePubSubBridge()
    manager = DisplayWebSocketManager(pubsub=bridge)
    board_name = "synthetic-offline-board"

    result = await manager.test_device(board_name, 101, "announcement")
    assert result.status == "unconfirmed"

    bridge.publish = AsyncMock(return_value=False)
    result = await manager.test_device(board_name, 101, "announcement")
    assert result.status == "dispatch_failed"
