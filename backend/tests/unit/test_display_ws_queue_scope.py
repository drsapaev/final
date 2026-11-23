"""QR-FE-008: display WS payloads must carry backend-owned queue scope.

`broadcast_daily_queue_state` sends a per-queue subset to EVERY connected
board; `_send_current_state` builds the board-wide initial snapshot. Both
payloads must carry the owning daily_queue.id (envelope + per entry) so a
multi-queue board can merge scoped updates instead of destroying rows of
untouched queues. Synthetic fixtures only — no real patients/staff.
"""
import asyncio
import json
from collections import defaultdict
from datetime import date, datetime, timezone
from types import SimpleNamespace

import pytest

from app.models.display_config import DisplayBoard
from app.models.online_queue import DailyQueue, OnlineQueueEntry
from app.models.setting import Setting
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

    async def accept(self, subprotocol: str | None = None) -> None:
        self.accepted = True

    async def send_text(self, data: str) -> None:
        self.messages.append(json.loads(data))


class _FakeQuery:
    def __init__(self, result_all=None, result_first=None):
        self._all = list(result_all) if result_all is not None else []
        self._first = result_first

    def filter(self, *args, **kwargs):
        # Emulate the one status filter the service applies to entries
        # (display_websocket._send_current_state: status.in_(["waiting",
        # "called"])); other filters (day/active/queue_id) are no-ops for
        # these single-queue fixtures. The IN-list arrives as a bound
        # value on the right side of the binary expression.
        for cond in args:
            value = getattr(getattr(cond, "right", None), "value", None)
            if isinstance(value, (list, tuple, set)) and set(value) == {"waiting", "called"}:
                self._all = [e for e in self._all if e.status in ("waiting", "called")]
        return self

    def order_by(self, *args, **kwargs):
        return self

    def populate_existing(self):
        return self

    def with_for_update(self):
        return self

    def all(self):
        return self._all

    def first(self):
        return self._first


class _FakeSession:
    def __init__(self, routes: dict):
        self._routes = routes

    def query(self, model):
        return self._routes.get(model, _FakeQuery())

    def commit(self):
        return None

    def rollback(self):
        return None

    def close(self):
        return None


def _synthetic_queue(queue_id: int) -> SimpleNamespace:
    return SimpleNamespace(
        id=queue_id,
        day=date(2026, 11, 4),
        opened_at=None,
        active=True,
        queue_resource_id=None,
        specialist=None,
        queue_tag="cardiology",
        specialist_id=None,
    )


def _synthetic_entry(entry_id: int, number: int, status: str) -> SimpleNamespace:
    return SimpleNamespace(
        id=entry_id,
        number=number,
        patient_name=f"Synthetic Patient {entry_id}",
        status=status,
        source="reception",
        created_at=datetime(2026, 11, 4, 8, 0, tzinfo=timezone.utc),
        called_at=(
            datetime(2026, 11, 4, 8, 5, tzinfo=timezone.utc) if status == "called" else None
        ),
    )


@pytest.mark.asyncio
async def test_broadcast_daily_queue_state_carries_queue_scope(monkeypatch):
    """queue_update envelope + every entry must carry the owning queue id."""
    queue = _synthetic_queue(101)
    entries = [
        _synthetic_entry(9001, 7, "waiting"),
        _synthetic_entry(9002, 8, "called"),
    ]
    session = _FakeSession(
        {
            OnlineQueueEntry: _FakeQuery(result_all=entries),
            DisplayBoard: _FakeQuery(result_first=None),
        }
    )
    monkeypatch.setattr(
        "app.services.display_websocket.SessionLocal", lambda: session
    )

    manager = DisplayWebSocketManager(pubsub=_FakePubSubBridge())

    async def _skip_initial_state(*args, **kwargs):
        return None

    manager._send_current_state = _skip_initial_state  # type: ignore[method-assign]

    ws = _FakeWebSocket()
    await manager.connect(ws, "dept_cardiology")

    await manager.broadcast_daily_queue_state(
        queue, board_ids=["dept_cardiology"], event_type="queue.updated"
    )
    await asyncio.sleep(0)

    updates = [m for m in ws.messages if m.get("type") == "queue_update"]
    assert updates, ws.messages
    message = updates[-1]
    assert message.get("event_type") == "queue.updated"
    data = message["data"]
    # Envelope scope: exactly one daily queue is described by this payload.
    assert data["queue_id"] == 101
    # Per-entry identity mirrors initial_state (id + queue_id).
    assert len(data["queue_entries"]) == 2
    for entry in data["queue_entries"]:
        assert entry["queue_id"] == 101
        assert entry["id"] in (9001, 9002)
    assert data["queue_entries"][0]["number"] == 7
    assert data["queue_entries"][0]["status"] == "waiting"


@pytest.mark.asyncio
async def test_send_current_state_entries_carry_queue_scope(monkeypatch):
    """initial_state entries must carry queue_id so later scoped merges match."""
    queue = _synthetic_queue(202)
    entries = [
        _synthetic_entry(9101, 1, "waiting"),
        _synthetic_entry(9102, 2, "called"),
        _synthetic_entry(9103, 3, "completed"),  # must stay off the board
    ]
    session = _FakeSession(
        {
            DailyQueue: _FakeQuery(result_all=[queue]),
            OnlineQueueEntry: _FakeQuery(result_all=entries),
            DisplayBoard: _FakeQuery(result_first=None),
            Setting: _FakeQuery(result_all=[]),
        }
    )
    monkeypatch.setattr(
        "app.services.display_websocket.SessionLocal", lambda: session
    )

    manager = DisplayWebSocketManager(pubsub=_FakePubSubBridge())
    ws = _FakeWebSocket()

    await manager._send_current_state(ws, "main_board")

    snapshots = [m for m in ws.messages if m.get("type") == "initial_state"]
    assert snapshots, ws.messages
    data = snapshots[0]["data"]
    rows = data["queue_entries"]
    # Display read-model: waiting/called only (completed filtered by backend).
    assert [r["id"] for r in rows] == [9101, 9102]
    for row in rows:
        assert row["queue_id"] == 202
        assert row["specialist_name"]


@pytest.mark.asyncio
async def test_broadcast_without_scope_still_single_queue_contract(monkeypatch):
    """No queue identity loss for resource-style queues (regression guard)."""
    queue = _synthetic_queue(303)
    entries = [_synthetic_entry(9201, 5, "waiting")]
    session = _FakeSession(
        {
            OnlineQueueEntry: _FakeQuery(result_all=entries),
            DisplayBoard: _FakeQuery(result_first=None),
        }
    )
    monkeypatch.setattr(
        "app.services.display_websocket.SessionLocal", lambda: session
    )

    manager = DisplayWebSocketManager(pubsub=_FakePubSubBridge())

    async def _skip_initial_state(*args, **kwargs):
        return None

    manager._send_current_state = _skip_initial_state  # type: ignore[method-assign]

    ws = _FakeWebSocket()
    await manager.connect(ws, "dept_x")

    await manager.broadcast_daily_queue_state(queue, event_type=None)
    await asyncio.sleep(0)

    updates = [m for m in ws.messages if m.get("type") == "queue_update"]
    assert updates, ws.messages
    assert updates[-1]["data"]["queue_id"] == 303
    assert "event_type" not in updates[-1]
