"""
Unit tests for queue time window rules (07:00).
"""

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import app.services.queue_service as queue_service
from app.models.clinic import Doctor
from app.models.online_queue import DailyQueue, OnlineQueueEntry
from app.models.patient import Patient
from app.models.visit import Visit
from app.services.queue_service import QueueBusinessService


class _QueueTokenFakeDb:
    def __init__(self) -> None:
        self.added = None

    def add(self, obj):
        self.added = obj

    def flush(self):
        return None

    def commit(self):
        return None

    def refresh(self, obj):
        return None


def _freeze_datetime(monkeypatch, frozen_dt: datetime) -> None:
    class FixedDateTime(datetime):
        @classmethod
        def now(cls, tz=None):  # type: ignore[override]
            if tz is not None:
                return frozen_dt.replace(tzinfo=tz)
            return frozen_dt

    monkeypatch.setattr(queue_service, "datetime", FixedDateTime)


def test_queue_time_window_blocks_before_start(monkeypatch):
    target = date(2026, 1, 1)
    _freeze_datetime(monkeypatch, datetime(2026, 1, 1, 6, 30))

    allowed, message = QueueBusinessService.check_queue_time_window(target)

    assert allowed is False
    assert "07:00" in message


def test_queue_time_window_allows_after_start(monkeypatch):
    target = date(2026, 1, 1)
    _freeze_datetime(monkeypatch, datetime(2026, 1, 1, 7, 5))

    allowed, _ = QueueBusinessService.check_queue_time_window(target)

    assert allowed is True


def _queue_service_with_static_settings(monkeypatch) -> QueueBusinessService:
    service = QueueBusinessService()
    monkeypatch.setattr(
        service,
        "_load_queue_settings",
        lambda db: {
            "timezone": "Asia/Tashkent",
            "default_max_slots": 15,
            "queue_start_hour": 7,
            "queue_end_hour": 9,
        },
    )
    return service


def test_assign_queue_token_caps_sensitive_qr_ttl_at_15_minutes(monkeypatch):
    frozen = datetime(2026, 1, 1, 8, 0)
    _freeze_datetime(monkeypatch, frozen)
    service = _queue_service_with_static_settings(monkeypatch)
    fake_db = _QueueTokenFakeDb()

    _, metadata = service.assign_queue_token(
        fake_db,
        specialist_id=None,
        department="clinic",
        generated_by_user_id=10,
        is_clinic_wide=True,
        expires_hours=24,
        commit=False,
    )

    now = frozen.replace(tzinfo=ZoneInfo("Asia/Tashkent"))
    assert metadata["expires_at"] - now == timedelta(minutes=15)
    assert metadata["ttl_minutes"] == 15
    assert fake_db.added.expires_at == metadata["expires_at"]


def test_assign_queue_token_enforces_sensitive_qr_ttl_floor(monkeypatch):
    frozen = datetime(2026, 1, 1, 8, 0)
    _freeze_datetime(monkeypatch, frozen)
    service = _queue_service_with_static_settings(monkeypatch)
    fake_db = _QueueTokenFakeDb()

    _, metadata = service.assign_queue_token(
        fake_db,
        specialist_id=None,
        department="clinic",
        generated_by_user_id=10,
        is_clinic_wide=True,
        expires_hours=0,
        commit=False,
    )

    now = frozen.replace(tzinfo=ZoneInfo("Asia/Tashkent"))
    assert metadata["expires_at"] - now == timedelta(minutes=5)
    assert metadata["ttl_minutes"] == 5


def _queue_with_entries(db_session, *, target_day: date):
    doctor = Doctor(specialty="cardiology", cabinet="101")
    db_session.add(doctor)
    db_session.flush()

    daily_queue = DailyQueue(
        day=target_day,
        specialist_id=doctor.id,
        queue_tag="cardio",
        active=True,
    )
    db_session.add(daily_queue)
    db_session.flush()

    first_time = datetime(2026, 1, 1, 7, 30)
    second_time = datetime(2026, 1, 1, 8, 0)
    first = OnlineQueueEntry(
        queue_id=daily_queue.id,
        number=1,
        patient_name="First Patient",
        status="waiting",
        queue_time=first_time,
        source="desk",
    )
    second = OnlineQueueEntry(
        queue_id=daily_queue.id,
        number=2,
        patient_name="Second Patient",
        status="waiting",
        queue_time=second_time,
        source="desk",
    )
    db_session.add_all([first, second])
    db_session.flush()
    return daily_queue, first, second


def _link_entry_to_visit(
    db_session,
    entry: OnlineQueueEntry,
    *,
    doctor_id: int,
    target_day: date,
    phone: str,
) -> Visit:
    patient = Patient(
        first_name="Queue",
        last_name="Owner",
        phone=phone,
    )
    db_session.add(patient)
    db_session.flush()

    visit = Visit(
        patient_id=patient.id,
        doctor_id=doctor_id,
        visit_date=target_day,
        visit_time="09:00",
        status="open",
        department="cardiology",
    )
    db_session.add(visit)
    db_session.flush()

    entry.patient_id = patient.id
    entry.visit_id = visit.id
    db_session.flush()
    return visit


def test_staff_call_next_patient_preserves_queue_time(db_session, monkeypatch):
    target_day = date(2026, 1, 1)
    _freeze_datetime(monkeypatch, datetime(2026, 1, 1, 9, 0))
    daily_queue, first, second = _queue_with_entries(
        db_session,
        target_day=target_day,
    )

    result = QueueBusinessService().staff_call_next_patient(
        db_session,
        queue_id=daily_queue.id,
        target_date=target_day,
        actor_user_id=42,
        commit=False,
    )

    assert result["success"] is True
    assert result["action"] == "staff_call_next_patient"
    assert result["entry_id"] == first.id
    assert result["previous_status"] == "waiting"
    assert result["status"] == "called"
    assert result["queue_time_preserved"] is True
    assert first.status == "called"
    assert first.queue_time == datetime(2026, 1, 1, 7, 30)
    assert first.called_at is not None
    assert second.status == "waiting"


def test_staff_skip_queue_entry_preserves_queue_time(db_session):
    target_day = date(2026, 1, 1)
    _daily_queue, first, _second = _queue_with_entries(
        db_session,
        target_day=target_day,
    )

    result = QueueBusinessService().staff_skip_queue_entry(
        db_session,
        entry_id=first.id,
        actor_user_id=42,
        commit=False,
    )

    assert result["success"] is True
    assert result["action"] == "staff_skip_queue_entry"
    assert result["previous_status"] == "waiting"
    assert result["status"] == "no_show"
    assert result["queue_time_preserved"] is True
    assert first.status == "no_show"
    assert first.queue_time == datetime(2026, 1, 1, 7, 30)


def test_staff_cancel_visit_queue_link_preserves_queue_time(db_session):
    target_day = date(2026, 1, 1)
    daily_queue, first, _second = _queue_with_entries(
        db_session,
        target_day=target_day,
    )
    visit = _link_entry_to_visit(
        db_session,
        first,
        doctor_id=daily_queue.specialist_id,
        target_day=target_day,
        phone="+998901001001",
    )

    result = QueueBusinessService().staff_cancel_visit_queue_link(
        db_session,
        visit_id=visit.id,
        actor_user_id=42,
        commit=False,
    )

    assert result["success"] is True
    assert result["action"] == "staff_cancel_visit_queue_link"
    assert result["visit_id"] == visit.id
    assert result["previous_status"] == "waiting"
    assert result["status"] == "cancelled"
    assert result["queue_time_preserved"] is True
    assert first.status == "cancelled"
    assert first.queue_time == datetime(2026, 1, 1, 7, 30)


def test_staff_move_visit_queue_link_preserves_queue_time(db_session):
    target_day = date(2026, 1, 1)
    daily_queue, first, _second = _queue_with_entries(
        db_session,
        target_day=target_day,
    )
    visit = _link_entry_to_visit(
        db_session,
        first,
        doctor_id=daily_queue.specialist_id,
        target_day=target_day,
        phone="+998901001002",
    )

    result = QueueBusinessService().staff_move_visit_queue_link(
        db_session,
        visit_id=visit.id,
        actor_user_id=42,
        commit=False,
    )

    assert result["success"] is True
    assert result["action"] == "staff_move_visit_queue_link"
    assert result["visit_id"] == visit.id
    assert result["previous_status"] == "waiting"
    assert result["status"] == "rescheduled"
    assert result["queue_time_preserved"] is True
    assert first.status == "rescheduled"
    assert first.queue_time == datetime(2026, 1, 1, 7, 30)
