from __future__ import annotations

from datetime import date, datetime
from types import SimpleNamespace

import pytest

from app.services.morning_assignment_api_service import MorningAssignmentApiService


@pytest.mark.unit
class TestMorningAssignmentApiService:
    def test_parse_target_date_handles_none_and_iso(self):
        assert MorningAssignmentApiService.parse_target_date(None) == date.today()
        assert MorningAssignmentApiService.parse_target_date("2026-02-14") == date(
            2026,
            2,
            14,
        )

    def test_parse_target_date_raises_for_invalid_date(self):
        with pytest.raises(ValueError):
            MorningAssignmentApiService.parse_target_date("bad-date")

    def test_manual_assignment_for_visits_returns_not_found_result(self, monkeypatch):
        class FakeMorningService:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc_val, exc_tb):
                return False

            def _assign_queues_for_visit(self, visit, visit_date):  # pragma: no cover
                return []

        monkeypatch.setattr(
            "app.services.morning_assignment_api_service.MorningAssignmentService",
            FakeMorningService,
        )

        committed = {"value": False}
        repository = SimpleNamespace(
            db="db",
            get_visit=lambda visit_id: None,
            get_patient=lambda patient_id: None,
            list_daily_queues=lambda day: [],
            count_queue_entries=lambda queue_id: 0,
            get_doctor=lambda doctor_id: None,
            commit=lambda: committed.__setitem__("value", True),
            rollback=lambda: None,
        )
        service = MorningAssignmentApiService(db=None, repository=repository)

        result = service.manual_assignment_for_visits(visit_ids=[10], force=False)

        assert result["success"] is True
        assert result["results"][0]["message"] == "Визит не найден"
        assert committed["value"] is True

    def test_get_queue_summary_payload_maps_queue_rows(self):
        queue = SimpleNamespace(
            id=1,
            queue_tag="cardio",
            specialist_id=7,
            active=True,
            opened_at=datetime(2026, 2, 14, 8, 0, 0),
        )
        repository = SimpleNamespace(
            db="db",
            get_visit=lambda visit_id: None,
            get_patient=lambda patient_id: None,
            list_daily_queues=lambda day: [queue],
            count_queue_entries=lambda queue_id: 4,
            get_doctor=lambda doctor_id: SimpleNamespace(
                user=SimpleNamespace(full_name="Doctor Name")
            ),
            commit=lambda: None,
            rollback=lambda: None,
        )
        service = MorningAssignmentApiService(db=None, repository=repository)

        payload = service.get_queue_summary_payload(target_date=date(2026, 2, 14))

        assert payload["queues_count"] == 1
        assert payload["total_entries"] == 4
        assert payload["queues"][0]["doctor_name"] == "Doctor Name"
