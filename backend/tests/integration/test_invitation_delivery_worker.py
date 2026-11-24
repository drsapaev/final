"""Synthetic arq outbox tests; Redis and external delivery are mocked."""
import asyncio
import os
import time
from datetime import UTC, date, datetime, timedelta
from uuid import uuid4

import pytest
import sqlalchemy as sa
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.schema import CreateSchema, DropSchema

from app.db.base_class import Base
from app.models.authentication import TokenBlacklist
from app.models.patient import Patient
from app.models.user import User
from app.models.visit import Visit
from app.models.visit_invitation_delivery import VisitInvitationDelivery
from app.services.profile_contact_security import ProfileBearerContext
from app.services.visit_invitation_delivery import stage_visit_invitation
from app.tasks import invitation_delivery as worker


class FakeRedis:
    def __init__(self):
        self.data = {}
        self.jobs = []

    async def get(self, key):
        return self.data.get(key)

    async def set(self, key, value):
        self.data[key] = value

    async def enqueue_job(self, name, **kwargs):
        self.jobs.append((name, kwargs))
        return object()


class FakeSender:
    calls = []
    succeed = True

    def __init__(self, db):
        self.db = db

    async def _send_pwa_invitation(self, patient, data, *, db, sms_opted_in):
        self.calls.append(data["visit_id"])
        if not self.succeed:
            raise TimeoutError("SYNTHETIC-SECRET-MUST-NOT-LOG")
        return {"success": True}


@pytest.fixture
def setup(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{tmp_path / 'invitation-worker.db'}")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)
    monkeypatch.setattr(worker, "SessionLocal", session)
    monkeypatch.setattr(worker, "NotificationService", FakeSender)
    FakeSender.calls = []
    FakeSender.succeed = True
    try:
        yield session
    finally:
        engine.dispose()


def _stage(session, channel="pwa"):
    with session() as db:
        actor = User(username="synthetic-" + uuid4().hex, hashed_password="synthetic", role="Admin", is_active=True, is_superuser=False)
        patient = Patient(first_name="SYNTHETIC", last_name="PATIENT", phone="+998900000000", notification_owner_generation=7)
        db.add_all([actor, patient])
        db.flush()
        visit = Visit(patient_id=patient.id, visit_date=date(2030, 1, 1), status="pending_confirmation",
                      source="desk", department="mixed", confirmation_context_epoch=9,
                      confirmation_token="synthetic-only-bearer", confirmation_expires_at=datetime.now(UTC) + timedelta(hours=1))
        db.add(visit)
        db.flush()
        bearer = ProfileBearerContext(actor.id, actor.auth_epoch, str(uuid4()), int(time.time()) + 3600, None)
        delivery_id = stage_visit_invitation(db, patient_id=patient.id, visit_id=visit.id, channel=channel,
                                             bearer=bearer, requester_type="admin")
        db.commit()
        return delivery_id, bearer


def test_sweep_and_worker_deliver_only_once(setup):
    delivery_id, _ = _stage(setup)
    redis = FakeRedis()
    asyncio.run(worker.run_visit_invitation_sweep({"redis": redis}))
    assert len(redis.jobs) == 1
    name, args = redis.jobs[0]
    assert name == "deliver_visit_invitation" and args["delivery_id"] == delivery_id
    assert "synthetic-only-bearer" not in repr(redis.jobs) and "998900000000" not in repr(redis.jobs)
    asyncio.run(worker.deliver_visit_invitation({}, delivery_id=delivery_id))
    asyncio.run(worker.deliver_visit_invitation({}, delivery_id=delivery_id))
    assert len(FakeSender.calls) == 1
    with setup() as db:
        assert db.get(VisitInvitationDelivery, delivery_id).state == "sent"


def test_timeout_leaves_unknown_and_sweep_never_retries(setup, caplog):
    delivery_id, _ = _stage(setup)
    FakeSender.succeed = False
    asyncio.run(worker.deliver_visit_invitation({}, delivery_id=delivery_id))
    redis = FakeRedis()
    asyncio.run(worker.run_visit_invitation_sweep({"redis": redis}))
    assert not redis.jobs and len(FakeSender.calls) == 1
    assert "SYNTHETIC-SECRET-MUST-NOT-LOG" not in caplog.text
    with setup() as db:
        assert db.get(VisitInvitationDelivery, delivery_id).state == "unknown"


def test_logout_after_enqueue_cancels_without_send(setup):
    delivery_id, bearer = _stage(setup)
    redis = FakeRedis()
    asyncio.run(worker.run_visit_invitation_sweep({"redis": redis}))
    with setup() as db:
        db.add(TokenBlacklist(jti=bearer.jti, user_id=bearer.user_id,
                              expires_at=datetime.now(UTC) + timedelta(hours=1), reason="logout"))
        db.commit()
    asyncio.run(worker.deliver_visit_invitation({}, delivery_id=delivery_id))
    assert not FakeSender.calls
    with setup() as db:
        assert db.get(VisitInvitationDelivery, delivery_id).state == "cancelled"


def test_cursor_moves_past_stuck_phone_and_wraps(setup, monkeypatch):
    monkeypatch.setattr(worker, "_BATCH_SIZE", 1)
    first, _ = _stage(setup, "phone")
    second, _ = _stage(setup, "pwa")
    redis = FakeRedis()
    for _ in range(3):
        asyncio.run(worker.run_visit_invitation_sweep({"redis": redis}))
    assert [job[1]["delivery_id"] for job in redis.jobs] == [first, second, first]


def test_worker_registry_enables_sweep_and_consumer():
    from app.tasks.worker import WorkerSettings

    assert worker.deliver_visit_invitation in WorkerSettings.functions
    assert worker.run_visit_invitation_sweep in WorkerSettings.functions
    assert any(job.coroutine == worker.run_visit_invitation_sweep for job in WorkerSettings.cron_jobs)


@pytest.mark.integration
def test_postgres_worker_nonowner_sweep_and_revoked_issuer(monkeypatch):
    from app.core.config import settings
    from app.db.capability_namespace import capability_schema_name
    from app.models.clinic import Doctor
    from app.models.visit import VisitService
    from tests.integration.test_invitation_subject_nonowner_pg import (
        install_invitation_subject_fence,
    )
    from tests.integration.test_visit_invitation_delivery import (
        _approval_migration,
        _issuer_migration,
        _migration,
    )

    raw = os.environ.get("DATABASE_URL", "")
    if not raw or make_url(raw).get_backend_name() != "postgresql" or not (make_url(raw).database or "").startswith("clinic_test"):
        pytest.skip("requires disposable clinic_test PostgreSQL")
    suffix = uuid4().hex
    schema, role, password = "invite_worker_" + suffix, "invite_worker_login_" + suffix, "synthetic-" + suffix
    cap = "invite_worker_cap_" + suffix
    admin = create_engine(raw)
    with admin.begin() as conn:
        conn.execute(CreateSchema(schema))
        conn.exec_driver_sql(f'CREATE ROLE "{role}" LOGIN PASSWORD \'{password}\'')
        conn.exec_driver_sql(f'CREATE ROLE "{cap}" NOLOGIN')
        owner_name = conn.execute(sa.text("SELECT current_user")).scalar_one()
    owner = create_engine(raw, connect_args={"options": f"-csearch_path={schema}"})
    runtime = None
    try:
        from alembic.migration import MigrationContext
        from alembic.operations import Operations

        with owner.begin() as conn:
            for model in (User, Doctor, TokenBlacklist, Patient, Visit, VisitService):
                conn.execute(sa.schema.CreateTable(model.__table__, include_foreign_key_constraints=[]))
            conn.execute(sa.text("CREATE TABLE doctor_price_overrides (id INTEGER PRIMARY KEY)"))
            migration = _migration()
            migration.op = Operations(MigrationContext.configure(conn))
            migration.upgrade()
            _issuer_migration(conn)
            _approval_migration(conn)
            conn.exec_driver_sql(f'GRANT SELECT ON "{schema}".doctors TO "{role}"')
        install_invitation_subject_fence(owner, schema=schema, owner_name=owner_name,
                                         runtime_role=role, subject_cap_role=cap, monkeypatch=monkeypatch)
        import importlib.util
        from pathlib import Path

        path = Path(__file__).resolve().parents[2] / "scripts/provision_invitation_delivery_role.py"
        spec = importlib.util.spec_from_file_location("invite_worker_provision", path)
        provisioner = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(provisioner)
        provisioner.provision(owner, schema, role)
        monkeypatch.setattr(settings, "INVITATION_DB_SCHEMA", schema)
        monkeypatch.setattr(settings, "INVITATION_DB_SCHEMA_OWNER", owner_name)
        monkeypatch.setattr(settings, "INVITATION_DB_TABLE_OWNER", owner_name)
        runtime = create_engine(make_url(raw).set(username=role, password=password), connect_args={"options": f"-csearch_path={schema}"})
        factory = sessionmaker(bind=runtime)
        monkeypatch.setattr(worker, "SessionLocal", factory)
        monkeypatch.setattr(worker, "NotificationService", FakeSender)
        FakeSender.calls = []
        FakeSender.succeed = True
        with Session(owner) as db:
            actor = User(username="synthetic-worker-issuer", hashed_password="synthetic", role="Admin", is_active=True, is_superuser=False)
            patient = Patient(first_name="SYNTHETIC", last_name="PATIENT", phone="+998900000000", notification_owner_generation=7)
            db.add_all([actor, patient])
            db.flush()
            visit = Visit(patient_id=patient.id, visit_date=date(2030, 1, 1), status="pending_confirmation", source="desk", department="mixed", confirmation_context_epoch=9, confirmation_token="synthetic-only-bearer", confirmation_expires_at=datetime.now(UTC) + timedelta(hours=1))
            db.add(visit)
            db.flush()
            patient_id, visit_id = patient.id, visit.id
            bearer = ProfileBearerContext(actor.id, actor.auth_epoch, str(uuid4()), int(time.time()) + 3600, None)
            db.commit()
        with factory() as db:
            delivery_id = stage_visit_invitation(db, patient_id=patient_id, visit_id=visit_id, channel="pwa", bearer=bearer, requester_type="admin")
            db.commit()
        redis = FakeRedis()
        asyncio.run(worker.run_visit_invitation_sweep({"redis": redis}))
        assert [job[1]["delivery_id"] for job in redis.jobs] == [delivery_id]
        asyncio.run(worker.deliver_visit_invitation({}, delivery_id=delivery_id))
        asyncio.run(worker.deliver_visit_invitation({}, delivery_id=delivery_id))
        assert len(FakeSender.calls) == 1
        with factory() as db:
            assert db.get(VisitInvitationDelivery, delivery_id).state == "sent"
        with Session(owner) as db:
            later = Visit(patient_id=patient_id, visit_date=date(2030, 1, 2), status="pending_confirmation", source="desk", department="mixed", confirmation_context_epoch=10, confirmation_token="synthetic-other-bearer", confirmation_expires_at=datetime.now(UTC) + timedelta(hours=1))
            db.add(later)
            db.flush()
            later_id = later.id
            db.commit()
        with factory() as db:
            second = stage_visit_invitation(db, patient_id=patient_id, visit_id=later_id, channel="pwa", bearer=bearer, requester_type="admin")
            db.commit()
        with Session(owner) as db:
            db.add(TokenBlacklist(jti=bearer.jti, user_id=bearer.user_id, expires_at=datetime.now(UTC) + timedelta(hours=1), reason="logout"))
            db.commit()
        asyncio.run(worker.deliver_visit_invitation({}, delivery_id=second))
        assert len(FakeSender.calls) == 1
        with factory() as db:
            assert db.get(VisitInvitationDelivery, second).state == "cancelled"
        # A hidden revoked JTI is not evidence of a valid issuer. The shared
        # pre-auth proof must fail before a new worker attempt can dispatch.
        with owner.begin() as conn:
            conn.exec_driver_sql(f'ALTER POLICY synthetic_subject_select ON "{schema}".token_blacklist USING (false)')
        with factory() as db:
            from app.services.visit_invitation_delivery import (
                InvitationRuntimeUnavailable,
            )

            with pytest.raises(InvitationRuntimeUnavailable):
                stage_visit_invitation(db, patient_id=patient_id, visit_id=later_id,
                                       channel="pwa", bearer=bearer, requester_type="admin")
            db.rollback()
        assert len(FakeSender.calls) == 1
    finally:
        if runtime is not None:
            runtime.dispose()
        owner.dispose()
        with admin.begin() as conn:
            conn.execute(DropSchema(schema, cascade=True))
            conn.execute(DropSchema(capability_schema_name(schema), cascade=True))
            conn.exec_driver_sql(f'DROP ROLE "{role}"')
            conn.exec_driver_sql(f'DROP ROLE "{cap}"')
        admin.dispose()
