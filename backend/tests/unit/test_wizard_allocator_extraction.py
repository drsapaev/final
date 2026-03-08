from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

import pytest

from app.services.registrar_wizard_queue_assignment_service import (
    RegistrarWizardQueueAssignmentService,
)


@dataclass
class _FakeVisit:
    id: int
    visit_date: date
    status: str = "confirmed"


class _FakeAssignmentService:
    def __init__(self, responses, errors=None):
        self.responses = responses
        self.errors = errors or {}
        self.calls = []

    def _assign_queues_for_visit(self, visit, target_day, *, source):
        self.calls.append((visit.id, target_day, source))
        if visit.id in self.errors:
            raise self.errors[visit.id]
        return self.responses.get(visit.id, [])


@pytest.mark.unit
def test_assign_same_day_queue_numbers_uses_extracted_wizard_seam():
    today = date.today()
    visit = _FakeVisit(id=101, visit_date=today)
    fake_assignment_service = _FakeAssignmentService(
        responses={101: [{"queue_tag": "cardiology_common", "number": 17, "queue_id": 5}]}
    )

    service = RegistrarWizardQueueAssignmentService(
        db=object(),
        assignment_service_factory=lambda _: fake_assignment_service,
    )

    queue_numbers = service.assign_same_day_queue_numbers(
        [visit],
        target_day=today,
        source="desk",
    )

    assert queue_numbers == {
        101: [{"queue_tag": "cardiology_common", "number": 17, "queue_id": 5}]
    }
    assert visit.status == "open"
    assert fake_assignment_service.calls == [(101, today, "desk")]


@pytest.mark.unit
def test_assign_same_day_queue_numbers_preserves_safe_behavior_for_empty_and_failed_assignments():
    today = date.today()
    future_visit = _FakeVisit(id=201, visit_date=today + timedelta(days=1))
    same_day_visit = _FakeVisit(id=202, visit_date=today)
    failed_visit = _FakeVisit(id=203, visit_date=today)
    fake_assignment_service = _FakeAssignmentService(
        responses={202: []},
        errors={203: RuntimeError("allocation failed")},
    )

    service = RegistrarWizardQueueAssignmentService(
        db=object(),
        assignment_service_factory=lambda _: fake_assignment_service,
    )

    queue_numbers = service.assign_same_day_queue_numbers(
        [future_visit, same_day_visit, failed_visit],
        target_day=today,
        source="desk",
    )

    assert queue_numbers == {}
    assert future_visit.status == "confirmed"
    assert same_day_visit.status == "confirmed"
    assert failed_visit.status == "confirmed"
    assert fake_assignment_service.calls == [
        (202, today, "desk"),
        (203, today, "desk"),
    ]
