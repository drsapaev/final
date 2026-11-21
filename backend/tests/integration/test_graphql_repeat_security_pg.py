"""Repeat GraphQL endpoint under a migrated, disposable nonowner database."""
from datetime import timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import sessionmaker

from app.api.deps import get_db
from app.core.config import settings
from app.crud.clinic import clinic_today
from app.db import session as db_session_module
from app.db.trusted_schema import pin_application_schema
from app.main import app
from app.models.clinic import ClinicSettings, Doctor
from app.models.patient import Patient
from app.models.service import Service
from app.models.user import User
from app.models.visit import Visit, VisitService
from app.services.authentication_service import authentication_service
from app.services.patient_subject_lock import lock_patient_subject
from app.services.visit_completion_evidence import capture_completion_evidence
from tests.integration.test_doctor_price_producer_races_pg import provisioned_database  # noqa: F401
from tests.integration.test_graphql_repeat_security import call


@pytest.fixture
def pg_graph(monkeypatch, provisioned_database):
    admin_engine, runtime_engine, schema_owner, _, runtime_role = provisioned_database
    admins = sessionmaker(bind=admin_engine, expire_on_commit=False, autoflush=False)
    sessions = sessionmaker(bind=runtime_engine, expire_on_commit=False, autoflush=False)
    suffix = uuid4().hex[:12]
    with admins() as db:
        actor = User(username=f"synthetic_gql_admin_{suffix}", hashed_password="!synthetic",
                     role="Admin", is_active=True)
        owner = User(username=f"synthetic_gql_doc_{suffix}", hashed_password="!synthetic",
                     role="Doctor", is_active=True)
        patient = Patient(first_name="SYNTHETIC", last_name=suffix, phone="+998900000000")
        service = Service(code=f"GQL{suffix}", name="Synthetic consultation",
                          price=Decimal("123.45"), active=True, is_consultation=True)
        db.add_all([actor, owner, patient, service])
        db.flush()
        doctor = Doctor(user_id=owner.id, specialty="general", active=True)
        db.add(doctor)
        db.flush()
        today = clinic_today(db)
        prior = Visit(patient_id=patient.id, doctor_id=doctor.id, visit_date=today - timedelta(days=1),
                      status="scheduled", discount_mode="none", source="desk")
        db.add(prior)
        db.flush()
        db.add(VisitService(visit_id=prior.id, service_id=service.id,
                            name=service.name, qty=1, price=service.price))
        db.flush()
        capture_completion_evidence(db, prior)
        prior.status = "completed"
        setting = db.query(ClinicSettings).filter_by(key="repeat_visit_discount").first()
        if setting is None:
            db.add(ClinicSettings(key="repeat_visit_discount", value=20))
        else:
            setting.value = 20
        db.commit()
        db.refresh(prior)
        assert prior.repeat_proof_generation == prior.repeat_evidence_generation
        assert prior.repeat_proof_consultation is True
        token = authentication_service.create_access_token({"sub": str(actor.id), "username": actor.username,
            "role": actor.role, "is_active": True, "is_superuser": False, "auth_epoch": actor.auth_epoch})
        ids = patient.id, doctor.id, service.id, prior.id, owner.id

    monkeypatch.setattr(settings, "TRUSTED_DB_SCHEMA", "public")
    monkeypatch.setattr(settings, "TRUSTED_DB_SCHEMA_OWNER", schema_owner)
    monkeypatch.setattr(settings, "TRUSTED_DB_RUNTIME_ROLE", runtime_role)
    monkeypatch.setattr(settings, "TRUSTED_DB_OWNER_MEMBERS", ())
    with admin_engine.connect() as connection:
        auth_owner = connection.execute(text("SELECT pg_catalog.pg_get_userbyid(relowner) FROM pg_catalog.pg_class WHERE oid='public.token_blacklist'::pg_catalog.regclass")).scalar_one()
        users_owner = connection.execute(text("SELECT pg_catalog.pg_get_userbyid(relowner) FROM pg_catalog.pg_class WHERE oid='public.users'::pg_catalog.regclass")).scalar_one()
    monkeypatch.setattr(settings, "TRUSTED_AUTH_TABLE_OWNER", auth_owner)
    monkeypatch.setattr(settings, "TRUSTED_AUTH_OWNER_MEMBERS", ())
    monkeypatch.setattr(settings, "TRUSTED_AUTH_READ_ROLES", ())
    monkeypatch.setattr(settings, "TRUSTED_AUTH_WRITE_ROLES", ())
    monkeypatch.setattr(settings, "TRUSTED_AUTH_USERS_OWNER", users_owner)
    monkeypatch.setattr(settings, "TRUSTED_AUTH_USERS_OWNER_MEMBERS", ())
    monkeypatch.setattr(settings, "TRUSTED_AUTH_USERS_WRITE_ROLES", ())
    monkeypatch.setattr(db_session_module, "SessionLocal", sessions)
    with sessions() as check:
        pin_application_schema(check, schema="public", expected_owner=schema_owner,
            expected_runtime_role=runtime_role, expected_auth_owner=auth_owner,
            expected_users_owner=users_owner)
        assert lock_patient_subject(check, patient.id)
        check.rollback()

    def database():
        with sessions() as db:
            yield db

    old = dict(app.dependency_overrides)
    app.dependency_overrides[get_db] = database
    try:
        with TestClient(app) as client:
            yield client, admins, {"Authorization": f"Bearer {token}"}, today, ids
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(old)


@pytest.mark.parametrize("locked", ["visit", "service", "doctor", "owner"])
def test_graphql_repeat_nowait_conflict_rolls_back_and_retry_succeeds(pg_graph, locked):
    client, admins, headers, today, (patient_id, doctor_id, service_id, prior_id, owner_id) = pg_graph
    with admins() as blocker:
        model, identifier = {
            "visit": (Visit, prior_id), "service": (Service, service_id),
            "doctor": (Doctor, doctor_id), "owner": (User, owner_id),
        }[locked]
        blocker.query(model).filter(model.id == identifier).with_for_update().one()
        result = call(client, headers, patient_id, doctor_id, service_id, today + timedelta(days=2))
        assert result["success"] is False
        assert result["errors"] == ["RETRYABLE_CONFLICT"]
        blocker.rollback()
    with admins() as verify:
        assert verify.query(Visit).filter_by(patient_id=patient_id).count() == 1
    result = call(client, headers, patient_id, doctor_id, service_id, today + timedelta(days=2))
    assert result["success"] is True, result
    with admins() as verify:
        visit = verify.get(Visit, int(result["visit"]["id"]))
        assert visit.encounter_id is not None
        assert verify.query(VisitService).filter_by(visit_id=visit.id).one().price == Decimal("98.76")
