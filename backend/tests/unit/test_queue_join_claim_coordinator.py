from __future__ import annotations

from datetime import date, datetime
from types import SimpleNamespace
from unittest.mock import Mock
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy.orm import sessionmaker

from app.crud.daily_queue_creation_policy import ONLINE_ISSUANCES_V1_POLICY_VERSION
from app.models.clinic import Doctor
from app.models.online_queue import DailyQueue, OnlineQueueEntry, QueueToken
from app.models.user import User
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
    service._load_queue_settings = Mock(return_value={"estimated_wait_minutes": 15})
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
@pytest.mark.parametrize(
    ("maximum", "issued", "allowed"),
    [(0, 0, False), (3, 3, False), (3, 2, True)],
)
def test_v1_queue_limit_uses_successful_online_issuance_count(
    maximum: int, issued: int, allowed: bool
) -> None:
    daily_queue = _queue(queue_id=10, specialist_id=1)
    daily_queue.policy_version = ONLINE_ISSUANCES_V1_POLICY_VERSION
    daily_queue.max_online_entries = maximum
    daily_queue.online_issued_count = issued
    db = Mock()

    result, message = QueueBusinessService.check_queue_limits(db, daily_queue)

    assert result is allowed
    if allowed:
        assert message == ""
    else:
        assert str(maximum) in message
    db.query.assert_not_called()


@pytest.mark.unit
def test_legacy_queue_limit_keeps_active_entry_count_and_fallback() -> None:
    daily_queue = _queue(queue_id=10, specialist_id=1)
    daily_queue.max_online_entries = 0
    db = Mock()
    db.query.return_value.filter.return_value.count.return_value = 14

    allowed, message = QueueBusinessService.check_queue_limits(db, daily_queue)

    assert allowed is True
    assert message == ""
    db.query.return_value.filter.return_value.count.assert_called_once()


@pytest.mark.unit
@pytest.mark.parametrize(
    ("issued_count", "active_entries", "expected_unbookable"),
    [(1, 0, True), (0, 1, False)],
)
def test_v1_doctor_selection_uses_issuance_quota_not_queue_length(
    db_session,
    test_doctor,
    monkeypatch,
    issued_count,
    active_entries,
    expected_unbookable,
) -> None:
    zone = ZoneInfo("Asia/Tashkent")
    day = date(2030, 1, 2)
    queue = DailyQueue(
        day=day,
        specialist_id=test_doctor.id,
        queue_tag=None,
        active=True,
        max_online_entries=1,
        policy_version=ONLINE_ISSUANCES_V1_POLICY_VERSION,
        online_issued_count=issued_count,
        online_start_time="07:00",
        online_end_time="09:00",
        opened_at=None,
    )
    db_session.add(queue)
    db_session.flush()
    for number in range(1, active_entries + 1):
        db_session.add(
            OnlineQueueEntry(
                queue_id=queue.id,
                number=number,
                patient_name="TEST Synthetic Patient",
                status="waiting",
                source="desk",
            )
        )
    db_session.flush()
    _freeze_queue_clock(
        monkeypatch,
        datetime(2030, 1, 2, 8, 0, tzinfo=zone),
    )

    unbookable = _operations._unbookable_doctor_ids(
        db_session,
        [test_doctor],
        day,
        settings={"timezone": "Asia/Tashkent"},
    )

    assert (test_doctor.id in unbookable) is expected_unbookable


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
    target_queue.online_issued_count = 4
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
    assert target_queue.online_issued_count == 4
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


@pytest.mark.unit
@pytest.mark.parametrize("queue_tag", [None, "cardiology"])
def test_token_admission_rechecks_cutoff_after_queue_row_lock(
    db_session, test_doctor, monkeypatch, queue_tag
) -> None:
    """A lock wait crossing the v1 cutoff must reject before issuing a ticket."""
    zone = ZoneInfo("Asia/Tashkent")
    clock = {"now": datetime(2030, 1, 2, 8, 59, 59, tzinfo=zone), "locks": 0}
    queue = DailyQueue(
        day=date(2030, 1, 2),
        specialist_id=test_doctor.id,
        queue_tag=queue_tag,
        active=True,
        max_online_entries=15,
        start_number=1,
        policy_version="daily_online_issuances_v1",
        online_start_time="07:00",
        online_end_time="09:00",
        opened_at=None,
    )
    db_session.add(queue)
    db_session.flush()
    token = QueueToken(
        token="TEST-cutoff-lock-wait",
        day=queue.day,
        active=True,
        is_clinic_wide=False,
        specialist_id=test_doctor.id,
        usage_count=0,
        expires_at=datetime(2030, 1, 2, 9, 10, tzinfo=zone),
    )
    db_session.add(token)
    db_session.flush()

    service = QueueBusinessService()
    service._load_queue_settings = Mock(
        return_value={"timezone": "Asia/Tashkent", "estimated_wait_minutes": 15}
    )
    import app.services.queue_service as queue_service_module

    monkeypatch.setattr(
        queue_service_module,
        "datetime",
        type(
            "ClockDateTime",
            (datetime,),
            {"now": classmethod(lambda cls, tz=None: clock["now"].astimezone(tz))},
        ),
    )

    original_execute = db_session.execute

    def execute_then_advance_clock(statement, *args, **kwargs):
        result = original_execute(statement, *args, **kwargs)
        if getattr(statement, "_for_update_arg", None) is not None:
            clock["locks"] += 1
            clock["now"] = datetime(2030, 1, 2, 9, 0, 1, tzinfo=zone)
        return result

    monkeypatch.setattr(db_session, "execute", execute_then_advance_clock)

    with pytest.raises(QueueValidationError, match="закрыта в 09:00"):
        service.join_queue_with_token(
            db_session,
            token_str=token.token,
            patient_name="TEST Synthetic Patient",
            phone="+998900000903",
            commit=False,
        )

    assert clock["locks"] == 1
    assert token.usage_count == 0
    assert (
        db_session.query(OnlineQueueEntry)
        .filter(OnlineQueueEntry.queue_id == queue.id)
        .count()
        == 0
    )


@pytest.mark.unit
def test_v1_token_admission_increments_count_and_rolls_back_atomically(
    test_db, monkeypatch
) -> None:
    from uuid import uuid4

    zone = ZoneInfo("Asia/Tashkent")
    suffix = uuid4().hex
    db = sessionmaker(bind=test_db)()
    user = User(
        username=f"aqs_quota_{suffix}",
        email=f"aqs-quota-{suffix}@example.test",
        full_name="TEST Quota Owner",
        hashed_password="not-a-real-password-hash",
        role="cardio",
        is_active=True,
        is_superuser=False,
    )
    db.add(user)
    db.flush()
    doctor = Doctor(user_id=user.id, specialty="Кардиология", active=True)
    db.add(doctor)
    db.flush()
    queue = DailyQueue(
        day=date(2030, 1, 2),
        specialist_id=doctor.id,
        queue_tag=None,
        active=True,
        max_online_entries=1,
        policy_version=ONLINE_ISSUANCES_V1_POLICY_VERSION,
        online_issued_count=0,
        online_start_time="07:00",
        online_end_time="09:00",
        opened_at=None,
    )
    db.add(queue)
    db.flush()
    token = QueueToken(
        token=f"TEST-v1-quota-rollback-{suffix}",
        day=queue.day,
        specialist_id=doctor.id,
        active=True,
        usage_count=0,
        expires_at=datetime(2030, 1, 2, 9, 10, tzinfo=zone),
    )
    db.add(token)
    db.commit()

    service = QueueBusinessService()
    service._load_queue_settings = Mock(
        return_value={
            "timezone": "Asia/Tashkent",
            "estimated_wait_minutes": 15,
        }
    )
    _freeze_queue_clock(
        monkeypatch,
        datetime(2030, 1, 2, 8, 0, tzinfo=zone),
    )

    try:
        result = service.join_queue_with_token(
            db,
            token_str=token.token,
            patient_name="TEST Synthetic Patient",
            phone="+998900000904",
            commit=False,
        )

        assert result["duplicate"] is False
        assert queue.online_issued_count == 1
        assert token.usage_count == 1
        assert (
            db.query(OnlineQueueEntry)
            .filter(OnlineQueueEntry.queue_id == queue.id)
            .count()
            == 1
        )
        with pytest.raises(QueueConflictError, match="лимит мест"):
            service.join_queue_with_token(
                db,
                token_str=token.token,
                patient_name="TEST Second Synthetic Patient",
                phone="+998900000905",
                commit=False,
            )
        assert queue.online_issued_count == 1
        assert token.usage_count == 1
        assert (
            db.query(OnlineQueueEntry)
            .filter(OnlineQueueEntry.queue_id == queue.id)
            .count()
            == 1
        )

        queue_id = queue.id
        token_id = token.id
        db.rollback()
        db.expire_all()

        persisted_queue = db.query(DailyQueue).filter(DailyQueue.id == queue_id).one()
        persisted_token = db.query(QueueToken).filter(QueueToken.id == token_id).one()
        assert persisted_queue.online_issued_count == 0
        assert persisted_token.usage_count == 0
        assert (
            db.query(OnlineQueueEntry)
            .filter(OnlineQueueEntry.queue_id == queue_id)
            .count()
            == 0
        )
    finally:
        db.rollback()
        user = db.query(User).filter(User.username == f"aqs_quota_{suffix}").one()
        doctor = db.query(Doctor).filter(Doctor.user_id == user.id).one()
        queue = db.query(DailyQueue).filter(DailyQueue.specialist_id == doctor.id).one()
        token = (
            db.query(QueueToken)
            .filter(QueueToken.token == f"TEST-v1-quota-rollback-{suffix}")
            .one()
        )
        db.delete(token)
        db.delete(queue)
        db.delete(doctor)
        db.delete(user)
        db.commit()
        db.close()
