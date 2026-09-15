from __future__ import annotations

from datetime import date
from types import SimpleNamespace

import pytest

import app.services.morning_assignment as morning_assignment_module
from app.crud.queue_owner_policy import QueueOwnerConfigurationError
from app.models.clinic import Doctor
from app.models.patient import Patient
from app.services.morning_assignment import (
    MorningAssignmentClaimError,
    MorningAssignmentService,
)
from app.services.queue_claim_service import (
    ActiveQueueClaim,
    QueueClaimConflictError,
)

_DAY = date(2026, 9, 12)


class _DoctorQuery:
    def __init__(self, doctor: SimpleNamespace) -> None:
        self._doctor = doctor

    def filter(self, *_criteria):
        return self

    def first(self):
        return self._doctor


class _DoctorOnlyDb:
    def __init__(self, doctor: SimpleNamespace) -> None:
        self._doctor = doctor
        self._patient = SimpleNamespace(
            id=77,
            first_name="Test",
            last_name="Patient",
            phone="+998901234567",
        )

    def query(self, model):
        if model is Doctor:
            return _DoctorQuery(self._doctor)
        if model is Patient:
            return _DoctorQuery(self._patient)
        raise AssertionError(f"Unexpected model query: {model}")


def _doctor(doctor_id: int) -> SimpleNamespace:
    return SimpleNamespace(
        id=doctor_id,
        cabinet="101",
        max_online_per_day=20,
    )


def _visit(*, doctor_id: int = 10) -> SimpleNamespace:
    return SimpleNamespace(id=301, patient_id=77, doctor_id=doctor_id)


def _claim(
    *,
    specialist_id: int | None,
    queue_resource_id: int | None = None,
    patient_id: int | None = None,
    visit_id: int | None = None,
):
    return ActiveQueueClaim(
        daily_queue=SimpleNamespace(
            id=9,
            specialist_id=specialist_id,
            queue_resource_id=queue_resource_id,
        ),
        entry=SimpleNamespace(
            id=41,
            number=17,
            patient_id=patient_id,
            visit_id=visit_id,
        ),
    )


@pytest.mark.unit
def test_prepare_rejects_existing_claim_owned_by_another_doctor(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db = _DoctorOnlyDb(_doctor(10))
    claim = _claim(specialist_id=11)
    calls: list[dict[str, object]] = []

    monkeypatch.setattr(
        morning_assignment_module,
        "resolve_tag_resource",
        lambda _db, _tag: None,
    )
    monkeypatch.setattr(
        morning_assignment_module,
        "lock_and_resolve_active_tag_claim",
        lambda _db, **kwargs: calls.append(kwargs) or claim,
    )

    with pytest.raises(QueueOwnerConfigurationError, match="different owner") as excinfo:
        MorningAssignmentService(db).prepare_wizard_queue_assignment(
            _visit(), "cardio", _DAY
        )

    assert isinstance(excinfo.value, MorningAssignmentClaimError)
    assert calls == [
        {
            "day": _DAY,
            "queue_tag": "cardio",
            "patient_id": 77,
            "phone": "+998901234567",
            # RQ-25.a.1 (S-22): the coordinator's legacy-phone bridge is
            # name-narrowed (patient_id stays the primary identity).
            "patient_name": "Patient Test",
        }
    ]


@pytest.mark.unit
def test_prepare_reuses_existing_claim_owned_by_resolved_doctor(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db = _DoctorOnlyDb(_doctor(10))
    # QD-2E review P1: the legacy-phone bridge resolves an ANONYMOUS row
    # (patient_id/visit_id NULL) — a successful reuse must BIND it to this
    # registration's patient and visit, not just return the number.
    claim = _claim(specialist_id=10)

    monkeypatch.setattr(
        morning_assignment_module,
        "resolve_tag_resource",
        lambda _db, _tag: None,
    )
    monkeypatch.setattr(
        morning_assignment_module,
        "lock_and_resolve_active_tag_claim",
        lambda _db, **_kwargs: claim,
    )

    prepared = MorningAssignmentService(db).prepare_wizard_queue_assignment(
        _visit(), "cardio", _DAY
    )

    assert prepared is not None
    assert prepared.create_handoff is None
    assert prepared.assignment == {
        "queue_tag": "cardio",
        "queue_id": 9,
        "number": 17,
        "status": "existing",
    }
    # the anonymous claim is now linked to THIS patient and visit
    assert claim.entry.patient_id == 77
    assert claim.entry.visit_id == 301


@pytest.mark.unit
def test_prepare_rejects_existing_claim_bound_to_another_visit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """QD-2E review P1: an active claim already bound to ANOTHER visit is a
    hard conflict — the existing binding is never silently rebound (the
    registration must not hijack another visit's ticket)."""
    db = _DoctorOnlyDb(_doctor(10))
    claim = _claim(specialist_id=10, patient_id=77, visit_id=555)

    monkeypatch.setattr(
        morning_assignment_module,
        "resolve_tag_resource",
        lambda _db, _tag: None,
    )
    monkeypatch.setattr(
        morning_assignment_module,
        "lock_and_resolve_active_tag_claim",
        lambda _db, **_kwargs: claim,
    )

    with pytest.raises(MorningAssignmentClaimError, match="another visit"):
        MorningAssignmentService(db).prepare_wizard_queue_assignment(
            _visit(), "cardio", _DAY
        )

    # the existing binding is preserved untouched
    assert claim.entry.visit_id == 555


@pytest.mark.unit
def test_prepare_rejects_existing_claim_bound_to_another_patient(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """QD-2E review P1 (belt-and-suspenders): a claim bound to another
    patient can never be adopted for this registration, even if a future
    coordinator change were to surface such a row."""
    db = _DoctorOnlyDb(_doctor(10))
    claim = _claim(specialist_id=10, patient_id=999, visit_id=555)

    monkeypatch.setattr(
        morning_assignment_module,
        "resolve_tag_resource",
        lambda _db, _tag: None,
    )
    monkeypatch.setattr(
        morning_assignment_module,
        "lock_and_resolve_active_tag_claim",
        lambda _db, **_kwargs: claim,
    )

    with pytest.raises(MorningAssignmentClaimError, match="another patient"):
        MorningAssignmentService(db).prepare_wizard_queue_assignment(
            _visit(), "cardio", _DAY
        )

    assert claim.entry.patient_id == 999
    assert claim.entry.visit_id == 555


@pytest.mark.unit
def test_prepare_keeps_existing_resource_claim_after_registry_deactivation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db = _DoctorOnlyDb(_doctor(10))
    claim = _claim(specialist_id=None, queue_resource_id=5)

    monkeypatch.setattr(
        morning_assignment_module,
        "resolve_tag_resource",
        lambda _db, _tag: None,
    )
    monkeypatch.setattr(
        morning_assignment_module,
        "lock_and_resolve_active_tag_claim",
        lambda _db, **_kwargs: claim,
    )

    prepared = MorningAssignmentService(db).prepare_wizard_queue_assignment(
        _visit(), "lab", _DAY
    )

    assert prepared is not None
    assert prepared.assignment == {
        "queue_tag": "lab",
        "queue_id": 9,
        "number": 17,
        "status": "existing",
    }
    # QD-2E review P1: the resource-surface reuse binds the anonymous claim
    # exactly like the doctor-axis reuse above.
    assert claim.entry.patient_id == 77
    assert claim.entry.visit_id == 301


@pytest.mark.unit
def test_prepare_maps_common_claim_conflict_to_morning_domain_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db = _DoctorOnlyDb(_doctor(10))

    monkeypatch.setattr(
        morning_assignment_module,
        "resolve_tag_resource",
        lambda _db, _tag: None,
    )

    def _raise_conflict(_db, **_kwargs):
        raise QueueClaimConflictError

    monkeypatch.setattr(
        morning_assignment_module,
        "lock_and_resolve_active_tag_claim",
        _raise_conflict,
    )

    with pytest.raises(MorningAssignmentClaimError, match="safely resolve"):
        MorningAssignmentService(db).prepare_wizard_queue_assignment(
            _visit(), "cardio", _DAY
        )
