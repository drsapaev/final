"""Regression contract — the call-notification cooldown guards only the
manual resend intent and is recorded only by a truthful delivery.

Post-merge review of PR #4013 (QPOSCALL-BE-001 follow-up): the first fix
placed the anti-duplicate timestamp into the shared canonical call service
BEFORE the delivery attempt. Consequences on that pre-fix source:

  1. A first attempt that never delivered (``sent=False`` — no user, no
     channel) or that raised still started the 60s window, so a retry —
     manual resend AND the canonical post-transition call — was answered
     ``{success: True, sent: False, reason: duplicate_suppressed}`` without
     any delivery attempt. A patient could be left without the only call
     notification.
  2. The suppression applied to ALL callers of
     ``QueuePositionNotificationService.notify_patient_called`` — the
     canonical QR call-next / nurse serving / GraphQL paths included.

Corrected contract (fail-first per the review):

  (a) a failed (no-channel) manual resend does NOT start the cooldown —
      the next attempt actually retries;
  (b) a raised sender error does NOT start the cooldown — the next
      attempt actually retries (and the failure surfaced honestly);
  (c) a manual resend that FOLLOWS a successful delivery may still be
      suppressed within the window (intentional anti-spam);
  (d) canonical transition calls are never suppressed — a true new
      waiting→called cycle always notifies despite any prior send;
  (e) a canonical call after a FAILED manual resend is delivered (the
      failed attempt must not poison the canonical plane);
  (f) the in-process log is bounded: expired keys are evicted on record.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock

import pytest
from fastapi import BackgroundTasks
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
# Synthetic helpers (same shape as test_qposcall_status_guard.py)
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
        code=f"synthetic_resend_{datetime.now(UTC).timestamp()}",
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


def _make_called_entry(
    db: Session, queue: DailyQueue, number: int, username: str
) -> OnlineQueueEntry:
    """A genuinely called ticket whose patient resolves to a user — the
    delivery path reaches the unified sender."""
    user = _make_user(db, username, role="Patient")
    patient = Patient(
        last_name="Синтетика",
        first_name=username,
        user_id=user.id,
        phone="+998000000000",
    )
    db.add(patient)
    db.flush()
    entry = OnlineQueueEntry(
        queue_id=queue.id,
        number=number,
        patient_name=f"Синтетика Тестовый #{number}",
        status="called",
        priority=0,
        queue_time=None,
        created_at=datetime.now(UTC),
        source="desk",
        patient_id=patient.id,
    )
    db.add(entry)
    db.flush()
    return entry


@pytest.fixture(autouse=True)
def _reset_call_log():
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


async def _manual_resend(db_session, entry) -> dict:
    """Drive the manual resend through the real endpoint (the intent switch
    manual_resend=True lives inside the endpoint, not in the tests)."""
    admin = _make_user(db_session, f"resend_admin_{entry.id}")
    request = SendCallNotificationRequest(entry_id=entry.id, cabinet_number="12")
    return await send_call_notification(
        request=request,
        background_tasks=BackgroundTasks(),
        db=db_session,
        current_user=admin,
    )


# ---------------------------------------------------------------------------
# (a) failed manual resend must not start the cooldown
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_no_channel_resend_does_not_start_cooldown(
    db_session, monkeypatch, fake_push
):
    day = datetime.now(UTC).date()
    queue = _make_queue(db_session, day)
    entry = _make_called_entry(db_session, queue, 1, "resend_patient_a")

    # First manual resend: the sender accepts the job but delivers nothing
    # (send_push -> False, no telegram fallback) — the patient got nothing.
    fake_push.return_value = False
    first = await _manual_resend(db_session, entry)
    assert first["sent"] is False

    # Second manual resend: must ACTUALLY retry, not report a suppression.
    second = await _manual_resend(db_session, entry)
    assert fake_push.await_count == 2
    assert second.get("reason") != "duplicate_suppressed"


# ---------------------------------------------------------------------------
# (b) raised sender error must not start the cooldown
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_raised_send_does_not_start_cooldown(db_session, monkeypatch, fake_push):
    day = datetime.now(UTC).date()
    queue = _make_queue(db_session, day)
    entry = _make_called_entry(db_session, queue, 2, "resend_patient_b")

    fake_push.side_effect = RuntimeError("fcm provider down")
    with pytest.raises(RuntimeError):
        await _manual_resend(db_session, entry)

    # Sender recovers — the next manual resend must really retry.
    fake_push.side_effect = None
    fake_push.return_value = True
    result = await _manual_resend(db_session, entry)
    assert result["sent"] is True
    assert fake_push.await_count == 2


# ---------------------------------------------------------------------------
# (c) manual resend after a SUCCESSFUL delivery is still suppressed (control)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_manual_resend_after_success_still_suppressed(
    db_session, monkeypatch, fake_push
):
    day = datetime.now(UTC).date()
    queue = _make_queue(db_session, day)
    entry = _make_called_entry(db_session, queue, 3, "resend_patient_c")

    first = await _manual_resend(db_session, entry)
    assert first["sent"] is True
    fake_push.assert_awaited_once()

    second = await _manual_resend(db_session, entry)
    fake_push.assert_awaited_once()  # exactly one delivery attempt total
    assert second["sent"] is False
    assert second.get("reason") == "duplicate_suppressed"


# ---------------------------------------------------------------------------
# (d) canonical transition calls are never suppressed
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_canonical_calls_are_never_suppressed(
    db_session, monkeypatch, fake_push
):
    day = datetime.now(UTC).date()
    queue = _make_queue(db_session, day)
    entry = _make_called_entry(db_session, queue, 4, "resend_patient_d")

    service = get_queue_position_service(db_session)
    # Two canonical post-transition calls in a row (a re-call after a new
    # waiting→called cycle): BOTH must notify — no in-process suppression.
    first = await service.notify_patient_called(entry, cabinet_number="12")
    second = await service.notify_patient_called(entry, cabinet_number="12")

    assert first["sent"] is True
    assert second["sent"] is True
    assert second.get("reason") != "duplicate_suppressed"
    assert fake_push.await_count == 2


# ---------------------------------------------------------------------------
# (e) a FAILED manual resend must not poison the canonical plane
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_canonical_call_after_failed_resend_is_delivered(
    db_session, monkeypatch, fake_push
):
    day = datetime.now(UTC).date()
    queue = _make_queue(db_session, day)
    entry = _make_called_entry(db_session, queue, 5, "resend_patient_e")

    # Failed manual resend (no channel) — pre-fix source recorded a
    # cooldown for it and then suppressed the canonical call below.
    fake_push.return_value = False
    failed = await _manual_resend(db_session, entry)
    assert failed["sent"] is False

    # The canonical plane (QR/nurse/GraphQL call shape — no manual flag)
    # must deliver despite the failed manual attempt seconds earlier.
    canonical = await get_queue_position_service(db_session).notify_patient_called(
        entry, cabinet_number="12"
    )
    assert canonical["sent"] is True
    assert canonical.get("reason") != "duplicate_suppressed"
    assert fake_push.await_count == 2


# ---------------------------------------------------------------------------
# (f) the in-process log is bounded — expired keys are evicted on record
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_call_log_prunes_expired_keys_on_record(
    db_session, monkeypatch, fake_push
):
    day = datetime.now(UTC).date()
    queue = _make_queue(db_session, day)
    entry = _make_called_entry(db_session, queue, 6, "resend_patient_f")

    log = QueuePositionNotificationService._manual_call_log
    stale_key = 987654321
    log[stale_key] = datetime.now(UTC) - timedelta(
        seconds=QueuePositionNotificationService.MANUAL_CALL_COOLDOWN_SECONDS * 10
    )

    await _manual_resend(db_session, entry)  # successful resend records a key

    assert entry.id in log
    assert stale_key not in log, "expired keys must be evicted (bounded log)"
