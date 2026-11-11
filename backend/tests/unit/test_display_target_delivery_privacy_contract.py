"""Contract tests — display target/delivery/privacy plane (audit PR #3961).

Findings covered (docs/audits/2026-11-09-queue-position-notifications-
source-review.md, Draft PR #3961):

- DISPLAYTARGET-BE-001 (P1/P2): REST call/announcement ``board_ids`` are
  integer DB ids while the WebSocket manager keys rooms by the board NAME
  string. The broadcast must resolve int ids → ``DisplayBoard.name`` and
  deliver to the string-keyed rooms; unresolvable ids are reported
  (``unknown_board_ids``) and an explicit request never falls back to
  all-rooms broadcast.
- DISPLAYDELIVERY-BE-001 (P1/P2): call/announcement responses must report
  the actual per-board transport outcome (``delivered_local`` /
  ``published_only`` / ``failed``). A failed broadcast may never surface as
  ``boards_notified > 0`` or an unconditional "sent" success; the committed
  queue transition stays committed (``call_committed=true``) while the
  display verdict is reported separately (``display_delivery`` =
  delivered/partial/failed/unknown).
- DISPLAYPRIVACY-BE-002 (P1/P2 conditional privacy): any failure to resolve
  a board's privacy policy — resolver error, unknown board, invalid stored
  value, no target boards — fails CLOSED to ``'none'`` masking, never
  degrades to ``'initials'``/``'full'``. Failure results are never cached.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from sqlalchemy.orm import Session

from app.models.clinic import Doctor
from app.models.display_config import DisplayBoard
from app.models.online_queue import DailyQueue, OnlineQueueEntry
from app.models.user import User
from app.schemas.misc_endpoints import AnnouncementRequest
from app.services import display_websocket as display_ws_service
from app.services.display_websocket import DisplayWebSocketManager
from app.services.display_websocket_api_service import DisplayWebSocketApiService


# ---------------------------------------------------------------------------
# Synthetic seed helpers (SQLite, function-scoped savepoint transaction)
# ---------------------------------------------------------------------------


def _make_user(db: Session, username: str, role: str = "Admin") -> User:
    user = User(
        username=username,
        full_name=username.title(),
        hashed_password="x",
        role=role,
        is_active=True,
    )
    db.add(user)
    db.flush()
    return user


def _make_doctor(db: Session, user_id: int, specialty: str) -> Doctor:
    doctor = Doctor(user_id=user_id, specialty=specialty, active=True)
    db.add(doctor)
    db.flush()
    return doctor


def _make_queue(db: Session, day, *, specialist_id: int | None) -> DailyQueue:
    queue = DailyQueue(day=day, specialist_id=specialist_id, active=True)
    db.add(queue)
    db.flush()
    return queue


def _make_entry(
    db: Session, queue: DailyQueue, number: int, *, patient_name: str | None = None
) -> OnlineQueueEntry:
    entry = OnlineQueueEntry(
        queue_id=queue.id,
        number=number,
        patient_name=patient_name or f"Синтетика #{number}",
        status="waiting",
        created_at=datetime.now(UTC),
        source="desk",
    )
    db.add(entry)
    db.flush()
    return entry


def _make_board(
    db: Session, name: str, *, show_patient_names: str = "initials"
) -> DisplayBoard:
    board = DisplayBoard(
        name=name,
        display_name=f"Табло {name}",
        show_patient_names=show_patient_names,
    )
    db.add(board)
    db.flush()
    return board


# ---------------------------------------------------------------------------
# Transport doubles: real manager, stubbed pubsub bridge, fake board sockets
# ---------------------------------------------------------------------------


class _FakeBoardSocket:
    def __init__(self) -> None:
        self.messages: list[dict] = []

    async def send_text(self, text: str) -> None:
        self.messages.append(json.loads(text))


class _StubPubSub:
    """RedisPubSubBridge double: records publishes, optional failures."""

    def __init__(self, fail_channels: frozenset[str] = frozenset()) -> None:
        self.published: list[tuple[str, dict]] = []
        self.subscriptions: dict[str, object] = {}
        self._fail = set(fail_channels)

    async def publish(self, channel: str, message: dict) -> None:
        if channel in self._fail:
            raise RuntimeError(f"SYNTHETIC pubsub failure: {channel}")
        self.published.append((channel, message))

    async def subscribe(self, channel: str, handler) -> None:
        self.subscriptions[channel] = handler

    async def unsubscribe(self, channel: str, handler) -> None:
        self.subscriptions.pop(channel, None)


def _real_manager(
    pubsub: _StubPubSub,
    rooms: dict[str, list[_FakeBoardSocket]] | None = None,
    cache: dict[str, str] | None = None,
) -> DisplayWebSocketManager:
    mgr = DisplayWebSocketManager.__new__(DisplayWebSocketManager)
    mgr.connections = {name: set(socks) for name, socks in (rooms or {}).items()}
    mgr.board_states = {}
    mgr._redis_handlers = {}
    mgr._name_format_cache = dict(cache or {})
    mgr._pubsub = pubsub
    return mgr


# ---------------------------------------------------------------------------
# DISPLAYTARGET-BE-001 — int board ids must reach string-named WS rooms
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_call_int_board_ids_deliver_to_string_named_room(db_session):
    """POST /display/call-patient with board_ids=[id] must deliver to the
    board's NAME-keyed WS room, not to a phantom integer room."""
    from datetime import UTC, datetime

    day = datetime.now(UTC).date()
    user = _make_user(db_session, "target_admin_1")
    doctor = _make_doctor(db_session, user.id, "cardiology")
    queue = _make_queue(db_session, day, specialist_id=doctor.id)
    entry = _make_entry(db_session, queue, 5, patient_name="SYNTHETIC-Petrov Ivan")
    board = _make_board(db_session, "main_board", show_patient_names="full")

    ws = _FakeBoardSocket()
    pubsub = _StubPubSub()
    # Seed the privacy cache so the manager needs no DB while proving the
    # targeting contract (delivery semantics are separate tests below).
    mgr = _real_manager(pubsub, {"main_board": [ws]}, {"main_board": "full"})
    service = DisplayWebSocketApiService(db_session, manager_provider=lambda: mgr)

    result = await service.call_patient(
        entry_id=entry.id, board_ids=[board.id], current_user=user
    )

    # The one live room received the event (pre-fix: int 1 addressed a
    # phantom room and no socket ever saw the event).
    assert len(ws.messages) == 1
    assert ws.messages[0]["type"] == "patient_call"
    # ...and the response reports the real room key, not the raw id.
    assert result["board_delivery"] == {"main_board": "delivered_local"}
    assert result["boards_notified"] == 1
    assert result["display_delivery"] == "delivered"
    assert result["boards_requested"] == 1
    db_session.refresh(entry)
    assert entry.status == "called"


@pytest.mark.asyncio
async def test_call_unresolvable_ids_reported_no_all_rooms_fallback(db_session):
    """An explicit board_ids request that resolves to no board must be
    reported, must NOT silently fall back to broadcasting on every live
    room, and the queue transition still commits honestly."""
    from datetime import UTC, datetime

    day = datetime.now(UTC).date()
    user = _make_user(db_session, "target_admin_2")
    doctor = _make_doctor(db_session, user.id, "cardiology")
    queue = _make_queue(db_session, day, specialist_id=doctor.id)
    entry = _make_entry(db_session, queue, 6)
    _make_board(db_session, "other_board")

    other_ws = _FakeBoardSocket()
    pubsub = _StubPubSub()
    mgr = _real_manager(pubsub, {"other_board": [other_ws]}, {"other_board": "full"})
    service = DisplayWebSocketApiService(db_session, manager_provider=lambda: mgr)

    result = await service.call_patient(
        entry_id=entry.id, board_ids=[9999], current_user=user
    )

    # other_board was never targeted by the operator: zero events there.
    assert other_ws.messages == []
    # The unresolvable id is reported, delivery is honestly failed, and
    # the committed transition is preserved explicitly.
    assert result["unknown_board_ids"] == [9999]
    assert result["display_delivery"] == "failed"
    assert result["boards_notified"] == 0
    assert result["call_committed"] is True
    db_session.refresh(entry)
    assert entry.status == "called"


# ---------------------------------------------------------------------------
# DISPLAYDELIVERY-BE-001 — truthful transport outcome reporting
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_call_transport_failure_reported_not_swallowed(db_session):
    """When the broadcaster raises, the response may not claim
    boards_notified>0; the delivery verdict is failed while the queue
    transition stays committed."""
    from datetime import UTC, datetime

    day = datetime.now(UTC).date()
    user = _make_user(db_session, "target_admin_3")
    doctor = _make_doctor(db_session, user.id, "cardiology")
    queue = _make_queue(db_session, day, specialist_id=doctor.id)
    entry = _make_entry(db_session, queue, 7)
    board = _make_board(db_session, "main_board")

    ws = _FakeBoardSocket()
    pubsub = _StubPubSub(fail_channels={"board:main_board"})
    mgr = _real_manager(pubsub, {"main_board": [ws]}, {"main_board": "full"})
    service = DisplayWebSocketApiService(db_session, manager_provider=lambda: mgr)

    result = await service.call_patient(
        entry_id=entry.id, board_ids=[board.id], current_user=user
    )

    assert result["display_delivery"] == "failed"
    assert result["boards_notified"] == 0
    assert result["board_delivery"] == {"main_board": "failed"}
    # The canonical transition is preserved, never rolled back.
    assert result["call_committed"] is True
    assert result["success"] is True
    db_session.refresh(entry)
    assert entry.status == "called"
    assert entry.called_at is not None


@pytest.mark.asyncio
async def test_call_partial_delivery_mixed_rooms(db_session):
    """One board delivered, one failed → partial verdict; boards_notified
    counts only the delivered board."""
    from datetime import UTC, datetime

    day = datetime.now(UTC).date()
    user = _make_user(db_session, "target_admin_4")
    doctor = _make_doctor(db_session, user.id, "cardiology")
    queue = _make_queue(db_session, day, specialist_id=doctor.id)
    entry = _make_entry(db_session, queue, 8)
    main = _make_board(db_session, "main_board")
    back = _make_board(db_session, "back_board")

    main_ws = _FakeBoardSocket()
    back_ws = _FakeBoardSocket()
    pubsub = _StubPubSub(fail_channels={"board:back_board"})
    mgr = _real_manager(
        pubsub,
        {"main_board": [main_ws], "back_board": [back_ws]},
        {"main_board": "full", "back_board": "full"},
    )
    service = DisplayWebSocketApiService(db_session, manager_provider=lambda: mgr)

    result = await service.call_patient(
        entry_id=entry.id, board_ids=[main.id, back.id], current_user=user
    )

    assert result["board_delivery"] == {
        "main_board": "delivered_local",
        "back_board": "failed",
    }
    assert result["display_delivery"] == "partial"
    assert result["boards_notified"] == 1
    assert result["boards_requested"] == 2


@pytest.mark.asyncio
async def test_call_published_only_reports_unknown(db_session):
    """A resolvable board with no local socket is published for other
    workers only: honest verdict is unknown, never a delivered claim."""
    from datetime import UTC, datetime

    day = datetime.now(UTC).date()
    user = _make_user(db_session, "target_admin_5")
    doctor = _make_doctor(db_session, user.id, "cardiology")
    queue = _make_queue(db_session, day, specialist_id=doctor.id)
    entry = _make_entry(db_session, queue, 9)
    main = _make_board(db_session, "main_board")
    back = _make_board(db_session, "back_board")

    main_ws = _FakeBoardSocket()
    pubsub = _StubPubSub()
    # back_board has a DB row but no connected socket on this worker.
    mgr = _real_manager(pubsub, {"main_board": [main_ws]}, {"main_board": "full"})
    service = DisplayWebSocketApiService(db_session, manager_provider=lambda: mgr)

    result = await service.call_patient(
        entry_id=entry.id, board_ids=[main.id, back.id], current_user=user
    )

    assert result["board_delivery"] == {
        "main_board": "delivered_local",
        "back_board": "published_only",
    }
    assert result["display_delivery"] == "unknown"
    assert result["boards_notified"] == 1


@pytest.mark.asyncio
async def test_call_broadcast_all_with_no_connections_reports_unknown(db_session):
    """board_ids=[] broadcasts to all rooms; with zero live rooms the
    response is honestly unknown, not a fake success count."""
    from datetime import UTC, datetime

    day = datetime.now(UTC).date()
    user = _make_user(db_session, "target_admin_6")
    doctor = _make_doctor(db_session, user.id, "cardiology")
    queue = _make_queue(db_session, day, specialist_id=doctor.id)
    entry = _make_entry(db_session, queue, 10)

    pubsub = _StubPubSub()
    mgr = _real_manager(pubsub, rooms={})
    service = DisplayWebSocketApiService(db_session, manager_provider=lambda: mgr)

    result = await service.call_patient(
        entry_id=entry.id, board_ids=[], current_user=user
    )

    assert result["boards_notified"] == 0
    assert result["display_delivery"] == "unknown"
    assert result["call_committed"] is True


@pytest.mark.asyncio
async def test_broadcast_to_board_status_contract():
    """Direct transport statuses: delivered_local / published_only /
    failed (pre-fix the function swallowed everything and returned None)."""
    ws = _FakeBoardSocket()
    pubsub = _StubPubSub(fail_channels={"board:back_board"})
    mgr = _real_manager(pubsub, {"main_board": [ws]}, {"main_board": "full"})

    ok = await mgr.broadcast_to_board("main_board", {"type": "ping"})
    remote_only = await mgr.broadcast_to_board("ghost_board", {"type": "ping"})
    failing = await mgr.broadcast_to_board("back_board", {"type": "ping"})

    assert ok == "delivered_local"
    assert remote_only == "published_only"
    assert failing == "failed"
    assert len(ws.messages) == 1


# ---------------------------------------------------------------------------
# DISPLAYTARGET/DELIVERY — announcement endpoint plane
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_announcement_int_board_ids_reach_string_named_room(
    db_session, monkeypatch
):
    """POST /display/announcement with board_ids=[id] must deliver to the
    board's NAME-keyed WS room."""
    from datetime import UTC, datetime

    from app.api.v1.endpoints import display_websocket as endpoints_module

    day = datetime.now(UTC).date()
    user = _make_user(db_session, "target_admin_7")
    board = _make_board(db_session, "main_board")

    ws = _FakeBoardSocket()
    pubsub = _StubPubSub()
    mgr = _real_manager(pubsub, {"main_board": [ws]})
    monkeypatch.setattr(
        endpoints_module, "get_display_manager", lambda: mgr, raising=True
    )

    request = AnnouncementRequest(text="SYNTHETIC-ANNOUNCEMENT", board_ids=[board.id])
    result = await endpoints_module.send_announcement_to_board(
        request=request, db=db_session, current_user=user
    )

    assert len(ws.messages) == 1
    assert ws.messages[0]["type"] == "announcement"
    assert ws.messages[0]["data"]["text"] == "SYNTHETIC-ANNOUNCEMENT"
    assert result["board_delivery"] == {"main_board": "delivered_local"}
    assert result["boards_notified"] == 1
    assert result["display_delivery"] == "delivered"
    assert result["boards_requested"] == 1


@pytest.mark.asyncio
async def test_announcement_transport_failure_reported(db_session, monkeypatch):
    """A failed announcement broadcast is reported as failed delivery —
    never an unconditional 'sent' success message."""
    from datetime import UTC, datetime

    from app.api.v1.endpoints import display_websocket as endpoints_module

    day = datetime.now(UTC).date()
    user = _make_user(db_session, "target_admin_8")
    board = _make_board(db_session, "main_board")

    ws = _FakeBoardSocket()
    pubsub = _StubPubSub(fail_channels={"board:main_board"})
    mgr = _real_manager(pubsub, {"main_board": [ws]})
    monkeypatch.setattr(
        endpoints_module, "get_display_manager", lambda: mgr, raising=True
    )

    request = AnnouncementRequest(text="SYNTHETIC-ANNOUNCEMENT-2", board_ids=[board.id])
    result = await endpoints_module.send_announcement_to_board(
        request=request, db=db_session, current_user=user
    )

    assert result["display_delivery"] == "failed"
    assert result["boards_notified"] == 0
    assert result["announcement_accepted"] is True
    # The message must not claim the announcement was already sent.
    assert "отправлено" not in result["message"].lower()


@pytest.mark.asyncio
async def test_announcement_unresolvable_ids_no_all_rooms_fallback(
    db_session, monkeypatch
):
    """An explicit announcement target that resolves to no board is
    reported; live boards are not silently addressed instead."""
    from datetime import UTC, datetime

    from app.api.v1.endpoints import display_websocket as endpoints_module

    day = datetime.now(UTC).date()
    user = _make_user(db_session, "target_admin_9")
    _make_board(db_session, "other_board")

    other_ws = _FakeBoardSocket()
    pubsub = _StubPubSub()
    mgr = _real_manager(pubsub, {"other_board": [other_ws]})
    monkeypatch.setattr(
        endpoints_module, "get_display_manager", lambda: mgr, raising=True
    )

    request = AnnouncementRequest(text="SYNTHETIC-ANNOUNCEMENT-3", board_ids=[9999])
    result = await endpoints_module.send_announcement_to_board(
        request=request, db=db_session, current_user=user
    )

    assert other_ws.messages == []
    assert result["unknown_board_ids"] == [9999]
    assert result["display_delivery"] == "failed"
    assert result["boards_notified"] == 0


# ---------------------------------------------------------------------------
# DISPLAYPRIVACY-BE-002 — fail-closed name masking
# ---------------------------------------------------------------------------


class _RaisingSessionLocal:
    """SessionLocal double that always fails (resolver outage)."""

    def __init__(self, *args, **kwargs):
        raise RuntimeError("SYNTHETIC resolver outage")


class _FakeResolverSession:
    """Session double whose query().filter().first() returns a canned row."""

    def __init__(self, first_row=None):
        self._first_row = first_row
        self.closed = False

    def query(self, *a, **kw):
        return self

    def filter(self, *a, **kw):
        return self

    def first(self):
        return self._first_row

    def close(self):
        self.closed = True


def test_resolve_name_format_fails_closed_on_resolver_error(monkeypatch):
    """A resolver outage must mask names ('none'), never degrade to
    initials; the failure is not cached."""
    monkeypatch.setattr(
        display_ws_service, "SessionLocal", _RaisingSessionLocal, raising=True
    )
    mgr = _real_manager(_StubPubSub(), rooms={})

    assert mgr._resolve_name_format(["main_board"]) == "none"
    assert "main_board" not in mgr._name_format_cache


def test_resolve_name_format_unknown_board_fails_closed(monkeypatch):
    """A board with no DB row must mask names ('none'), not initials."""
    monkeypatch.setattr(
        display_ws_service,
        "SessionLocal",
        lambda: _FakeResolverSession(first_row=None),
        raising=True,
    )
    mgr = _real_manager(_StubPubSub(), rooms={})

    assert mgr._resolve_name_format(["ghost_board"]) == "none"
    assert "ghost_board" not in mgr._name_format_cache


def test_resolve_name_format_invalid_value_fails_closed(monkeypatch):
    """A row whose stored value is not full/initials/none masks the name."""
    monkeypatch.setattr(
        display_ws_service,
        "SessionLocal",
        lambda: _FakeResolverSession(
            first_row=SimpleNamespace(show_patient_names="bogus")
        ),
        raising=True,
    )
    mgr = _real_manager(_StubPubSub(), rooms={})

    assert mgr._resolve_name_format(["sick_board"]) == "none"
    assert "sick_board" not in mgr._name_format_cache


def test_resolve_name_format_no_targets_fails_closed():
    """No target boards and no live connections mask the name ('none')."""
    mgr = _real_manager(_StubPubSub(), rooms={})

    assert mgr._resolve_name_format(None) == "none"


def test_resolve_name_format_valid_rows_cache_and_strict_priority(monkeypatch):
    """Valid rows resolve and cache with the strict none ⊂ initials ⊂ full
    priority preserved."""
    rows = {
        "board_a": SimpleNamespace(show_patient_names="full"),
        "board_b": SimpleNamespace(show_patient_names="initials"),
        "board_c": SimpleNamespace(show_patient_names="none"),
    }

    class _NameInspectQuery:
        def __init__(self, session):
            self._session = session

        def filter(self, *criteria, **kw):
            board_name = None
            for c in criteria:
                # DisplayBoard.name == b → BindParameter; read the literal.
                value = getattr(getattr(c, "right", None), "value", None)
                if isinstance(value, str):
                    board_name = value
            self._session._last_board = board_name
            return self

        def first(self):
            return rows.get(self._session._last_board)

    class _NameInspectSession(_FakeResolverSession):
        def query(self, *a, **kw):
            return _NameInspectQuery(self)

    monkeypatch.setattr(
        display_ws_service, "SessionLocal", lambda: _NameInspectSession(), raising=True
    )
    mgr = _real_manager(_StubPubSub(), rooms={})

    assert mgr._resolve_name_format(["board_a", "board_b"]) == "initials"
    assert mgr._resolve_name_format(["board_a", "board_c"]) == "none"
    assert mgr._resolve_name_format(["board_a"]) == "full"
    assert mgr._name_format_cache == {
        "board_a": "full",
        "board_b": "initials",
        "board_c": "none",
    }


def test_patient_call_message_masks_when_resolution_fails(monkeypatch):
    """End-to-end privacy proof: a resolver outage on the call path masks
    the patient name in the broadcast payload itself."""
    monkeypatch.setattr(
        display_ws_service, "SessionLocal", _RaisingSessionLocal, raising=True
    )
    mgr = _real_manager(_StubPubSub(), rooms={})
    entry = SimpleNamespace(
        id=1,
        number=3,
        patient_name="SYNTHETIC-Petrov Ivan",
        called_at=None,
        queue=SimpleNamespace(specialist=SimpleNamespace(specialty="cardiology")),
    )

    message = mgr.build_patient_call_message(entry, "Dr X", "10", board_ids=["main_board"])
    assert message["data"]["patient_name"] == "Пациент"
