"""Neutral registrar inbox task with authorized patient-data lookup."""
import asyncio
import importlib.util
import os
import threading
import time
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
from fastapi import HTTPException, Request, Response
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session
from sqlalchemy.schema import CreateSchema, DropSchema

from app.models.notification import NotificationDelivery, NotificationEvent
from app.models.patient import Patient
from app.models.visit import Visit
from app.models.visit_invitation_delivery import VisitInvitationDelivery
from app.services.notification_platform_service import NotificationPlatformService
from app.services.notification_service import NotificationService
from app.services.profile_contact_security import ProfileBearerContext
from app.services.visit_invitation_delivery import (
    deliver_registrar_invitation,
    stage_visit_invitation,
)
from tests.conftest import mint_access_token
from tests.integration.test_derma_price_override_integrity import _create_user


def _make_task(db, monkeypatch):
    registrar = _create_user(db, role="Registrar", label="synthetic-invitation")
    issuer = _create_user(db, role="Admin", label="synthetic-issuer")
    patient = Patient(first_name="SYNTHETIC", last_name="PATIENT", phone="+998900000000", notification_owner_generation=17)
    db.add(patient)
    db.flush()
    visit = Visit(patient_id=patient.id, visit_date=date(2030, 1, 2), visit_time="10:30",
                  status="pending_confirmation", source="desk", department="mixed",
                  confirmation_context_epoch=19, confirmation_token="synthetic-only-bearer",
                  confirmation_expires_at=datetime.now(UTC) + timedelta(hours=1))
    db.add(visit)
    db.flush()
    bearer = ProfileBearerContext(issuer.id, issuer.auth_epoch, str(uuid4()), int(time.time()) + 3600, None)
    intent_id = stage_visit_invitation(db, patient_id=patient.id, visit_id=visit.id, channel="phone", bearer=bearer, requester_type="admin")
    db.commit()
    broadcasts = []

    async def broadcast(platform, user_id, delivery, **kwargs):
        broadcasts.append(platform.serialize_delivery(delivery))

    monkeypatch.setattr(NotificationPlatformService, "_broadcast_delivery", broadcast)
    assert asyncio.run(deliver_registrar_invitation(db, intent_id, NotificationService(db)))
    assert not asyncio.run(deliver_registrar_invitation(db, intent_id, NotificationService(db)))
    event = db.query(NotificationEvent).filter(NotificationEvent.source_module == "visit_confirmation_secure").one()
    assert db.get(VisitInvitationDelivery, intent_id).state == "sent"
    assert broadcasts and all("SYNTHETIC" not in repr(item) and "998900000000" not in repr(item)
                              and "synthetic-only-bearer" not in repr(item) for item in broadcasts)
    assert event.deep_link == f"/registrar?invitation={event.correlation_id}"
    assert event.payload_snapshot["metadata"] == {}
    return registrar, patient.id, visit.id, event.correlation_id


def test_task_read_authorized_and_no_store(client, db_session, monkeypatch):
    registrar, patient_id, visit_id, handle = _make_task(db_session, monkeypatch)
    response = client.get(f"/api/v1/notifications/visit-invitation-tasks/{handle}",
                          headers={"Authorization": f"Bearer {mint_access_token(registrar)}"})
    assert response.status_code == 200, response.text
    assert response.headers["cache-control"] == "private, no-store"
    assert response.json() == {"visit_id": visit_id, "patient_name": "PATIENT SYNTHETIC",
                               "patient_phone": "+998900000000", "visit_date": "2030-01-02", "visit_time": "10:30"}
    assert "synthetic-only-bearer" not in response.text and str(patient_id) not in response.json().keys()


def test_other_recipient_and_transferred_owner_cannot_read(client, db_session, monkeypatch):
    registrar, patient_id, _visit_id, handle = _make_task(db_session, monkeypatch)
    other = _create_user(db_session, role="Registrar", label="other")
    url = f"/api/v1/notifications/visit-invitation-tasks/{handle}"
    response = client.get(url, headers={"Authorization": f"Bearer {mint_access_token(other)}"})
    assert response.status_code == 404 and "SYNTHETIC" not in response.text
    patient = db_session.get(Patient, patient_id)
    patient.notification_owner_generation += 1
    db_session.commit()
    response = client.get(url, headers={"Authorization": f"Bearer {mint_access_token(registrar)}"})
    assert response.status_code == 404 and "SYNTHETIC" not in response.text


def test_role_revocation_denies_task(client, db_session, monkeypatch):
    registrar, _patient_id, _visit_id, handle = _make_task(db_session, monkeypatch)
    token = mint_access_token(registrar)
    registrar.role = "Patient"
    db_session.commit()
    response = client.get(f"/api/v1/notifications/visit-invitation-tasks/{handle}",
                          headers={"Authorization": f"Bearer {token}"})
    assert response.status_code in (401, 403, 404) and "SYNTHETIC" not in response.text


@pytest.mark.parametrize("delivery_state", ["pending", "unknown", "sent", "cancelled"])
def test_admin_status_is_context_bound_and_contains_no_patient_details(client, db_session, monkeypatch, delivery_state):
    _registrar, patient_id, visit_id, _handle = _make_task(db_session, monkeypatch)
    admin = _create_user(db_session, role="Admin", label="synthetic-status")
    intent = db_session.query(VisitInvitationDelivery).filter(VisitInvitationDelivery.visit_id == visit_id).one()
    intent.state = delivery_state
    db_session.commit()
    headers = {"Authorization": f"Bearer {mint_access_token(admin)}"}
    url = f"/api/v1/notifications/visit-invitation-status/{visit_id}"
    response = client.get(url, headers=headers)
    assert response.status_code == 200, response.text
    assert response.headers["cache-control"] == "private, no-store"
    assert response.json() == {"visit_id": visit_id, "state": delivery_state, "channel": "phone", "confirmation_expired": False}
    assert "SYNTHETIC" not in response.text and "998900000000" not in response.text and "synthetic-only-bearer" not in response.text
    # A new owner must never see the old owner's delivery outcome.
    db_session.get(Patient, patient_id).notification_owner_generation += 1
    db_session.commit()
    response = client.get(url, headers=headers)
    assert response.status_code == 200 and response.json()["state"] == "none"


def test_status_rejects_registrar_and_revoked_session(client, db_session, monkeypatch):
    import jwt

    from app.core.config import settings
    from app.models.authentication import TokenBlacklist

    registrar, _patient_id, visit_id, _handle = _make_task(db_session, monkeypatch)
    url = f"/api/v1/notifications/visit-invitation-status/{visit_id}"
    response = client.get(url, headers={"Authorization": f"Bearer {mint_access_token(registrar)}"})
    assert response.status_code in (401, 403) and "SYNTHETIC" not in response.text
    assert response.headers["cache-control"] == "private, no-store"
    admin = _create_user(db_session, role="Admin", label="synthetic-status-revoked")
    token = mint_access_token(admin)
    claims = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    db_session.add(TokenBlacklist(jti=claims["jti"], user_id=admin.id,
                                  expires_at=datetime.now(UTC) + timedelta(hours=1), reason="logout"))
    db_session.commit()
    response = client.get(url, headers={"Authorization": f"Bearer {token}"})
    assert response.status_code in (401, 403) and "SYNTHETIC" not in response.text
    assert response.headers["cache-control"] == "private, no-store"
    invalid = client.get("/api/v1/notifications/visit-invitation-status/not-a-number",
                         headers={"Authorization": f"Bearer {mint_access_token(admin)}"})
    assert invalid.status_code == 422 and invalid.headers["cache-control"] == "private, no-store"


@pytest.mark.integration
def test_postgres_read_and_owner_transfer_serialize_both_orders(monkeypatch):
    import jwt

    from app.api.v1.endpoints.notifications import read_visit_invitation_task
    from app.core.config import settings
    from app.db.capability_namespace import capability_schema_name
    from app.models.authentication import TokenBlacklist
    from app.models.clinic import Doctor
    from app.models.patient_access_audit import PatientAccessAuditLog
    from app.models.user import User
    from app.models.visit import VisitService
    from app.services import patient_access_audit
    from tests.integration.test_invitation_subject_nonowner_pg import (
        install_invitation_subject_fence,
    )

    raw = os.environ.get("DATABASE_URL", "")
    if not raw or make_url(raw).get_backend_name() != "postgresql" or not (make_url(raw).database or "").startswith("clinic_test"):
        pytest.skip("requires disposable clinic_test PostgreSQL")
    suffix = uuid4().hex
    schema, role, password = "invitation_read_" + suffix, "invite_read_" + suffix, "synthetic-" + suffix
    cap = "invite_read_cap_" + suffix
    admin = sa.create_engine(raw)
    with admin.begin() as conn:
        conn.execute(CreateSchema(schema))
        conn.exec_driver_sql(f'CREATE ROLE "{role}" LOGIN PASSWORD \'{password}\'')
        conn.exec_driver_sql(f'CREATE ROLE "{cap}" NOLOGIN')
        owner_name = conn.execute(sa.text("SELECT current_user")).scalar_one()
    engine = sa.create_engine(raw, connect_args={"options": f"-csearch_path={schema} -clock_timeout=5000"})
    runtime = None
    try:
        with engine.begin() as conn:
            for model in (User, Doctor, Patient, Visit, VisitService, NotificationEvent, NotificationDelivery, TokenBlacklist, PatientAccessAuditLog):
                conn.execute(sa.schema.CreateTable(model.__table__, include_foreign_key_constraints=[]))
            conn.execute(sa.text("CREATE TABLE doctor_price_overrides (id INTEGER PRIMARY KEY)"))
            migration_path = Path(__file__).resolve().parents[2] / "alembic/versions/0117_visit_invitation_delivery.py"
            spec = importlib.util.spec_from_file_location("invitation_read_migration", migration_path)
            migration = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(migration)
            migration.op = Operations(MigrationContext.configure(conn))
            migration.upgrade()
            issuer_path = Path(__file__).resolve().parents[2] / "alembic/versions/0126_invitation_issuer_auth.py"
            issuer_spec = importlib.util.spec_from_file_location("invitation_read_issuer", issuer_path)
            issuer_migration = importlib.util.module_from_spec(issuer_spec)
            issuer_spec.loader.exec_module(issuer_migration)
            issuer_migration.op = Operations(MigrationContext.configure(conn))
            issuer_migration.upgrade()
            from tests.integration.test_visit_invitation_delivery import (
                _approval_migration,
            )
            _approval_migration(conn)
            for name in ("notification_events", "notification_deliveries", "patient_access_audit_logs"):
                conn.exec_driver_sql(f'GRANT SELECT,INSERT,UPDATE ON "{schema}"."{name}" TO "{role}"')
            conn.exec_driver_sql(f'GRANT USAGE ON ALL SEQUENCES IN SCHEMA "{schema}" TO "{role}"')
        install_invitation_subject_fence(engine, schema=schema, owner_name=owner_name,
                                         runtime_role=role, subject_cap_role=cap, monkeypatch=monkeypatch)
        provision_path = Path(__file__).resolve().parents[2] / "scripts/provision_invitation_delivery_role.py"
        spec = importlib.util.spec_from_file_location("invitation_read_provision", provision_path)
        provisioner = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(provisioner)
        provisioner.provision(engine, schema, role)
        monkeypatch.setattr(settings, "INVITATION_DB_SCHEMA", schema)
        monkeypatch.setattr(settings, "INVITATION_DB_SCHEMA_OWNER", owner_name)
        monkeypatch.setattr(settings, "INVITATION_DB_TABLE_OWNER", owner_name)
        runtime = sa.create_engine(make_url(raw).set(username=role, password=password), connect_args={"options": f"-csearch_path={schema} -clock_timeout=5000"})
        with Session(engine) as db:
            actor = User(username="synthetic-invitation-reader", email="synthetic-invitation@example.invalid", hashed_password="synthetic", role="Registrar", is_active=True, is_superuser=False)
            patient = Patient(first_name="SYNTHETIC", last_name="PATIENT", phone="+998900000000", notification_owner_generation=7)
            db.add_all([actor, patient])
            db.flush()
            visit = Visit(patient_id=patient.id, visit_date=date(2030, 1, 2), visit_time="10:30", status="pending_confirmation", source="desk", department="mixed", confirmation_context_epoch=9, confirmation_token="synthetic-only-bearer", confirmation_expires_at=datetime.now(UTC) + timedelta(hours=1))
            db.add(visit)
            db.flush()
            db.refresh(patient)
            db.refresh(visit)
            from app.services.visit_invitation_delivery import _digest
            intent = VisitInvitationDelivery(visit_id=visit.id, visit_id_snapshot=visit.id, patient_id=patient.id, patient_id_snapshot=patient.id, owner_generation=patient.notification_owner_generation, context_epoch=visit.confirmation_context_epoch, token_digest=_digest(visit.confirmation_token), channel="phone", state="sent")
            db.add(intent)
            db.flush()
            handle = str(uuid4())
            event = NotificationEvent(event_type="appointment_confirmation_task", correlation_id=handle, dedup_key="synthetic-event", source_module="visit_confirmation_secure", entity_type="visit_invitation_delivery", entity_id=str(intent.id), title="Задача", message="Новая задача")
            db.add(event)
            db.flush()
            db.add(NotificationDelivery(event_id=event.id, recipient_type="user", recipient_id=actor.id, role="registrar", channel="inbox", dedup_key="synthetic-delivery", sequence_id=1, delivery_status="delivered"))
            db.commit()
            actor_id, patient_id, token = actor.id, patient.id, mint_access_token(actor)
        request = Request({"type": "http", "method": "GET", "path": "/", "headers": [(b"authorization", f"Bearer {token}".encode())], "client": ("127.0.0.1", 1234), "server": ("test", 80), "scheme": "http"})
        entered, release, transfer_started, transfer_done, reader_started = (threading.Event() for _ in range(5))
        original = patient_access_audit._build_patient_access_entry

        def block_audit(*args, **kwargs):
            entered.set()
            assert release.wait(5)
            return original(*args, **kwargs)

        monkeypatch.setattr(patient_access_audit, "_build_patient_access_entry", block_audit)
        results, errors = [], []

        def read():
            try:
                with Session(runtime) as db:
                    actor = db.get(User, actor_id)
                    reader_started.set()
                    results.append(read_visit_invitation_task(handle, request, Response(), db, actor))
            except Exception as exc:
                errors.append(exc)

        def transfer():
            try:
                with Session(engine) as db:
                    transfer_started.set()
                    db.execute(sa.update(Patient).where(Patient.id == patient_id).values(user_id=actor_id))
                    db.commit()
                    transfer_done.set()
            except Exception as exc:
                errors.append(exc)

        reader = threading.Thread(target=read)
        reader.start()
        assert entered.wait(5)
        writer = threading.Thread(target=transfer)
        writer.start()
        assert transfer_started.wait(5) and not transfer_done.wait(0.25)
        release.set()
        reader.join(10)
        writer.join(10)
        assert not errors and transfer_done.is_set() and results[0].patient_name == "PATIENT SYNTHETIC"
        # Transfer commits first: stale handle yields 404 without exposing PHI.
        with Session(runtime) as db:
            actor = db.get(User, actor_id)
            with pytest.raises(HTTPException) as denied:
                read_visit_invitation_task(handle, request, Response(), db, actor)
            assert denied.value.status_code == 404 and "SYNTHETIC" not in str(denied.value.detail)
        # Logout commits while the request is waiting for the same User lock.
        # The handler must recheck the exact JTI after acquiring that lock.
        claims = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        assert claims.get("jti")
        results.clear()
        errors.clear()
        logout = Session(engine)
        try:
            logout.query(User).filter(User.id == actor_id).with_for_update().one()
            logout.add(TokenBlacklist(jti=claims["jti"], user_id=actor_id,
                                      expires_at=datetime.now(UTC) + timedelta(hours=1), reason="logout"))
            logout.flush()
            reader_started.clear()
            waiting = threading.Thread(target=read)
            waiting.start()
            assert reader_started.wait(5)
            assert not threading.Event().wait(0.25) and waiting.is_alive()
            logout.commit()
            waiting.join(10)
            assert not waiting.is_alive() and not results and len(errors) == 1
            assert isinstance(errors[0], HTTPException) and errors[0].status_code == 404
        finally:
            logout.close()
    finally:
        if runtime is not None:
            runtime.dispose()
        engine.dispose()
        with admin.begin() as conn:
            conn.execute(DropSchema(schema, cascade=True))
            conn.execute(DropSchema(capability_schema_name(schema), cascade=True))
            conn.exec_driver_sql(f'DROP ROLE "{role}"')
            conn.exec_driver_sql(f'DROP ROLE "{cap}"')
        admin.dispose()
