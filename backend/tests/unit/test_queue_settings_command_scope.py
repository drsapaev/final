from datetime import date, timedelta

import pytest

import app.crud.clinic as clinic_crud
import app.services.queue_svc._core as queue_core
from app.models.clinic import ClinicSettings, Doctor
from app.services.queue_service import QueueBusinessService


def test_daily_queue_creation_refreshes_settings_between_commands(
    db_session, monkeypatch
):
    queue_tag = "aqs-settings-cache-test"
    setting = ClinicSettings(key="queue_start_hour", value=7, category="queue")
    start_number_setting = ClinicSettings(
        key=f"start_number_{queue_tag}", value=5, category="queue"
    )
    db_session.add(setting)
    db_session.add(start_number_setting)
    db_session.flush()

    original_loader = queue_core.get_queue_settings
    reads = 0

    def load_settings(db):
        nonlocal reads
        reads += 1
        return original_loader(db)

    monkeypatch.setattr(queue_core, "get_queue_settings", load_settings)
    monkeypatch.setattr(
        clinic_crud,
        "get_queue_settings",
        lambda _db: {"start_numbers": {queue_tag: 99}},
    )

    doctor = Doctor(specialty="cardiology", cabinet="101")
    db_session.add(doctor)
    db_session.flush()

    service = QueueBusinessService()
    first_day = date(2026, 10, 1)
    first_queue = service.get_or_create_daily_queue(
        db_session,
        day=first_day,
        specialist_id=doctor.id,
        queue_tag=queue_tag,
    )
    assert first_queue.online_start_time == "07:00"
    assert first_queue.online_end_time == "09:00"
    assert first_queue.start_number == 5

    setting.value = 8
    start_number_setting.value = 9
    db_session.flush()

    existing_queue = service.get_or_create_daily_queue(
        db_session,
        day=first_day,
        specialist_id=doctor.id,
        queue_tag=queue_tag,
    )
    assert existing_queue.id == first_queue.id
    assert existing_queue.online_start_time == "07:00"
    assert existing_queue.online_end_time == "09:00"
    assert existing_queue.start_number == 5

    next_day_queue = service.get_or_create_daily_queue(
        db_session,
        day=first_day + timedelta(days=1),
        specialist_id=doctor.id,
        queue_tag=queue_tag,
    )

    assert next_day_queue.online_start_time == "08:00"
    assert next_day_queue.online_end_time == "09:00"
    assert next_day_queue.start_number == 9
    assert reads == 2


def test_nested_queue_commands_share_one_settings_snapshot(db_session, monkeypatch):
    settings = {
        "timezone": "Asia/Tashkent",
        "queue_start_hour": 8,
        "auto_close_time": "10:00",
        "start_numbers": {},
        "max_per_day": {},
    }
    monkeypatch.setenv("QUEUE_POLICY_V2_CREATION_ENABLED", "true")
    reads = 0

    def load_settings(_db):
        nonlocal reads
        reads += 1
        return dict(settings)

    monkeypatch.setattr(queue_core, "get_queue_settings", load_settings)

    doctor = Doctor(specialty="cardiology", cabinet="101")
    db_session.add(doctor)
    db_session.flush()

    _, metadata = QueueBusinessService().assign_queue_token(
        db_session,
        specialist_id=doctor.id,
        department=doctor.specialty,
        generated_by_user_id=None,
        target_date=date(2026, 10, 3),
        queue_tag="aqs-settings-nested-test",
        commit=False,
    )

    assert metadata["start_time"] == "08:00"
    assert metadata["end_time"] == "10:00"
    assert metadata["policy_version"] == "daily_online_issuances_v1"
    assert reads == 1


def test_settings_context_is_cleared_when_command_raises(monkeypatch):
    settings = {"timezone": "UTC"}
    reads = 0

    def load_settings(_db):
        nonlocal reads
        reads += 1
        return dict(settings)

    class FailingDb:
        def add(self, _obj):
            raise RuntimeError("synthetic add failure")

    monkeypatch.setattr(queue_core, "get_queue_settings", load_settings)
    service = QueueBusinessService()
    db = FailingDb()

    with pytest.raises(RuntimeError, match="synthetic add failure"):
        service.assign_queue_token(
            db,
            specialist_id=None,
            department="clinic",
            generated_by_user_id=None,
            is_clinic_wide=True,
            target_date=date(2026, 10, 3),
            commit=False,
        )

    service.get_local_timestamp(db)

    assert reads == 2
