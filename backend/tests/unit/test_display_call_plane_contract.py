"""Contract tests — display call/queue-state plane (audit PR #3961).

Findings covered (audit rounds 30, docs/audits/2026-11-09-queue-position-
notifications-source-review.md, Draft PR #3961):

- DISPLAYCALL-BE-001 (P1): the display call command must not resurrect
  served/cancelled/no-show/already-called entries. Only ``waiting`` may
  transition to ``called``; an INACTIVE queue fails closed; every rejection
  is a 409 domain error with the queue row untouched and ZERO broadcasts.
- DISPLAYCALL-BE-002 (P1/P2): display quick-call "next" must follow the
  canonical staff fairness order (priority DESC → coalesce(queue_time,
  created_at) ASC → id ASC — the ``staff_call_next_patient`` selector),
  not the printed ticket number.
- DISPLAYCALL-BE-003 (P1/P2): the waiting→called claim is an atomic
  conditional UPDATE keyed on status='waiting'. A second claim attempt
  against the same entry loses the race, reports a conflict, and never
  emits a second TV broadcast.
- DISPLAYWS-BE-003 (P1/P2): the department queue snapshot returns ONLY the
  requested department's entries — matched through the SSOT mapping
  (doctor specialty axis incl. the dental family spellings + registry
  queue-tag axis) — and an unknown department gets an honest empty state
  instead of every active queue of the day.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.orm import Session

from app.models.clinic import Doctor
from app.models.online_queue import DailyQueue, OnlineQueueEntry, QueueResource
from app.models.user import User
from app.services.display_websocket_api_service import (
    DisplayWebSocketApiDomainError,
    DisplayWebSocketApiService,
)

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


def _make_resource(db: Session, code: str, tag: str) -> QueueResource:
    resource = QueueResource(
        code=code,
        queue_tag=tag,
        display_name=f"Ресурс {tag}",
        active=True,
    )
    db.add(resource)
    db.flush()
    return resource


def _make_queue(
    db: Session,
    day,
    *,
    specialist_id: int | None = None,
    queue_resource_id: int | None = None,
    queue_tag: str | None = None,
    active: bool = True,
) -> DailyQueue:
    queue = DailyQueue(
        day=day,
        specialist_id=specialist_id,
        queue_resource_id=queue_resource_id,
        queue_tag=queue_tag,
        active=active,
    )
    db.add(queue)
    db.flush()
    return queue


def _make_entry(
    db: Session,
    queue: DailyQueue,
    number: int,
    *,
    status: str = "waiting",
    priority: int = 0,
    queue_time: datetime | None = None,
    created_at: datetime | None = None,
    patient_name: str | None = None,
) -> OnlineQueueEntry:
    entry = OnlineQueueEntry(
        queue_id=queue.id,
        number=number,
        patient_name=patient_name or f"Синтетика #{number}",
        status=status,
        priority=priority,
        queue_time=queue_time,
        created_at=created_at or datetime.now(UTC),
        source="desk",
    )
    db.add(entry)
    db.flush()
    return entry


def _service_with_silent_manager(db: Session) -> tuple[DisplayWebSocketApiService, AsyncMock]:
    broadcast = AsyncMock()
    manager = SimpleNamespace(connections=[], broadcast_patient_call=broadcast)
    return DisplayWebSocketApiService(db, manager_provider=lambda: manager), broadcast


def _clinic_day(db: Session):
    return DisplayWebSocketApiService(db)._clinic_today()


# ---------------------------------------------------------------------------
# DISPLAYCALL-BE-001 — no resurrection of terminal/non-waiting entries
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.asyncio
@pytest.mark.parametrize(
    "terminal_status",
    ["called", "in_service", "diagnostics", "served", "incomplete", "no_show", "cancelled"],
)
async def test_display_call_rejects_non_waiting_entry(db_session, terminal_status):
    """DISPLAYCALL-BE-001: a terminal/active-non-waiting entry cannot be
    re-called from the display surface — 409, row untouched, no broadcast."""
    service, broadcast = _service_with_silent_manager(db_session)
    day = _clinic_day(db_session)
    user = _make_user(db_session, "call_plane_admin_1")
    doctor = _make_doctor(db_session, user.id, "cardiology")
    queue = _make_queue(db_session, day, specialist_id=doctor.id, queue_tag="cardiology")
    entry = _make_entry(db_session, queue, number=5, status=terminal_status)

    with pytest.raises(DisplayWebSocketApiDomainError) as exc_info:
        await service.call_patient(
            entry_id=entry.id, board_ids=[], current_user=user
        )

    assert exc_info.value.status_code == 409
    db_session.refresh(entry)
    assert entry.status == terminal_status
    assert entry.called_at is None
    broadcast.assert_not_awaited()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_display_call_rejects_inactive_queue(db_session):
    """DISPLAYCALL-BE-001: a closed (inactive) queue is not callable from
    the display surface even when the entry still says waiting."""
    service, broadcast = _service_with_silent_manager(db_session)
    day = _clinic_day(db_session)
    user = _make_user(db_session, "call_plane_admin_2")
    doctor = _make_doctor(db_session, user.id, "dermatology")
    queue = _make_queue(
        db_session, day, specialist_id=doctor.id, queue_tag="dermatology", active=False
    )
    entry = _make_entry(db_session, queue, number=2)

    with pytest.raises(DisplayWebSocketApiDomainError) as exc_info:
        await service.call_patient(entry_id=entry.id, board_ids=[], current_user=user)

    assert exc_info.value.status_code == 409
    db_session.refresh(entry)
    assert entry.status == "waiting"
    broadcast.assert_not_awaited()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_display_call_happy_path_waiting_to_called_once(db_session):
    """DISPLAYCALL-BE-001 positive control: a legitimate waiting entry on an
    active queue is called exactly once, with operator attribution, and a
    single broadcast."""
    service, broadcast = _service_with_silent_manager(db_session)
    day = _clinic_day(db_session)
    user = _make_user(db_session, "call_plane_admin_3")
    doctor = _make_doctor(db_session, user.id, "cardiology")
    queue = _make_queue(db_session, day, specialist_id=doctor.id, queue_tag="cardiology")
    entry = _make_entry(db_session, queue, number=7)

    result = await service.call_patient(entry_id=entry.id, board_ids=[], current_user=user)

    assert result["success"] is True
    db_session.refresh(entry)
    assert entry.status == "called"
    assert entry.called_at is not None
    assert entry.called_by_user_id == user.id
    broadcast.assert_awaited_once()


# ---------------------------------------------------------------------------
# DISPLAYCALL-BE-002 — fairness order, not ticket-number order
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_display_next_waiting_prefers_priority_over_ticket_number(db_session):
    """DISPLAYCALL-BE-002: a restored priority=1 patient with ticket #12 must
    be called before a later priority=0 ticket #3 (staff fairness SSOT)."""
    day = _clinic_day(db_session)
    user = _make_user(db_session, "call_plane_admin_4")
    doctor = _make_doctor(db_session, user.id, "cardiology")
    queue = _make_queue(db_session, day, specialist_id=doctor.id, queue_tag="cardiology")
    base = datetime.now(UTC) - timedelta(hours=1)
    _make_entry(db_session, queue, number=3, priority=0, queue_time=base)
    restored = _make_entry(
        db_session, queue, number=12, priority=1, queue_time=base + timedelta(minutes=1)
    )

    repo = DisplayWebSocketApiService(db_session).repository
    nxt = repo.get_next_waiting_entry(queue_id=queue.id)

    assert nxt is not None
    assert nxt.id == restored.id


@pytest.mark.unit
def test_display_next_waiting_tie_breaks_by_queue_time_then_id(db_session):
    """DISPLAYCALL-BE-002: equal priority → earlier coalesce(queue_time,
    created_at) wins; a NULL queue_time falls back to created_at."""
    day = _clinic_day(db_session)
    user = _make_user(db_session, "call_plane_admin_5")
    doctor = _make_doctor(db_session, user.id, "cardiology")
    queue = _make_queue(db_session, day, specialist_id=doctor.id, queue_tag="cardiology")
    base = datetime.now(UTC) - timedelta(hours=2)
    early = _make_entry(
        db_session, queue, number=9, priority=0, queue_time=None, created_at=base
    )
    _make_entry(
        db_session,
        queue,
        number=1,
        priority=0,
        queue_time=base + timedelta(minutes=30),
        created_at=base + timedelta(minutes=5),
    )

    repo = DisplayWebSocketApiService(db_session).repository
    nxt = repo.get_next_waiting_entry(queue_id=queue.id)

    assert nxt is not None
    assert nxt.id == early.id


@pytest.mark.unit
@pytest.mark.asyncio
async def test_display_quick_call_calls_priority_entry_not_lowest_ticket(db_session):
    """DISPLAYCALL-BE-002 end-to-end through quick_call_next: the returned
    payload is the priority entry's ticket number; the low-priority one
    stays waiting."""
    service, broadcast = _service_with_silent_manager(db_session)
    day = _clinic_day(db_session)
    user = _make_user(db_session, "call_plane_doctor_6", role="Doctor")
    doctor = _make_doctor(db_session, user.id, "cardiology")
    queue = _make_queue(db_session, day, specialist_id=doctor.id, queue_tag="cardiology")
    base = datetime.now(UTC) - timedelta(hours=1)
    low = _make_entry(db_session, queue, number=3, priority=0, queue_time=base)
    restored = _make_entry(
        db_session, queue, number=12, priority=1, queue_time=base + timedelta(minutes=1)
    )

    result = await service.quick_call_next(
        specialty="cardiology", board_id=None, current_user=user
    )

    assert result["success"] is True
    assert result["call_data"]["number"] == restored.number
    db_session.refresh(restored)
    db_session.refresh(low)
    assert restored.status == "called"
    assert low.status == "waiting"
    broadcast.assert_awaited_once()


# ---------------------------------------------------------------------------
# DISPLAYCALL-BE-003 — atomic at-most-once claim
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_claim_waiting_entry_is_conditional_on_status(db_session):
    """DISPLAYCALL-BE-003: the claim primitive is a conditional UPDATE —
    it succeeds exactly once per waiting entry and returns False for any
    already-transitioned entry."""
    day = _clinic_day(db_session)
    user = _make_user(db_session, "call_plane_admin_7")
    doctor = _make_doctor(db_session, user.id, "cardiology")
    queue = _make_queue(db_session, day, specialist_id=doctor.id, queue_tag="cardiology")
    entry = _make_entry(db_session, queue, number=4)
    repo = DisplayWebSocketApiService(db_session).repository
    now = datetime.now(UTC)

    assert repo.claim_waiting_entry(
        entry, called_at=now, called_by_user_id=user.id
    ) is True
    assert (
        repo.claim_waiting_entry(
            entry, called_at=now, called_by_user_id=user.id
        )
        is False
    )
    db_session.refresh(entry)
    assert entry.status == "called"
    assert entry.called_by_user_id == user.id


@pytest.mark.unit
@pytest.mark.asyncio
async def test_display_call_conflicts_when_entry_claimed_concurrently(db_session):
    """DISPLAYCALL-BE-003: if the row stopped being waiting between selection
    and the write (another operator won the race), the loser gets a 409 and
    emits NO broadcast — no duplicate TV call event."""
    service, broadcast = _service_with_silent_manager(db_session)
    day = _clinic_day(db_session)
    user = _make_user(db_session, "call_plane_admin_8")
    doctor = _make_doctor(db_session, user.id, "cardiology")
    queue = _make_queue(db_session, day, specialist_id=doctor.id, queue_tag="cardiology")
    entry = _make_entry(db_session, queue, number=6)

    real_claim = service.repository.claim_waiting_entry

    def racing_claim(entry, *, called_at, called_by_user_id):
        # Simulate the concurrent winner committing first: by the time the
        # loser's conditional UPDATE runs, the row is no longer waiting.
        entry.status = "called"
        entry.called_at = called_at
        db_session.commit()
        return real_claim(
            entry, called_at=called_at, called_by_user_id=called_by_user_id
        )

    service.repository.claim_waiting_entry = racing_claim

    with pytest.raises(DisplayWebSocketApiDomainError) as exc_info:
        await service.call_patient(entry_id=entry.id, board_ids=[], current_user=user)

    assert exc_info.value.status_code == 409
    broadcast.assert_not_awaited()


# ---------------------------------------------------------------------------
# DISPLAYWS-BE-003 — department snapshot scoping
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_department_snapshot_returns_only_requested_department(db_session):
    """DISPLAYWS-BE-003: /ws/queue/cardiology must not include laboratory
    (or any other department's) patients; totals are scoped to the filter."""
    service, _ = _service_with_silent_manager(db_session)
    day = _clinic_day(db_session)
    user = _make_user(db_session, "call_plane_admin_9")
    cardio_doctor = _make_doctor(db_session, user.id, "cardiology")
    cardio_queue = _make_queue(
        db_session, day, specialist_id=cardio_doctor.id, queue_tag="cardiology"
    )
    cardio_waiting = _make_entry(db_session, cardio_queue, number=1)
    cardio_served = _make_entry(
        db_session, cardio_queue, number=2, status="served"
    )
    lab_resource = _make_resource(db_session, "lab_resource", "lab")
    lab_queue = _make_queue(
        db_session, day, specialist_id=None, queue_resource_id=lab_resource.id, queue_tag="lab"
    )
    lab_entry = _make_entry(db_session, lab_queue, number=9)

    payload = service.get_department_queue_state_payload(department="cardiology")

    ids = [e["id"] for e in payload["entries"]]
    assert cardio_waiting.id in ids
    assert cardio_served.id in ids
    assert lab_entry.id not in ids
    assert payload["department"] == "cardiology"
    assert payload["total_waiting"] == 1
    assert payload["current_number"] == 2

    lab_payload = service.get_department_queue_state_payload(department="lab")
    lab_ids = [e["id"] for e in lab_payload["entries"]]
    assert lab_ids == [lab_entry.id]
    assert lab_payload["total_waiting"] == 1


@pytest.mark.unit
def test_department_snapshot_matches_dental_family_spellings(db_session):
    """DISPLAYWS-BE-003: the requested department resolves through the
    canonical specialty vocabulary — 'stomatology' reaches a doctor stored
    as 'dentistry' (D-1 family expansion)."""
    service, _ = _service_with_silent_manager(db_session)
    day = _clinic_day(db_session)
    user = _make_user(db_session, "call_plane_admin_10")
    dental_doctor = _make_doctor(db_session, user.id, "dentistry")
    dental_queue = _make_queue(
        db_session, day, specialist_id=dental_doctor.id, queue_tag="dentistry"
    )
    dental_entry = _make_entry(db_session, dental_queue, number=3)

    payload = service.get_department_queue_state_payload(department="stomatology")

    ids = [e["id"] for e in payload["entries"]]
    assert dental_entry.id in ids
    assert payload["total_waiting"] == 1


@pytest.mark.unit
def test_department_snapshot_unknown_department_is_honestly_empty(db_session):
    """DISPLAYWS-BE-003: a department that maps to no queue/tag returns an
    empty state — never the whole day's queues under a misleading label."""
    service, _ = _service_with_silent_manager(db_session)
    day = _clinic_day(db_session)
    user = _make_user(db_session, "call_plane_admin_11")
    doctor = _make_doctor(db_session, user.id, "cardiology")
    queue = _make_queue(db_session, day, specialist_id=doctor.id, queue_tag="cardiology")
    _make_entry(db_session, queue, number=1)

    payload = service.get_department_queue_state_payload(department="nonexistent_dept")

    assert payload["entries"] == []
    assert payload["total_waiting"] == 0
    assert payload["current_number"] == 0
