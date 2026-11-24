"""Real endpoint checks on a disposable database migrated through 0117.

No network notification is sent; delivery is staged in the same transaction.
This is not evidence for the still-unimplemented financial approval fence.
"""
from __future__ import annotations

import base64
import importlib.util
import json
import os
from contextlib import contextmanager
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from unittest.mock import AsyncMock
from uuid import uuid4

import jwt
import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker

from app.api.deps import get_db
from app.core.config import settings
from app.main import app
from app.models.clinic import Doctor
from app.models.doctor_price_intent import DoctorPriceIntent, DoctorPriceIntentLine
from app.models.doctor_price_override import DoctorPriceOverride
from app.models.patient import Patient
from app.models.service import Service
from app.models.user import User
from app.models.visit import Visit, VisitService
from app.models.visit_invitation_delivery import (
    VisitInvitationDelivery,
    VisitInvitationIssuerAuth,
)
from app.services.authentication_service import authentication_service


def _module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="session")
def provisioned_database():
    url = make_url(os.getenv("DATABASE_URL", "sqlite://"))
    runtime_role = os.getenv("PRICE_TEST_RUNTIME_ROLE")
    capability_role = os.getenv("PRICE_TEST_CAPABILITY_ROLE")
    if (os.getenv("DOCTOR_PRICE_ENDPOINT_TEST_DB") != "1" or url.get_backend_name() != "postgresql"
            or not (url.database or "").startswith("clinic_test_") or not runtime_role or not capability_role):
        pytest.skip("requires explicitly isolated PostgreSQL and disposable roles")
    with provision_price_endpoint_database(url, runtime_role, capability_role) as profile:
        yield profile


@contextmanager
def provision_price_endpoint_database(url, runtime_role, capability_role):
    """Apply the protected endpoint setup to a fresh disposable 0117 database."""
    admin_engine = create_engine(url)
    runtime_engine = None
    try:
        quote = admin_engine.dialect.identifier_preparer.quote_identifier
        root = Path(__file__).resolve().parents[3]
        with admin_engine.begin() as db:
            revision = db.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
            assert revision == "0117_visit_invitation_delivery"
            schema_owner = db.execute(text("SELECT pg_catalog.pg_get_userbyid(nspowner) FROM pg_catalog.pg_namespace WHERE nspname='public'")).scalar_one()
            table_owner = db.execute(text("SELECT pg_catalog.pg_get_userbyid(relowner) FROM pg_catalog.pg_class WHERE oid='public.visit_invitation_deliveries'::pg_catalog.regclass")).scalar_one()
            # Apply the price and invitation pieces used by this focused fixture.
            # The Visit ORM also requires the appointment provenance fields from 0153.
            # The standard invitation provisioner checks the trigger body from 0130.
            operations = Operations(MigrationContext.configure(db, opts={"version_table_schema": "public"}))
            for revision in (
                "0121_doctor_price_runtime_access",
                "0126_invitation_issuer_auth",
                "0128_invitation_price_approval",
                "0130_invitation_nonce_guard",
                "0153_visit_start_appointment",
            ):
                migration = _module(f"synthetic_{revision}", root / "backend/alembic/versions" / f"{revision}.py")
                migration.op = operations
                migration.upgrade()
            # Synthetic-only clinical permissions make the full route executable;
            # production grants for clinical tables require their own review.
            protected = {"doctor_price_hmac_key_versions", "doctor_price_intents", "doctor_price_intent_keys",
                         "doctor_price_intent_lines", "visit_invitation_deliveries", "visit_invitation_issuer_auth",
                         "visit_invitation_price_approval_auth", "visit_invitation_approval_recoveries", "alembic_version"}
            db.execute(text("ALTER TABLE public.visits ENABLE ROW LEVEL SECURITY"))
            relations = db.execute(text("""
                SELECT c.relname,c.relrowsecurity FROM pg_catalog.pg_class c
                JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace
                WHERE n.nspname='public' AND c.relkind IN ('r','p')
            """)).all()
            for relation in relations:
                if relation.relname in protected:
                    continue
                table = f"public.{quote(relation.relname)}"
                db.exec_driver_sql(f"GRANT SELECT, INSERT, UPDATE ON {table} TO {quote(runtime_role)}")
                if relation.relrowsecurity:
                    db.exec_driver_sql(f"CREATE POLICY synthetic_price_test_runtime ON {table} TO {quote(runtime_role)} USING (true) WITH CHECK (true)")
            sequences = db.execute(text("""
                SELECT c.relname FROM pg_catalog.pg_class c JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace
                WHERE n.nspname='public' AND c.relkind='S'
            """)).scalars().all()
            for sequence in sequences:
                if sequence in {"doctor_price_generation_seq", "doctor_price_intents_id_seq",
                                "doctor_price_intent_keys_id_seq", "doctor_price_intent_lines_id_seq"} or sequence.startswith("visit_invitation_"):
                    continue
                db.exec_driver_sql(f"GRANT USAGE ON SEQUENCE public.{quote(sequence)} TO {quote(runtime_role)}")
        price = _module("synthetic_price_role_provision", root / "scripts/provision_doctor_price_backend_role.py")
        invitation = _module("synthetic_invitation_role_provision", root / "backend/scripts/provision_invitation_delivery_role.py")
        subject = _module("synthetic_subject_role_provision", root / "scripts/provision_confirmation_subject_role.py")
        price.provision(admin_engine, "public", runtime_role)
        invitation.provision(admin_engine, "public", runtime_role)
        try:
            subject.provision(admin_engine, "public", capability_role, runtime_role, expected_owner=schema_owner)
        except Exception:
            # Diagnostic metadata only, from this explicitly disposable database.
            from app.db.capability_namespace import capability_schema_name
            with admin_engine.connect() as db:
                routines = db.execute(text("""
                  SELECT p.proname,pg_catalog.pg_get_userbyid(p.proowner) AS owner,
                         CASE WHEN a.grantee=0 THEN 'PUBLIC' ELSE pg_catalog.pg_get_userbyid(a.grantee) END AS grantee,
                         a.privilege_type,a.is_grantable
                  FROM pg_catalog.pg_proc p JOIN pg_catalog.pg_namespace n ON n.oid=p.pronamespace,
                    LATERAL pg_catalog.aclexplode(COALESCE(p.proacl,pg_catalog.acldefault('f',p.proowner))) a
                  WHERE n.nspname=:schema ORDER BY p.proname,grantee
                """), {"schema": capability_schema_name("public")}).all()
                print("SYNTHETIC_CAPABILITY_ROUTINES", routines)
            raise
        runtime_engine = create_engine(url)

        @event.listens_for(runtime_engine, "handle_error")
        def record_synthetic_privilege_error(context):
            original = context.original_exception
            if getattr(original, "sqlstate", None) == "42501":
                diag = getattr(original, "diag", None)
                print("SYNTHETIC_PERMISSION_FAILURE", getattr(diag, "message_primary", "unknown"))

        @event.listens_for(runtime_engine, "connect")
        def assume_synthetic_login(connection, _):
            previous = connection.autocommit
            connection.autocommit = True
            try:
                with connection.cursor() as cursor:
                    cursor.execute(f"SET SESSION AUTHORIZATION {quote(runtime_role)}")
            finally:
                connection.autocommit = previous
        yield admin_engine, runtime_engine, schema_owner, table_owner, runtime_role
    finally:
        if runtime_engine is not None:
            runtime_engine.dispose()
        admin_engine.dispose()


def pin_price_endpoint_test_settings(monkeypatch, admin_engine, schema_owner, table_owner, runtime_role):
    monkeypatch.setattr(settings, "DOCTOR_PRICE_HMAC_KEYS", SecretStr(json.dumps({"1": base64.urlsafe_b64encode(b"a" * 32).decode()})))
    monkeypatch.setattr(settings, "DOCTOR_PRICE_HMAC_ACTIVE_VERSION", 1)
    monkeypatch.setattr(settings, "DOCTOR_PRICE_DB_SCHEMA", "public")
    monkeypatch.setattr(settings, "DOCTOR_PRICE_DB_SCHEMA_OWNER", schema_owner)
    monkeypatch.setattr(settings, "DOCTOR_PRICE_DB_RUNTIME_ROLE", runtime_role)
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
    monkeypatch.setattr(settings, "INVITATION_DB_SCHEMA", "public")
    monkeypatch.setattr(settings, "INVITATION_DB_SCHEMA_OWNER", schema_owner)
    monkeypatch.setattr(settings, "INVITATION_DB_TABLE_OWNER", table_owner)


@pytest.fixture
def migrated_endpoint(monkeypatch, provisioned_database):
    admin_engine, runtime_engine, schema_owner, table_owner, runtime_role = provisioned_database
    admins = sessionmaker(bind=admin_engine, expire_on_commit=False, autoflush=False)
    sessions = sessionmaker(bind=runtime_engine, expire_on_commit=False, autoflush=False)
    suffix = uuid4().hex[:10]
    with admins() as db:
        actor = User(username=f"dpc_{suffix}", email=f"{suffix}@example.test", full_name="Synthetic Doctor",
                     hashed_password="synthetic", role="Doctor", is_active=True, is_superuser=False)
        patient = Patient(first_name="Synthetic", last_name=f"Patient{suffix}", phone="+998901234567")
        foreign = Patient(first_name="Synthetic", last_name=f"Other{suffix}", phone="+998901234568")
        db.add_all([actor, patient, foreign])
        db.flush()
        doctor = Doctor(user_id=actor.id, specialty="cardiology", active=True)
        service = Service(code=f"T{suffix}", name="Synthetic service", price=Decimal("123.45"),
                          active=True, is_consultation=False, allow_doctor_price_override=True)
        db.add_all([doctor, service])
        db.flush()
        db.add(Visit(patient_id=patient.id, doctor_id=doctor.id, visit_date=date.today(),
                     status="open", discount_mode="none", source="desk"))
        db.commit()
        token = authentication_service.create_access_token({"sub": str(actor.id), "username": actor.username,
            "role": actor.role, "is_active": True, "is_superuser": False, "auth_epoch": actor.auth_epoch})
        actor_id, patient_id, foreign_id, service_id = actor.id, patient.id, foreign.id, service.id
    pin_price_endpoint_test_settings(monkeypatch, admin_engine, schema_owner, table_owner, runtime_role)

    def session_override():
        with sessions() as session:
            yield session

    app.dependency_overrides[get_db] = session_override
    try:
        with TestClient(app) as client:
            yield client, admins, {"Authorization": f"Bearer {token}"}, actor_id, patient_id, foreign_id, service_id
    finally:
        app.dependency_overrides.pop(get_db, None)


def _payload(patient_id, service_id, custom=None):
    line = {"service_id": service_id, "quantity": 1}
    if custom is not None:
        line["custom_price"] = custom
    return {"patient_id": patient_id, "services": [line], "visit_date": (date.today() + timedelta(days=3)).isoformat(),
            "visit_time": "10:00", "discount_mode": "none", "all_free": False, "confirmation_channel": "phone"}


def test_migrated_schedule_keeps_baseline_creates_pending_and_stages_once(migrated_endpoint):
    client, sessions, auth, actor_id, patient_id, _, service_id = migrated_endpoint
    headers = {**auth, "Idempotency-Key": f"synthetic-{uuid4()}", "Idempotency-Intent": "new"}
    payload = _payload(patient_id, service_id, "0.00")
    first = client.post("/api/v1/doctor/visits/schedule-next", json=payload, headers=headers)
    assert first.status_code == 200, first.text
    body = first.json()
    assert body["idempotent_replay"] is False and body["confirmation"]["notification_sent"] is False
    assert len(body["price_override_requests"]) == 1
    visit_id = body["visit_id"]
    with sessions() as db:
        line = db.query(VisitService).filter_by(visit_id=visit_id).one()
        override = db.query(DoctorPriceOverride).filter_by(visit_id=visit_id).one()
        intent = db.query(DoctorPriceIntent).filter_by(visit_id=visit_id).one()
        intent_line = db.query(DoctorPriceIntentLine).filter_by(intent_id=intent.id).one()
        delivery = db.query(VisitInvitationDelivery).filter_by(visit_id=visit_id).one()
        assert line.price == Decimal("123.45")
        assert override.status == "pending" and override.target_visit_service_id == line.id
        assert override.visit_price_before == Decimal("123.45") and override.new_price == Decimal("0.00")
        assert override.requester_user_id == actor_id and override.requester_type == "doctor"
        assert intent_line.raw_custom_minor == 0 and intent_line.baseline_minor == 12345 and intent_line.proposed_minor == 0
        assert delivery.state == "pending"
    retry = client.post("/api/v1/doctor/visits/schedule-next", json=payload, headers=headers)
    assert retry.status_code == 200, retry.text
    assert retry.json()["visit_id"] == visit_id and retry.json()["idempotent_replay"] is True
    with sessions() as db:
        assert db.query(VisitInvitationDelivery).filter_by(visit_id=visit_id).count() == 1
        assert db.query(DoctorPriceOverride).filter_by(visit_id=visit_id).count() == 1


def test_unavailable_delivery_preserves_visit_and_replay_without_restaging(migrated_endpoint, monkeypatch):
    from app.api.v1.endpoints.doctor_integration import _visits

    client, sessions, auth, actor_id, patient_id, _, service_id = migrated_endpoint
    staged = []

    def unavailable(_db, **kwargs):
        staged.append(kwargs)
        return None

    monkeypatch.setattr(_visits, "stage_visit_invitation", unavailable)
    headers = {**auth, "Idempotency-Key": f"synthetic-{uuid4()}", "Idempotency-Intent": "new"}
    payload = _payload(patient_id, service_id, "0.00")
    first = client.post("/api/v1/doctor/visits/schedule-next", json=payload, headers=headers)
    assert first.status_code == 200, first.text
    assert "недоступна" in first.json()["message"]
    assert first.json()["confirmation"]["notification_sent"] is False
    assert len(staged) == 1
    assert staged[0]["bearer"].user_id == actor_id
    assert staged[0]["bearer"].jti and staged[0]["bearer"].expires_at
    assert staged[0]["requester_type"] == "doctor"
    assert staged[0]["doctor_id"] is not None and staged[0]["doctor_generation"] is not None
    retry = client.post("/api/v1/doctor/visits/schedule-next", json=payload, headers=headers)
    assert retry.status_code == 200, retry.text
    assert retry.json()["visit_id"] == first.json()["visit_id"]
    assert retry.json()["idempotent_replay"] is True and len(staged) == 1
    with sessions() as db:
        assert db.query(VisitInvitationDelivery).filter_by(visit_id=first.json()["visit_id"]).count() == 0
        assert db.query(DoctorPriceIntent).filter_by(visit_id=first.json()["visit_id"]).count() == 1


def test_admin_without_doctor_requests_pending_despite_physician_flag(migrated_endpoint):
    client, sessions, _, _, patient_id, _, service_id = migrated_endpoint
    suffix = uuid4().hex[:10]
    with sessions() as db:
        actor = User(username=f"admin_{suffix}", email=f"admin_{suffix}@example.test",
                     full_name="Synthetic Admin", hashed_password="synthetic", role="Admin",
                     is_active=True, is_superuser=False)
        db.add(actor)
        service = db.query(Service).filter_by(id=service_id).one()
        service.allow_doctor_price_override = False
        db.commit()
        actor_id = actor.id
        token = authentication_service.create_access_token({"sub": str(actor.id), "username": actor.username,
            "role": actor.role, "is_active": True, "is_superuser": False, "auth_epoch": actor.auth_epoch})
    headers = {"Authorization": f"Bearer {token}", "Idempotency-Key": f"synthetic-{uuid4()}",
               "Idempotency-Intent": "new"}
    payload = _payload(patient_id, service_id, "0.00")
    response = client.post("/api/v1/doctor/visits/schedule-next", json=payload, headers=headers)
    assert response.status_code == 200, response.text
    with sessions() as db:
        visit_id = response.json()["visit_id"]
        visit = db.query(Visit).filter_by(id=visit_id).one()
        override = db.query(DoctorPriceOverride).filter_by(visit_id=visit_id).one()
        delivery = db.query(VisitInvitationDelivery).filter_by(visit_id=visit_id).one()
        issuer = db.query(VisitInvitationIssuerAuth).filter_by(delivery_id=delivery.id).one()
        assert visit.doctor_id is None
        assert override.requester_type == "admin" and override.requester_user_id == actor_id
        assert override.doctor_id is None and override.status == "pending"
        assert override.visit_price_before == Decimal("123.45") and override.new_price == Decimal("0.00")
        assert issuer.requester_type == "admin" and issuer.actor_user_id == actor_id
        assert issuer.doctor_id is None and issuer.doctor_generation is None
    replay = client.post("/api/v1/doctor/visits/schedule-next", json=payload, headers=headers)
    assert replay.status_code == 200, replay.text
    assert replay.json()["visit_id"] == visit_id and replay.json()["idempotent_replay"] is True


@pytest.mark.parametrize("role", ["Registrar", "Cashier"])
def test_staff_doctor_profile_still_requires_patient_assignment(migrated_endpoint, role):
    client, sessions, _, _, patient_id, foreign_id, service_id = migrated_endpoint
    suffix = uuid4().hex[:10]
    with sessions() as db:
        actor = User(username=f"staff_{suffix}", email=f"staff_{suffix}@example.test",
                     full_name="Synthetic Staff", hashed_password="synthetic", role=role,
                     is_active=True, is_superuser=False)
        db.add(actor)
        db.flush()
        doctor = Doctor(user_id=actor.id, specialty="cardiology", active=True)
        db.add(doctor)
        db.flush()
        db.add(Visit(patient_id=patient_id, doctor_id=doctor.id, visit_date=date.today(),
                     status="open", discount_mode="none", source="desk"))
        db.commit()
        actor_id, doctor_id = actor.id, doctor.id
        token = authentication_service.create_access_token({"sub": str(actor.id), "username": actor.username,
            "role": actor.role, "is_active": True, "is_superuser": False, "auth_epoch": actor.auth_epoch})
    headers = {"Authorization": f"Bearer {token}", "Idempotency-Key": f"synthetic-{uuid4()}",
               "Idempotency-Intent": "new"}
    denied = client.post("/api/v1/doctor/visits/schedule-next", json=_payload(foreign_id, service_id, "0.00"), headers=headers)
    assert denied.status_code == 403, denied.text
    accepted = client.post("/api/v1/doctor/visits/schedule-next", json=_payload(patient_id, service_id, "0.00"), headers=headers)
    assert accepted.status_code == 200, accepted.text
    with sessions() as db:
        visit_id = accepted.json()["visit_id"]
        visit = db.query(Visit).filter_by(id=visit_id).one()
        override = db.query(DoctorPriceOverride).filter_by(visit_id=visit_id).one()
        delivery = db.query(VisitInvitationDelivery).filter_by(visit_id=visit_id).one()
        issuer = db.query(VisitInvitationIssuerAuth).filter_by(delivery_id=delivery.id).one()
        assert visit.doctor_id == doctor_id
        assert override.requester_type == "doctor" and override.requester_user_id == actor_id
        assert issuer.requester_type == "doctor" and issuer.doctor_id == doctor_id
        assert db.query(DoctorPriceIntent).filter_by(patient_id=foreign_id).count() == 0


@pytest.mark.parametrize("revocation", ["session", "doctor"])
def test_keyed_replay_rechecks_current_session_and_doctor(migrated_endpoint, revocation):
    client, sessions, auth, actor_id, patient_id, _, service_id = migrated_endpoint
    headers = {**auth, "Idempotency-Key": f"synthetic-{uuid4()}", "Idempotency-Intent": "new"}
    payload = _payload(patient_id, service_id, "0.00")
    first = client.post("/api/v1/doctor/visits/schedule-next", json=payload, headers=headers)
    assert first.status_code == 200, first.text
    visit_id = first.json()["visit_id"]
    with sessions() as db:
        if revocation == "session":
            actor = db.query(User).filter_by(id=actor_id).one()
            actor.auth_epoch += 1
        else:
            doctor = db.query(Doctor).filter_by(user_id=actor_id).one()
            doctor.active = False
        db.commit()
    replay = client.post("/api/v1/doctor/visits/schedule-next", json=payload, headers=headers)
    assert replay.status_code in (401, 403, 409), replay.text
    assert "confirmation" not in replay.json()
    with sessions() as db:
        assert db.query(Visit).filter_by(id=visit_id).count() == 1
        assert db.query(DoctorPriceIntent).filter_by(visit_id=visit_id).count() == 1
        assert db.query(VisitInvitationDelivery).filter_by(visit_id=visit_id).count() == 1


def test_auth_ignores_temp_shadow_users_and_blacklist(migrated_endpoint, provisioned_database):
    client, sessions, auth, actor_id, patient_id, _, service_id = migrated_endpoint
    _, runtime_engine, _, _, _ = provisioned_database
    created = []
    runtime_engine.dispose()

    @event.listens_for(runtime_engine, "connect")
    def hostile_shadow(connection, _):
        previous = connection.autocommit
        connection.autocommit = True
        try:
            with connection.cursor() as cursor:
                cursor.execute("CREATE TEMP TABLE users AS SELECT * FROM public.users WHERE id = %s", (actor_id,))
                cursor.execute("UPDATE pg_temp.users SET is_active = FALSE")
                cursor.execute("CREATE TEMP TABLE token_blacklist AS SELECT * FROM public.token_blacklist WHERE FALSE")
                cursor.execute("SET search_path = pg_temp, public, pg_catalog")
                created.append(True)
        finally:
            connection.autocommit = previous

    try:
        headers = {**auth, "Idempotency-Key": f"synthetic-{uuid4()}", "Idempotency-Intent": "new"}
        payload = _payload(patient_id, service_id, "0.00")
        first = client.post("/api/v1/doctor/visits/schedule-next", json=payload, headers=headers)
        assert created and first.status_code == 200, first.text
        claims = jwt.decode(auth["Authorization"].removeprefix("Bearer "), options={"verify_signature": False})
        with sessions() as db:
            db.execute(text("INSERT INTO public.token_blacklist (jti, user_id, expires_at, reason) "
                            "VALUES (:jti, :user_id, :expires, 'logout')"),
                       {"jti": claims["jti"], "user_id": actor_id, "expires": datetime.now(UTC) + timedelta(hours=1)})
            db.commit()
        retry = client.post("/api/v1/doctor/visits/schedule-next", json=payload, headers=headers)
        assert retry.status_code == 401, retry.text
        assert "confirmation" not in retry.json()
    finally:
        event.remove(runtime_engine, "connect", hostile_shadow)
        runtime_engine.dispose()


def test_hidden_blacklisted_jti_fails_closed_before_any_issuer_write(migrated_endpoint, provisioned_database):
    client, sessions, auth, actor_id, patient_id, _, service_id = migrated_endpoint
    admin_engine, _, _, _, runtime_role = provisioned_database
    quote = admin_engine.dialect.identifier_preparer.quote_identifier
    claims = jwt.decode(auth["Authorization"].removeprefix("Bearer "), options={"verify_signature": False})
    with admin_engine.begin() as db:
        had_rls, had_force = db.execute(text(
            "SELECT relrowsecurity, relforcerowsecurity FROM pg_catalog.pg_class "
            "WHERE oid='public.token_blacklist'::pg_catalog.regclass"
        )).one()
        db.execute(text("INSERT INTO public.token_blacklist (jti,user_id,expires_at,reason) "
                        "VALUES (:jti,:user_id,:expires,'logout')"),
                   {"jti": claims["jti"], "user_id": actor_id, "expires": datetime.now(UTC) + timedelta(hours=1)})
        db.execute(text("ALTER TABLE public.token_blacklist ENABLE ROW LEVEL SECURITY"))
        db.execute(text("ALTER TABLE public.token_blacklist FORCE ROW LEVEL SECURITY"))
        db.exec_driver_sql(f"CREATE POLICY synthetic_auth_hidden ON public.token_blacklist AS RESTRICTIVE FOR SELECT TO {quote(runtime_role)} USING (false)")
    headers = {**auth, "Idempotency-Key": f"synthetic-{uuid4()}", "Idempotency-Intent": "new"}
    payload = _payload(patient_id, service_id, "0.00")
    try:
        hidden = client.post("/api/v1/doctor/visits/schedule-next", json=payload, headers=headers)
        assert hidden.status_code == 503, hidden.text
        with admin_engine.begin() as db:
            db.execute(text("DROP POLICY synthetic_auth_hidden ON public.token_blacklist"))
        visible = client.post("/api/v1/doctor/visits/schedule-next", json=payload, headers=headers)
        assert visible.status_code == 401, visible.text
        with sessions() as db:
            assert db.query(DoctorPriceIntent).filter_by(patient_id=patient_id).count() == 0
    finally:
        with admin_engine.begin() as db:
            db.execute(text("DROP POLICY IF EXISTS synthetic_auth_hidden ON public.token_blacklist"))
            if not had_force:
                db.execute(text("ALTER TABLE public.token_blacklist NO FORCE ROW LEVEL SECURITY"))
            if not had_rls:
                db.execute(text("ALTER TABLE public.token_blacklist DISABLE ROW LEVEL SECURITY"))


def test_schedule_dependency_tree_has_no_early_auth_dependency():
    from app.api.deps import get_current_user
    from app.api.v1.endpoints.doctor_integration._visits import (
        _schedule_next_authenticated_user,
        router,
    )

    route = next(route for route in router.routes if getattr(route, "path", None) == "/doctor/visits/schedule-next")
    dependencies = []

    def visit(node):
        dependencies.append(node.call)
        for dependency in node.dependencies:
            visit(dependency)

    visit(route.dependant)
    assert dependencies.count(_schedule_next_authenticated_user) == 1
    assert get_current_user not in dependencies


@pytest.mark.parametrize("state", ["wrong_role", "inactive"])
def test_schedule_denial_uses_canonical_audit_gate(migrated_endpoint, monkeypatch, state):
    import app.core.audit as audit

    client, sessions, _, _, patient_id, _, service_id = migrated_endpoint
    suffix = uuid4().hex[:10]
    with sessions() as db:
        actor = User(username=f"denied_{suffix}", email=f"denied_{suffix}@example.test",
                     full_name="Synthetic Denial", hashed_password="synthetic",
                     role="Nurse" if state == "wrong_role" else "Admin",
                     is_active=state != "inactive", is_superuser=False)
        db.add(actor)
        db.commit()
        actor_id = actor.id
        token = authentication_service.create_access_token({"sub": str(actor.id), "username": actor.username,
            "role": actor.role, "is_active": actor.is_active, "is_superuser": False, "auth_epoch": actor.auth_epoch})
    events = []
    attribute = "log_critical_change" if state == "wrong_role" else "log_audit_event"
    original = getattr(audit, attribute)

    def recorded(*args, **kwargs):
        events.append((kwargs.get("user_id"), kwargs.get("action")))
        return original(*args, **kwargs)

    monkeypatch.setattr(audit, attribute, recorded)
    response = client.post("/api/v1/doctor/visits/schedule-next", json=_payload(patient_id, service_id),
                           headers={"Authorization": f"Bearer {token}", "Idempotency-Key": f"synthetic-{uuid4()}",
                                    "Idempotency-Intent": "new"})
    assert response.status_code == 403, response.text
    assert (actor_id, "ACCESS_DENIED") in events
    with sessions() as db:
        assert db.query(DoctorPriceIntent).filter_by(actor_user_id_snapshot=actor_id).count() == 0


@pytest.mark.parametrize("super_role", ["Nurse", "SuperAdmin"])
def test_schedule_superuser_role_bypass_is_preserved(migrated_endpoint, super_role):
    client, sessions, _, _, patient_id, _, service_id = migrated_endpoint
    suffix = uuid4().hex[:10]
    with sessions() as db:
        actor = User(username=f"super_{suffix}", email=f"super_{suffix}@example.test",
                     full_name="Synthetic Superuser", hashed_password="synthetic", role=super_role,
                     is_active=True, is_superuser=True)
        db.add(actor)
        db.commit()
        actor_id = actor.id
        token = authentication_service.create_access_token({"sub": str(actor.id), "username": actor.username,
            "role": actor.role, "is_active": True, "is_superuser": True, "auth_epoch": actor.auth_epoch})
    response = client.post("/api/v1/doctor/visits/schedule-next", json=_payload(patient_id, service_id, "0.00"),
                           headers={"Authorization": f"Bearer {token}", "Idempotency-Key": f"synthetic-{uuid4()}",
                                    "Idempotency-Intent": "new"})
    assert response.status_code == 200, response.text
    with sessions() as db:
        override = db.query(DoctorPriceOverride).filter_by(visit_id=response.json()["visit_id"]).one()
        assert override.requester_type == "admin" and override.requester_user_id == actor_id


@pytest.mark.parametrize("specialty,role", [("derma", "derma"), ("dental", "dentist")])
def test_specialty_issuer_pins_before_auth_and_returns_precommit_snapshot(
    migrated_endpoint, provisioned_database, monkeypatch, specialty, role,
):
    from app.services.dental_api_service import DentalApiService

    client, sessions, _, _, patient_id, _, service_id = migrated_endpoint
    _, runtime_engine, _, _, _ = provisioned_database
    suffix = uuid4().hex[:10]
    with sessions() as db:
        actor = User(username=f"special_{suffix}", email=f"special_{suffix}@example.test",
                     full_name="Synthetic Specialist", hashed_password="synthetic", role=role,
                     is_active=True, is_superuser=False)
        db.add(actor)
        db.flush()
        doctor = Doctor(user_id=actor.id, specialty="dermatology" if specialty == "derma" else "dental", active=True)
        db.add(doctor)
        db.flush()
        visit = Visit(patient_id=patient_id, doctor_id=doctor.id, visit_date=date.today(),
                      status="open", discount_mode="none", source="desk")
        service = db.get(Service, service_id)
        db.add(visit)
        db.flush()
        line = VisitService(visit_id=visit.id, service_id=service_id, code=service.code,
                            name=service.name, qty=1, price=Decimal("123.45"))
        db.add(line)
        db.commit()
        actor_id, visit_id, line_id = actor.id, visit.id, line.id
        token = authentication_service.create_access_token({"sub": str(actor.id), "username": actor.username,
            "role": actor.role, "is_active": True, "is_superuser": False, "auth_epoch": actor.auth_epoch})
    monkeypatch.setattr(DentalApiService, "send_price_override_notification", AsyncMock())
    runtime_engine.dispose()
    created = []

    @event.listens_for(runtime_engine, "connect")
    def hostile_shadow(connection, _):
        previous = connection.autocommit
        connection.autocommit = True
        try:
            with connection.cursor() as cursor:
                cursor.execute("CREATE TEMP TABLE users AS SELECT * FROM public.users WHERE id=%s", (actor_id,))
                cursor.execute("UPDATE pg_temp.users SET is_active=FALSE")
                cursor.execute("CREATE TEMP TABLE token_blacklist AS SELECT * FROM public.token_blacklist WHERE FALSE")
                cursor.execute("CREATE TEMP TABLE doctor_price_overrides AS SELECT * FROM public.doctor_price_overrides WHERE FALSE")
                cursor.execute("SET search_path = pg_temp, public, pg_catalog")
                created.append(True)
        finally:
            connection.autocommit = previous

    try:
        headers = {"Authorization": f"Bearer {token}"}
        payload = {"visit_id": visit_id, "service_id": service_id, "target_visit_service_id": line_id,
                   "new_price": "0.00", "reason": "synthetic"}
        response = client.post(f"/api/v1/{specialty}/price-override", json=payload, headers=headers)
        assert created and response.status_code == 200, response.text
        assert Decimal(str(response.json()["new_price"])) == Decimal("0.00")
        with sessions() as db:
            override = db.query(DoctorPriceOverride).filter_by(visit_id=visit_id).one()
            assert override.status == "pending" and override.target_visit_service_id == line_id
            claims = jwt.decode(token, options={"verify_signature": False})
            db.execute(text("INSERT INTO public.token_blacklist (jti,user_id,expires_at,reason) "
                            "VALUES (:jti,:user_id,:expires,'logout')"),
                       {"jti": claims["jti"], "user_id": actor_id, "expires": datetime.now(UTC) + timedelta(hours=1)})
            db.commit()
        revoked = client.post(f"/api/v1/{specialty}/price-override", json=payload, headers=headers)
        assert revoked.status_code == 401, revoked.text
        with sessions() as db:
            assert db.query(DoctorPriceOverride).filter_by(visit_id=visit_id).count() == 1
    finally:
        event.remove(runtime_engine, "connect", hostile_shadow)
        runtime_engine.dispose()


def test_unkeyed_retry_is_ambiguous_but_explicit_new_key_creates_new(migrated_endpoint):
    client, sessions, auth, _, patient_id, _, service_id = migrated_endpoint
    payload = _payload(patient_id, service_id)
    first = client.post("/api/v1/doctor/visits/schedule-next", json=payload, headers=auth)
    assert first.status_code == 200, first.text
    retry = client.post("/api/v1/doctor/visits/schedule-next", json=payload, headers=auth)
    assert retry.status_code == 409 and retry.json()["detail"]["code"] == "ambiguous_retry"
    new = client.post("/api/v1/doctor/visits/schedule-next", json=payload,
                      headers={**auth, "Idempotency-Key": f"synthetic-{uuid4()}", "Idempotency-Intent": "new"})
    assert new.status_code == 200, new.text
    assert new.json()["visit_id"] != first.json()["visit_id"]


def test_unassigned_patient_and_subcent_numeric_fail_without_writes(migrated_endpoint):
    client, sessions, auth, _, patient_id, foreign_id, service_id = migrated_endpoint
    headers = {**auth, "Idempotency-Key": f"synthetic-{uuid4()}", "Idempotency-Intent": "new"}
    denied = client.post("/api/v1/doctor/visits/schedule-next", json=_payload(foreign_id, service_id, "1.00"), headers=headers)
    assert denied.status_code == 403, denied.text
    payload = _payload(patient_id, service_id)
    raw = json.dumps(payload).replace('"quantity": 1', '"quantity": 1, "custom_price": 1e-1000')
    invalid = client.post("/api/v1/doctor/visits/schedule-next", content=raw,
                          headers={**headers, "Content-Type": "application/json"})
    assert invalid.status_code == 422, invalid.text
    with sessions() as db:
        assert db.query(DoctorPriceIntent).filter_by(patient_id=foreign_id).count() == 0
        assert db.query(DoctorPriceIntent).filter_by(patient_id=patient_id).count() == 0


def test_mismatched_trusted_invitation_schema_fails_before_clinical_reads(migrated_endpoint, provisioned_database, monkeypatch):
    from app.services.doctor_price_intent_service import DoctorPriceIntentService
    client, sessions, auth, _, patient_id, _, service_id = migrated_endpoint
    admin_engine, _, schema_owner, _, _ = provisioned_database
    shadow = "synthetic_other_" + uuid4().hex[:12]
    quote = admin_engine.dialect.identifier_preparer.quote_identifier
    with admin_engine.begin() as db:
        db.exec_driver_sql(f"CREATE SCHEMA {quote(shadow)} AUTHORIZATION {quote(schema_owner)}")
        db.execute(text(f"CREATE TABLE {quote(shadow)}.patients AS SELECT * FROM public.patients WHERE id=:id"), {"id": patient_id})
        db.execute(text(f"CREATE TABLE {quote(shadow)}.visits AS SELECT * FROM public.visits WHERE patient_id=:id"), {"id": patient_id})
        assert db.execute(text(f"SELECT count(*) FROM {quote(shadow)}.patients WHERE id=:id"), {"id": patient_id}).scalar_one() == 1
    try:
        monkeypatch.setattr(settings, "INVITATION_DB_SCHEMA", shadow)
        monkeypatch.setattr(settings, "INVITATION_DB_SCHEMA_OWNER", schema_owner)
        calls = []
        monkeypatch.setattr(DoctorPriceIntentService, "pin_trusted_schema", lambda self: calls.append(True))
        result = client.post("/api/v1/doctor/visits/schedule-next", json=_payload(patient_id, service_id),
                             headers={**auth, "Idempotency-Key": f"synthetic-{uuid4()}", "Idempotency-Intent": "new"})
        assert result.status_code == 503, result.text
        assert calls == []
        with sessions() as db:
            assert db.query(DoctorPriceIntent).filter_by(patient_id=patient_id).count() == 0
            assert db.query(VisitInvitationDelivery).filter_by(patient_id=patient_id).count() == 0
    finally:
        with admin_engine.begin() as db:
            db.exec_driver_sql(f"DROP SCHEMA IF EXISTS {quote(shadow)} CASCADE")


def test_replay_override_lock_conflict_rolls_back_and_recovers(migrated_endpoint):
    client, sessions, auth, _, patient_id, _, service_id = migrated_endpoint
    payload = _payload(patient_id, service_id, "0.00")
    headers = {**auth, "Idempotency-Key": f"synthetic-{uuid4()}", "Idempotency-Intent": "new"}
    first = client.post("/api/v1/doctor/visits/schedule-next", json=payload, headers=headers)
    assert first.status_code == 200, first.text
    override_id = first.json()["price_override_requests"][0]["id"]
    with sessions() as blocker:
        blocker.execute(text("SELECT id FROM doctor_price_overrides WHERE id=:id FOR UPDATE"), {"id": override_id})
        blocked = client.post("/api/v1/doctor/visits/schedule-next", json=payload, headers=headers)
        assert blocked.status_code == 409, blocked.text
        assert blocked.json()["detail"]["code"] == "pending_outcome"
        blocker.rollback()
    replay = client.post("/api/v1/doctor/visits/schedule-next", json=payload, headers=headers)
    assert replay.status_code == 200 and replay.json()["idempotent_replay"] is True


def test_override_deleted_after_evidence_probe_never_replays_success(migrated_endpoint, provisioned_database):
    import threading
    from concurrent.futures import ThreadPoolExecutor

    client, sessions, auth, _, patient_id, _, service_id = migrated_endpoint
    _, runtime_engine, _, _, _ = provisioned_database
    payload = _payload(patient_id, service_id, "0.00")
    headers = {**auth, "Idempotency-Key": f"synthetic-{uuid4()}", "Idempotency-Intent": "new"}
    first = client.post("/api/v1/doctor/visits/schedule-next", json=payload, headers=headers)
    assert first.status_code == 200, first.text
    override_id = first.json()["price_override_requests"][0]["id"]
    reached, proceed = threading.Event(), threading.Event()
    seen = [False]

    def barrier(_conn, _cursor, statement, _params, _ctx, _many):
        if not seen[0] and statement.lstrip().upper().startswith("SELECT") and "FROM doctor_price_intent_lines" in statement:
            seen[0] = True
            reached.set()
            assert proceed.wait(timeout=10)

    event.listen(runtime_engine, "after_cursor_execute", barrier)
    try:
        with ThreadPoolExecutor(max_workers=1) as pool:
            pending = pool.submit(client.post, "/api/v1/doctor/visits/schedule-next", json=payload, headers=headers)
            assert reached.wait(timeout=10)
            with sessions() as writer:
                writer.execute(text("DELETE FROM doctor_price_overrides WHERE id=:id"), {"id": override_id})
                writer.commit()
            proceed.set()
            replay = pending.result(timeout=15)
        assert replay.status_code == 409, replay.text
        assert replay.json()["detail"]["code"] == "ambiguous_retry"
        again = client.post("/api/v1/doctor/visits/schedule-next", json=payload, headers=headers)
        assert again.status_code == 409
        with sessions() as db:
            assert db.query(DoctorPriceIntent).filter_by(patient_id=patient_id).count() == 1
            assert db.query(VisitInvitationDelivery).filter_by(patient_id=patient_id).count() == 1
    finally:
        proceed.set()
        event.remove(runtime_engine, "after_cursor_execute", barrier)
