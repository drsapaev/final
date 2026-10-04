from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from types import SimpleNamespace

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
    def test_aggregate_limits_report_queue_length_and_null_mixed_quota(self):
        doctors = [
            _FakeDoctor(id=7, user_id=42, specialty="cardiology"),
            _FakeDoctor(id=8, user_id=43, specialty="cardiology"),
        ]
        queues = {
            7: [
                SimpleNamespace(
                    id=101,
                    max_online_entries=4,
                    policy_version="legacy",
                    online_issued_count=0,
                )
            ],
            8: [
                SimpleNamespace(
                    id=102,
                    max_online_entries=3,
                    policy_version="daily_online_issuances_v1",
                    online_issued_count=1,
                )
            ],
        }

        class Repository:
            def list_active_doctors(self, *, specialty):
                assert specialty == "cardiology"
                return doctors

            def list_active_daily_queues(self, *, day, specialist_id):
                assert day == date.today()
                return queues[specialist_id]

            def count_entries(self, *, queue_id):
                return {101: 7, 102: 1}[queue_id]

            def count_active_entries(self, *, queue_id):
                return {101: 0, 102: 1}[queue_id]

        service = QueueLimitsApiService(
            db=object(),
            repository=Repository(),
            get_settings=lambda _db: {
                "max_per_day": {"cardiology": 15},
                "start_numbers": {},
            },
        )

        result = service.get_queue_limits(specialty="cardiology")[0]

        assert result["current_usage"] == 8
        assert result["queue_length"] == 1
        assert result["aggregate_max_per_day"] == 7
        assert result["policy_version"] == "mixed"
        assert result["online_issued_count"] is None
        assert result["online_bookings_remaining"] is None

    def test_rowless_shared_resource_quota_is_aggregated_once(
        self, db_session, monkeypatch
    ):
        import app.services.queue_limits_api_service as limits_service_module
        from app.models.clinic import Doctor
        from app.models.online_queue import QueueResource

        day = date(2030, 1, 2)
        doctors = [
            Doctor(specialty="synthetic-shared-resource"),
            Doctor(specialty="synthetic-shared-resource"),
        ]
        resource = QueueResource(
            code="synthetic-shared-resource",
            queue_tag="synthetic-shared-resource",
            display_name="Synthetic shared resource",
            active=True,
            max_online_per_day=4,
        )
        db_session.add_all([*doctors, resource])
        db_session.flush()
        monkeypatch.setenv("QUEUE_POLICY_V2_CREATION_ENABLED", "true")
        monkeypatch.setattr(limits_service_module, "clinic_today", lambda _db: day)

        class Repository:
            def list_active_doctors(self, *, specialty):
                assert specialty == "synthetic-shared-resource"
                return doctors

            def list_active_daily_queues(self, *, day, specialist_id):
                assert day == date(2030, 1, 2)
                return []

            def count_entries(self, *, queue_id):
                raise AssertionError("rowless resource has no persisted queue")

            def count_active_entries(self, *, queue_id):
                raise AssertionError("rowless resource has no persisted queue")

        service = QueueLimitsApiService(
            db=db_session,
            repository=Repository(),
            get_settings=lambda _db: {
                "max_per_day": {},
                "start_numbers": {},
            },
        )

        result = service.get_queue_limits(specialty="synthetic-shared-resource")[0]

        assert result["doctors_count"] == 2
        assert result["aggregate_max_per_day"] == 4
        assert result["policy_version"] == "daily_online_issuances_v1"
        assert result["online_issued_count"] == 0
        assert result["online_bookings_remaining"] == 4

    def test_inactive_shared_resource_identity_does_not_advertise_fresh_quota(
        self, db_session, monkeypatch
    ):
        import app.services.queue_limits_api_service as limits_service_module
        from app.models.clinic import Doctor
        from app.models.online_queue import DailyQueue, QueueResource

        day = date(2030, 1, 2)
        doctors = [
            Doctor(specialty="synthetic-inactive-shared-resource"),
            Doctor(specialty="synthetic-inactive-shared-resource"),
        ]
        resource = QueueResource(
            code="synthetic-inactive-shared-resource",
            queue_tag="synthetic-inactive-shared-resource",
            display_name="Synthetic inactive shared resource",
            active=True,
            max_online_per_day=4,
        )
        db_session.add_all([*doctors, resource])
        db_session.flush()
        inactive_queue = DailyQueue(
            day=day,
            specialist_id=None,
            queue_resource_id=resource.id,
            queue_tag=resource.queue_tag,
            active=False,
            policy_version="daily_online_issuances_v1",
            online_start_time="07:00",
            online_end_time="09:00",
            max_online_entries=4,
            online_issued_count=3,
        )
        db_session.add(inactive_queue)
        db_session.flush()
        monkeypatch.setenv("QUEUE_POLICY_V2_CREATION_ENABLED", "true")
        monkeypatch.setattr(limits_service_module, "clinic_today", lambda _db: day)

        class Repository:
            def list_active_doctors(self, *, specialty):
                assert specialty == "synthetic-inactive-shared-resource"
                return doctors

            def list_active_daily_queues(self, *, day, specialist_id):
                assert day == date(2030, 1, 2)
                return []

            def count_entries(self, *, queue_id):
                raise AssertionError("inactive identity is not an active queue")

            def count_active_entries(self, *, queue_id):
                raise AssertionError("inactive identity is not an active queue")

        service = QueueLimitsApiService(
            db=db_session,
            repository=Repository(),
            get_settings=lambda _db: {"max_per_day": {}, "start_numbers": {}},
        )

        result = service.get_queue_limits(
            specialty="synthetic-inactive-shared-resource"
        )[0]

        assert result["doctors_count"] == 2
        assert result["aggregate_max_per_day"] == 4
        assert result["policy_version"] == "daily_online_issuances_v1"
        assert result["online_issued_count"] is None
        assert result["online_bookings_remaining"] is None

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
