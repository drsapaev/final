from __future__ import annotations

import contextlib
from datetime import datetime
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest

from app.crud.queue_owner_invariant import QueueProfileBindingChanged
from app.graphql import mutations as gql_mutations
from app.graphql.types import QueueEntryInput
from app.models.clinic import Doctor
from app.models.online_queue import DailyQueue, OnlineQueueEntry, QueueResource
from app.models.user import User


@pytest.mark.unit
@pytest.mark.queue
def test_join_queue_rejects_phone_only_tag_claim_owned_by_another_doctor(
    db_session,
    test_doctor,
    test_patient,
    monkeypatch,
) -> None:
    """A tag-wide claim is resolved before creating the requested queue."""
    other_user = User(
        username="synthetic_gql_claim_owner",
        hashed_password="synthetic-test-only",
        role="Doctor",
        is_active=True,
    )
    db_session.add(other_user)
    db_session.flush()
    other_doctor = Doctor(
        user_id=other_user.id,
        specialty=test_doctor.specialty,
        active=True,
    )
    db_session.add(other_doctor)
    db_session.flush()

    queue_tag = "synthetic-shared-claim"
    clinic_day = datetime.now(ZoneInfo("Asia/Tashkent")).date()
    foreign_queue = DailyQueue(
        day=clinic_day,
        specialist_id=other_doctor.id,
        queue_tag=queue_tag,
        active=True,
        max_online_entries=15,
    )
    db_session.add(foreign_queue)
    db_session.flush()
    db_session.add(
        OnlineQueueEntry(
            queue_id=foreign_queue.id,
            number=1,
            patient_id=None,
            phone=test_patient.phone,
            source="online",
            status="waiting",
        )
    )
    db_session.commit()

    monkeypatch.setattr(
        gql_mutations,
        "get_db_session",
        lambda: contextlib.nullcontext(db_session),
    )
    monkeypatch.setattr(
        gql_mutations,
        "get_queue_settings",
        lambda db: {"queue_start_hour": 0, "timezone": "Asia/Tashkent"},
    )
    monkeypatch.setattr(
        gql_mutations,
        "ensure_doctor_eligible_for_appointment",
        lambda db, doctor_id: None,
    )

    result = gql_mutations.Mutation._join_queue_impl(
        SimpleNamespace(context=None),
        QueueEntryInput(
            patient_id=test_patient.id,
            doctor_id=test_doctor.id,
            queue_tag=queue_tag,
        ),
    )

    assert result.success is False
    assert result.errors == ["QUEUE_CONFLICT"]
    assert result.queue_entry is None
    assert (
        db_session.query(OnlineQueueEntry)
        .filter(OnlineQueueEntry.queue_id == foreign_queue.id)
        .count()
        == 1
    )
    assert (
        db_session.query(DailyQueue)
        .filter(
            DailyQueue.day == clinic_day,
            DailyQueue.specialist_id == test_doctor.id,
            DailyQueue.queue_tag == queue_tag,
        )
        .count()
        == 0
    )


@pytest.mark.unit
@pytest.mark.queue
def test_join_queue_maps_stale_profile_binding_to_structured_conflict(
    db_session,
    test_doctor,
    test_patient,
    monkeypatch,
) -> None:
    queue_tag = "synthetic-profile-binding-change"
    monkeypatch.setattr(
        gql_mutations,
        "get_db_session",
        lambda: contextlib.nullcontext(db_session),
    )
    monkeypatch.setattr(
        gql_mutations,
        "get_queue_settings",
        lambda db: {"queue_start_hour": 0, "timezone": "Asia/Tashkent"},
    )

    def reject_changed_binding(*args, **kwargs):
        raise QueueProfileBindingChanged()

    monkeypatch.setattr(
        gql_mutations, "lock_and_resolve_active_tag_claim", reject_changed_binding
    )
    queues_before = (
        db_session.query(DailyQueue)
        .filter(
            DailyQueue.specialist_id == test_doctor.id,
            DailyQueue.queue_tag == queue_tag,
        )
        .count()
    )

    result = gql_mutations.Mutation._join_queue_impl(
        SimpleNamespace(context=None),
        QueueEntryInput(
            patient_id=test_patient.id,
            doctor_id=test_doctor.id,
            queue_tag=queue_tag,
        ),
    )

    assert result.success is False
    assert result.errors == ["PROFILE_BINDING_CHANGED"]
    assert "refresh" in result.message.lower()
    assert result.queue_entry is None
    assert (
        db_session.query(DailyQueue)
        .filter(
            DailyQueue.specialist_id == test_doctor.id,
            DailyQueue.queue_tag == queue_tag,
        )
        .count()
        == queues_before
    )


@pytest.mark.unit
@pytest.mark.queue
def test_join_queue_recognizes_existing_resource_surface_claim(
    db_session,
    test_doctor,
    test_patient,
    monkeypatch,
) -> None:
    queue_tag = "synthetic-resource-claim"
    clinic_day = datetime.now(ZoneInfo("Asia/Tashkent")).date()
    resource = QueueResource(
        code="synthetic_resource_claim",
        queue_tag=queue_tag,
        display_name="Synthetic resource claim",
        active=True,
        start_number_online=1,
        max_online_per_day=15,
    )
    db_session.add(resource)
    db_session.flush()
    resource_queue = DailyQueue(
        day=clinic_day,
        specialist_id=None,
        queue_resource_id=resource.id,
        queue_tag=queue_tag,
        active=True,
        max_online_entries=15,
    )
    db_session.add(resource_queue)
    db_session.flush()
    db_session.add(
        OnlineQueueEntry(
            queue_id=resource_queue.id,
            number=1,
            patient_id=test_patient.id,
            source="online",
            status="waiting",
        )
    )
    db_session.commit()

    monkeypatch.setattr(
        gql_mutations,
        "get_db_session",
        lambda: contextlib.nullcontext(db_session),
    )
    monkeypatch.setattr(
        gql_mutations,
        "get_queue_settings",
        lambda db: {"queue_start_hour": 0, "timezone": "Asia/Tashkent"},
    )

    result = gql_mutations.Mutation._join_queue_impl(
        SimpleNamespace(context=None),
        QueueEntryInput(
            patient_id=test_patient.id,
            doctor_id=test_doctor.id,
            queue_tag=queue_tag,
        ),
    )

    assert result.success is False
    assert result.errors == ["ALREADY_IN_QUEUE"]
    assert result.queue_entry is None
    assert (
        db_session.query(OnlineQueueEntry)
        .filter(OnlineQueueEntry.queue_id == resource_queue.id)
        .count()
        == 1
    )


@pytest.mark.unit
@pytest.mark.queue
@pytest.mark.parametrize(
    ("locked_time", "cutoff", "expected_error"),
    [
        (datetime(2030, 1, 2, 9, 0), "09:00", "ONLINE_BOOKING_CLOSED"),
        (datetime(2030, 1, 3, 0, 0), "23:59", "QUEUE_DAY_CHANGED"),
    ],
)
def test_graphql_join_rechecks_v1_window_after_queue_lock(
    db_session,
    test_doctor,
    test_patient,
    monkeypatch,
    locked_time,
    cutoff,
    expected_error,
) -> None:
    clock_values = [datetime(2030, 1, 2, 8, 59), locked_time]
    clock_calls = 0

    class LockBoundaryDateTime(datetime):
        @classmethod
        def now(cls, tz=None):  # type: ignore[override]
            nonlocal clock_calls
            frozen = clock_values[min(clock_calls, len(clock_values) - 1)]
            clock_calls += 1
            return frozen.replace(tzinfo=tz) if tz is not None else frozen

    day = datetime(2030, 1, 2, 9, 0).date()
    queue = DailyQueue(
        day=day,
        specialist_id=test_doctor.id,
        queue_tag=None,
        active=True,
        max_online_entries=15,
        policy_version="daily_online_issuances_v1",
        online_start_time="07:00",
        online_end_time=cutoff,
    )
    db_session.add(queue)
    db_session.flush()

    monkeypatch.setattr(
        gql_mutations,
        "get_db_session",
        lambda: contextlib.nullcontext(db_session),
    )
    monkeypatch.setattr(
        gql_mutations,
        "get_queue_settings",
        lambda db: {
            "timezone": "Asia/Tashkent",
            "queue_start_hour": 7,
            "auto_close_time": cutoff,
        },
    )
    monkeypatch.setattr(
        gql_mutations,
        "ensure_doctor_eligible_for_appointment",
        lambda db, doctor_id: None,
    )
    monkeypatch.setattr(gql_mutations, "datetime", LockBoundaryDateTime)

    result = gql_mutations.Mutation._join_queue_impl(
        SimpleNamespace(context=None),
        QueueEntryInput(patient_id=test_patient.id, doctor_id=test_doctor.id),
    )

    assert clock_calls == 2
    assert result.success is False
    assert result.errors == [expected_error]
    assert result.queue_entry is None
    assert (
        db_session.query(OnlineQueueEntry)
        .filter(OnlineQueueEntry.queue_id == queue.id)
        .count()
        == 0
    )


@pytest.mark.unit
@pytest.mark.queue
@pytest.mark.parametrize(
    (
        "policy_version",
        "online_issued_count",
        "existing_source",
        "expected_success",
        "expected_count",
    ),
    [
        (
            "daily_online_issuances_v1",
            0,
            "desk",
            True,
            1,
        ),
        (
            "daily_online_issuances_v1",
            1,
            None,
            False,
            1,
        ),
        (
            "legacy",
            0,
            "online",
            False,
            0,
        ),
    ],
    ids=(
        "v1-does-not-count-staff",
        "v1-counter-does-not-reset",
        "legacy-keeps-active-cap",
    ),
)
def test_graphql_join_uses_policy_specific_daily_quota(
    db_session,
    test_doctor,
    test_patient,
    monkeypatch,
    policy_version,
    online_issued_count,
    existing_source,
    expected_success,
    expected_count,
) -> None:
    class FixedDateTime(datetime):
        @classmethod
        def now(cls, tz=None):  # type: ignore[override]
            fixed = datetime(2030, 1, 2, 8, 0)
            return fixed.replace(tzinfo=tz) if tz is not None else fixed

    day = datetime(2030, 1, 2).date()
    queue = DailyQueue(
        day=day,
        specialist_id=test_doctor.id,
        queue_tag=None,
        active=True,
        max_online_entries=1,
        policy_version=policy_version,
        online_issued_count=online_issued_count,
        online_start_time="07:00",
        online_end_time="09:00",
    )
    db_session.add(queue)
    db_session.flush()

    existing_entries = 0
    if existing_source is not None:
        db_session.add(
            OnlineQueueEntry(
                queue_id=queue.id,
                number=1,
                patient_id=None,
                status="waiting",
                source=existing_source,
            )
        )
        db_session.flush()
        existing_entries = 1

    monkeypatch.setattr(
        gql_mutations,
        "get_db_session",
        lambda: contextlib.nullcontext(db_session),
    )
    monkeypatch.setattr(
        gql_mutations,
        "get_queue_settings",
        lambda db: {
            "timezone": "Asia/Tashkent",
            "queue_start_hour": 7,
            "auto_close_time": "09:00",
        },
    )
    monkeypatch.setattr(
        gql_mutations,
        "ensure_doctor_eligible_for_appointment",
        lambda db, doctor_id: None,
    )
    monkeypatch.setattr(gql_mutations, "datetime", FixedDateTime)

    result = gql_mutations.Mutation._join_queue_impl(
        SimpleNamespace(context=None),
        QueueEntryInput(patient_id=test_patient.id, doctor_id=test_doctor.id),
    )

    assert result.success is expected_success
    assert queue.online_issued_count == expected_count
    assert db_session.query(OnlineQueueEntry).filter(
        OnlineQueueEntry.queue_id == queue.id
    ).count() == existing_entries + int(expected_success)
    if expected_success:
        assert result.queue_entry is not None
    else:
        assert result.errors == ["QUEUE_LIMIT_EXCEEDED"]
        assert result.queue_entry is None
