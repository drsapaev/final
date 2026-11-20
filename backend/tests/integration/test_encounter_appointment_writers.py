"""Source Visit provenance for legacy appointment flow (synthetic records)."""
from __future__ import annotations

from datetime import date
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.api.v1.endpoints.appointment_flow import _resolve_appointment_and_visit
from app.models.appointment import Appointment
from app.models.clinic import Doctor
from app.models.encounter import Encounter
from app.models.visit import Visit
from app.services.appointment_flow_api_service import AppointmentFlowApiService
from app.services.canonical_visit_service import (
    CanonicalVisitResolutionError,
    CanonicalVisitService,
)


def _visit(db, patient, doctor, *, when='10:00', encounter=True):
    group = Encounter(patient_id=patient.id, provenance='new') if encounter else None
    if group:
        db.add(group)
        db.flush()
    visit = Visit(patient_id=patient.id, doctor_id=doctor.id,
                  visit_date=date(2026, 4, 1), visit_time=when,
                  status='open', encounter_id=group.id if group else None)
    db.add(visit)
    db.commit()
    return visit


def _resolve(db, visit):
    return AppointmentFlowApiService(db).resolve_appointment_from_visit(
        appointment_id=visit.id, emr_data=SimpleNamespace(appointment_id=0)
    )[0]


def test_source_propagates_and_replay_is_stable(db_session, test_patient, test_doctor):
    visit = _visit(db_session, test_patient, test_doctor)
    appointment = _resolve(db_session, visit)
    assert appointment.source_visit_id == visit.id
    assert appointment.encounter_id == visit.encounter_id
    assert _resolve(db_session, visit).id == appointment.id
    assert CanonicalVisitService(db_session).resolve_canonical_visit(appointment.id) == visit.id


def test_two_equal_looking_visits_do_not_share_a_source(db_session, test_patient, test_doctor):
    first = _visit(db_session, test_patient, test_doctor)
    second = _visit(db_session, test_patient, test_doctor)
    a = _resolve(db_session, first)
    b = _resolve(db_session, second)
    assert a.id != b.id
    assert a.encounter_id == first.encounter_id
    assert b.encounter_id == second.encounter_id
    assert CanonicalVisitService(db_session).resolve_canonical_visit(b.id) == second.id


def test_legacy_match_is_not_given_source_or_encounter(db_session, test_patient, test_doctor):
    visit = _visit(db_session, test_patient, test_doctor)
    appointment = Appointment(patient_id=visit.patient_id, doctor_id=visit.doctor_id,
                              appointment_date=visit.visit_date, appointment_time=visit.visit_time,
                              status='paid')
    db_session.add(appointment)
    db_session.commit()
    assert _resolve(db_session, visit).id == appointment.id
    assert appointment.source_visit_id is None
    assert appointment.encounter_id is None


def test_unknown_group_stays_unknown(db_session, test_patient, test_doctor):
    visit = _visit(db_session, test_patient, test_doctor, encounter=False)
    appointment = _resolve(db_session, visit)
    assert appointment.source_visit_id == visit.id
    assert appointment.encounter_id is None


def test_changed_source_context_is_refused(db_session, test_patient, test_doctor):
    visit = _visit(db_session, test_patient, test_doctor)
    appointment = _resolve(db_session, visit)
    # Metadata-only SQLite tests have no migration triggers; a stale source
    # must still be rejected by the resolver even if constraints were absent.
    appointment.encounter_id = None
    db_session.flush()
    with pytest.raises(CanonicalVisitResolutionError) as exc:
        CanonicalVisitService(db_session).resolve_canonical_visit(appointment.id)
    assert exc.value.status_code == 409


def test_other_doctor_cannot_create_from_visit(db_session, test_patient, test_doctor, test_doctor_user):
    db_session.add(Doctor(user_id=test_doctor_user.id, specialty="therapy", active=True))
    db_session.commit()
    visit = _visit(db_session, test_patient, test_doctor)
    # Avoid the existing ID namespace collision branch.
    assert db_session.get(Appointment, visit.id) is None
    with pytest.raises(HTTPException) as exc:
        _resolve_appointment_and_visit(db_session, visit.id, current_user=test_doctor_user)
    assert exc.value.status_code == 403
    assert db_session.query(Appointment).filter_by(source_visit_id=visit.id).count() == 0


def test_http_other_doctor_cannot_create_source_appointment(
    client, db_session, test_patient, test_doctor, test_doctor_user
):
    db_session.add(Doctor(user_id=test_doctor_user.id, specialty="therapy", active=True))
    db_session.commit()
    visit = _visit(db_session, test_patient, test_doctor)
    assert db_session.get(Appointment, visit.id) is None
    login = client.post("/api/v1/authentication/login", json={
        "username": test_doctor_user.username, "password": "doctor123"
    })
    assert login.status_code == 200
    response = client.get(
        f"/api/v1/appointments/{visit.id}/canonical-visit",
        headers={"Authorization": f"Bearer {login.json()['access_token']}"},
    )
    assert response.status_code == 403
    assert db_session.query(Appointment).filter_by(source_visit_id=visit.id).count() == 0


@pytest.fixture
def appointment_source_pg_engine():
    """Isolate all DDL and records in a disposable PostgreSQL test database."""
    import os
    import uuid

    from sqlalchemy import create_engine
    from sqlalchemy.engine import make_url
    from sqlalchemy.schema import CreateSchema, DropSchema

    from app.db.base import Base

    raw = os.environ.get('DATABASE_URL', '')
    if not raw or make_url(raw).get_backend_name() != 'postgresql':
        pytest.skip('requires disposable PostgreSQL')
    url = make_url(raw)
    if os.environ.get('CI', '').lower() != 'true' and not (url.database or '').startswith('clinic_test'):
        pytest.skip('requires an explicitly disposable clinic_test database')
    name = 'test_appointment_source_' + uuid.uuid4().hex
    admin = create_engine(url)
    with admin.begin() as connection:
        connection.execute(CreateSchema(name))
    engine = create_engine(url, connect_args={'options': f'-csearch_path={name} -cstatement_timeout=15000 -clock_timeout=15000'})
    try:
        Base.metadata.create_all(engine)
        yield engine
    finally:
        engine.dispose()
        with admin.begin() as connection:
            connection.execute(DropSchema(name, cascade=True))
        admin.dispose()


def _seed_pg(engine):
    from sqlalchemy.orm import Session

    from app.models.patient import Patient
    from app.models.user import User

    with Session(engine, expire_on_commit=False) as db:
        user = User(username='source-doctor', hashed_password='synthetic', role='Doctor', is_active=True)
        patient = Patient(first_name='Synthetic', last_name='Patient')
        db.add_all([user, patient])
        db.flush()
        doctor = Doctor(user_id=user.id, specialty='therapy', active=True)
        db.add(doctor)
        db.flush()
        encounter = Encounter(patient_id=patient.id, provenance='new')
        db.add(encounter)
        db.flush()
        visit = Visit(patient_id=patient.id, doctor_id=doctor.id, encounter_id=encounter.id,
                      visit_date=date(2026, 4, 1), visit_time='10:00', status='open')
        db.add(visit)
        db.commit()
        return user.id, doctor.id, visit.id


def test_pg_source_creation_is_serialized(appointment_source_pg_engine):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    from sqlalchemy.orm import Session

    engine = appointment_source_pg_engine
    _, _, visit_id = _seed_pg(engine)
    start = Barrier(2)

    def resolve():
        with Session(engine) as db:
            start.wait(timeout=10)
            return AppointmentFlowApiService(db).resolve_appointment_from_visit(
                appointment_id=visit_id, emr_data=SimpleNamespace(appointment_id=0)
            )[0].id

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(resolve) for _ in range(2)]
        ids = [future.result(timeout=20) for future in futures]
    assert ids[0] == ids[1]
    with Session(engine) as db:
        assert db.query(Appointment).filter_by(source_visit_id=visit_id).count() == 1


def test_pg_reassignment_during_source_creation_is_rechecked(appointment_source_pg_engine):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event

    from sqlalchemy.orm import Session

    from app.api.v1.endpoints.appointment_flow import _prepare_visit_doctor_access
    from app.models.user import User
    from app.repositories.appointment_flow_api_repository import (
        AppointmentFlowApiRepository,
    )

    engine = appointment_source_pg_engine
    user_id, _, visit_id = _seed_pg(engine)
    before_visit_lock = Event()

    class InstrumentedRepository(AppointmentFlowApiRepository):
        def get_locked_visit(self, source_id):
            before_visit_lock.set()
            return super().get_locked_visit(source_id)

    def resolve():
        with Session(engine) as db:
            actor = db.get(User, user_id)
            service = AppointmentFlowApiService(db, repository=InstrumentedRepository(db))
            with pytest.raises(HTTPException) as exc:
                service.resolve_appointment_from_visit(
                    appointment_id=visit_id,
                    emr_data=SimpleNamespace(appointment_id=0),
                    prepare_visit=lambda hint: _prepare_visit_doctor_access(db, hint, actor),
                )
            return exc.value.status_code

    with Session(engine) as blocker:
        visit = blocker.query(Visit).filter_by(id=visit_id).with_for_update().one()
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(resolve)
            assert before_visit_lock.wait(timeout=10)
            visit.doctor_id = None
            blocker.commit()
            assert future.result(timeout=20) == 409
    with Session(engine) as db:
        assert db.query(Appointment).filter_by(source_visit_id=visit_id).count() == 0


def test_pg_doctor_rebind_before_creation_revokes_actor(appointment_source_pg_engine):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event

    from sqlalchemy.orm import Session

    from app.api.v1.endpoints.appointment_flow import _prepare_visit_doctor_access
    from app.models.user import User
    from app.repositories.appointment_flow_api_repository import (
        AppointmentFlowApiRepository,
    )

    engine = appointment_source_pg_engine
    user_id, doctor_id, visit_id = _seed_pg(engine)
    hint_read = Event()
    reached_visit_lock = Event()

    class InstrumentedRepository(AppointmentFlowApiRepository):
        def get_visit(self, source_id):
            result = super().get_visit(source_id)
            hint_read.set()
            return result

        def get_locked_visit(self, source_id):
            reached_visit_lock.set()
            return super().get_locked_visit(source_id)

    def resolve():
        with Session(engine) as db:
            actor = db.get(User, user_id)
            service = AppointmentFlowApiService(db, repository=InstrumentedRepository(db))
            with pytest.raises(HTTPException) as exc:
                service.resolve_appointment_from_visit(
                    appointment_id=visit_id,
                    emr_data=SimpleNamespace(appointment_id=0),
                    prepare_visit=lambda hint: _prepare_visit_doctor_access(db, hint, actor),
                )
            return exc.value.status_code

    with Session(engine) as blocker:
        replacement = User(username='new-owner', hashed_password='synthetic', role='Doctor', is_active=True)
        blocker.add(replacement)
        blocker.commit()
        doctor = blocker.query(Doctor).filter_by(id=doctor_id).with_for_update().one()
        doctor.user_id = replacement.id
        blocker.flush()
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(resolve)
            assert hint_read.wait(timeout=10)
            assert not reached_visit_lock.wait(timeout=0.3)
            blocker.commit()
            assert future.result(timeout=20) == 403
    with Session(engine) as db:
        assert db.query(Appointment).filter_by(source_visit_id=visit_id).count() == 0


def test_source_creation_failed_commit_rolls_back(db_session, test_patient, test_doctor, monkeypatch):
    visit = _visit(db_session, test_patient, test_doctor)
    visit_id = visit.id
    original_commit = db_session.commit

    def fail_commit():
        raise RuntimeError('synthetic commit failure')

    monkeypatch.setattr(db_session, 'commit', fail_commit)
    with pytest.raises(RuntimeError, match='synthetic commit failure'):
        _resolve(db_session, visit)
    db_session.rollback()
    monkeypatch.setattr(db_session, 'commit', original_commit)
    assert db_session.query(Appointment).filter_by(source_visit_id=visit_id).count() == 0
