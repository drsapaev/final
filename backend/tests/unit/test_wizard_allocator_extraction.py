from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

import pytest

from app.services.morning_assignment import MorningAssignmentPreparedQueueAssignment
from app.services.registrar_wizard_queue_assignment_service import (
    RegistrarWizardQueueAssignmentService,
)


@dataclass
class _FakeVisit:
    id: int
    visit_date: date
    status: str = "confirmed"


class _FakeAssignmentService:
    def __init__(self, queue_tags, prepared_assignments, errors=None):
        self.queue_tags = queue_tags
        self.prepared_assignments = prepared_assignments
        self.errors = errors or {}
        self.calls = []

    def _get_visit_queue_tags(self, visit):
        return self.queue_tags.get(visit.id, set())

    def prepare_wizard_queue_assignment(self, visit, queue_tag, target_day, *, source):
        self.calls.append((visit.id, queue_tag, target_day, source))
        key = (visit.id, queue_tag)
        if key in self.errors:
            raise self.errors[key]
        return self.prepared_assignments.get(key)


@pytest.mark.unit
def test_assign_same_day_queue_numbers_uses_extracted_wizard_seam():
    today = date.today()
    visit = _FakeVisit(id=101, visit_date=today)
    fake_assignment_service = _FakeAssignmentService(
        queue_tags={101: {"cardiology_common"}},
        prepared_assignments={
            (101, "cardiology_common"): MorningAssignmentPreparedQueueAssignment(
                assignment={"queue_tag": "cardiology_common", "number": 17, "queue_id": 5}
            )
        },
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
    assert fake_assignment_service.calls == [(101, "cardiology_common", today, "desk")]


@pytest.mark.unit
def test_assign_same_day_queue_numbers_preserves_safe_behavior_for_empty_and_failed_assignments():
    today = date.today()
    future_visit = _FakeVisit(id=201, visit_date=today + timedelta(days=1))
    same_day_visit = _FakeVisit(id=202, visit_date=today)
    failed_visit = _FakeVisit(id=203, visit_date=today)
    fake_assignment_service = _FakeAssignmentService(
        queue_tags={202: {"cardiology_common"}, 203: {"cardiology_common"}},
        prepared_assignments={},
        errors={(203, "cardiology_common"): RuntimeError("allocation failed")},
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
        (202, "cardiology_common", today, "desk"),
        (203, "cardiology_common", today, "desk"),
    ]
