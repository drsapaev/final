"""Patient writers against the actual 0110 triggers and synthetic databases."""

import importlib
import importlib.util
import os
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path
from unittest.mock import AsyncMock, Mock

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.schema import CreateSchema, CreateTable, DropSchema

from app.crud.patient import update_patient as mobile_update_patient
from app.db.base_class import Base
from app.models.patient import Patient, PatientBirthDateEvidence
from app.models.user import User
from app.schemas.patient import PatientCreate, PatientUpdate
from app.services.patient_service import PatientService


@pytest.fixture(params=["sqlite", "postgresql"])
def migrated_engine(request, tmp_path):
    schema = None
    admin = None
    if request.param == "sqlite":
        engine = create_engine(f"sqlite:///{tmp_path / 'birth-writers.db'}")
    else:
        raw = os.environ.get("DATABASE_URL", "")
        if not raw or make_url(raw).get_backend_name() != "postgresql":
            pytest.skip("requires disposable PostgreSQL")
        url = make_url(raw)
        if not (url.database or "").startswith("clinic_test") and os.environ.get("CI", "").lower() != "true":
            pytest.skip("requires synthetic clinic_test database")
        schema = "birth_writers_" + uuid.uuid4().hex
        admin = create_engine(url)
        with admin.begin() as conn:
            conn.execute(CreateSchema(schema))
        engine = create_engine(url, connect_args={"options": f"-csearch_path={schema} -clock_timeout=10000"})
    try:
        Base.metadata.create_all(engine)
        with engine.begin() as conn:
            conn.execute(text("DROP TABLE patient_birth_date_evidence"))
            if conn.dialect.name == "postgresql":
                conn.execute(text("ALTER TABLE patients DROP CONSTRAINT ck_patient_birth_date_precision"))
                conn.execute(text("ALTER TABLE patients DROP COLUMN birth_date_precision"))
                conn.execute(text("ALTER TABLE patients DROP COLUMN birth_date_generation"))
            else:
                # Reconstruct the predecessor without a metadata table rebuild
                # during 0110 itself; this also retains the ORM's old columns.
                predecessor = str(CreateTable(Patient.__table__).compile(dialect=engine.dialect))
                predecessor = "\n".join(
                    line for line in predecessor.splitlines()
                    if "birth_date_generation" not in line and "birth_date_precision" not in line
                )
                conn.execute(text("DROP TABLE patients"))
                conn.execute(text(predecessor))
            path = Path(__file__).resolve().parents[2] / "alembic/versions/0110_patient_birth_precision.py"
            spec = importlib.util.spec_from_file_location("test_0110_birth_writers", path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            module.op = Operations(MigrationContext.configure(conn))
            module.upgrade()
        yield engine
    finally:
        engine.dispose()
        if admin is not None:
            with admin.begin() as conn:
                conn.execute(DropSchema(schema, cascade=True))
            admin.dispose()


def _actor(db):
    actor = User(username="synthetic-writer", email="writer@invalid.example", full_name="Synthetic",
                 hashed_password="synthetic", role="Admin", is_active=True, is_superuser=True)
    db.add(actor)
    db.commit()
    return actor


def test_service_and_mobile_record_only_reported_precision(migrated_engine, monkeypatch):
    monkeypatch.setattr("app.services.patient_service._dispatch_patient_registered_notification_async", lambda **_: None)
    monkeypatch.setattr("app.services.patient_service.notification_sender_service.send_patient_registered_notification", AsyncMock(return_value=True))
    with Session(migrated_engine, expire_on_commit=False, autoflush=False) as db:
        actor = _actor(db)
        service = PatientService(db)
        patient = service.create_patient(
            request=None,
            patient_in=PatientCreate(first_name="Synthetic", last_name="Patient", birth_date=date(2000, 1, 1)),
            current_user=actor,
        )
        db.refresh(patient)
        assert patient.birth_date == date(2000, 1, 1)
        assert patient.birth_date_precision == "reported_exact"
        first_generation = patient.birth_date_generation
        assert first_generation > 0
        service.update_patient(request=None, patient_id=patient.id, patient_in=PatientUpdate(address="Synthetic"), current_user=actor)
        db.refresh(patient)
        assert patient.birth_date_generation == first_generation
        assert patient.birth_date_precision == "reported_exact"
        mobile_update_patient(db, patient_id=patient.id, update_data={"birth_date": date(2001, 2, 3)})
        db.refresh(patient)
        changed_generation = patient.birth_date_generation
        assert changed_generation > first_generation and patient.birth_date_precision == "reported_exact"
        service.update_patient(request=None, patient_id=patient.id, patient_in=PatientUpdate(birth_date=date(2000, 1, 1)), current_user=actor)
        db.refresh(patient)
        assert patient.birth_date_generation > changed_generation
        assert patient.birth_date_precision == "reported_exact"
        assert db.query(PatientBirthDateEvidence).count() == 0
        mobile_update_patient(db, patient_id=patient.id, update_data={"birth_date": None})
        db.refresh(patient)
        assert patient.birth_date is None and patient.birth_date_precision == "unknown"


def test_audit_failure_rolls_back_date_and_precision(migrated_engine, monkeypatch):
    with Session(migrated_engine, expire_on_commit=False, autoflush=False) as db:
        actor = _actor(db)
        patient = Patient(first_name="Synthetic", last_name="Patient", birth_date=date(2000, 1, 1))
        db.add(patient)
        db.commit()
        db.refresh(patient)
        before = (patient.birth_date, patient.birth_date_generation, patient.birth_date_precision)
        monkeypatch.setattr("app.services.patient_service.log_critical_change", lambda **_: None)
        with pytest.raises(RuntimeError, match="audit unavailable"):
            PatientService(db).update_patient(
                request=None, patient_id=patient.id,
                patient_in=PatientUpdate(birth_date=date(2001, 2, 3)), current_user=actor,
            )
        db.refresh(patient)
        assert (patient.birth_date, patient.birth_date_generation, patient.birth_date_precision) == before
        assert db.query(PatientBirthDateEvidence).count() == 0


def test_same_date_precision_change_invalidates_previous_evidence(migrated_engine):
    with Session(migrated_engine, expire_on_commit=False, autoflush=False) as db:
        actor = _actor(db)
        patient = Patient(first_name="Synthetic", last_name="Patient", birth_date=date(2000, 1, 1))
        db.add(patient)
        db.commit()
        db.refresh(patient)
        patient.birth_date_precision = "year_only"
        db.commit()
        db.refresh(patient)
        previous = patient.birth_date_generation
        db.add(PatientBirthDateEvidence(patient_id=patient.id, patient_id_snapshot=patient.id,
                                        birth_date_generation=previous, actor_user_id_snapshot=actor.id,
                                        actor_role="Admin"))
        db.commit()
        PatientService(db).update_patient(
            request=None, patient_id=patient.id,
            patient_in=PatientUpdate(birth_date=date(2000, 1, 1)), current_user=actor,
        )
        db.refresh(patient)
        assert patient.birth_date_precision == "reported_exact"
        assert patient.birth_date_generation > previous
        assert db.query(PatientBirthDateEvidence).filter_by(
            patient_id=patient.id, birth_date_generation=patient.birth_date_generation,
        ).count() == 0


def test_create_audit_failure_rolls_back_patient_and_never_sends(migrated_engine, monkeypatch):
    notify_async = AsyncMock(return_value=True)
    dispatch = Mock()
    monkeypatch.setattr("app.services.patient_service.notification_sender_service.send_patient_registered_notification", notify_async)
    monkeypatch.setattr("app.services.patient_service._dispatch_patient_registered_notification_async", dispatch)
    monkeypatch.setattr("app.services.patient_service.log_critical_change", lambda **_: None)
    with Session(migrated_engine, expire_on_commit=False, autoflush=False) as db:
        actor = _actor(db)
        before = db.query(Patient).count()
        with pytest.raises(RuntimeError, match="audit unavailable"):
            PatientService(db).create_patient(
                request=None, current_user=actor,
                patient_in=PatientCreate(first_name="Synthetic", last_name="Patient", birth_date=date(2000, 1, 1)),
            )
        assert db.query(Patient).count() == before
        assert db.query(PatientBirthDateEvidence).count() == 0
    notify_async.assert_not_called()
    dispatch.assert_not_called()


def test_mobile_failure_after_precision_write_rolls_back_both(migrated_engine, monkeypatch):
    from app.services.patient_birth_precision import record_reported_birth_date

    def fail_after_write(db, patient, *, expected_date):
        record_reported_birth_date(db, patient, expected_date=expected_date)
        raise RuntimeError("synthetic failure")

    monkeypatch.setattr(importlib.import_module("app.crud.patient"), "record_reported_birth_date", fail_after_write)
    with Session(migrated_engine, expire_on_commit=False, autoflush=False) as db:
        patient = Patient(first_name="Synthetic", last_name="Patient", birth_date=date(2000, 1, 1))
        db.add(patient)
        db.commit()
        db.refresh(patient)
        before = (patient.birth_date, patient.birth_date_generation, patient.birth_date_precision)
        with pytest.raises(RuntimeError, match="synthetic failure"):
            mobile_update_patient(db, patient_id=patient.id, update_data={"birth_date": date(2001, 2, 3)})
        db.refresh(patient)
        assert (patient.birth_date, patient.birth_date_generation, patient.birth_date_precision) == before


def test_rest_graphql_and_mobile_share_reported_provenance(migrated_engine, monkeypatch):
    from app.api.deps import get_db
    from app.main import app
    from tests.conftest import mint_access_token

    monkeypatch.setattr("app.services.patient_service._dispatch_patient_registered_notification_async", lambda **_: None)
    monkeypatch.setattr("app.services.patient_service.notification_sender_service.send_patient_registered_notification", AsyncMock(return_value=True))
    session_factory = sessionmaker(bind=migrated_engine, autoflush=False, expire_on_commit=False)
    monkeypatch.setattr(importlib.import_module("app.db.session"), "SessionLocal", session_factory)
    with session_factory() as db:
        actor = _actor(db)
        headers = {"Authorization": f"Bearer {mint_access_token(actor)}"}

    def override_db():
        with session_factory() as db:
            yield db

    app.dependency_overrides[get_db] = override_db
    try:
        with TestClient(app) as client:
            response = client.post("/api/v1/patients/", headers=headers, json={
                "first_name": "Synthetic", "last_name": "Rest", "birth_date": "2000-01-01",
            })
            assert response.status_code == 200, response.text
            patient_id = response.json()["id"]
            gql = client.post("/api/graphql", headers=headers, json={
                "query": "mutation($id: Int!, $input: PatientUpdateInput!) { updatePatient(id:$id,input:$input) { success errors } }",
                "variables": {"id": patient_id, "input": {"birthDate": "2001-02-03"}},
            })
            assert gql.status_code == 200, gql.text
            assert gql.json()["data"]["updatePatient"]["success"], gql.text
            with session_factory() as db:
                patient = db.get(Patient, patient_id)
                assert patient.birth_date == date(2001, 2, 3)
                assert patient.birth_date_precision == "reported_exact"
                patient_user = User(username="synthetic-patient", email="patient@invalid.example", full_name="Synthetic",
                                    hashed_password="synthetic", role="Patient", is_active=True, is_superuser=False)
                db.add(patient_user)
                db.flush()
                patient.user_id = patient_user.id
                db.commit()
                patient_headers = {"Authorization": f"Bearer {mint_access_token(patient_user)}"}
            mobile = client.put("/api/v1/mobile/profile", headers=patient_headers, json={"birth_date": "2002-03-04"})
            assert mobile.status_code == 200, mobile.text
            with session_factory() as db:
                patient = db.get(Patient, patient_id)
                assert patient.birth_date == date(2002, 3, 4)
                assert patient.birth_date_precision == "reported_exact"
                before = patient.birth_date_generation
            omitted = client.put("/api/v1/mobile/profile", headers=patient_headers, json={"address": "Synthetic"})
            assert omitted.status_code == 200, omitted.text
            empty = client.put("/api/v1/mobile/profile", headers=patient_headers, json={"birth_date": ""})
            assert empty.status_code == 200, empty.text
            with session_factory() as db:
                patient = db.get(Patient, patient_id)
                assert patient.birth_date == date(2002, 3, 4)
                assert patient.birth_date_generation == before
            cleared = client.put("/api/v1/mobile/profile", headers=patient_headers, json={"birth_date": None})
            assert cleared.status_code == 200, cleared.text
        with session_factory() as db:
            patient = db.get(Patient, patient_id)
            assert patient.birth_date is None
            assert patient.birth_date_precision == "unknown"
            assert patient.birth_date_generation > before
            assert db.query(PatientBirthDateEvidence).count() == 0
    finally:
        app.dependency_overrides.clear()


def test_postgres_stale_same_value_waits_and_writes_the_explicit_date(migrated_engine):
    if migrated_engine.dialect.name != "postgresql":
        pytest.skip("requires PostgreSQL row-lock barrier")
    with Session(migrated_engine, expire_on_commit=False) as db:
        actor = _actor(db)
        patient = Patient(first_name="Synthetic", last_name="Patient", birth_date=date(2000, 1, 1))
        db.add(patient)
        db.commit()
        actor_id, patient_id = actor.id, patient.id
    loaded, held, attempt, release = (threading.Event() for _ in range(4))
    writer_pid = []

    def first_writer():
        with Session(migrated_engine, autoflush=False) as db:
            assert loaded.wait(5)
            patient = db.query(Patient).filter_by(id=patient_id).with_for_update().one()
            patient.birth_date = date(2001, 2, 3)
            db.flush()
            held.set()
            assert release.wait(10)
            db.commit()

    def second_writer():
        with Session(migrated_engine, autoflush=False) as db:
            actor = db.get(User, actor_id)
            assert db.get(Patient, patient_id).birth_date == date(2000, 1, 1)
            writer_pid.append(db.execute(text("SELECT pg_backend_pid() ")).scalar_one())
            loaded.set()
            assert held.wait(5)
            attempt.set()
            PatientService(db).update_patient(
                request=None, patient_id=patient_id,
                patient_in=PatientUpdate(birth_date=date(2000, 1, 1)), current_user=actor,
            )

    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(first_writer)
        second = pool.submit(second_writer)
        try:
            assert attempt.wait(5)
            deadline = time.monotonic() + 5
            with migrated_engine.connect() as observer:
                while time.monotonic() < deadline:
                    blocked = observer.execute(text("SELECT cardinality(pg_blocking_pids(:pid))"), {"pid": writer_pid[0]}).scalar_one()
                    if blocked:
                        break
                    time.sleep(0.02)
                else:
                    pytest.fail("date writer did not wait for concurrent Patient update")
        finally:
            release.set()
        first.result(timeout=10)
        second.result(timeout=10)
    with Session(migrated_engine) as db:
        patient = db.get(Patient, patient_id)
        assert patient.birth_date == date(2000, 1, 1)
        assert patient.birth_date_precision == "reported_exact"
        assert db.query(PatientBirthDateEvidence).count() == 0


@pytest.mark.parametrize("first", ["writer", "delete"])
def test_postgres_audit_user_lock_precedes_patient_in_both_orders(migrated_engine, monkeypatch, first):
    if migrated_engine.dialect.name != "postgresql":
        pytest.skip("requires PostgreSQL row-lock barrier")
    import app.services.patient_service as patient_service_module

    with Session(migrated_engine, expire_on_commit=False) as db:
        actor = _actor(db)
        patient = Patient(first_name="Synthetic", last_name="Patient", birth_date=date(2000, 1, 1), user_id=actor.id)
        db.add(patient)
        db.commit()
        actor_id, patient_id = actor.id, patient.id

    holding, attempt, release = (threading.Event() for _ in range(3))
    waiting_pid = []
    original_audit = patient_service_module.log_critical_change

    def audit_barrier(**kwargs):
        if first == "writer":
            holding.set()
            assert release.wait(10)
        return original_audit(**kwargs)

    monkeypatch.setattr(patient_service_module, "log_critical_change", audit_barrier)

    def writer():
        with Session(migrated_engine, autoflush=False) as db:
            actor = db.get(User, actor_id)
            if first == "delete":
                waiting_pid.append(db.execute(text("SELECT pg_backend_pid() ")).scalar_one())
                assert holding.wait(5)
                attempt.set()
            PatientService(db).update_patient(
                request=None, patient_id=patient_id,
                patient_in=PatientUpdate(birth_date=date(2001, 2, 3)), current_user=actor,
            )

    def deleter():
        with Session(migrated_engine, autoflush=False) as db:
            if first == "delete":
                db.query(User).filter_by(id=actor_id).with_for_update().one()
                holding.set()
                assert release.wait(10)
            else:
                assert holding.wait(5)
                waiting_pid.append(db.execute(text("SELECT pg_backend_pid() ")).scalar_one())
                attempt.set()
            db.execute(text("DELETE FROM users WHERE id=:id"), {"id": actor_id})
            db.commit()

    with ThreadPoolExecutor(max_workers=2) as pool:
        first_future = pool.submit(writer if first == "writer" else deleter)
        second_future = pool.submit(deleter if first == "writer" else writer)
        try:
            assert attempt.wait(5)
            deadline = time.monotonic() + 5
            with migrated_engine.connect() as observer:
                while time.monotonic() < deadline:
                    blocked = observer.execute(text("SELECT cardinality(pg_blocking_pids(:pid))"), {"pid": waiting_pid[0]}).scalar_one()
                    if blocked:
                        break
                    time.sleep(0.02)
                else:
                    pytest.fail("competing operation did not wait on actor User")
        finally:
            release.set()
        first_future.result(timeout=10)
        if first == "delete":
            with pytest.raises(LookupError, match="audit actor unavailable"):
                second_future.result(timeout=10)
        else:
            second_future.result(timeout=10)
    with Session(migrated_engine) as db:
        patient = db.get(Patient, patient_id)
        assert patient.user_id is None
        assert patient.birth_date == (date(2001, 2, 3) if first == "writer" else date(2000, 1, 1))
