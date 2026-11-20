"""Unit checks of the transaction-bound 0107 payment fence."""
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from fastapi import HTTPException

from app.models.all_free_request import AllFreeRequest
from app.models.encounter import Encounter
from app.models.visit import Visit
from app.services.all_free_guard import lock_visit_without_pending


def _case(db, patient, actor, status):
    encounter = Encounter(patient_id=patient.id, provenance="new")
    db.add(encounter)
    db.flush()
    visit = Visit(patient_id=patient.id, encounter_id=encounter.id, status="pending_confirmation", confirmation_context_epoch=7)
    db.add(visit)
    db.flush()
    if status is not None:
        request = AllFreeRequest(
            visit_id=visit.id, patient_id=patient.id, encounter_id=encounter.id,
            visit_id_snapshot=visit.id, patient_id_snapshot=patient.id, encounter_id_snapshot=encounter.id,
            visit_context_epoch=7, encounter_generation=encounter.generation, baseline_total=Decimal("10.00"),
            status=status, requested_by_user_id=actor.id, requested_by_user_id_snapshot=actor.id,
            requested_by_role_snapshot="Admin", policy_auto_approve=False,
            **({"decision_kind": "admin", "decided_by_user_id": actor.id,
                "decided_by_user_id_snapshot": actor.id, "decided_by_role_snapshot": "Admin",
                "decided_at": datetime.now(UTC)} if status == "rejected" else {}),
        )
        db.add(request)
    db.commit()
    return visit


def test_pending_request_denies_payment_and_preserves_visit(db_session, test_patient, admin_user):
    visit = _case(db_session, test_patient, admin_user, "pending")
    with pytest.raises(HTTPException) as error:
        lock_visit_without_pending(db_session, visit.id)
    assert error.value.status_code == 409
    assert db_session.get(Visit, visit.id).status == "pending_confirmation"


@pytest.mark.parametrize("status", [None, "rejected"])
def test_unrelated_or_rejected_visit_can_be_locked(db_session, test_patient, admin_user, status):
    visit = _case(db_session, test_patient, admin_user, status)
    assert lock_visit_without_pending(db_session, visit.id) is None


def test_dirty_visit_is_rejected_without_losing_pending_mutation(db_session, test_patient, admin_user):
    visit = _case(db_session, test_patient, admin_user, None)
    visit.notes = "synthetic caller mutation"
    with pytest.raises(HTTPException) as error:
        lock_visit_without_pending(db_session, visit.id)
    assert error.value.status_code == 409
    assert visit.notes == "synthetic caller mutation"


def test_dirty_request_is_rejected_without_losing_pending_mutation(db_session, test_patient, admin_user):
    visit = _case(db_session, test_patient, admin_user, "pending")
    request = db_session.query(AllFreeRequest).filter_by(visit_id=visit.id).one()
    request.baseline_total = Decimal("9.99")
    with pytest.raises(HTTPException) as error:
        lock_visit_without_pending(db_session, visit.id)
    assert error.value.status_code == 409
    assert request.baseline_total == Decimal("9.99")


def test_missing_request_table_fails_closed():
    import sqlalchemy as sa
    from sqlalchemy.orm import Session
    engine = sa.create_engine("sqlite://")
    try:
        with engine.begin() as connection:
            connection.execute(sa.text("CREATE TABLE visits (id INTEGER PRIMARY KEY)"))
        with Session(engine) as db:
            with pytest.raises(HTTPException) as error:
                lock_visit_without_pending(db, 1)
            assert error.value.status_code == 503
    finally:
        engine.dispose()


def test_sqlite_uncommitted_request_cannot_be_raced(tmp_path):
    import sqlalchemy as sa
    from sqlalchemy.orm import Session

    from app.db.base_class import Base
    from app.models.patient import Patient
    from app.models.user import User
    from app.services.all_free_policy import lock_all_free_policy

    engine = sa.create_engine(f"sqlite:///{tmp_path / 'allfree-guard.sqlite'}", connect_args={"timeout": 0.1})
    try:
        Base.metadata.create_all(engine)
        with Session(engine, expire_on_commit=False) as db:
            actor = User(username="synthetic-guard", hashed_password="!", role="Admin", is_active=True)
            patient = Patient(first_name="Synthetic", last_name="Guard")
            db.add_all([actor, patient])
            db.flush()
            visit = _case(db, patient, actor, None)
            ids = {"visit": visit.id, "patient": patient.id, "actor": actor.id, "encounter": visit.encounter_id}
        with Session(engine) as stager:
            lock_all_free_policy(stager)
            encounter = stager.get(Encounter, ids["encounter"])
            stager.add(AllFreeRequest(
                visit_id=ids["visit"], patient_id=ids["patient"], encounter_id=ids["encounter"],
                visit_id_snapshot=ids["visit"], patient_id_snapshot=ids["patient"], encounter_id_snapshot=ids["encounter"],
                visit_context_epoch=7, encounter_generation=encounter.generation, baseline_total=Decimal("10.00"),
                status="pending", requested_by_user_id=ids["actor"], requested_by_user_id_snapshot=ids["actor"],
                requested_by_role_snapshot="Admin", policy_auto_approve=False,
            ))
            stager.flush()
            with Session(engine) as payer:
                with pytest.raises(HTTPException) as error:
                    lock_visit_without_pending(payer, ids["visit"])
                assert error.value.status_code == 503
                payer.rollback()
            stager.commit()
        with Session(engine) as payer:
            with pytest.raises(HTTPException) as error:
                lock_visit_without_pending(payer, ids["visit"])
            assert error.value.status_code == 409
    finally:
        engine.dispose()
