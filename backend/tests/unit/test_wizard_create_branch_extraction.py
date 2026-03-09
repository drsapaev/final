from __future__ import annotations

from datetime import date
from types import SimpleNamespace

import pytest

from app.services.morning_assignment import (
    MorningAssignmentCreateBranchHandoff,
    MorningAssignmentPreparedQueueAssignment,
)
from app.services.registrar_wizard_queue_assignment_service import (
    RegistrarWizardQueueAssignmentService,
)


class _FakeVisit:
    def __init__(self, *, visit_id: int, visit_date: date, status: str = "confirmed") -> None:
        self.id = visit_id
        self.visit_date = visit_date
        self.status = status


class _FakeAssignmentService:
    def __init__(self, prepared_assignments):
        self.prepared_assignments = prepared_assignments
        self.calls = []

    def _get_visit_queue_tags(self, visit):
        return {"cardiology_common"}

    def prepare_wizard_queue_assignment(self, visit, queue_tag, target_day, *, source):
        self.calls.append((visit.id, queue_tag, target_day, source))
        return self.prepared_assignments[(visit.id, queue_tag)]


@pytest.mark.unit
def test_assign_same_day_queue_numbers_uses_explicit_create_branch_handoff():
    today = date.today()
    visit = _FakeVisit(visit_id=301, visit_date=today)
    create_handoff = MorningAssignmentCreateBranchHandoff(
        queue_tag="cardiology_common",
        daily_queue=SimpleNamespace(id=9),
        create_entry_kwargs={
            "daily_queue": SimpleNamespace(id=9),
            "patient_id": 77,
            "patient_name": "Wizard Patient",
            "phone": "+998901112233",
            "visit_id": 301,
            "source": "desk",
            "status": "waiting",
            "queue_time": object(),
            "services": [{"id": 1, "code": "K01", "name": "Consult", "price": 100000.0}],
            "service_codes": ["K01"],
            "auto_number": True,
            "commit": False,
        },
    )
    fake_assignment_service = _FakeAssignmentService(
        {
            (301, "cardiology_common"): MorningAssignmentPreparedQueueAssignment(
                create_handoff=create_handoff
            )
        }
    )
    captured_handoffs = []

    service = RegistrarWizardQueueAssignmentService(
        db=object(),
        assignment_service_factory=lambda _: fake_assignment_service,
        create_entry_allocator=lambda handoff: (
            captured_handoffs.append(handoff) or SimpleNamespace(number=23)
        ),
    )

    queue_numbers = service.assign_same_day_queue_numbers(
        [visit],
        target_day=today,
        source="desk",
    )

    assert queue_numbers == {
        301: [
            {
                "queue_tag": "cardiology_common",
                "queue_id": 9,
                "number": 23,
                "status": "assigned",
            }
        ]
    }
    assert visit.status == "open"
    assert fake_assignment_service.calls == [(301, "cardiology_common", today, "desk")]
    assert captured_handoffs == [create_handoff]
