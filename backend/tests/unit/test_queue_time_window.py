"""
Unit tests for queue time window rules (07:00).
"""

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import app.services.queue_service as queue_service
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
