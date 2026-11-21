"""Synthetic standalone encounter creation and transaction boundaries."""
from __future__ import annotations

import os
from datetime import date
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.crud.visit import create_visit
from app.models.encounter import Encounter
from app.models.patient import Patient
from app.models.visit import Visit
from app.services.encounter_creation import (
    EncounterCreationError,
    create_standalone_encounter,
    resolve_new_encounter,
)
from app.services.visits_api_service import VisitsApiService


def _patient(db, suffix: str) -> Patient:
    patient = Patient(first_name="SYNTHETIC-Encounter", last_name=f"SYNTHETIC-{suffix}")
    db.add(patient)
    db.flush()
    return patient


def _payload(patient_id: int | None) -> SimpleNamespace:
    return SimpleNamespace(patient_id=patient_id, doctor_id=None, planned_date=date.today(), notes=None, source="desk")


def test_crud_without_explicit_encounter_stays_unresolved(db_session):
    patient = _patient(db_session, "UNRESOLVED")
    visit = create_visit(db_session, patient.id, commit=False)
    assert visit.encounter_id is None
    assert db_session.query(Encounter).count() == 0


def test_new_group_is_shared_only_inside_its_creating_transaction(db_session):
    patient = _patient(db_session, "GROUP")
    group = create_standalone_encounter(db_session, patient_id=patient.id)
    first = create_visit(db_session, patient.id, encounter_id=group.id, commit=False)
    second = create_visit(db_session, patient.id, encounter_id=group.id, commit=False)
    assert first.encounter_id == second.encounter_id == group.id
    assert group.patient_id == patient.id and group.provenance == "new"
    db_session.commit()
    with pytest.raises(EncounterCreationError):
        resolve_new_encounter(db_session, patient_id=patient.id, encounter_id=group.id)


def test_explicit_group_requires_same_patient_and_not_legacy(db_session):
    first = _patient(db_session, "FIRST")
    second = _patient(db_session, "SECOND")
    group = create_standalone_encounter(db_session, patient_id=first.id)
    with pytest.raises(EncounterCreationError):
        create_visit(db_session, second.id, encounter_id=group.id, commit=False)
    group.provenance = "legacy_unresolved"
    # The resolver must flush this pending change, rather than refresh over it.
    with pytest.raises(EncounterCreationError):
        create_visit(db_session, first.id, encounter_id=group.id, commit=False)
    assert group.provenance == "legacy_unresolved"
    assert db_session.query(Visit).count() == 0


def test_nested_rollback_cannot_reuse_marker_even_when_pk_is_reused(db_session):
    patient = _patient(db_session, "SAVEPOINT")
    nested = db_session.begin_nested()
    old = create_standalone_encounter(db_session, patient_id=patient.id)
    old_id = old.id
    nested.rollback()
    replacement = Encounter(id=old_id, patient_id=patient.id, provenance="new")
    db_session.add(replacement)
    db_session.flush()
    with pytest.raises(EncounterCreationError):
        resolve_new_encounter(db_session, patient_id=patient.id, encounter_id=old_id)


def test_root_rollback_cannot_reuse_previous_marker(db_session):
    patient = _patient(db_session, "ROLLBACK")
    db_session.commit()
    group = create_standalone_encounter(db_session, patient_id=patient.id)
    group_id = group.id
    db_session.rollback()
    replacement = Encounter(id=group_id, patient_id=patient.id, provenance="new")
    db_session.add(replacement)
    db_session.flush()
    with pytest.raises(EncounterCreationError):
        resolve_new_encounter(db_session, patient_id=patient.id, encounter_id=group_id)


def test_pending_encounter_deletion_cannot_be_used(db_session):
    patient = _patient(db_session, "DELETED")
    group = create_standalone_encounter(db_session, patient_id=patient.id)
    db_session.delete(group)
    with pytest.raises(EncounterCreationError):
        resolve_new_encounter(db_session, patient_id=patient.id, encounter_id=group.id)


def test_group_and_visit_rollback_together_without_internal_commit(db_session):
    patient = _patient(db_session, "ATOMIC")
    db_session.commit()
    group = create_standalone_encounter(db_session, patient_id=patient.id)
    create_visit(db_session, patient.id, encounter_id=group.id, commit=False)
    db_session.rollback()
    assert db_session.query(Encounter).filter(Encounter.patient_id == patient.id).count() == 0
    assert db_session.query(Visit).filter(Visit.patient_id == patient.id).count() == 0


def test_another_session_cannot_use_uncommitted_creation_marker(db_session, test_db):
    from sqlalchemy.orm import Session

    patient = _patient(db_session, "SESSION")
    group = create_standalone_encounter(db_session, patient_id=patient.id)
    with Session(test_db) as other:
        with pytest.raises(EncounterCreationError):
            resolve_new_encounter(other, patient_id=patient.id, encounter_id=group.id)


@pytest.mark.parametrize("use_crud", [False, True])
def test_api_service_creates_distinct_patient_scoped_encounters(
    db_session, admin_user, monkeypatch, use_crud
):
    monkeypatch.setenv("USE_CRUD_VISITS", "true" if use_crud else "false")
    patient = _patient(db_session, "API")
    db_session.commit()
    service = VisitsApiService(db_session)
    first = service.create_visit(request=None, payload=_payload(patient.id), current_user=admin_user)
    second = service.create_visit(request=None, payload=_payload(patient.id), current_user=admin_user)
    visits = [db_session.get(Visit, first["id"]), db_session.get(Visit, second["id"])]
    assert visits[0].encounter_id != visits[1].encounter_id
    for visit in visits:
        encounter = db_session.get(Encounter, visit.encounter_id)
        assert encounter.patient_id == patient.id and encounter.provenance == "new"


@pytest.mark.parametrize("use_crud", [False, True])
def test_audit_failure_rolls_back_visit_and_encounter(
    db_session, admin_user, monkeypatch, use_crud
):
    monkeypatch.setenv("USE_CRUD_VISITS", "true" if use_crud else "false")
    patient = _patient(db_session, "AUDIT")
    db_session.commit()
    service = VisitsApiService(db_session)
    def fail_audit(**_kwargs):
        raise RuntimeError("synthetic audit failure")
    monkeypatch.setattr(service.repository, "log_critical_change", fail_audit)
    with pytest.raises(RuntimeError, match="synthetic audit failure"):
        service.create_visit(request=None, payload=_payload(patient.id), current_user=admin_user)
    assert db_session.query(Encounter).filter(Encounter.patient_id == patient.id).count() == 0
    assert db_session.query(Visit).filter(Visit.patient_id == patient.id).count() == 0


@pytest.mark.parametrize("use_crud", [False, True])
@pytest.mark.parametrize("patient_id", [None, 987654321])
def test_missing_patient_returns_validation_error_without_encounter(db_session, admin_user, monkeypatch, use_crud, patient_id):
    monkeypatch.setenv("USE_CRUD_VISITS", "true" if use_crud else "false")
    service = VisitsApiService(db_session)
    with pytest.raises(HTTPException) as error:
        service.create_visit(request=None, payload=_payload(patient_id), current_user=admin_user)
    assert error.value.status_code == 422
    assert db_session.query(Encounter).count() == 0


def test_http_standalone_visit_has_linked_encounter(client, db_session, auth_headers):
    patient = _patient(db_session, "HTTP")
    db_session.commit()
    response = client.post(
        "/api/v1/visits/visits",
        json={"patient_id": patient.id, "planned_date": date.today().isoformat()},
        headers=auth_headers,
    )
    assert response.status_code == 201, response.text
    visit = db_session.get(Visit, response.json()["id"])
    encounter = db_session.get(Encounter, visit.encounter_id)
    assert encounter.patient_id == patient.id and encounter.provenance == "new"


@pytest.fixture(scope="module")
def standalone_pg_engine():
    from sqlalchemy import create_engine
    from sqlalchemy.engine import make_url
    from sqlalchemy.schema import CreateSchema, DropSchema

    raw_url = os.environ.get("DATABASE_URL", "")
    if not raw_url or make_url(raw_url).get_backend_name() != "postgresql":
        pytest.skip("requires a disposable PostgreSQL database")
    url = make_url(raw_url)
    if not (url.database or "").startswith("clinic_test") and os.environ.get("CI", "").lower() != "true":
        pytest.skip("requires a disposable clinic_test database")
    schema = "test_encounter_core_" + uuid4().hex
    admin_engine = create_engine(url)
    with admin_engine.begin() as conn:
        conn.execute(CreateSchema(schema))
    engine = create_engine(url, connect_args={"options": f"-csearch_path={schema} -clock_timeout=10000"})
    try:
        import app.db.base  # noqa: F401
        from app.db.base_class import Base
        Base.metadata.create_all(engine)
        yield engine
    finally:
        engine.dispose()
        with admin_engine.begin() as conn:
            conn.execute(DropSchema(schema, cascade=True))
        admin_engine.dispose()


def test_pg_group_commit_and_rollback_are_atomic(standalone_pg_engine):
    from sqlalchemy.orm import Session

    with Session(standalone_pg_engine, expire_on_commit=False) as db:
        patient = _patient(db, "PG-ATOMIC")
        db.commit()
        patient_id = patient.id
        group = create_standalone_encounter(db, patient_id=patient_id)
        first = create_visit(db, patient_id, encounter_id=group.id, commit=False)
        second = create_visit(db, patient_id, encounter_id=group.id, commit=False)
        assert first.encounter_id == second.encounter_id == group.id
        db.rollback()
        assert db.query(Encounter).filter(Encounter.patient_id == patient_id).count() == 0
        assert db.query(Visit).filter(Visit.patient_id == patient_id).count() == 0

        committed = create_standalone_encounter(db, patient_id=patient_id)
        first = create_visit(db, patient_id, encounter_id=committed.id, commit=False)
        second = create_visit(db, patient_id, encounter_id=committed.id, commit=False)
        group_id = committed.id
        db.commit()
        with pytest.raises(EncounterCreationError):
            resolve_new_encounter(db, patient_id=patient_id, encounter_id=group_id)
        assert db.query(Visit).filter(Visit.encounter_id == group_id).count() == 2


def test_pg_audit_failure_leaves_no_partial_standalone(standalone_pg_engine, monkeypatch):
    from sqlalchemy.orm import Session

    with Session(standalone_pg_engine, expire_on_commit=False) as db:
        patient = _patient(db, "PG-AUDIT")
        db.commit()
        service = VisitsApiService(db)
        def fail_audit(**_kwargs):
            raise RuntimeError("synthetic audit failure")
        monkeypatch.setattr(service.repository, "log_critical_change", fail_audit)
        for use_crud in (False, True):
            monkeypatch.setenv("USE_CRUD_VISITS", "true" if use_crud else "false")
            with pytest.raises(RuntimeError, match="synthetic audit failure"):
                service.create_visit(request=None, payload=_payload(patient.id), current_user=SimpleNamespace(id=1))
            assert db.query(Encounter).filter(Encounter.patient_id == patient.id).count() == 0
            assert db.query(Visit).filter(Visit.patient_id == patient.id).count() == 0
