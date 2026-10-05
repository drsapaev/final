from datetime import date

import pytest
from sqlalchemy import func

from app.crud.daily_queue_creation_policy import (
    LEGACY_POLICY_VERSION,
    ONLINE_ISSUANCES_V1_POLICY_VERSION,
    daily_queue_creation_snapshot,
)
from app.models.clinic import Doctor
from app.models.online_queue import DailyQueue, QueueResource
from app.services.queue_service import QueueBusinessService


def test_creation_snapshot_defaults_to_legacy_and_inherits_clinic_start_number(
    db_session, monkeypatch
):
    monkeypatch.delenv("QUEUE_POLICY_V2_CREATION_ENABLED", raising=False)
    doctor = Doctor(specialty="aqs-snapshot", start_number_online=1)

    snapshot = daily_queue_creation_snapshot(
        db_session,
        doctor=doctor,
        queue_tag="aqs-snapshot",
        settings={"start_numbers": {"aqs-snapshot": 41}},
    )

    assert snapshot == {
        "policy_version": LEGACY_POLICY_VERSION,
        "online_issued_count": 0,
        "online_start_time": "07:00",
        "online_end_time": "09:00",
        "start_number": 41,
    }


def test_creation_flag_selects_v1_for_new_snapshot_only(db_session, monkeypatch):
    monkeypatch.setenv("QUEUE_POLICY_V2_CREATION_ENABLED", " TRUE ")
    doctor = Doctor(specialty="aqs-v1", start_number_online=7)
    db_session.add(doctor)
    db_session.flush()

    snapshot = daily_queue_creation_snapshot(
        db_session,
        day=date(2026, 10, 1),
        doctor=doctor,
        queue_tag="aqs-v1",
        settings={"start_numbers": {"aqs-v1": 41}},
    )

    assert snapshot == {
        "policy_version": ONLINE_ISSUANCES_V1_POLICY_VERSION,
        "online_issued_count": 0,
        "online_start_time": "07:00",
        "online_end_time": "09:00",
        "start_number": 7,
    }


def test_v1_creation_snapshot_uses_configured_clinic_window(db_session, monkeypatch):
    monkeypatch.setenv("QUEUE_POLICY_V2_CREATION_ENABLED", "true")
    doctor = Doctor(specialty="aqs-v1-window")
    db_session.add(doctor)
    db_session.flush()

    snapshot = daily_queue_creation_snapshot(
        db_session,
        day=date(2026, 10, 1),
        doctor=doctor,
        queue_tag="aqs-v1-window",
        settings={
            "queue_start_hour": 8,
            "auto_close_time": "10:30",
            "start_numbers": {},
        },
    )

    assert snapshot["policy_version"] == ONLINE_ISSUANCES_V1_POLICY_VERSION
    assert snapshot["online_start_time"] == "08:00"
    assert snapshot["online_end_time"] == "10:30"


def test_v1_creation_snapshot_rejects_overnight_or_empty_window(
    db_session, monkeypatch
):
    monkeypatch.setenv("QUEUE_POLICY_V2_CREATION_ENABLED", "true")
    doctor = Doctor(specialty="aqs-invalid-window")
    db_session.add(doctor)
    db_session.flush()

    for end_time in ("07:00", "06:59", "24:00", "9:00", "09:60"):
        with pytest.raises(ValueError):
            daily_queue_creation_snapshot(
                db_session,
                day=date(2026, 10, 1),
                doctor=doctor,
                queue_tag="aqs-invalid-window",
                settings={
                    "queue_start_hour": 7,
                    "auto_close_time": end_time,
                    "start_numbers": {},
                },
            )


def test_existing_daily_queue_is_not_rewritten_when_creation_flag_changes(
    db_session, monkeypatch
):
    doctor = Doctor(specialty="aqs-existing")
    db_session.add(doctor)
    db_session.flush()
    queue = DailyQueue(
        day=date(2026, 10, 1),
        specialist_id=doctor.id,
        queue_tag="aqs-existing",
        policy_version=LEGACY_POLICY_VERSION,
        online_issued_count=4,
    )
    db_session.add(queue)
    db_session.flush()
    original_queue_id = queue.id

    monkeypatch.setenv("QUEUE_POLICY_V2_CREATION_ENABLED", "true")
    reused = QueueBusinessService().get_or_create_daily_queue(
        db_session,
        day=queue.day,
        specialist_id=doctor.id,
        queue_tag="aqs-existing",
    )

    assert reused.id == original_queue_id
    assert reused.policy_version == LEGACY_POLICY_VERSION
    assert reused.online_issued_count == 4


def test_queue_service_creates_v1_snapshots_for_doctor_and_resource_owners(
    db_session, monkeypatch
):
    monkeypatch.setenv("QUEUE_POLICY_V2_CREATION_ENABLED", "true")
    day = date(2026, 10, 2)
    doctor = Doctor(specialty="aqs-v1-doctor", start_number_online=7)
    resource = QueueResource(
        code="aqs-v1-resource",
        queue_tag="aqs-v1-resource",
        display_name="Synthetic queue resource",
        start_number_online=11,
        max_online_per_day=8,
    )
    db_session.add_all([doctor, resource])
    db_session.flush()

    service = QueueBusinessService()
    doctor_queue = service.get_or_create_daily_queue(
        db_session,
        day=day,
        specialist_id=doctor.id,
        queue_tag=doctor.specialty,
    )
    resource_queue = service.get_or_create_daily_queue(
        db_session,
        day=day,
        specialist_id=None,
        queue_tag=resource.queue_tag,
    )

    assert doctor_queue.policy_version == ONLINE_ISSUANCES_V1_POLICY_VERSION
    assert doctor_queue.online_issued_count == 0
    assert doctor_queue.start_number == 7
    assert resource_queue.policy_version == ONLINE_ISSUANCES_V1_POLICY_VERSION
    assert resource_queue.online_issued_count == 0
    assert resource_queue.queue_resource_id == resource.id
    assert resource_queue.specialist_id is None
    assert resource_queue.start_number == 11


def test_legacy_crud_creator_keeps_explicit_start_number_default(
    db_session, monkeypatch
):
    from app.crud.online_queue import get_or_create_daily_queue

    monkeypatch.setenv("QUEUE_POLICY_V2_CREATION_ENABLED", "true")
    doctor = Doctor(specialty="aqs-explicit-start", start_number_online=7)
    db_session.add(doctor)
    db_session.flush()

    queue = get_or_create_daily_queue(
        db_session,
        day=date(2026, 10, 3),
        specialist_id=doctor.id,
        queue_tag=doctor.specialty,
        defaults={"start_number": 23},
    )

    assert queue.start_number == 23
    assert queue.policy_version == ONLINE_ISSUANCES_V1_POLICY_VERSION
    assert queue.online_issued_count == 0


def test_v1_creation_rejects_inactive_doctor_identity_recreation(
    db_session, monkeypatch
):
    monkeypatch.setenv("QUEUE_POLICY_V2_CREATION_ENABLED", "true")
    day = date(2026, 10, 4)
    doctor = Doctor(specialty="aqs-inactive-doctor")
    db_session.add(doctor)
    db_session.flush()
    previous = DailyQueue(
        day=day,
        specialist_id=doctor.id,
        queue_tag=doctor.specialty,
        active=False,
        policy_version=ONLINE_ISSUANCES_V1_POLICY_VERSION,
        online_issued_count=3,
    )
    db_session.add(previous)
    db_session.flush()

    with pytest.raises(ValueError, match="daily queue identity"):
        QueueBusinessService().get_or_create_daily_queue(
            db_session,
            day=day,
            specialist_id=doctor.id,
            queue_tag=doctor.specialty,
        )

    queues = (
        db_session.query(DailyQueue)
        .filter(DailyQueue.day == day, DailyQueue.specialist_id == doctor.id)
        .all()
    )
    assert [queue.id for queue in queues] == [previous.id]
    assert previous.online_issued_count == 3


def test_v1_creation_rejects_inactive_resource_identity_recreation(
    db_session, monkeypatch
):
    monkeypatch.setenv("QUEUE_POLICY_V2_CREATION_ENABLED", "true")
    day = date(2026, 10, 5)
    resource = QueueResource(
        code="aqs-inactive-resource",
        queue_tag="aqs-inactive-resource",
        display_name="Inactive resource",
        max_online_per_day=8,
    )
    db_session.add(resource)
    db_session.flush()
    previous = DailyQueue(
        day=day,
        specialist_id=None,
        queue_resource_id=resource.id,
        queue_tag=resource.queue_tag,
        active=False,
        policy_version=ONLINE_ISSUANCES_V1_POLICY_VERSION,
        online_issued_count=2,
    )
    db_session.add(previous)
    db_session.flush()

    with pytest.raises(ValueError, match="daily queue identity"):
        QueueBusinessService().get_or_create_daily_queue(
            db_session,
            day=day,
            specialist_id=None,
            queue_tag=resource.queue_tag,
        )

    queues = (
        db_session.query(DailyQueue)
        .filter(
            DailyQueue.day == day,
            DailyQueue.queue_resource_id == resource.id,
        )
        .all()
    )
    assert [queue.id for queue in queues] == [previous.id]
    assert previous.online_issued_count == 2


def test_v1_resource_identity_does_not_collide_with_doctor_id_axis(
    db_session, monkeypatch
):
    monkeypatch.setenv("QUEUE_POLICY_V2_CREATION_ENABLED", "true")
    day = date(2026, 10, 6)
    shared_owner_id = (
        max(
            db_session.query(func.max(Doctor.id)).scalar() or 0,
            db_session.query(func.max(QueueResource.id)).scalar() or 0,
        )
        + 1
    )
    doctor = Doctor(id=shared_owner_id, specialty="aqs-doctor-axis")
    resource = QueueResource(
        id=shared_owner_id,
        code="aqs-resource-axis",
        queue_tag="aqs-resource-axis",
        display_name="Resource axis",
        max_online_per_day=8,
    )
    db_session.add_all([doctor, resource])
    db_session.flush()
    assert doctor.id == resource.id == shared_owner_id
    db_session.add(
        DailyQueue(
            day=day,
            specialist_id=doctor.id,
            queue_tag=doctor.specialty,
            active=False,
            policy_version=ONLINE_ISSUANCES_V1_POLICY_VERSION,
            online_issued_count=1,
        )
    )
    db_session.flush()

    queue = QueueBusinessService().get_or_create_daily_queue(
        db_session,
        day=day,
        specialist_id=None,
        queue_tag=resource.queue_tag,
    )

    assert queue.queue_resource_id == resource.id
    assert queue.specialist_id is None
    assert queue.policy_version == ONLINE_ISSUANCES_V1_POLICY_VERSION


def test_legacy_creation_keeps_inactive_identity_compatibility(db_session, monkeypatch):
    monkeypatch.delenv("QUEUE_POLICY_V2_CREATION_ENABLED", raising=False)
    day = date(2026, 10, 7)
    doctor = Doctor(specialty="aqs-legacy-inactive")
    db_session.add(doctor)
    db_session.flush()
    previous = DailyQueue(
        day=day,
        specialist_id=doctor.id,
        queue_tag=doctor.specialty,
        active=False,
        policy_version=LEGACY_POLICY_VERSION,
        online_issued_count=4,
    )
    db_session.add(previous)
    db_session.flush()

    queue = QueueBusinessService().get_or_create_daily_queue(
        db_session,
        day=day,
        specialist_id=doctor.id,
        queue_tag=doctor.specialty,
    )

    assert queue.id != previous.id
    assert queue.policy_version == LEGACY_POLICY_VERSION
    assert previous.online_issued_count == 4
