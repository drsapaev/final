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


@pytest.mark.unit
@pytest.mark.parametrize('source_id', [None, 55])
def test_expected_visit_rejects_unproven_or_other_source_before_lock(source_id):
    class Repository:
        def get_appointment(self, appointment_id):
            return _appointment(source_visit_id=source_id)

        def lock_source_visit(self, visit_id):
            raise AssertionError('must not lock an unrelated Visit')

        def list_visits_for_appointment(self, appointment):
            raise AssertionError('legacy heuristics cannot prove payment binding')

    with pytest.raises(CanonicalVisitResolutionError) as exc:
        CanonicalVisitService(db=None, repository=Repository()).resolve_canonical_visit(
            12, create_if_missing=False, expected_visit_id=44
        )
    assert exc.value.status_code == 409


@pytest.mark.unit
def test_expected_visit_rechecks_source_after_appointment_lock():
    visit = SimpleNamespace(id=44, patient_id=5, encounter_id=None)

    class Repository:
        def get_appointment(self, appointment_id):
            return _appointment(source_visit_id=44)

        def lock_source_visit(self, visit_id):
            assert visit_id == 44
            return visit

        def lock_appointment(self, appointment_id):
            return _appointment(source_visit_id=55, encounter_id=None)

    with pytest.raises(CanonicalVisitResolutionError) as exc:
        CanonicalVisitService(db=None, repository=Repository()).resolve_canonical_visit(
            12, create_if_missing=False, expected_visit_id=44
        )
    assert exc.value.status_code == 409


@pytest.mark.unit
def test_expected_visit_accepts_consistent_locked_source():
    visit = SimpleNamespace(id=44, patient_id=5, encounter_id=None)

    class Repository:
        def get_appointment(self, appointment_id):
            return _appointment(source_visit_id=44)

        def lock_source_visit(self, visit_id):
            return visit

        def lock_appointment(self, appointment_id):
            return _appointment(source_visit_id=44, encounter_id=None)

    assert CanonicalVisitService(db=None, repository=Repository()).resolve_canonical_visit(
        12, create_if_missing=False, expected_visit_id=44
    ) == 44
