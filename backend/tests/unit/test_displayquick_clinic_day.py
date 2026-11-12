"""Contract tests — quick-call canonical clinic-day selection (audit PR #3961).

Finding covered:

- DISPLAYQUICK-BE-001 (P2): the multi-doctor least-loaded chooser counted
  queue loads for the HOST-local ``date.today()`` while the service's
  queue lookup uses the CLINIC-local day (queue-settings timezone SSOT).
  On a UTC host between 19:00-24:00Z for an Asia/Tashkent clinic the
  chooser saw the previous date: it could elect a doctor whose
  current-clinic-day queue is empty (or missing) and answer 404 /
  queue_empty while a sibling doctor had waiting patients.

Repair direction (per the audit): the repository accepts a canonical
``day`` parameter passed from the service; no timezone hardcoding in the
repository. The ``day=None`` fallback keeps the legacy host-date contract
for old callers.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.orm import Session

from app.models.clinic import Doctor
from app.models.online_queue import DailyQueue, OnlineQueueEntry
from app.models.user import User
from app.repositories import display_websocket_api_repository as repo_module
from app.repositories.display_websocket_api_repository import (
    DisplayWebSocketApiRepository,
)
from app.services.display_websocket_api_service import (
    DisplayWebSocketApiService,
)

HOST_DAY = date(2026, 11, 10)  # host-local (UTC) date in the finding's window
CLINIC_DAY = date(2026, 11, 11)  # Asia/Tashkent clinic-local date (next day)


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


def _make_doctor(db: Session, specialty: str) -> Doctor:
    user = _make_user(
        db,
        f"doc_{specialty}_{datetime.now(UTC).timestamp()}",
        role="Doctor",
    )
    doctor = Doctor(user_id=user.id, specialty=specialty, active=True)
    db.add(doctor)
    db.flush()
    return doctor


def _make_loaded_queue(
    db: Session,
    doctor: Doctor,
    day: date,
    *,
    waiting: int,
    called: int = 0,
) -> DailyQueue:
    queue = DailyQueue(
        day=day,
        specialist_id=doctor.id,
        queue_tag="Стоматология",
        active=True,
    )
    db.add(queue)
    db.flush()
    number = 0
    for _ in range(waiting):
        number += 1
        db.add(
            OnlineQueueEntry(
                queue_id=queue.id,
                number=number,
                patient_name=f"Синтетика Ожидание #{number}",
                status="waiting",
                priority=0,
                queue_time=None,
                created_at=datetime(2026, 11, 11, 9, 0, tzinfo=UTC),
                source="desk",
            )
        )
    for _ in range(called):
        number += 1
        db.add(
            OnlineQueueEntry(
                queue_id=queue.id,
                number=number,
                patient_name=f"Синтетика Вызван #{number}",
                status="called",
                priority=0,
                queue_time=None,
                created_at=datetime(2026, 11, 11, 9, 0, tzinfo=UTC),
                source="desk",
            )
        )
    db.flush()
    return queue


def _freeze_host_date(monkeypatch, fixed: date) -> None:
    """The repository fallback must observe the HOST date; the service is
    expected to override it with the canonical clinic day."""
    monkeypatch.setattr(
        repo_module,
        "date",
        SimpleNamespace(today=staticmethod(lambda: fixed)),
    )


# ---------------------------------------------------------------------------
# DISPLAYQUICK-BE-001 — repository honors the canonical day
# ---------------------------------------------------------------------------


def test_repository_load_counts_only_canonical_day(db_session, monkeypatch):
    """With the canonical day passed, the chooser counts loads on THAT day
    only; the legacy no-day call keeps the host-date fallback."""
    _freeze_host_date(monkeypatch, HOST_DAY)
    doctor_a = _make_doctor(db_session, "dentistry")  # lower id
    doctor_b = _make_doctor(db_session, "dentistry")
    _make_loaded_queue(db_session, doctor_a, HOST_DAY, waiting=1, called=5)
    _make_loaded_queue(db_session, doctor_b, CLINIC_DAY, waiting=2)

    repo = DisplayWebSocketApiRepository(db_session)

    legacy = repo.get_active_doctor_by_specialty("dentistry")
    assert legacy.id == doctor_a.id, "host-date fallback unchanged"

    canonical = repo.get_active_doctor_by_specialty("dentistry", day=CLINIC_DAY)
    assert canonical.id == doctor_b.id, (
        "the chooser must rank by the canonical (clinic) day, not the host date"
    )


# ---------------------------------------------------------------------------
# DISPLAYQUICK-BE-001 — service passes the clinic day (cross-midnight)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_quick_call_selects_by_clinic_day(db_session, monkeypatch):
    """Host 2026-11-10 20:30 UTC / clinic 2026-11-11 01:30: quick-call must
    choose by current clinic-day waiting+called and actually call a waiting
    entry — never answer 404/queue_empty while a sibling has waiting
    patients."""
    _freeze_host_date(monkeypatch, HOST_DAY)
    doctor_a = _make_doctor(db_session, "dentistry")  # lowest id wins the bug
    doctor_b = _make_doctor(db_session, "dentistry")
    queue_b = _make_loaded_queue(db_session, doctor_b, CLINIC_DAY, waiting=2)
    _make_loaded_queue(db_session, doctor_a, HOST_DAY, waiting=1, called=5)

    broadcast = AsyncMock(return_value={})
    manager = SimpleNamespace(broadcast_patient_call=broadcast)
    service = DisplayWebSocketApiService(db_session, manager_provider=lambda: manager)
    # The service resolves the clinic-local day (queue-settings timezone);
    # frozen here to the finding's cross-midnight scenario.
    monkeypatch.setattr(service, "_clinic_today", lambda: CLINIC_DAY)

    result = await service.quick_call_next(
        specialty="dentistry",
        board_id=None,
        current_user=SimpleNamespace(role="Admin"),
    )

    assert result.get("success") is True, result
    assert result.get("queue_empty") is not True
    db_session.refresh(queue_b)
    remaining = (
        db_session.query(OnlineQueueEntry)
        .filter(
            OnlineQueueEntry.queue_id == queue_b.id,
            OnlineQueueEntry.status == "waiting",
        )
        .count()
    )
    called_now = (
        db_session.query(OnlineQueueEntry)
        .filter(
            OnlineQueueEntry.queue_id == queue_b.id,
            OnlineQueueEntry.status == "called",
        )
        .count()
    )
    assert called_now == 1, "one clinic-day entry transitioned to called"
    assert remaining == 1
    broadcast.assert_awaited_once()
