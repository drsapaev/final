"""
Unit tests for queue time window rules (07:00).
"""

from datetime import date, datetime

import app.services.queue_service as queue_service
from app.services.queue_service import QueueBusinessService


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
