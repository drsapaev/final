"""Completion evidence and batch rollback for synthetic SQLite visits."""
from __future__ import annotations

from datetime import date
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.api.v1.endpoints.visits import set_status
from app.db.base_class import Base
from app.models.visit import Visit, VisitService
from app.services import emr_completion_policy, visit_completion_evidence
from app.services.batch_patient_service import (
    BatchPatientService,
    BatchUpdateRequest,
    EntryAction,
)
from app.services.visit_completion_evidence import (
    RepeatEvidenceBusy,
    capture_completion_evidence,
)
from tests.integration.test_docsched_schedule_next_integrity import (
    _make_patient,
    _make_service,
)
from tests.integration.test_repeat_completion_catalog_race_pg import _case


@pytest.mark.parametrize("consultation", [True, False])
def test_completion_freezes_current_catalog_classification(db_session, test_doctor, consultation):
    patient = _make_patient(db_session)
    service = _make_service(db_session, is_consultation=consultation)
    test_doctor.repeat_owner_generation = 11
    visit = Visit(patient_id=patient.id, doctor_id=test_doctor.id, visit_date=date(2030, 1, 1),
                  status="in_progress", source="desk", discount_mode="none", repeat_evidence_generation=13,
                  repeat_assigned_doctor_user_id=test_doctor.user_id, repeat_assigned_owner_generation=11)
    db_session.add(visit)
    db_session.flush()
    db_session.add(VisitService(visit_id=visit.id, service_id=service.id, name=service.name, qty=1, price=service.price))
    db_session.commit()
    capture_completion_evidence(db_session, visit)
    visit.status = "completed"
    db_session.commit()
    assert visit.repeat_proof_generation == 13
    assert visit.repeat_proof_doctor_user_id == test_doctor.user_id
    assert visit.repeat_proof_consultation is consultation
    service.is_consultation = not consultation
    db_session.commit()
    db_session.refresh(visit)
    assert visit.repeat_proof_consultation is consultation


def test_catalog_contention_aborts_entire_batch(db_session, monkeypatch):
    patient = _make_patient(db_session)
    day = date(2030, 1, 1)
    first = Visit(patient_id=patient.id, visit_date=day, status="open", source="desk", discount_mode="none")
    second = Visit(patient_id=patient.id, visit_date=day, status="in_progress", source="desk", discount_mode="none")
    db_session.add_all([first, second])
    db_session.commit()
    first_id, second_id = first.id, second.id
    monkeypatch.setattr(emr_completion_policy, "require_saved_emr_for_visit", lambda *args, **kwargs: None)

    def contention(db, visit):
        db.rollback()
        raise RepeatEvidenceBusy()

    monkeypatch.setattr(visit_completion_evidence, "capture_completion_evidence", contention)
    request = BatchUpdateRequest(entries=[
        EntryAction(id=first_id, entry_type="visit", action="update", status="in_progress"),
        EntryAction(id=second_id, entry_type="visit", action="update", status="completed"),
    ])
    with pytest.raises(RepeatEvidenceBusy) as error:
        BatchPatientService(db_session).batch_update(patient.id, day, request, actor_user_id=1)
    assert error.value.status_code == 409
    db_session.expire_all()
    assert db_session.get(Visit, first_id).status == "open"
    assert db_session.get(Visit, second_id).status == "in_progress"


def test_sqlite_writer_conflict_rolls_back_completion(tmp_path):
    import app.db.base  # noqa: F401 — register full metadata

    engine = create_engine(f"sqlite:///{tmp_path / 'synthetic.sqlite'}", connect_args={"timeout": 0.1})
    try:
        Base.metadata.create_all(engine)
        visit_id, service_id = _case(engine)
        with Session(engine) as writer, Session(engine) as completing:
            writer.execute(text("UPDATE services SET is_consultation=false WHERE id=:id"), {"id": service_id})
            visit = completing.get(Visit, visit_id)
            visit.status = "completed"
            with pytest.raises(RepeatEvidenceBusy) as error:
                capture_completion_evidence(completing, visit)
            assert error.value.status_code == 409
            writer.rollback()
        with Session(engine) as verify:
            assert verify.get(Visit, visit_id).status == "in_progress"
            assert verify.get(Visit, visit_id).repeat_proof_generation is None
    finally:
        engine.dispose()


def test_direct_status_cas_maps_sqlite_contention_to_retry(tmp_path):
    import app.db.base  # noqa: F401 — register full metadata

    engine = create_engine(f"sqlite:///{tmp_path / 'direct.sqlite'}", connect_args={"timeout": 0.1})
    try:
        Base.metadata.create_all(engine)
        visit_id, service_id = _case(engine)
        with Session(engine) as writer, Session(engine) as completing:
            writer.execute(text("UPDATE services SET is_consultation=false WHERE id=:id"), {"id": service_id})
            with pytest.raises(RepeatEvidenceBusy) as error:
                set_status(visit_id, "completed", db=completing,
                           current_user=SimpleNamespace(role="Admin", is_superuser=False))
            assert error.value.status_code == 409
            writer.rollback()
        with Session(engine) as verify:
            assert verify.get(Visit, visit_id).status == "in_progress"
            assert verify.get(Visit, visit_id).repeat_proof_generation is None
    finally:
        engine.dispose()
