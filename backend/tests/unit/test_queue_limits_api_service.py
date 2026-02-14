from __future__ import annotations

from datetime import date
from types import SimpleNamespace

import pytest

from app.services.queue_limits_api_service import QueueLimitsApiService


@pytest.mark.unit
class TestQueueLimitsApiService:
    def test_get_queue_limits_aggregates_usage_by_specialty(self):
        doctors = [
            SimpleNamespace(
                id=1,
                user_id=11,
                specialty="cardio",
                cabinet="101",
                user=SimpleNamespace(full_name="A"),
            ),
            SimpleNamespace(
                id=2,
                user_id=22,
                specialty="cardio",
                cabinet="102",
                user=SimpleNamespace(full_name="B"),
            ),
        ]
        repository = SimpleNamespace(
            list_active_doctors=lambda specialty: doctors,
            get_daily_queue=lambda day, specialist_id: SimpleNamespace(id=specialist_id),
            count_entries=lambda queue_id: 3 if queue_id == 11 else 2,
            get_doctor=lambda doctor_id: None,
            get_or_create_daily_queue=lambda **kwargs: None,
            save=lambda: None,
            rollback=lambda: None,
        )
        service = QueueLimitsApiService(
            db=None,
            repository=repository,
            get_settings=lambda db: {"max_per_day": {"cardio": 10}, "start_numbers": {}},
            update_settings=lambda db, settings, user_id: None,
        )

        result = service.get_queue_limits(specialty=None)

        assert len(result) == 1
        assert result[0]["specialty"] == "cardio"
        assert result[0]["current_usage"] == 5
        assert result[0]["max_per_day"] == 10

    def test_set_doctor_queue_limit_raises_when_doctor_missing(self):
        repository = SimpleNamespace(
            list_active_doctors=lambda specialty: [],
            get_daily_queue=lambda **kwargs: None,
            count_entries=lambda queue_id: 0,
            get_doctor=lambda doctor_id: None,
            get_or_create_daily_queue=lambda **kwargs: None,
            save=lambda: None,
            rollback=lambda: None,
        )
        service = QueueLimitsApiService(
            db=None,
            repository=repository,
            get_settings=lambda db: {},
            update_settings=lambda db, settings, user_id: None,
        )

        with pytest.raises(ValueError, match="DOCTOR_NOT_FOUND"):
            service.set_doctor_queue_limit(
                limit_data=SimpleNamespace(
                    doctor_id=100,
                    day=date(2026, 2, 14),
                    max_online_entries=7,
                )
            )

    def test_reset_queue_limits_resets_all_specialties(self):
        updates: list[dict] = []
        service = QueueLimitsApiService(
            db="db",
            repository=SimpleNamespace(rollback=lambda: None),
            get_settings=lambda db: {"max_per_day": {"cardio": 20}, "start_numbers": {"cardio": 5}},
            update_settings=lambda db, settings, user_id: updates.append(
                {"db": db, "settings": settings, "user_id": user_id}
            ),
        )

        result = service.reset_queue_limits(specialty=None, current_user_id=7)

        assert result["success"] is True
        assert updates[0]["user_id"] == 7
        assert updates[0]["settings"]["max_per_day"] == {}
        assert updates[0]["settings"]["start_numbers"] == {}
