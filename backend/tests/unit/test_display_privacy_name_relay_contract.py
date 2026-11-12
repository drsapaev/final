"""Contract tests — display privacy/name/relay residual plane (audit PR #3961).

Findings covered (docs/audits/2026-11-09-queue-position-notifications-
source-review.md, Draft PR #3961):

- DISPLAYPRIVACY-BE-001 (P1 conditional): the per-board name-format cache is
  never invalidated when an admin successfully downgrades
  ``DisplayBoard.show_patient_names`` on a live board — the stale ``full``
  entry keeps disclosing patient names until the process restarts. The fix
  adds an explicit invalidation primitive (local pop + a cross-worker
  control message on the ``nameformat_ctl`` Redis channel) that the admin
  board-update path must invoke.
- DISPLAYNAME-BE-001 (P2): ``_format_patient_name(..., 'initials')``
  returns a ONE-token name verbatim — a patient recorded with a single
  name token is fully disclosed on a board configured to show initials
  only. The one-token case must mask to its first letter.
- DISPLAYRELAY-BE-001 (P1/P2 conditional): un-targeted call/announcement
  (``board_ids=None`` — the operator left the target selector empty)
  resolves the target set to the calling worker's LOCAL WebSocket rooms;
  if every kiosk sits on another uvicorn worker, zero publishes occur and
  no board sees the event. The un-targeted target set must come from the
  ``DisplayBoard`` registry (DB rows — reachable cross-worker via the
  per-board Redis publish), merged with the local rooms.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from sqlalchemy.orm import Session

from app.models.clinic import Doctor
from app.models.online_queue import DailyQueue, OnlineQueueEntry
from app.models.user import User
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


# ---------------------------------------------------------------------------
# Transport doubles: real manager, stubbed pubsub bridge, fake board sockets
# ---------------------------------------------------------------------------


class _FakeBoardSocket:
    def __init__(self) -> None:
        self.messages: list[dict] = []

    async def send_text(self, text: str) -> None:
        self.messages.append(json.loads(text))


class _StubPubSub:
    """RedisPubSubBridge double: records publishes and subscriptions."""

    def __init__(self) -> None:
        self.published: list[tuple[str, dict]] = []
        self.subscriptions: dict[str, object] = {}

    async def publish(self, channel: str, message: dict) -> None:
        self.published.append((channel, message))

    async def publish_ephemeral(self, channel: str, message: dict) -> None:
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


class _RaisingSessionLocal:
    """SessionLocal double that always fails (registry/resolver outage)."""

    def __init__(self, *args, **kwargs):
        raise RuntimeError("SYNTHETIC registry outage")


class _RegistryQuery:
    """Query double for the synthetic registry session.

    - ``first()`` answers the per-board name-format resolver
      (``query(DisplayBoard).filter(DisplayBoard.name == b).first()``).
    - ``all()`` answers the un-targeted board-registry listing
      (``query(DisplayBoard.name).all()``) with one tuple per row.
    """

    def __init__(self, session: _RegistrySession) -> None:
        self._session = session
        self._name: str | None = None

    def filter(self, *criteria, **kw):
        for c in criteria:
            value = getattr(getattr(c, "right", None), "value", None)
            if isinstance(value, str):
                self._name = value
        return self

    def first(self):
        if self._name is None:
            return None
        stored = self._session.boards.get(self._name)
        if stored is None:
            return None
        return SimpleNamespace(name=self._name, show_patient_names=stored)

    def all(self):
        return [(name,) for name in self._session.boards]


class _RegistrySession:
    """SessionLocal double backed by a synthetic DisplayBoard row table."""

    def __init__(self, boards: dict[str, str]) -> None:
        # {board_name: show_patient_names}; the test mutates this mapping to
        # simulate an admin settings update between broadcasts.
        self.boards = boards
        self.closed = False

    def query(self, *a, **kw):
        return _RegistryQuery(self)

    def close(self):
        self.closed = True


# ---------------------------------------------------------------------------
# DISPLAYPRIVACY-BE-001 — admin downgrade must invalidate the format cache
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_admin_downgrade_invalidates_cached_full(monkeypatch):
    """A cached 'full' entry must be invalidated by the explicit
    invalidate call so the downgrade re-reads the (now masked) policy.
    Pre-fix the manager had no invalidation primitive at all."""
    boards = {"main_board": "full"}
    monkeypatch.setattr(
        display_ws_service,
        "SessionLocal",
        lambda: _RegistrySession(boards),
        raising=True,
    )
    mgr = _real_manager(_StubPubSub(), rooms={})

    # First resolve caches the row value.
    assert mgr._resolve_name_format(["main_board"]) == "full"
    assert mgr._name_format_cache["main_board"] == "full"

    # Admin downgrades the board privacy setting.
    boards["main_board"] = "none"

    # The invalidation primitive clears the stale entry synchronously.
    mgr.invalidate_name_format_cache("main_board")
    assert "main_board" not in mgr._name_format_cache

    # The next resolve re-reads the downgraded policy.
    assert mgr._resolve_name_format(["main_board"]) == "none"


@pytest.mark.asyncio
async def test_invalidate_publishes_cross_worker_control_message():
    """The invalidation primitive publishes a nameformat_invalidate control
    message so OTHER workers drop their stale cache entry too (the cache is
    per-process; the admin PUT and the next call POST may land on different
    uvicorn workers)."""
    pubsub = _StubPubSub()
    mgr = _real_manager(pubsub, rooms={}, cache={"main_board": "full"})

    await mgr._publish_nameformat_invalidation("main_board")

    control = [
        (ch, msg)
        for ch, msg in pubsub.published
        if ch == "nameformat_ctl"
        and msg.get("type") == "nameformat_invalidate"
        and msg.get("board_name") == "main_board"
    ]
    assert control, "no cross-worker nameformat_invalidate control message published"


@pytest.mark.asyncio
async def test_control_message_handler_pops_stale_entry_cross_worker():
    """A worker that receives the control message drops its stale cache
    entry (this is how the worker running the next call POST learns about
    the admin downgrade done on another worker)."""
    pubsub = _StubPubSub()
    mgr = _real_manager(pubsub, rooms={}, cache={"main_board": "full"})

    # The broadcast/connect plane ensures the control subscription.
    await mgr._ensure_nameformat_ctl_subscription()
    handler = pubsub.subscriptions.get("nameformat_ctl")
    assert handler is not None, "manager did not subscribe the control channel"

    await handler({"type": "nameformat_invalidate", "board_name": "main_board"})
    assert "main_board" not in mgr._name_format_cache


@pytest.mark.asyncio
async def test_invalidate_without_board_name_clears_whole_cache():
    """A board-name-less invalidation (delete/unknown-target sweep) clears
    every cached entry conservatively."""
    pubsub = _StubPubSub()
    mgr = _real_manager(pubsub, rooms={}, cache={"a": "full", "b": "initials"})

    mgr.invalidate_name_format_cache(None)
    assert mgr._name_format_cache == {}


# ---------------------------------------------------------------------------
# DISPLAYNAME-BE-001 — a one-token name may not be disclosed by 'initials'
# ---------------------------------------------------------------------------


def test_one_token_name_masked_under_initials():
    """'initials' on a single-token name must not return it verbatim."""
    mgr = _real_manager(_StubPubSub(), rooms={})
    assert mgr._format_patient_name("Айгуль", "initials") == "А."


def test_two_token_initials_regression_guard():
    """The two-token initials contract is unchanged."""
    mgr = _real_manager(_StubPubSub(), rooms={})
    assert (
        mgr._format_patient_name("SYNTHETIC-Petrov Ivan", "initials")
        == "SYNTHETIC-Petrov I."
    )


def test_one_token_full_stays_verbatim_and_none_masks():
    """'full' and 'none' are untouched by the one-token masking."""
    mgr = _real_manager(_StubPubSub(), rooms={})
    assert mgr._format_patient_name("Айгуль", "full") == "Айгуль"
    assert mgr._format_patient_name("Айгуль", "none") == "Пациент"
    assert mgr._format_patient_name("", "initials") == "Пациент"


# ---------------------------------------------------------------------------
# DISPLAYRELAY-BE-001 — un-targeted broadcast reaches registry boards
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_untargeted_call_reaches_db_board_on_other_worker(
    db_session, monkeypatch
):
    """board_ids=[] with ZERO local rooms must still publish the patient
    call for the registry board (kiosks connected to another worker receive
    it via the per-board Redis channel). Pre-fix: no publish at all."""
    day = datetime.now(UTC).date()
    user = _make_user(db_session, "relay_admin_1")
    doctor = _make_doctor(db_session, user.id, "cardiology")
    queue = _make_queue(db_session, day, specialist_id=doctor.id)
    entry = _make_entry(db_session, queue, 5, patient_name="SYNTHETIC-Petrov Ivan")

    monkeypatch.setattr(
        display_ws_service,
        "SessionLocal",
        lambda: _RegistrySession({"main_board": "full"}),
        raising=True,
    )
    pubsub = _StubPubSub()
    # The calling worker has no kiosks at all — they all sit elsewhere.
    mgr = _real_manager(pubsub, rooms={})
    service = DisplayWebSocketApiService(db_session, manager_provider=lambda: mgr)

    result = await service.call_patient(
        entry_id=entry.id,
        board_ids=[],
        current_user=user,
    )

    channels = [ch for ch, _msg in pubsub.published]
    assert (
        "board:main_board" in channels
    ), f"un-targeted call never published to the registry board: {channels}"
    assert result["board_delivery"] == {"main_board": "published_only"}
    db_session.refresh(entry)
    assert entry.status == "called"


@pytest.mark.asyncio
async def test_untargeted_announcement_reaches_db_board_on_other_worker(
    monkeypatch,
):
    """board_ids=None announcement with no local rooms must publish for the
    registry board instead of silently reaching nobody."""
    monkeypatch.setattr(
        display_ws_service,
        "SessionLocal",
        lambda: _RegistrySession({"main_board": "full"}),
        raising=True,
    )
    pubsub = _StubPubSub()
    mgr = _real_manager(pubsub, rooms={})

    statuses = await mgr.broadcast_announcement(
        "SYNTHETIC-ANNOUNCEMENT", board_ids=None
    )

    channels = [ch for ch, _msg in pubsub.published]
    assert (
        "board:main_board" in channels
    ), f"un-targeted announcement never published to the registry board: {channels}"
    assert statuses == {"main_board": "published_only"}


@pytest.mark.asyncio
async def test_untargeted_merges_registry_and_local_rooms_dedup(
    db_session, monkeypatch
):
    """The un-targeted target set is DB registry rows ∪ local rooms,
    deduplicated, so a locally connected board is delivered directly and a
    remote-only board is still published."""
    day = datetime.now(UTC).date()
    user = _make_user(db_session, "relay_admin_2")
    doctor = _make_doctor(db_session, user.id, "cardiology")
    queue = _make_queue(db_session, day, specialist_id=doctor.id)
    entry = _make_entry(db_session, queue, 6, patient_name="SYNTHETIC-Petrov Ivan")

    monkeypatch.setattr(
        display_ws_service,
        "SessionLocal",
        lambda: _RegistrySession({"main_board": "full", "back_board": "full"}),
        raising=True,
    )
    ws = _FakeBoardSocket()
    pubsub = _StubPubSub()
    mgr = _real_manager(pubsub, {"main_board": [ws]}, {"main_board": "full"})
    service = DisplayWebSocketApiService(db_session, manager_provider=lambda: mgr)

    result = await service.call_patient(
        entry_id=entry.id,
        board_ids=[],
        current_user=user,
    )

    assert ws.messages and ws.messages[0]["type"] == "patient_call"
    assert result["board_delivery"] == {
        "main_board": "delivered_local",
        "back_board": "published_only",
    }


@pytest.mark.asyncio
async def test_untargeted_db_outage_falls_back_to_local_rooms(monkeypatch):
    """A registry read failure degrades honestly to the local rooms only
    (best effort) — the broadcast itself must not crash."""
    monkeypatch.setattr(
        display_ws_service, "SessionLocal", _RaisingSessionLocal, raising=True
    )
    ws = _FakeBoardSocket()
    pubsub = _StubPubSub()
    mgr = _real_manager(pubsub, {"local_only": [ws]}, {})

    statuses = await mgr.broadcast_announcement("SYNTHETIC", board_ids=None)

    assert statuses == {"local_only": "delivered_local"}
    assert len(ws.messages) == 1
