import asyncio
import json
from collections import defaultdict

import pytest

from app.services.display_websocket import DisplayWebSocketManager


class _FakePubSubBridge:
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

    async def subscribe(self, logical_channel: str, handler) -> None:
        self._subscribers[logical_channel].append((self._id, handler))

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

    async def accept(self) -> None:
        self.accepted = True

    async def send_text(self, data: str) -> None:
        self.messages.append(json.loads(data))


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
