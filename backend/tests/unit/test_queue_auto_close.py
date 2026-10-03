"""Auto-close selection uses the clinic calendar and clock."""

from datetime import datetime
from zoneinfo import ZoneInfo

import app.services.queue_auto_close as queue_auto_close
from app.models.clinic import Doctor
from app.models.online_queue import DailyQueue
from app.services.queue_auto_close import QueueAutoCloseService


def _freeze_utc_clock(monkeypatch, *, hour: int, minute: int = 0) -> None:
    class FixedDateTime(datetime):
        @classmethod
        def now(cls, tz=None):  # type: ignore[override]
            instant = datetime(2026, 1, 1, 19, 30, tzinfo=ZoneInfo("UTC"))
            if tz is not None:
                return instant.astimezone(tz).replace(hour=hour, minute=minute)
            return instant.replace(tzinfo=None)

    monkeypatch.setattr(queue_auto_close, "datetime", FixedDateTime)
    monkeypatch.setattr(
        queue_auto_close,
        "get_queue_settings",
        lambda db: {"timezone": "Asia/Tashkent"},
    )


def _daily_queue(db_session, *, day, end_time="08:00"):
    doctor = Doctor(specialty="cardiology")
    db_session.add(doctor)
    db_session.flush()
    queue = DailyQueue(
        day=day,
        specialist_id=doctor.id,
        queue_tag="cardiology",
        online_end_time=end_time,
        active=True,
    )
    db_session.add(queue)
    db_session.flush()
    return queue


def test_auto_close_uses_clinic_day_and_includes_exact_cutoff(
    db_session, monkeypatch
):
    from datetime import date

    _freeze_utc_clock(monkeypatch, hour=8)
    clinic_queue = _daily_queue(db_session, day=date(2026, 1, 2))
    host_day_queue = _daily_queue(db_session, day=date(2026, 1, 1))

    result = QueueAutoCloseService(db_session).check_and_close_expired_queues()

    assert result["date"] == "2026-01-02"
    assert result["check_time"] == "08:00"
    assert [item["queue_id"] for item in result["closed_queues"]] == [
        clinic_queue.id
    ]
    assert clinic_queue.opened_at is not None
    assert host_day_queue.opened_at is None


def test_pending_close_uses_clinic_clock_and_day(db_session, monkeypatch):
    from datetime import date

    _freeze_utc_clock(monkeypatch, hour=7, minute=30)
    clinic_queue = _daily_queue(
        db_session, day=date(2026, 1, 2), end_time="08:00"
    )
    _daily_queue(db_session, day=date(2026, 1, 1), end_time="09:00")

    pending = QueueAutoCloseService(db_session).get_queues_pending_close()

    assert [item["queue_id"] for item in pending] == [clinic_queue.id]
    assert pending[0]["current_time"] == "07:30"
    assert pending[0]["minutes_remaining"] == 30
