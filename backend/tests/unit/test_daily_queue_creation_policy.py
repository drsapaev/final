from datetime import date

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

    snapshot = daily_queue_creation_snapshot(
        db_session,
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

    snapshot = daily_queue_creation_snapshot(
        db_session,
        doctor=Doctor(specialty="aqs-v1-window"),
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
    import pytest

    monkeypatch.setenv("QUEUE_POLICY_V2_CREATION_ENABLED", "true")
    doctor = Doctor(specialty="aqs-invalid-window")

    for end_time in ("07:00", "06:59", "24:00", "9:00", "09:60"):
        with pytest.raises(ValueError):
            daily_queue_creation_snapshot(
                db_session,
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
