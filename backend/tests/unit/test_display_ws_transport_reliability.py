"""Contract tests — display WS transport reliability plane (audit PR #3961).

Findings covered (rounds 31/33, docs/audits/2026-11-09-queue-position-
notifications-source-review.md, Draft PR #3961):

- DISPLAYSESSION-BE-001 (P2): the per-queue broadcast must close its
  SQLAlchemy session on success AND on failure, and a legacy row with a
  NULL ``created_at`` must not kill the whole board update.
- DISPLAYRELAY-BE-002 (P2): a crashed Redis pub/sub listener must recover
  with bounded backoff and restore the previously subscribed channels —
  without forcing the board to reconnect.
- DISPLAYRELAY-BE-003 (P2): a failed initial Redis SUBSCRIBE must not be
  permanently cached; the next connection to the same board retries it and
  exactly one handler ends up registered.
- DISPLAYSTATUS-BE-001 (P2): zero LOCAL sockets must never be reported as
  a system-wide offline board — connections are per-worker.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.orm import Session

from app.models.display_config import DisplayBoard
from app.models.online_queue import DailyQueue, OnlineQueueEntry, QueueResource
from app.models.user import User
from app.services import display_websocket as service_module
from app.services.display_websocket import DisplayWebSocketManager
from app.services.ws_redis_pubsub import RedisPubSubBridge

# ---------------------------------------------------------------------------
# Synthetic helpers
# ---------------------------------------------------------------------------


class _FakeWebSocket:
    def __init__(self) -> None:
        self.accepted = False
        self.messages: list[dict] = []

    async def accept(self, subprotocol: str | None = None) -> None:
        self.accepted = True

    async def send_text(self, data: str) -> None:
        self.messages.append(__import__("json").loads(data))


class _SilentBridge:
    """Bridge stub that reports subscribe() success honestly."""

    def __init__(self) -> None:
        self.subscriptions: list[tuple[str, object]] = []
        self.fail_next = False

    async def subscribe(self, logical_channel: str, handler) -> bool:
        if self.fail_next:
            self.fail_next = False
            return False
        self.subscriptions.append((logical_channel, handler))
        return True

    async def unsubscribe(self, logical_channel: str, handler) -> None:
        self.subscriptions = [
            (c, h)
            for c, h in self.subscriptions
            if not (c == logical_channel and h == handler)
        ]

    async def publish(self, logical_channel: str, payload: dict) -> bool:
        for channel, handler in list(self.subscriptions):
            if channel == logical_channel:
                await handler(payload)
        return True


class _SessionSpy:
    """Wraps a Session and counts close() calls."""

    def __init__(self, inner) -> None:
        self._inner = inner
        self.close_calls = 0

    def query(self, *args, **kwargs):
        return self._inner.query(*args, **kwargs)

    def close(self) -> None:
        # Только счёт: реальная SessionLocal() закрывает СВОЙ коннект, а
        # не общий fixture-сессию (закрытие детачило бы DailyQueue и
        # ломало lazy-load — артефакт общего инстанса в тесте).
        self.close_calls += 1

    def __getattr__(self, name):  # pragma: no cover - passthrough
        return getattr(self._inner, name)


def _spy_factory(db_session, spies: list) -> _SessionSpy:
    """One spy per SessionLocal() call — the resolver opens its own session,
    the broadcast opens another; the test inspects them individually."""

    def factory() -> _SessionSpy:
        spy = _SessionSpy(db_session)
        spies.append(spy)
        return spy

    return factory


def _make_user(db: Session, username: str) -> User:
    user = User(
        username=username,
        full_name=username.title(),
        hashed_password="x",
        role="Admin",
        is_active=True,
    )
    db.add(user)
    db.flush()
    return user


def _make_board(db: Session, name: str) -> DisplayBoard:
    board = DisplayBoard(
        name=name,
        display_name=f"Табло {name}",
        location="Синтетика",
        theme="light",
        show_patient_names="full",
        queue_display_count=5,
        sound_enabled=True,
        voice_announcements=False,
        show_announcements=True,
        active=True,
    )
    db.add(board)
    db.flush()
    return board


def _make_queue(db: Session, day) -> DailyQueue:
    resource = QueueResource(
        code="synthetic_reliability",
        queue_tag="Синтетика",
        display_name="Ресурс Синтетика",
        active=True,
    )
    db.add(resource)
    db.flush()
    queue = DailyQueue(
        day=day, queue_resource_id=resource.id, queue_tag="Синтетика", active=True
    )
    db.add(queue)
    db.flush()
    return queue


def _make_entry(
    db: Session,
    queue: DailyQueue,
    number: int,
    *,
    created_at: datetime | None = None,
    status: str = "waiting",
) -> OnlineQueueEntry:
    entry = OnlineQueueEntry(
        queue_id=queue.id,
        number=number,
        patient_name=f"Синтетика Тестовый #{number}",
        status=status,
        priority=0,
        queue_time=None,
        created_at=created_at,
        source="desk",
    )
    db.add(entry)
    db.flush()
    return entry


async def _skip_initial_state(*args, **kwargs):
    return None


# ---------------------------------------------------------------------------
# DISPLAYSESSION-BE-001 — session lifecycle + legacy NULL created_at row
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_daily_broadcast_null_created_at_row_delivers_and_closes_session(
    db_session, monkeypatch
):
    """A legacy entry with created_at=NULL must not kill the update; the
    session is closed exactly once on the success path."""
    day = datetime.now(UTC).date()
    queue = _make_queue(db_session, day)
    _make_entry(db_session, queue, 1, created_at=datetime.now(UTC))
    legacy = _make_entry(db_session, queue, 2, created_at=None)
    # server_default=func.now() подставляет время при INSERT; легаси-строку
    # симулируем прямой UPDATE в обход клиентского дефолта.
    db_session.query(OnlineQueueEntry).filter(OnlineQueueEntry.id == legacy.id).update(
        {"created_at": None}, synchronize_session=False
    )
    db_session.expire(legacy)
    db_session.flush()

    spies: list[_SessionSpy] = []
    monkeypatch.setattr(service_module, "SessionLocal", _spy_factory(db_session, spies))

    ws = _FakeWebSocket()
    manager = DisplayWebSocketManager(pubsub=_SilentBridge())
    manager._send_current_state = _skip_initial_state  # type: ignore[assignment]
    manager.connections["main_board"] = {ws}

    await manager.broadcast_daily_queue_state(queue, board_ids=["main_board"])

    assert spies[0].close_calls == 1
    updates = [m for m in ws.messages if m.get("type") == "queue_update"]
    assert updates, "queue_update must still be delivered despite NULL row"
    rows = updates[0]["data"]["queue_entries"]
    assert len(rows) == 2
    null_row = [r for r in rows if r["number"] == 2]
    assert null_row and null_row[0]["created_at"] is None


@pytest.mark.asyncio
async def test_daily_broadcast_failure_still_closes_session(db_session, monkeypatch):
    """A broadcast transport failure must not leak the SQLAlchemy session —
    close() happens in a finally, on failure too."""
    day = datetime.now(UTC).date()
    queue = _make_queue(db_session, day)
    _make_entry(db_session, queue, 1, created_at=datetime.now(UTC))

    spies: list[_SessionSpy] = []
    monkeypatch.setattr(service_module, "SessionLocal", _spy_factory(db_session, spies))

    manager = DisplayWebSocketManager(pubsub=_SilentBridge())
    manager._send_current_state = _skip_initial_state  # type: ignore[assignment]
    manager.broadcast_to_board = AsyncMock(side_effect=RuntimeError("transport down"))

    await manager.broadcast_daily_queue_state(queue, board_ids=["main_board"])

    assert spies[0].close_calls == 1


# ---------------------------------------------------------------------------
# DISPLAYRELAY-BE-003 — failed initial SUBSCRIBE is retried, not cached
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_failed_subscribe_not_cached_next_connection_retries():
    """First SUBSCRIBE fails → the handler is NOT cached; the second
    connection to the same board retries and exactly one Redis handler is
    registered; remote events then reach the live sockets."""
    bridge = _SilentBridge()
    bridge.fail_next = True
    manager = DisplayWebSocketManager(pubsub=bridge)
    manager._send_current_state = _skip_initial_state  # type: ignore[assignment]

    ws1 = _FakeWebSocket()
    ws2 = _FakeWebSocket()

    await manager.connect(ws1, "main_board")
    assert "main_board" not in manager._redis_handlers

    await manager.connect(ws2, "main_board")
    assert len(manager._redis_handlers) == 1
    assert len(bridge.subscriptions) == 1

    await bridge.publish("board:main_board", {"type": "remote_event"})
    assert ws1.messages[0]["type"] == "remote_event"
    assert ws2.messages[0]["type"] == "remote_event"

    await manager.disconnect(ws1, "main_board")
    await manager.disconnect(ws2, "main_board")
    assert not manager._redis_handlers
    assert not bridge.subscriptions


# ---------------------------------------------------------------------------
# DISPLAYRELAY-BE-002 — crashed listener recovers with bounded backoff
# ---------------------------------------------------------------------------


class _HealingPubsub:
    """Fake redis PubSub: the first listen() crashes, the second heals."""

    def __init__(self) -> None:
        self.subscribed: list[str] = []
        self.pending: list[dict] = []
        self.listen_calls = 0

    async def subscribe(self, channel: str) -> None:
        self.subscribed.append(channel)

    async def unsubscribe(self, channel: str) -> None:
        pass

    async def aclose(self) -> None:
        pass

    async def listen(self):
        self.listen_calls += 1
        if self.listen_calls == 1:
            raise RuntimeError("transient redis outage")
        while True:
            if self.pending:
                yield self.pending.pop(0)
            else:
                await asyncio.sleep(0.005)


@pytest.mark.asyncio
async def test_listener_crash_reconnects_and_restores_subscription(monkeypatch):
    """After a listener crash the bridge must reconnect with bounded
    backoff, re-SUBSCRIBE the old channel and deliver the remote event —
    without any browser reconnect."""
    bridge = RedisPubSubBridge(
        channel_prefix="test_relay",
        redis_url="redis://synthetic",
        reconnect_backoff_base=0.005,
    )
    fake = _HealingPubsub()

    async def fake_ready() -> bool:
        if bridge._pubsub is None:
            bridge._pubsub = fake
        return True

    monkeypatch.setattr(bridge, "_ensure_ready", fake_ready)

    received: list[dict] = []

    async def handler(payload: dict) -> None:
        received.append(payload)

    await bridge.subscribe("board:main_board", handler)
    assert bridge._listener_task is not None

    # Wait for: crash → bounded backoff → resubscribe → new listener.
    deadline = 300
    for _ in range(deadline):
        await asyncio.sleep(0.01)
        if (
            fake.listen_calls >= 2
            and fake.subscribed.count("test_relay:board:main_board") >= 2
        ):
            break
    assert fake.listen_calls >= 2, "listener must restart after the crash"
    assert fake.subscribed.count("test_relay:board:main_board") >= 2, (
        "the old channel must be re-SUBSCRIBED on recovery"
    )

    fake.pending.append(
        {
            "type": "message",
            "channel": "test_relay:board:main_board",
            "data": '{"source": "other-worker", "payload": {"number": 5}}',
        }
    )
    deadline = 200
    for _ in range(deadline):
        await asyncio.sleep(0.01)
        if received:
            break
    assert received == [{"number": 5}]


# ---------------------------------------------------------------------------
# DISPLAYSTATUS-BE-001 — worker-local status must not claim offline
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_boards_status_zero_local_sockets_is_unknown_not_offline(
    db_session, monkeypatch
):
    """A board with zero LOCAL connections must report online=None with a
    worker_local scope — never a false system-wide offline."""
    from app.api.v1.endpoints import display_websocket as endpoints_module

    _make_board(db_session, "main_board")
    _make_board(db_session, "other_board")
    user = _make_user(db_session, "status_admin_1")

    ws = _FakeWebSocket()
    manager = DisplayWebSocketManager(pubsub=_SilentBridge())
    manager._send_current_state = _skip_initial_state  # type: ignore[assignment]
    await manager.connect(ws, "main_board")
    monkeypatch.setattr(
        endpoints_module, "get_display_manager", lambda: manager, raising=True
    )

    result = endpoints_module.get_boards_status(db=db_session, current_user=user)

    by_name = {b["name"]: b for b in result["boards"]}
    assert by_name["main_board"]["online"] is True
    assert by_name["main_board"]["websocket_connections"] == 1
    # main_board is live locally, but the scope is still per-worker.
    assert by_name["main_board"]["online_scope"] == "worker_local"

    # Zero LOCAL sockets: indeterminate, NOT a false offline.
    assert by_name["other_board"]["online"] is None
    assert by_name["other_board"]["websocket_connections"] == 0
    assert by_name["other_board"]["online_scope"] == "worker_local"
    assert result["connections_scope"] == "worker_local"
