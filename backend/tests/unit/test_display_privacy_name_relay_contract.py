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

import asyncio
import json
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from sqlalchemy.orm import Session
from sqlalchemy.sql.elements import False_, True_

from app.models.clinic import Doctor
from app.models.online_queue import DailyQueue, OnlineQueueEntry
from app.models.user import User
from app.services import display_websocket as display_ws_service
from app.services.display_websocket import DisplayWebSocketManager
from app.services.display_websocket_api_service import DisplayWebSocketApiService
from app.services.ws_redis_pubsub import RedisPubSubBridge

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

    async def subscribe(self, channel: str, handler) -> bool:
        self.subscriptions[channel] = handler
        # #4035 review: the double must honour the REAL bridge contract —
        # a truthy result only after a (simulated) successful subscribe;
        # the production method returns bool, never None.
        return True

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
      (``query(DisplayBoard.name).filter(DisplayBoard.active == True).all()``)
      with one tuple per row, honouring the ``active`` criterion.
    """

    def __init__(self, session: _RegistrySession) -> None:
        self._session = session
        self._name: str | None = None
        self._active_only = False

    def filter(self, *criteria, **kw):
        for c in criteria:
            value = getattr(getattr(c, "right", None), "value", None)
            right = getattr(c, "right", None)
            if isinstance(value, str):
                self._name = value
            elif isinstance(right, True_):
                # DisplayBoard.active == True / .is_(True) wraps the literal
                # into sqlalchemy.sql.elements.True_ (no .value attribute).
                self._active_only = True
            elif isinstance(right, False_):
                self._active_only = False
        return self

    def first(self):
        if self._name is None:
            return None
        stored = self._session.boards.get(self._name)
        if stored is None:
            return None
        fmt, _active = self._session.board_row(stored)
        return SimpleNamespace(name=self._name, show_patient_names=fmt)

    def all(self):
        rows = []
        for name, stored in self._session.boards.items():
            _fmt, active = self._session.board_row(stored)
            if self._active_only and not active:
                continue
            rows.append((name,))
        return rows


class _RegistrySession:
    """SessionLocal double backed by a synthetic DisplayBoard row table.

    Row values model the ``active`` column too: a plain string means
    ``(show_patient_names, active=True)``; a ``(fmt, active)`` tuple sets
    the flag explicitly (an inactive/retired board row).
    """

    def __init__(self, boards: dict[str, str | tuple[str, bool]]) -> None:
        # {board_name: show_patient_names}; the test mutates this mapping to
        # simulate an admin settings update between broadcasts.
        self.boards = boards
        self.closed = False

    @staticmethod
    def board_row(stored: str | tuple[str, bool]) -> tuple[str, bool]:
        if isinstance(stored, tuple):
            fmt, active = stored
            return fmt, bool(active)
        return stored, True

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


# ---------------------------------------------------------------------------
# #4035 review residual P1 — a FAILED control subscribe must not leave a
# "phantom" bridge registration that turns the retry into a false success
# ---------------------------------------------------------------------------


class _FakeRedisPubSub:
    """Underlying redis-py pubsub double for the REAL RedisPubSubBridge."""

    def __init__(self) -> None:
        self.subscribe_calls: list[str] = []
        self.unsubscribe_calls: list[str] = []

    async def subscribe(self, channel: str) -> None:
        self.subscribe_calls.append(channel)

    async def unsubscribe(self, channel: str) -> None:
        self.unsubscribe_calls.append(channel)

    async def listen(self):
        return
        yield  # pragma: no cover — the real listener never runs in tests


def _gated_real_bridge(monkeypatch, state: dict):
    """Real RedisPubSubBridge with a synthetic readiness gate.

    ``state['ready']`` toggles what ``_ensure_ready`` answers, so the test
    drives the exact failure→recovery chain the reviewer specified without
    a Redis server.
    """
    bridge = RedisPubSubBridge(
        channel_prefix="display_ws", redis_url="redis://synthetic:6379/0"
    )
    bridge._pubsub = _FakeRedisPubSub()

    async def _gate():
        return state["ready"]

    monkeypatch.setattr(bridge, "_ensure_ready", _gate, raising=True)
    return bridge


@pytest.mark.asyncio
async def test_failed_ctl_subscribe_leaves_no_phantom_and_recovers(monkeypatch):
    """P1 residual of #4035: with Redis not ready the control subscribe
    fails — it must NOT leave the handler registered in the bridge. On
    recovery the retry must perform a REAL underlying Redis SUBSCRIBE
    (exactly one), and only then may the manager cache ``ok=True``.
    Pre-fix: attempt 1 leaves a phantom handler (no rollback), attempt 2
    sees ``was_added=False``, skips the real subscribe branch and returns
    ``True`` — ``_nameformat_ctl_ok=True`` with zero Redis SUBSCRIBE."""
    state = {"ready": False}
    bridge = _gated_real_bridge(monkeypatch, state)
    monkeypatch.setattr(
        display_ws_service,
        "SessionLocal",
        lambda: _RegistrySession({"main_board": "full"}),
        raising=True,
    )
    mgr = _real_manager(bridge, rooms={}, cache={"main_board": "full"})

    # Attempt 1: Redis not ready — honest failure, no phantom registration.
    await mgr._ensure_nameformat_ctl_subscription()
    assert mgr._nameformat_ctl_ok is False
    handlers_after_fail = bridge._handlers.get("nameformat_ctl", set())
    assert (
        not handlers_after_fail
    ), "failed control subscribe left a phantom bridge handler registration"

    # Attempt 2: Redis ready — retry must issue a REAL underlying SUBSCRIBE.
    state["ready"] = True
    await mgr._ensure_nameformat_ctl_subscription()
    assert mgr._nameformat_ctl_ok is True
    real_subs = [
        ch for ch in bridge._pubsub.subscribe_calls if ch.endswith(":nameformat_ctl")
    ]
    assert real_subs == [
        "display_ws:nameformat_ctl"
    ], f"expected exactly one real control-channel SUBSCRIBE, got {real_subs}"

    # A control message delivered through the REAL bridge dispatch path
    # (the listen-loop calls every registered handler) must drop the
    # worker's stale cached 'full'.
    for handler in list(bridge._handlers.get("nameformat_ctl", set())):
        await handler({"type": "nameformat_invalidate", "board_name": "main_board"})
    assert "main_board" not in mgr._name_format_cache


@pytest.mark.asyncio
async def test_failed_ctl_subscribe_undoes_bridge_registration(monkeypatch):
    """P1 residual of #4035 (manager-side guard): even if the bridge does
    NOT roll back its registration on a failed subscribe, the manager must
    explicitly undo it — otherwise the retry's ``was_added=False`` skips
    the real SUBSCRIBE forever. The stub models the pre-fix bridge bug."""
    monkeypatch.setattr(
        display_ws_service,
        "SessionLocal",
        lambda: _RegistrySession({"main_board": "full"}),
        raising=True,
    )

    class _FailKeepsHandler(_StubPubSub):
        """Bridge double with the pre-fix bug: keeps the handler on False."""

        def __init__(self) -> None:
            super().__init__()
            self.ready = False

        async def subscribe(self, channel, handler):
            self.subscriptions[channel] = handler
            return self.ready

    stub = _FailKeepsHandler()
    mgr = _real_manager(stub, rooms={}, cache={"main_board": "full"})

    await mgr._ensure_nameformat_ctl_subscription()
    assert mgr._nameformat_ctl_ok is False
    assert (
        "nameformat_ctl" not in stub.subscriptions
    ), "failed subscribe left a phantom handler registration in the bridge"

    stub.ready = True
    await mgr._ensure_nameformat_ctl_subscription()
    assert mgr._nameformat_ctl_ok is True
    assert (
        stub.subscriptions.get("nameformat_ctl") is mgr._nameformat_ctl_handler
    ), "recovered retry did not (re)register the control handler"


@pytest.mark.asyncio
async def test_concurrent_ctl_subscription_issues_single_real_subscribe(monkeypatch):
    """Concurrent first connects all ensure the control subscription, but
    exactly ONE real underlying Redis SUBSCRIBE must be issued."""
    state = {"ready": True}
    bridge = _gated_real_bridge(monkeypatch, state)
    mgr = _real_manager(bridge, rooms={}, cache={})

    await asyncio.gather(*(mgr._ensure_nameformat_ctl_subscription() for _ in range(8)))

    assert mgr._nameformat_ctl_ok is True
    real_subs = [
        ch for ch in bridge._pubsub.subscribe_calls if ch.endswith(":nameformat_ctl")
    ]
    assert len(real_subs) == 1, f"expected one real SUBSCRIBE, got {real_subs}"


# ---------------------------------------------------------------------------
# #4035 review residual P2 — un-targeted fan-out must exclude INACTIVE
# DisplayBoard rows (registry and locally-connected alike)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_untargeted_call_excludes_inactive_boards(db_session, monkeypatch):
    """board_ids=None targets only ACTIVE registry boards: a retired board
    (active=False) with a live local socket gets no un-targeted publish and
    its 'none' policy must not force unrelated active boards to mask names."""
    day = datetime.now(UTC).date()
    user = _make_user(db_session, "relay_admin_3")
    doctor = _make_doctor(db_session, user.id, "cardiology")
    queue = _make_queue(db_session, day, specialist_id=doctor.id)
    entry = _make_entry(db_session, queue, 7, patient_name="SYNTHETIC-Ivanov Petro")

    monkeypatch.setattr(
        display_ws_service,
        "SessionLocal",
        lambda: _RegistrySession(
            {"main_board": "full", "retired_board": ("none", False)}
        ),
        raising=True,
    )
    retired_ws = _FakeBoardSocket()
    pubsub = _StubPubSub()
    mgr = _real_manager(pubsub, {"main_board": [], "retired_board": [retired_ws]}, {})
    service = DisplayWebSocketApiService(db_session, manager_provider=lambda: mgr)

    result = await service.call_patient(
        entry_id=entry.id,
        board_ids=[],
        current_user=user,
    )

    channels = [ch for ch, _msg in pubsub.published]
    assert (
        "board:retired_board" not in channels
    ), f"inactive board received an un-targeted publish: {channels}"
    assert "board:main_board" in channels
    assert "retired_board" not in result["board_delivery"]
    assert retired_ws.messages == [], "inactive board got a local delivery"

    main_payloads = [m for ch, m in pubsub.published if ch == "board:main_board"]
    assert main_payloads, "no call payload published for the active board"
    patient_name = main_payloads[0]["data"]["patient_name"]
    assert patient_name == "SYNTHETIC-Ivanov Petro", (
        f"inactive board's 'none' policy leaked into the strictest-format "
        f"aggregation: patient_name={patient_name!r}"
    )


@pytest.mark.asyncio
async def test_untargeted_announcement_excludes_inactive_boards(monkeypatch):
    """Announcement variant: the retired board is absent from the target
    set and from the delivery verdicts."""
    monkeypatch.setattr(
        display_ws_service,
        "SessionLocal",
        lambda: _RegistrySession(
            {"main_board": "full", "retired_board": ("none", False)}
        ),
        raising=True,
    )
    retired_ws = _FakeBoardSocket()
    pubsub = _StubPubSub()
    mgr = _real_manager(pubsub, {"retired_board": [retired_ws]}, {})

    statuses = await mgr.broadcast_announcement("SYNTHETIC", board_ids=None)

    assert statuses == {"main_board": "published_only"}, statuses
    channels = [ch for ch, _msg in pubsub.published]
    assert "board:retired_board" not in channels
    assert retired_ws.messages == []
