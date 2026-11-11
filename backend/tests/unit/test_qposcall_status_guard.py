"""Contract tests — manual call-notification status guard (audit PR #3961).

Finding covered:

- QPOSCALL-BE-001 (P2): ``POST /queue/position/notify/call`` sent a false
  high-priority "Вас вызывают!" message for waiting/no_show/served tickets
  — no queue-state validation. The manual call notification is now an
  auditable RESEND for an already-called ticket only:
    * a waiting/terminal ticket → HTTP 409, ZERO delivery attempts;
    * a genuinely called ticket → one delivered notification, no state
      transition, and an in-process anti-duplicate cooldown suppresses
      immediate repeated resends (honest `sent=False, reason=duplicate_suppressed`);
    * defense-in-depth: the service itself suppresses (logs, honest result)
      any non-called entry passed from other call sites.
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest
from fastapi import BackgroundTasks, HTTPException
from sqlalchemy.orm import Session

from app.api.v1.endpoints.queue_position import (
    SendCallNotificationRequest,
    send_call_notification,
)
from app.models.online_queue import DailyQueue, OnlineQueueEntry, QueueResource
from app.models.patient import Patient
from app.models.user import User
from app.services.queue_position_notifications import (
    QueuePositionNotificationService,
    get_queue_position_service,
)

# ---------------------------------------------------------------------------
# Synthetic helpers
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


def _make_queue(db: Session, day) -> DailyQueue:
    resource = QueueResource(
        code=f"synthetic_call_guard_{datetime.now(UTC).timestamp()}",
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
    status: str,
    patient: Patient | None = None,
) -> OnlineQueueEntry:
    entry = OnlineQueueEntry(
        queue_id=queue.id,
        number=number,
        patient_name=f"Синтетика Тестовый #{number}",
        status=status,
        priority=0,
        queue_time=None,
        created_at=datetime.now(UTC),
        source="desk",
        patient_id=patient.id if patient else None,
    )
    db.add(entry)
    db.flush()
    return entry


def _make_patient_with_user(db: Session, username: str) -> tuple[Patient, User]:
    """Patient linked to a User — the delivery path resolves user_id."""
    user = _make_user(db, username, role="Patient")
    patient = Patient(
        last_name="Синтетика",
        first_name=username,
        user_id=user.id,
        phone="+998000000000",
    )
    db.add(patient)
    db.flush()
    return patient, user


@pytest.fixture(autouse=True)
def _reset_call_log():
    """Anti-duplicate log is class-level; isolate per test (tolerant while
    the attribute does not exist yet — RED state)."""
    log = getattr(QueuePositionNotificationService, "_manual_call_log", None)
    if log is not None:
        log.clear()
    yield
    if log is not None:
        log.clear()


@pytest.fixture
def fake_push(monkeypatch):
    """Stubs the unified sender; returns the AsyncMock to assert calls."""
    push = AsyncMock(return_value=True)
    monkeypatch.setattr(
        "app.services.notifications.notification_sender_service.send_push", push
    )
    monkeypatch.setattr(
        "app.services.notifications.notification_sender_service"
        ".send_patient_telegram_event_notification",
        AsyncMock(return_value=False),
    )
    return push


# ---------------------------------------------------------------------------
# RED cases — QPOSCALL-BE-001
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_manual_call_notification_rejected_for_waiting_ticket(
    db_session, monkeypatch, fake_push
):
    """A waiting ticket must NOT receive the high-priority call message —
    the endpoint answers 409 and no delivery is attempted."""
    day = datetime.now(UTC).date()
    queue = _make_queue(db_session, day)
    entry = _make_entry(db_session, queue, 1, status="waiting")
    user = _make_user(db_session, "call_admin_1")

    request = SendCallNotificationRequest(entry_id=entry.id, cabinet_number="201")
    with pytest.raises(HTTPException) as excinfo:
        await send_call_notification(
            request=request,
            background_tasks=BackgroundTasks(),
            db=db_session,
            current_user=user,
        )
    assert excinfo.value.status_code == 409
    fake_push.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("terminal_status", ["served", "no_show", "cancelled"])
async def test_manual_call_notification_rejected_for_terminal_tickets(
    db_session, monkeypatch, fake_push, terminal_status
):
    """Served/no-show/cancelled tickets must not get a false 'called' push."""
    day = datetime.now(UTC).date()
    queue = _make_queue(db_session, day)
    entry = _make_entry(db_session, queue, 2, status=terminal_status)
    user = _make_user(db_session, f"call_admin_{terminal_status}")

    request = SendCallNotificationRequest(entry_id=entry.id)
    with pytest.raises(HTTPException) as excinfo:
        await send_call_notification(
            request=request,
            background_tasks=BackgroundTasks(),
            db=db_session,
            current_user=user,
        )
    assert excinfo.value.status_code == 409
    fake_push.assert_not_awaited()
    # No state transition happened anywhere.
    db_session.refresh(entry)
    assert entry.status == terminal_status


@pytest.mark.asyncio
async def test_manual_resend_delivers_once_for_called_ticket(
    db_session, monkeypatch, fake_push
):
    """A genuinely called ticket receives exactly one notification and the
    ticket status stays 'called' (no transition, no rollback)."""
    day = datetime.now(UTC).date()
    queue = _make_queue(db_session, day)
    patient, _tg = _make_patient_with_user(db_session, "call_patient_3")
    entry = _make_entry(db_session, queue, 3, status="called", patient=patient)
    user = _make_user(db_session, "call_admin_3")

    request = SendCallNotificationRequest(entry_id=entry.id, cabinet_number="305")
    result = await send_call_notification(
        request=request,
        background_tasks=BackgroundTasks(),
        db=db_session,
        current_user=user,
    )

    fake_push.assert_awaited_once()
    assert result.sent is True
    db_session.refresh(entry)
    assert entry.status == "called"


@pytest.mark.asyncio
async def test_anti_duplicate_cooldown_suppresses_immediate_resend(
    db_session, monkeypatch, fake_push
):
    """A second manual resend for the same ticket within the cooldown window
    is honestly reported as suppressed — the patient is not spammed."""
    day = datetime.now(UTC).date()
    queue = _make_queue(db_session, day)
    patient, _tg = _make_patient_with_user(db_session, "call_patient_4")
    entry = _make_entry(db_session, queue, 4, status="called", patient=patient)
    user = _make_user(db_session, "call_admin_4")

    request = SendCallNotificationRequest(entry_id=entry.id)
    service = get_queue_position_service(db_session)
    first = await service.notify_patient_called(entry, cabinet_number="12")
    assert first["sent"] is True
    fake_push.assert_awaited_once()

    second = await service.notify_patient_called(entry, cabinet_number="12")
    fake_push.assert_awaited_once()  # still exactly ONE delivery attempt
    assert second["sent"] is False
    assert second.get("reason") == "duplicate_suppressed"
    db_session.refresh(entry)
    assert entry.status == "called"


@pytest.mark.asyncio
async def test_service_defense_suppresses_false_call_for_waiting_ticket(
    db_session, monkeypatch, fake_push
):
    """Defense-in-depth for non-endpoint call sites (QR/nurse/graphql): the
    service itself suppresses a false 'called' message for a waiting ticket
    and reports an honest invalid_entry_status result."""
    day = datetime.now(UTC).date()
    queue = _make_queue(db_session, day)
    entry = _make_entry(db_session, queue, 5, status="waiting")

    service = get_queue_position_service(db_session)
    result = await service.notify_patient_called(entry, cabinet_number="1")

    fake_push.assert_not_awaited()
    assert result["sent"] is False
    assert result.get("reason") == "invalid_entry_status"
    db_session.refresh(entry)
    assert entry.status == "waiting"
