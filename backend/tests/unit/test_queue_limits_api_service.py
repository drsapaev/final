from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import pytest

from app.services.queue_limits_api_service import QueueLimitsApiService


@dataclass
class _FakeUser:
    full_name: str | None = None
    username: str = "doctor-1"


@dataclass
class _FakeDoctor:
    id: int
    user_id: int | None
    specialty: str
    cabinet: str | None = None
    user: _FakeUser | None = None


class _FakeRepository:
    def __init__(self, doctors: list[_FakeDoctor]):
        self._doctors = doctors

    def list_active_doctors(self, *, specialty: str | None):
        if specialty:
            return [doctor for doctor in self._doctors if doctor.specialty == specialty]
        return self._doctors

    def get_daily_queue(self, *, day: date, specialist_id: int):
        return None


@pytest.mark.unit
class TestQueueLimitsApiService:
    def test_queue_status_falls_back_to_username_when_full_name_missing(self, db_session):
        service = QueueLimitsApiService(
            db_session,
            repository=_FakeRepository(
                [
                    _FakeDoctor(
                        id=7,
                        user_id=42,
                        specialty="cardiology",
                        cabinet="101",
                        user=_FakeUser(full_name=None, username="doc-fallback"),
                    )
                ]
            ),
            get_settings=lambda _db: {"max_per_day": {"cardiology": 12}, "start_numbers": {}},
        )

        result = service.get_queue_status_with_limits(day=date.today(), specialty=None)

        assert len(result) == 1
        assert result[0]["doctor_name"] == "doc-fallback"
        assert result[0]["max_entries"] == 12
        assert result[0]["online_available"] is True

