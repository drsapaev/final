from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo

import pytest
from fastapi import HTTPException

from app.api.v1.endpoints.registrar_integration import (
    REGISTRAR_BATCH_ACTIVE_DUPLICATE_STATUSES,
    _find_registrar_batch_existing_entry_or_raise,
)
from app.models.online_queue import DailyQueue, OnlineQueueEntry


def _create_daily_queue(db_session, *, specialist_id: int) -> DailyQueue:
    queue = DailyQueue(
        day=date.today(),
        specialist_id=specialist_id,
        queue_tag=None,
        active=True,
    )
    db_session.add(queue)
    db_session.commit()
    db_session.refresh(queue)
    return queue


def _create_entry(
    db_session,
    *,
    queue_id: int,
    patient_id: int,
    patient_name: str,
    phone: str | None,
    number: int,
    status: str,
) -> OnlineQueueEntry:
    entry = OnlineQueueEntry(
        queue_id=queue_id,
        number=number,
        patient_id=patient_id,
        patient_name=patient_name,
        phone=phone,
        source="online",
        status=status,
        queue_time=datetime.now(ZoneInfo("Asia/Tashkent")).replace(microsecond=0),
    )
    db_session.add(entry)
    db_session.commit()
    db_session.refresh(entry)
    return entry


def test_registrar_batch_duplicate_gate_supports_canonical_active_statuses():
    assert REGISTRAR_BATCH_ACTIVE_DUPLICATE_STATUSES == (
        "waiting",
        "called",
        "in_service",
        "diagnostics",
    )


def test_registrar_batch_duplicate_gate_returns_existing_called_entry(
    db_session,
    test_patient,
    cardio_user,
):
    queue = _create_daily_queue(db_session, specialist_id=cardio_user.id)
    existing_entry = _create_entry(
        db_session,
        queue_id=queue.id,
        patient_id=test_patient.id,
        patient_name=test_patient.short_name(),
        phone=test_patient.phone,
        number=7,
        status="called",
    )

    resolved_entry = _find_registrar_batch_existing_entry_or_raise(
        db_session,
        queue_id=queue.id,
        patient_id=test_patient.id,
    )

    assert resolved_entry is not None
    assert resolved_entry.id == existing_entry.id
    assert resolved_entry.status == "called"


def test_registrar_batch_duplicate_gate_returns_existing_in_service_entry(
    db_session,
    test_patient,
    cardio_user,
):
    queue = _create_daily_queue(db_session, specialist_id=cardio_user.id)
    existing_entry = _create_entry(
        db_session,
        queue_id=queue.id,
        patient_id=test_patient.id,
        patient_name=test_patient.short_name(),
        phone=test_patient.phone,
        number=11,
        status="in_service",
    )

    resolved_entry = _find_registrar_batch_existing_entry_or_raise(
        db_session,
        queue_id=queue.id,
        patient_id=test_patient.id,
    )

    assert resolved_entry is not None
    assert resolved_entry.id == existing_entry.id
    assert resolved_entry.status == "in_service"


def test_registrar_batch_duplicate_gate_returns_none_when_no_active_entry(
    db_session,
    test_patient,
    cardio_user,
):
    queue = _create_daily_queue(db_session, specialist_id=cardio_user.id)

    resolved_entry = _find_registrar_batch_existing_entry_or_raise(
        db_session,
        queue_id=queue.id,
        patient_id=test_patient.id,
    )

    assert resolved_entry is None


def test_registrar_batch_duplicate_gate_raises_409_on_ambiguous_active_rows(
    db_session,
    test_patient,
    cardio_user,
):
    queue = _create_daily_queue(db_session, specialist_id=cardio_user.id)
    _create_entry(
        db_session,
        queue_id=queue.id,
        patient_id=test_patient.id,
        patient_name=test_patient.short_name(),
        phone=test_patient.phone,
        number=3,
        status="waiting",
    )
    _create_entry(
        db_session,
        queue_id=queue.id,
        patient_id=test_patient.id,
        patient_name=test_patient.short_name(),
        phone=test_patient.phone,
        number=4,
        status="diagnostics",
    )

    with pytest.raises(HTTPException) as exc_info:
        _find_registrar_batch_existing_entry_or_raise(
            db_session,
            queue_id=queue.id,
            patient_id=test_patient.id,
        )

    assert exc_info.value.status_code == 409
    assert "Неоднозначная активная запись очереди" in exc_info.value.detail
