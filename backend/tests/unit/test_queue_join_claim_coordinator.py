from __future__ import annotations

from datetime import date, datetime
from types import SimpleNamespace
from unittest.mock import Mock
from zoneinfo import ZoneInfo

import pytest

from app.models.online_queue import DailyQueue, OnlineQueueEntry
from app.services.queue_service import (
    QueueBusinessService,
    QueueConflictError,
    QueueValidationError,
)
from app.services.queue_svc import _operations


def _queue(*, queue_id: int, specialist_id: int) -> DailyQueue:
    queue = DailyQueue(
        day=date(2030, 1, 2),
        specialist_id=specialist_id,
        queue_tag="cardiology",
        active=True,
        max_online_entries=15,
    )
    queue.id = queue_id
    return queue


def _service_for_exact_token(
    *, target_queue: DailyQueue, token: object
) -> QueueBusinessService:
    service = QueueBusinessService()
    service.validate_queue_token = Mock(
        return_value=(
            token,
            {
                "day": target_queue.day,
                "daily_queue": target_queue,
                "specialist_name": "TEST Doctor",
                "cabinet": "TEST-1",
            },
        )
    )
    service._load_queue_settings = Mock(
        return_value={"estimated_wait_minutes": 15}
    )
    return service


def _freeze_queue_clock(monkeypatch, frozen: datetime) -> None:
    import app.services.queue_service as queue_service_module

    class FixedDateTime(datetime):
        @classmethod
        def now(cls, tz=None):  # type: ignore[override]
            if tz is not None:
                return frozen.replace(tzinfo=tz)
            return frozen

    monkeypatch.setattr(queue_service_module, "datetime", FixedDateTime)


@pytest.mark.unit
def test_exact_token_rejects_same_tag_claim_owned_by_another_doctor(
    monkeypatch,
) -> None:
    target_queue = _queue(queue_id=10, specialist_id=1)
    foreign_queue = _queue(queue_id=20, specialist_id=2)
    existing_entry = OnlineQueueEntry(
        queue_id=foreign_queue.id,
        number=1,
        patient_name="TEST Patient",
        phone="+998900000901",
        status="waiting",
    )
    token = SimpleNamespace(is_clinic_wide=False, specialist_id=1)
    service = _service_for_exact_token(target_queue=target_queue, token=token)
    service.create_queue_entry = Mock()
    resolve_claim = Mock(
        return_value=SimpleNamespace(
            daily_queue=foreign_queue,
            entry=existing_entry,
        )
    )
    monkeypatch.setattr(_operations, "_lock_and_resolve_tag_claim", resolve_claim)

    with pytest.raises(QueueConflictError, match="другую очередь"):
        service.join_queue_with_token(
            Mock(),
            token_str="TEST-token",
            patient_name="TEST Patient",
            phone="+998900000901",
        )

    resolve_claim.assert_called_once()
    service.create_queue_entry.assert_not_called()


@pytest.mark.unit
def test_exact_token_returns_same_owner_claim_without_capacity_rejection(
    monkeypatch,
) -> None:
    target_queue = _queue(queue_id=10, specialist_id=1)
    target_queue.policy_version = "daily_online_issuances_v1"
    target_queue.online_start_time = "07:00"
    target_queue.online_end_time = "09:00"
    existing_queue = _queue(queue_id=11, specialist_id=1)
    existing_queue.opened_at = None
    existing_entry = OnlineQueueEntry(
        queue_id=existing_queue.id,
        number=7,
        patient_name="TEST Patient",
        phone="+998900000902",
        status="waiting",
    )
    existing_entry.id = 70
    token = SimpleNamespace(is_clinic_wide=False, specialist_id=1)
    service = _service_for_exact_token(target_queue=target_queue, token=token)
    _freeze_queue_clock(
        monkeypatch,
        datetime(2030, 1, 2, 10, 0, tzinfo=ZoneInfo("Asia/Tashkent")),
    )
    service.create_queue_entry = Mock()
    service.check_queue_limits = Mock(side_effect=AssertionError("must not run"))
    resolve_claim = Mock(
        return_value=SimpleNamespace(
            daily_queue=existing_queue,
            entry=existing_entry,
        )
    )
    monkeypatch.setattr(_operations, "_lock_and_resolve_tag_claim", resolve_claim)
    db = Mock()
    db.query.return_value.filter.return_value.scalar.return_value = 1

    result = service.join_queue_with_token(
        db,
        token_str="TEST-token",
        patient_name="TEST Patient",
        phone="+998900000902",
    )

    assert result["duplicate"] is True
    assert result["entry"] is existing_entry
    assert result["daily_queue"] is existing_queue
    resolve_claim.assert_called_once()
    service.check_queue_limits.assert_not_called()
    service.create_queue_entry.assert_not_called()


@pytest.mark.unit
def test_token_admission_rejects_v1_at_cutoff_without_scheduler(monkeypatch) -> None:
    target_queue = _queue(queue_id=10, specialist_id=1)
    target_queue.specialist_id = None
    target_queue.queue_tag = None
    target_queue.queue_resource_id = 1
    target_queue.policy_version = "daily_online_issuances_v1"
    target_queue.online_start_time = "07:00"
    target_queue.online_end_time = "09:00"
    target_queue.opened_at = None  # scheduler has not marked service open
    token = SimpleNamespace(is_clinic_wide=False, specialist_id=1)
    service = _service_for_exact_token(target_queue=target_queue, token=token)
    service.check_uniqueness = Mock(return_value=(None, ""))
    service.create_queue_entry = Mock()
    _freeze_queue_clock(
        monkeypatch,
        datetime(2030, 1, 2, 9, 0, tzinfo=ZoneInfo("Asia/Tashkent")),
    )
    db = Mock()
    db.query.return_value.filter.return_value.scalar.return_value = 0

    with pytest.raises(QueueValidationError, match="закрыта в 09:00"):
        service.join_queue_with_token(
            db,
            token_str="TEST-token",
            patient_name="TEST New Patient",
            phone="+998900000903",
        )

    service.create_queue_entry.assert_not_called()
