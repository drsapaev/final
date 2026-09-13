from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from types import SimpleNamespace

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
        lifecycle_service_factory=lambda db: SimpleNamespace(
            activate_confirmed_visit=lambda visit_id, current_user=None, commit=False: None
        ),
    )

    queue_numbers = service.assign_same_day_queue_numbers(
        [visit],
        target_day=today,
        source="desk",
    )

    assert queue_numbers == {
        101: [{"queue_tag": "cardiology_common", "number": 17, "queue_id": 5}]
    }
    assert visit.status == "confirmed"  # Gate C: status set by VisitLifecycleService, not directly
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
        lifecycle_service_factory=lambda db: SimpleNamespace(
            activate_confirmed_visit=lambda visit_id, current_user=None, commit=False: None
        ),
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


@pytest.mark.unit
def test_cart_locks_all_tag_scopes_sorted_before_any_prepare(monkeypatch):
    """QD-2E P1: the wizard cart takes EVERY (day, tag) claim scope of
    the whole cart, in sorted order, BEFORE the first
    prepare_wizard_queue_assignment (i.e. before any routing/owner
    lookup/write) — the single external cart commit stays untouched,
    while two concurrent carts (or a cart and any single-tag writer)
    can no longer hold overlapping scopes in inverted orders.
    """
    import app.services.registrar_wizard_queue_assignment_service as wizard_module

    today = date.today()
    multi_tag_visit = _FakeVisit(id=401, visit_date=today)
    single_tag_visit = _FakeVisit(id=402, visit_date=today)
    future_visit = _FakeVisit(id=403, visit_date=today + timedelta(days=1))

    events: list[tuple[str, object]] = []

    class _RecordingAssignmentService(_FakeAssignmentService):
        def _get_visit_queue_tags(self, visit):
            # Scope collection itself is part of the locking phase.
            events.append(("collect", visit.id))
            return super()._get_visit_queue_tags(visit)

        def prepare_wizard_queue_assignment(self, visit, queue_tag, target_day, *, source):
            events.append(("prepare", (visit.id, queue_tag)))
            return super().prepare_wizard_queue_assignment(
                visit, queue_tag, target_day, source=source
            )

    fake_assignment_service = _RecordingAssignmentService(
        queue_tags={
            401: {"cardio", "lab"},
            402: {"derma"},
            403: {"future_tag"},
        },
        prepared_assignments={
            (401, "cardio"): MorningAssignmentPreparedQueueAssignment(
                assignment={"queue_tag": "cardio", "number": 1, "queue_id": 5}
            ),
            (401, "lab"): MorningAssignmentPreparedQueueAssignment(
                assignment={"queue_tag": "lab", "number": 2, "queue_id": 6}
            ),
            (402, "derma"): MorningAssignmentPreparedQueueAssignment(
                assignment={"queue_tag": "derma", "number": 3, "queue_id": 7}
            ),
        },
    )

    def _recording_lock(_db, queue_tag, day):
        events.append(("lock", (day, queue_tag)))

    monkeypatch.setattr(wizard_module, "lock_queue_tag_claim_scope", _recording_lock)

    service = RegistrarWizardQueueAssignmentService(
        db=object(),
        assignment_service_factory=lambda _: fake_assignment_service,
        lifecycle_service_factory=lambda db: SimpleNamespace(
            activate_confirmed_visit=lambda visit_id, current_user=None, commit=False: None
        ),
    )

    queue_numbers = service.assign_same_day_queue_numbers(
        [multi_tag_visit, single_tag_visit, future_visit],
        target_day=today,
        source="desk",
    )

    # The cart still materializes through the single external
    # transaction (all assignments returned).
    assert queue_numbers == {
        401: [
            {"queue_tag": "cardio", "number": 1, "queue_id": 5},
            {"queue_tag": "lab", "number": 2, "queue_id": 6},
        ],
        402: [{"queue_tag": "derma", "number": 3, "queue_id": 7}],
    }

    lock_events = [payload for kind, payload in events if kind == "lock"]
    prepare_events = [payload for kind, payload in events if kind == "prepare"]

    # Every eligible cart scope is locked exactly ONCE, in sorted
    # (day, tag) order; the future visit's tag is not part of the scope.
    assert lock_events == [
        (today, "cardio"),
        (today, "derma"),
        (today, "lab"),
    ], lock_events

    # All locks happen BEFORE the first prepare call.
    first_prepare_index = next(
        index for index, (kind, _) in enumerate(events) if kind == "prepare"
    )
    last_lock_index = max(
        index for index, (kind, _) in enumerate(events) if kind == "lock"
    )
    assert last_lock_index < first_prepare_index, events
    assert len(prepare_events) == 3
