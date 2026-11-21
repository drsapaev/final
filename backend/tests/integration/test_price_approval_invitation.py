"""Synthetic approval-scoped invitation and neutral recovery tests."""
import asyncio
import os
import threading
import time
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy.engine import make_url
from sqlalchemy.schema import CreateSchema, DropSchema

from app.models.doctor_price_override import DoctorPriceOverride
from app.models.notification import NotificationEvent
from app.models.patient import Patient
from app.models.service import Service
from app.models.visit import Visit, VisitService
from app.models.visit_invitation_delivery import (
    VisitInvitationApprovalRecovery,
    VisitInvitationDelivery,
    VisitInvitationPriceApprovalAuth,
)
from app.services.notification_platform_service import NotificationPlatformService
from app.services.notification_service import NotificationService
from app.services.profile_contact_security import ProfileBearerContext
from app.services.visit_invitation_delivery import (
    InvitationContextChanged,
    claim_visit_invitation,
    deliver_price_approval_recovery,
    send_claimed_visit_invitation,
    stage_price_approval_invitation,
    stage_price_approval_recovery,
)
from tests.conftest import mint_access_token
from tests.integration.test_derma_price_override_integrity import _create_user


@pytest.fixture
def approved(db_session):
    actor = _create_user(db_session, role="Registrar", label="synthetic-approver")
    patient = Patient(first_name="SYNTHETIC", last_name="PATIENT", phone="+998900000000", notification_owner_generation=9)
    service = Service(name="SYNTHETIC", price=Decimal("100.00"), active=True)
    db_session.add_all([patient, service])
    db_session.flush()
    visit = Visit(patient_id=patient.id, visit_date=date(2030, 1, 1), status="pending_confirmation",
                  source="desk", department="mixed", confirmation_context_epoch=12,
                  confirmation_channel="pwa", confirmation_token="synthetic-current-bearer",
                  confirmation_expires_at=datetime.now(UTC) + timedelta(hours=1))
    db_session.add(visit)
    db_session.flush()
    line = VisitService(visit_id=visit.id, service_id=service.id, name="SYNTHETIC",
                        qty=2, price=Decimal("73.50"), currency="UZS", price_line_generation=21)
    db_session.add(line)
    db_session.flush()
    override = DoctorPriceOverride(visit_id=visit.id, service_id=service.id,
        target_scope="visit_service", target_visit_service_id=line.id,
        original_price=Decimal("100.00"), new_price=Decimal("73.50"), reason="SYNTHETIC",
        status="approved", approved_by=actor.id, approved_at=datetime.now(UTC))
    db_session.add(override)
    db_session.commit()
    bearer = ProfileBearerContext(actor.id, actor.auth_epoch, str(uuid4()), int(time.time()) + 3600, None)
    return actor, patient, visit, line, override, bearer


def _stage(db, approved):
    actor, patient, visit, _line, override, bearer = approved
    return stage_price_approval_invitation(db, override=override, actor=actor, bearer=bearer, patient=patient, visit=visit)


class Sender:
    def __init__(self):
        self.calls = 0

    async def _send_pwa_invitation(self, patient, data, *, db, sms_opted_in):
        self.calls += 1
        return {"success": True}


def test_registrar_approval_is_narrowly_bound_and_sent_once(db_session, approved):
    delivery_id = _stage(db_session, approved)
    db_session.commit()
    proof = db_session.get(VisitInvitationPriceApprovalAuth, delivery_id)
    assert proof.override_id == approved[4].id and proof.line_id == approved[3].id
    assert proof.unit_price == Decimal("73.50") and proof.quantity == 2
    assert approved[5].jti not in proof.jti_ciphertext
    claimed = claim_visit_invitation(db_session, delivery_id)
    sender = Sender()
    assert asyncio.run(send_claimed_visit_invitation(db_session, claimed, sender))
    assert not asyncio.run(send_claimed_visit_invitation(db_session, claimed, sender))
    assert sender.calls == 1


@pytest.mark.parametrize("state", ["pending", "unknown"])
def test_approval_does_not_stage_over_unresolved_invitation(db_session, approved, state):
    first = _stage(db_session, approved)
    db_session.commit()
    assert first is not None
    if state == "unknown":
        db_session.get(VisitInvitationDelivery, first).state = "unknown"
        db_session.commit()
    assert _stage(db_session, approved) is None
    db_session.rollback()
    assert db_session.query(VisitInvitationDelivery).filter_by(visit_id=approved[2].id).count() == 1
    assert db_session.get(VisitInvitationDelivery, first).state == state


@pytest.mark.parametrize("mutation", ["approval_status", "approver", "line_generation", "price", "quantity"])
def test_changed_approval_or_line_never_sends(db_session, approved, mutation):
    delivery_id = _stage(db_session, approved)
    db_session.commit()
    claimed = claim_visit_invitation(db_session, delivery_id)
    actor, _patient, _visit, line, override, _bearer = approved
    if mutation == "approval_status":
        override.status = "rejected"
    elif mutation == "approver":
        override.approved_by = None
    elif mutation == "line_generation":
        line.price_line_generation += 1
    elif mutation == "price":
        line.price = Decimal("74.50")
    else:
        line.qty += 1
    db_session.commit()
    sender = Sender()
    assert not asyncio.run(send_claimed_visit_invitation(db_session, claimed, sender))
    assert sender.calls == 0 and db_session.get(VisitInvitationDelivery, delivery_id).state == "unknown"
    assert actor.is_active


def test_stage_rejects_unapproved_or_forged_actor(db_session, approved):
    actor, patient, visit, _line, override, bearer = approved
    override.status = "pending"
    db_session.flush()
    with pytest.raises(InvitationContextChanged):
        stage_price_approval_invitation(db_session, override=override, actor=actor, bearer=bearer, patient=patient, visit=visit)


def test_recovery_waits_for_admin_and_old_handle_stays_invalid_after_reissue(client, db_session, approved, monkeypatch):
    import jwt

    from app.core.config import settings
    from app.models.authentication import TokenBlacklist

    actor, patient, visit, _line, override, bearer = approved
    visit.confirmation_token = None
    visit.confirmation_expires_at = None
    db_session.flush()
    recovery_id = stage_price_approval_recovery(db_session, override=override, actor=actor, bearer=bearer, patient=patient, visit=visit)
    assert stage_price_approval_recovery(db_session, override=override, actor=actor, bearer=bearer, patient=patient, visit=visit) == recovery_id
    db_session.commit()
    assert not asyncio.run(deliver_price_approval_recovery(db_session, recovery_id, NotificationService(db_session)))
    assert db_session.get(VisitInvitationApprovalRecovery, recovery_id).state == "pending"
    admin = _create_user(db_session, role="Admin", label="synthetic-recovery-admin")
    broadcasts = []

    async def record(platform, user_id, delivery, **kwargs):
        broadcasts.append(platform.serialize_delivery(delivery))

    monkeypatch.setattr(NotificationPlatformService, "_broadcast_delivery", record)
    assert asyncio.run(deliver_price_approval_recovery(db_session, recovery_id, NotificationService(db_session)))
    assert not asyncio.run(deliver_price_approval_recovery(db_session, recovery_id, NotificationService(db_session)))
    event = db_session.query(NotificationEvent).filter(NotificationEvent.source_module == "visit_confirmation_recovery").one()
    assert broadcasts and "SYNTHETIC" not in repr(broadcasts) and "998900000000" not in repr(broadcasts)
    handle = event.correlation_id
    admin_token = mint_access_token(admin)
    headers = {"Authorization": f"Bearer {admin_token}"}
    url = f"/api/v1/notifications/visit-invitation-recoveries/{handle}"
    response = client.get(url, headers=headers)
    assert response.status_code == 200 and response.json() == {"visit_id": visit.id}
    assert response.headers["cache-control"] == "private, no-store"
    status = client.get(f"/api/v1/notifications/visit-invitation-status/{visit.id}", headers=headers)
    assert status.status_code == 200 and status.json()["state"] == "reissue_required"
    claims = jwt.decode(admin_token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    db_session.add(TokenBlacklist(jti=claims["jti"], user_id=admin.id,
                                  expires_at=datetime.now(UTC) + timedelta(hours=1), reason="logout"))
    db_session.commit()
    revoked = client.get(url, headers=headers)
    assert revoked.status_code in (401, 403) and revoked.headers["cache-control"] == "private, no-store"
    headers = {"Authorization": f"Bearer {mint_access_token(admin)}"}
    visit.confirmation_token = "synthetic-new-bearer"
    visit.confirmation_expires_at = datetime.now(UTC) - timedelta(minutes=1)
    db_session.commit()
    response = client.get(url, headers=headers)
    assert response.status_code == 404 and "SYNTHETIC" not in response.text


def test_pending_recovery_is_resolved_after_owner_change(db_session, approved):
    actor, patient, visit, _line, override, bearer = approved
    visit.confirmation_token = None
    visit.confirmation_expires_at = None
    db_session.flush()
    recovery_id = stage_price_approval_recovery(db_session, override=override, actor=actor, bearer=bearer, patient=patient, visit=visit)
    db_session.commit()
    _create_user(db_session, role="Admin", label="synthetic-owner-change-admin")
    patient.notification_owner_generation += 1
    db_session.commit()
    assert not asyncio.run(deliver_price_approval_recovery(db_session, recovery_id, NotificationService(db_session)))
    assert db_session.get(VisitInvitationApprovalRecovery, recovery_id).state == "resolved"
    assert db_session.query(NotificationEvent).filter(NotificationEvent.source_module == "visit_confirmation_recovery").count() == 0


def test_recovery_sweep_retries_after_admin_appears_and_issuer_logout(db_session, approved, monkeypatch):
    from contextlib import contextmanager

    from app.models.authentication import TokenBlacklist
    from app.tasks import invitation_delivery as worker
    from tests.integration.test_invitation_delivery_worker import FakeRedis

    actor, patient, visit, _line, override, bearer = approved
    visit.confirmation_token = None
    visit.confirmation_expires_at = None
    db_session.flush()
    recovery_id = stage_price_approval_recovery(db_session, override=override, actor=actor, bearer=bearer, patient=patient, visit=visit)
    db_session.commit()

    @contextmanager
    def shared_session():
        yield db_session

    monkeypatch.setattr(worker, "SessionLocal", shared_session)
    monkeypatch.setattr(worker, "NotificationService", NotificationService)
    redis = FakeRedis()
    asyncio.run(worker.run_visit_invitation_sweep({"redis": redis}))
    assert redis.jobs and redis.jobs[-1][1]["recovery_id"] == recovery_id
    asyncio.run(worker.deliver_visit_invitation({}, recovery_id=recovery_id))
    assert db_session.get(VisitInvitationApprovalRecovery, recovery_id).state == "pending"
    db_session.add(TokenBlacklist(jti=bearer.jti, user_id=actor.id,
                                  expires_at=datetime.now(UTC) + timedelta(hours=1), reason="logout"))
    db_session.commit()
    _create_user(db_session, role="Admin", label="synthetic-later-admin")
    broadcasts = []

    async def record(platform, user_id, delivery, **kwargs):
        broadcasts.append(platform.serialize_delivery(delivery))

    monkeypatch.setattr(NotificationPlatformService, "_broadcast_delivery", record)
    asyncio.run(worker.run_visit_invitation_sweep({"redis": redis}))
    assert redis.jobs[-1][1]["recovery_id"] == recovery_id
    asyncio.run(worker.deliver_visit_invitation({}, recovery_id=recovery_id))
    asyncio.run(worker.deliver_visit_invitation({}, recovery_id=recovery_id))
    assert db_session.get(VisitInvitationApprovalRecovery, recovery_id).state == "dispatched"
    assert db_session.query(NotificationEvent).filter(NotificationEvent.source_module == "visit_confirmation_recovery").count() == 1
    assert broadcasts and "SYNTHETIC" not in repr(broadcasts) and "998900000000" not in repr(broadcasts)


def test_postgres_recovery_workers_and_reissue_serialize(monkeypatch):
    """Recovery workers use a real nonowner subject capability and row locks."""
    from pathlib import Path

    from sqlalchemy.orm import Session

    from app.db.capability_namespace import capability_schema_name
    from app.models.authentication import TokenBlacklist
    from app.models.clinic import Doctor
    from app.models.user import User
    from app.services import visit_invitation_delivery as service_module
    from tests.integration.test_invitation_subject_nonowner_pg import (
        _module,
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
    schema = "invite_recovery_race_" + suffix
    role, cap, password = "recovery_login_" + suffix, "recovery_cap_" + suffix, "synthetic-" + suffix
    admin = sa.create_engine(raw)
    with admin.begin() as conn:
        conn.execute(CreateSchema(schema))
        conn.exec_driver_sql(f'CREATE ROLE "{role}" LOGIN PASSWORD \'{password}\'')
        conn.exec_driver_sql(f'CREATE ROLE "{cap}" NOLOGIN')
        owner_name = conn.execute(sa.text("SELECT CURRENT_USER")).scalar_one()
    engine = sa.create_engine(raw, connect_args={"options": f"-csearch_path={schema} -clock_timeout=5000"})
    runtime = None
    created, release = threading.Event(), threading.Event()

    class Platform:
        INBOX_CHANNEL = "inbox"

        def __init__(self, db):
            self.db = db

        def _create_or_get_event(self, **kwargs):
            self.db.execute(sa.text("INSERT INTO synthetic_events DEFAULT VALUES"))
            if pause_event[0]:
                created.set()
                assert release.wait(5)
            return object()

        def _create_or_get_delivery(self, **kwargs):
            return object()

        async def _broadcast_delivery(self, *_):
            pass

    class Sender:
        def _platform_service(self, db):
            return Platform(db)

    pause_event = [False]
    errors = []
    try:
        with engine.begin() as conn:
            for model in (User, Doctor, TokenBlacklist, Patient, Visit, VisitService, DoctorPriceOverride):
                conn.execute(sa.schema.CreateTable(model.__table__, include_foreign_key_constraints=[]))
            conn.execute(sa.text("CREATE TABLE synthetic_events (id SERIAL PRIMARY KEY)"))
            migration = _migration()
            migration.op = Operations(MigrationContext.configure(conn))
            migration.upgrade()
            _issuer_migration(conn)
            _approval_migration(conn)
            conn.exec_driver_sql(f'GRANT SELECT, INSERT ON "{schema}".synthetic_events TO "{role}"')
            conn.exec_driver_sql(f'GRANT SELECT, UPDATE (id) ON "{schema}".doctor_price_overrides TO "{role}"')
            conn.exec_driver_sql(f'GRANT USAGE ON ALL SEQUENCES IN SCHEMA "{schema}" TO "{role}"')
        install_invitation_subject_fence(engine, schema=schema, owner_name=owner_name,
                                         runtime_role=role, subject_cap_role=cap, monkeypatch=monkeypatch)
        provision = _module(Path(__file__).resolve().parents[2] / "scripts/provision_invitation_delivery_role.py")
        provision.provision(engine, schema, role)
        runtime = sa.create_engine(make_url(raw).set(username=role, password=password),
                                   connect_args={"options": f"-csearch_path={schema} -clock_timeout=5000"})
        with Session(engine) as db:
            actor = User(username="synthetic-race-admin", hashed_password="synthetic", role="Admin", is_active=True, is_superuser=False)
            patient = Patient(first_name="SYNTHETIC", last_name="PATIENT", notification_owner_generation=7)
            db.add_all([actor, patient])
            db.flush()
            visit = Visit(patient_id=patient.id, visit_date=date(2030, 1, 1), status="pending_confirmation", source="desk", department="mixed", confirmation_context_epoch=9)
            db.add(visit)
            db.flush()
            db.refresh(patient)
            db.refresh(visit)
            owner_generation, context_epoch = patient.notification_owner_generation, visit.confirmation_context_epoch
            override = DoctorPriceOverride(visit_id=visit.id, original_price=Decimal("10"), new_price=Decimal("5"), reason="synthetic", status="approved", approved_by=actor.id)
            db.add(override)
            db.flush()
            recovery = VisitInvitationApprovalRecovery(visit_id=visit.id, visit_id_snapshot=visit.id, patient_id=patient.id,
                patient_id_snapshot=patient.id, override_id=override.id, override_id_snapshot=override.id,
                actor_user_id_snapshot=actor.id, owner_generation=owner_generation, context_epoch=context_epoch, state="pending")
            db.add(recovery)
            db.flush()
            rid, pid, vid, actor_id = recovery.id, patient.id, visit.id, actor.id
            db.commit()
        start = threading.Barrier(2)
        outcomes = []

        def worker():
            try:
                with Session(runtime) as db:
                    start.wait(5)
                    outcomes.append(asyncio.run(deliver_price_approval_recovery(db, rid, Sender())))
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=worker) for _ in range(2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(10)
        assert not errors and all(not thread.is_alive() for thread in threads)
        assert sorted(outcomes) == [False, True]
        with Session(engine) as db:
            assert db.execute(sa.text("SELECT count(*) FROM synthetic_events")).scalar_one() == 1
            assert db.get(VisitInvitationApprovalRecovery, rid).state == "dispatched"

        # Reissue acquires the patient/visit locks first: the worker must see the
        # new bearer after commit and resolve rather than create a stale task.
        with Session(engine) as db:
            override = DoctorPriceOverride(visit_id=vid, original_price=Decimal("10"), new_price=Decimal("6"), reason="synthetic", status="approved", approved_by=actor_id)
            db.add(override)
            db.flush()
            recovery = VisitInvitationApprovalRecovery(visit_id=vid, visit_id_snapshot=vid, patient_id=pid, patient_id_snapshot=pid,
                override_id=override.id, override_id_snapshot=override.id, actor_user_id_snapshot=actor_id,
                owner_generation=owner_generation, context_epoch=context_epoch, state="pending")
            db.add(recovery)
            db.flush()
            second = recovery.id
            db.commit()
        with Session(engine) as reissue:
            reissue.query(Patient).filter_by(id=pid).with_for_update().one()
            reissue.query(Visit).filter_by(id=vid).with_for_update().one()
            reissue.execute(sa.text("UPDATE visits SET confirmation_token=:token, confirmation_expires_at=:expiry WHERE id=:id"),
                            {"token": "synthetic-new-bearer", "expiry": datetime.now(UTC) + timedelta(hours=1), "id": vid})
            results = []
            started, finished = threading.Event(), threading.Event()
            def run_second():
                try:
                    with Session(runtime) as db:
                        started.set()
                        results.append(asyncio.run(deliver_price_approval_recovery(db, second, Sender())))
                except Exception as exc:
                    errors.append(exc)
                finally:
                    finished.set()
            thread = threading.Thread(target=run_second)
            thread.start()
            assert started.wait(5) and not finished.wait(0.2)
            reissue.commit()
            thread.join(10)
            assert not thread.is_alive() and not errors and results == [False]
        with Session(engine) as db:
            assert db.get(VisitInvitationApprovalRecovery, second).state == "resolved"
            assert db.execute(sa.text("SELECT count(*) FROM synthetic_events")).scalar_one() == 1

        # Reverse order: delivery holds the subject locks until its neutral task
        # commits. A concurrent reissue waits; the old handle is then stale.
        with Session(engine) as db:
            db.execute(sa.text("UPDATE visits SET confirmation_token=NULL, confirmation_expires_at=NULL WHERE id=:id"), {"id": vid})
            override = DoctorPriceOverride(visit_id=vid, original_price=Decimal("10"), new_price=Decimal("7"), reason="synthetic", status="approved", approved_by=actor_id)
            db.add(override)
            db.flush()
            recovery = VisitInvitationApprovalRecovery(visit_id=vid, visit_id_snapshot=vid, patient_id=pid, patient_id_snapshot=pid,
                override_id=override.id, override_id_snapshot=override.id, actor_user_id_snapshot=actor_id,
                owner_generation=owner_generation, context_epoch=context_epoch, state="pending")
            db.add(recovery)
            db.flush()
            third = recovery.id
            db.commit()
        pause_event[0] = True
        delivered, reissued = [], threading.Event()
        def run_third():
            try:
                with Session(runtime) as db:
                    delivered.append(asyncio.run(deliver_price_approval_recovery(db, third, Sender())))
            except Exception as exc:
                errors.append(exc)
        def concurrent_reissue():
            try:
                with Session(engine) as db:
                    db.query(Patient).filter_by(id=pid).with_for_update().one()
                    db.query(Visit).filter_by(id=vid).with_for_update().one()
                    db.execute(sa.text("UPDATE visits SET confirmation_token=:token, confirmation_expires_at=:expiry WHERE id=:id"),
                               {"token": "synthetic-reissued-bearer", "expiry": datetime.now(UTC) + timedelta(hours=1), "id": vid})
                    db.commit()
                    reissued.set()
            except Exception as exc:
                errors.append(exc)
        delivery_thread = threading.Thread(target=run_third)
        delivery_thread.start()
        assert created.wait(5)
        reissue_thread = threading.Thread(target=concurrent_reissue)
        reissue_thread.start()
        assert not reissued.wait(0.2)
        release.set()
        delivery_thread.join(10)
        reissue_thread.join(10)
        assert not errors and delivered == [True] and reissued.is_set()
        with Session(engine) as db:
            recovery = db.get(VisitInvitationApprovalRecovery, third)
            assert recovery.state == "dispatched"
            assert not service_module._recovery_matches_token(recovery, db.get(Visit, vid))
            assert db.execute(sa.text("SELECT count(*) FROM synthetic_events")).scalar_one() == 2
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


@pytest.mark.parametrize("database", ["sqlite", "postgresql"])
def test_approval_migration_is_immutable_and_downgrade_safe(tmp_path, database):
    from tests.integration.test_visit_invitation_delivery import (
        _approval_migration,
        _issuer_migration,
        _migration,
    )

    raw = os.environ.get("DATABASE_URL", "")
    if database == "postgresql":
        if not raw or make_url(raw).get_backend_name() != "postgresql" or not (make_url(raw).database or "").startswith("clinic_test"):
            pytest.skip("requires disposable clinic_test PostgreSQL")
        schema = "invite_approval_test_" + uuid4().hex
        admin = sa.create_engine(raw)
        with admin.begin() as conn:
            conn.execute(CreateSchema(schema))
        engine = sa.create_engine(raw, connect_args={"options": f"-csearch_path={schema}"})
    else:
        admin = schema = None
        engine = sa.create_engine(f"sqlite:///{tmp_path / 'approval-migration.db'}")
    try:
        with engine.begin() as conn:
            for table in ("patients", "visits", "users", "doctors", "doctor_price_overrides", "visit_services"):
                conn.execute(sa.text(f"CREATE TABLE {table} (id INTEGER PRIMARY KEY)"))
                conn.execute(sa.text(f"INSERT INTO {table} (id) VALUES (1)"))
            migration = _migration()
            migration.op = Operations(MigrationContext.configure(conn))
            migration.upgrade()
            _issuer_migration(conn)
            approval = _approval_migration(conn)
            approval.downgrade()
            approval.upgrade()
            conn.execute(sa.text("""INSERT INTO visit_invitation_deliveries
              (id,visit_id,visit_id_snapshot,patient_id,patient_id_snapshot,owner_generation,context_epoch,token_digest,channel,state)
              VALUES (1,1,1,1,1,7,9,:digest,'pwa','pending')"""), {"digest": "a" * 64})
            conn.execute(sa.text("""INSERT INTO visit_invitation_price_approval_auth
              (delivery_id,actor_user_id,actor_user_id_snapshot,actor_auth_epoch,override_id,override_id_snapshot,line_id,line_id_snapshot,line_generation,unit_price,quantity,expires_at,cipher_version,jti_ciphertext)
              VALUES (1,1,1,0,1,1,1,1,3,73.50,2,9999999999,1,:cipher)"""), {"cipher": "x" * 100})
            conn.execute(sa.text("""INSERT INTO visit_invitation_approval_recoveries
              (id,visit_id,visit_id_snapshot,patient_id,patient_id_snapshot,override_id,override_id_snapshot,actor_user_id_snapshot,owner_generation,context_epoch,state)
              VALUES (1,1,1,1,1,1,1,1,7,9,'pending')"""))
            for sql in ("UPDATE visit_invitation_price_approval_auth SET unit_price=1 WHERE delivery_id=1",
                        "UPDATE visit_invitation_approval_recoveries SET owner_generation=8 WHERE id=1",
                        "DELETE FROM visit_invitation_approval_recoveries WHERE id=1"):
                with pytest.raises(sa.exc.DBAPIError), conn.begin_nested():
                    conn.execute(sa.text(sql))
            with pytest.raises(sa.exc.DBAPIError), conn.begin_nested():
                approval.downgrade()
            assert conn.execute(sa.text("SELECT count(*) FROM visit_invitation_approval_recoveries")).scalar_one() == 1
    finally:
        engine.dispose()
        if admin is not None:
            with admin.begin() as conn:
                conn.execute(DropSchema(schema, cascade=True))
            admin.dispose()
