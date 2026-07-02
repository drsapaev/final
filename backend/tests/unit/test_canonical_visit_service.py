from __future__ import annotations

from datetime import date, datetime
from types import SimpleNamespace

import pytest

from app.services.canonical_visit_service import (
    CanonicalVisitResolutionError,
    CanonicalVisitService,
)


def _appointment(**overrides):
    payload = {
        "id": 12,
        "patient_id": 5,
        "doctor_id": 7,
        "appointment_date": date(2026, 3, 17),
        "appointment_time": "09:00",
        "status": "paid",
        "notes": "Follow-up",
        "department_id": 1,
        "created_at": datetime(2026, 3, 17, 9, 0, 0),
    }
    payload.update(overrides)
    return SimpleNamespace(**payload)


@pytest.mark.unit
class TestCanonicalVisitService:
    def test_returns_existing_visit_when_found(self):
        visit = SimpleNamespace(id=44)

        class Repository:
            def get_appointment(self, appointment_id):
                assert appointment_id == 12
                return _appointment()

            def list_visits_for_appointment(self, appointment):
                return [visit]

        service = CanonicalVisitService(db=None, repository=Repository())

        assert service.resolve_canonical_visit(12) == 44

    def test_raises_when_multiple_visit_candidates_exist(self):
        class Repository:
            def get_appointment(self, appointment_id):
                return _appointment()

            def list_visits_for_appointment(self, appointment):
                return [SimpleNamespace(id=1), SimpleNamespace(id=2)]

        service = CanonicalVisitService(db=None, repository=Repository())

        with pytest.raises(CanonicalVisitResolutionError) as exc_info:
            service.resolve_canonical_visit(12)

        assert exc_info.value.status_code == 409

    def test_creates_visit_when_missing_and_allowed(self):
        created_visit = SimpleNamespace(id=88)

        class Repository:
            def get_appointment(self, appointment_id):
                return _appointment(status="in_visit")

            def list_visits_for_appointment(self, appointment):
                return []

            def create_visit(self, visit):
                assert visit.patient_id == 5
                assert visit.status == "in_progress"
                return created_visit

        service = CanonicalVisitService(db=None, repository=Repository())

        assert service.resolve_canonical_visit(12) == 88

    def test_cancelled_appointment_fails_fast(self):
        class Repository:
            def get_appointment(self, appointment_id):
                return _appointment(status="cancelled")

            def list_visits_for_appointment(self, appointment):
                return []

        service = CanonicalVisitService(db=None, repository=Repository())

        with pytest.raises(CanonicalVisitResolutionError) as exc_info:
            service.resolve_canonical_visit(12)

        assert exc_info.value.status_code == 409
