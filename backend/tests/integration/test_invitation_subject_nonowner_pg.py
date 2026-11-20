"""Synthetic non-owner invitation tests using real subject-fence migrations.

The shared helper installs a *partial* migration graph in a disposable schema;
full-chain migrated PostgreSQL remains a separate required integration check.
"""
from __future__ import annotations

import importlib.util
import os
import secrets
from pathlib import Path
from uuid import uuid4

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session
from sqlalchemy.schema import CreateSchema, DropSchema

from app.core.config import settings
from app.db.capability_namespace import capability_schema_name
from app.models.authentication import TokenBlacklist
from app.models.clinic import Doctor
from app.models.patient import Patient
from app.models.user import User
from app.models.visit import Visit, VisitService

ROOT = Path(__file__).resolve().parents[3]


def _module(path: Path):
    spec = importlib.util.spec_from_file_location("synthetic_invitation_subject_" + uuid4().hex, path)
    assert spec and spec.loader
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def install_invitation_subject_fence(owner_engine, *, schema: str, owner_name: str,
                                     runtime_role: str, subject_cap_role: str, monkeypatch) -> None:
    """Install real subject triggers and role profile into an empty test schema.

    Caller creates the isolated schema, LOGIN and NOLOGIN roles and full ORM
    users, token_blacklist, patients, visits and visit_services tables first.
    Caller owns 0117/0126/0128 installation/provision and schema/role cleanup.
    Never use this helper against non-test databases or nonempty subject tables.
    """
    if owner_engine.dialect.name != "postgresql" or not (owner_engine.url.database or "").startswith("clinic_test"):
        raise RuntimeError("A disposable clinic_test PostgreSQL database is required")
    if schema in {"public", "pg_catalog", "information_schema"} or not schema:
        raise RuntimeError("An isolated synthetic schema is required")
    quote = owner_engine.dialect.identifier_preparer.quote_identifier
    qs, qr = quote(schema), quote(runtime_role)
    opts = {"version_table_schema": schema}
    with owner_engine.begin() as conn:
        actual = conn.execute(sa.text("SELECT pg_catalog.current_schema()" )).scalar_one()
        if actual != schema:
            raise RuntimeError("Test engine schema does not match explicit schema")
        for table in ("patients", "visits", "visit_services"):
            if conn.execute(sa.text(f"SELECT EXISTS (SELECT 1 FROM {qs}.{quote(table)} LIMIT 1)")).scalar_one():
                raise RuntimeError("Subject migrations require empty synthetic tables")
        # ORM metadata includes later columns. Reconstruct the pre-migration
        # state only inside this empty throwaway schema, retaining all other DDL.
        conn.exec_driver_sql(f"ALTER TABLE {qs}.visits DROP COLUMN confirmation_context_epoch")
        conn.exec_driver_sql(f"ALTER TABLE {qs}.patients DROP COLUMN notification_owner_generation")
        migration_dir = ROOT / "backend/alembic/versions"
        migration = _module(migration_dir / "0102_visit_confirmation_context.py")
        migration.op = Operations(MigrationContext.configure(conn, opts=opts))
        migration.upgrade()
        bootstrap = _module(migration_dir / "0112_doctor_price_context.py")
        bootstrap.op = Operations(MigrationContext.configure(conn, opts=opts))
        bootstrap._bootstrap_capability_namespace(schema)
        for filename in ("0113_subject_ownership.py", "0115_confirmation_trigger_path.py",
                         "0116_patient_owner_confirmation.py"):
            migration = _module(migration_dir / filename)
            migration.op = Operations(MigrationContext.configure(conn, opts=opts))
            migration.upgrade()
        conn.exec_driver_sql(f"GRANT USAGE ON SCHEMA {qs} TO {qr}")
        for table in ("patients", "visits", "users", "token_blacklist"):
            conn.exec_driver_sql(f"ALTER TABLE {qs}.{quote(table)} ENABLE ROW LEVEL SECURITY")
            conn.exec_driver_sql(f"ALTER TABLE {qs}.{quote(table)} FORCE ROW LEVEL SECURITY")
        for table in ("users", "token_blacklist"):
            qt = quote(table)
            conn.exec_driver_sql(f"GRANT SELECT ON {qs}.{qt} TO {qr}")
            conn.exec_driver_sql(f"CREATE POLICY synthetic_subject_select ON {qs}.{qt} FOR SELECT TO {qr} USING (true)")
        # UPDATE permission is only for locking; policy rejects actual edits.
        conn.exec_driver_sql(f"GRANT UPDATE (auth_epoch) ON {qs}.users TO {qr}")
        conn.exec_driver_sql(f"CREATE POLICY synthetic_user_lock ON {qs}.users FOR UPDATE TO {qr} USING (true) WITH CHECK (false)")
        conn.exec_driver_sql(f"GRANT UPDATE (id) ON {qs}.visits TO {qr}")
        conn.exec_driver_sql(f"CREATE POLICY synthetic_visit_lock ON {qs}.visits FOR UPDATE TO {qr} USING (true) WITH CHECK (false)")
        conn.exec_driver_sql(f"REVOKE UPDATE ON {qs}.patients FROM {qr}")
    provision = _module(ROOT / "scripts/provision_confirmation_subject_role.py")
    provision.provision(owner_engine, schema, subject_cap_role, runtime_role, expected_owner=owner_name)
    for key, value in {
        "TRUSTED_DB_SCHEMA": schema, "TRUSTED_DB_SCHEMA_OWNER": owner_name,
        "TRUSTED_DB_RUNTIME_ROLE": runtime_role, "TRUSTED_DB_OWNER_MEMBERS": (),
        "TRUSTED_AUTH_TABLE_OWNER": owner_name, "TRUSTED_AUTH_OWNER_MEMBERS": (),
        "TRUSTED_AUTH_READ_ROLES": (), "TRUSTED_AUTH_WRITE_ROLES": (),
        "TRUSTED_AUTH_USERS_OWNER": owner_name, "TRUSTED_AUTH_USERS_OWNER_MEMBERS": (),
        "TRUSTED_AUTH_USERS_WRITE_ROLES": (),
        "INVITATION_DB_SCHEMA": schema, "INVITATION_DB_SCHEMA_OWNER": owner_name,
        "INVITATION_DB_TABLE_OWNER": owner_name,
    }.items():
        monkeypatch.setattr(settings, key, value)
    with owner_engine.connect() as conn:
        assert not conn.execute(sa.text("SELECT pg_catalog.has_table_privilege(:role,:table,'UPDATE')"),
                                {"role": runtime_role, "table": f'{qs}.patients'}).scalar_one()
        assert not conn.execute(sa.text("SELECT pg_catalog.has_any_column_privilege(:role,:table,'UPDATE')"),
                                {"role": runtime_role, "table": f'{qs}.patients'}).scalar_one()


@pytest.fixture
def subject_environment(monkeypatch):
    raw = os.getenv("DATABASE_URL", "sqlite://")
    url = make_url(raw)
    if url.get_backend_name() != "postgresql" or not (url.database or "").startswith("clinic_test"):
        pytest.skip("requires disposable clinic_test PostgreSQL")
    suffix = uuid4().hex
    schema, login, cap = "invite_subject_" + suffix, "invite_login_" + suffix, "invite_subject_cap_" + suffix
    password = secrets.token_urlsafe(24)
    private = capability_schema_name(schema)
    admin = sa.create_engine(url, hide_parameters=True)
    with admin.begin() as conn:
        conn.execute(CreateSchema(schema))
        owner_name = conn.execute(sa.text("SELECT CURRENT_USER")).scalar_one()
        for role, kind in ((login, "LOGIN"), (cap, "NOLOGIN")):
            ddl = conn.execute(sa.text("SELECT pg_catalog.format('CREATE ROLE %I ' || CAST(:kind AS text) || ' NOSUPERUSER NOBYPASSRLS PASSWORD %L', CAST(:role AS text), CAST(:password AS text))"),
                               {"role": role, "kind": kind, "password": password}).scalar_one()
            conn.exec_driver_sql(ddl)
    owner = sa.create_engine(url, connect_args={"options": f"-csearch_path={schema} -clock_timeout=5000"}, hide_parameters=True)
    runtime = None
    try:
        with owner.begin() as conn:
            for model in (User, Doctor, TokenBlacklist, Patient, Visit, VisitService):
                conn.execute(sa.schema.CreateTable(model.__table__, include_foreign_key_constraints=[]))
        install_invitation_subject_fence(owner, schema=schema, owner_name=owner_name, runtime_role=login,
                                         subject_cap_role=cap, monkeypatch=monkeypatch)
        runtime = sa.create_engine(url.set(username=login, password=password),
                                   connect_args={"options": f"-csearch_path={schema} -clock_timeout=5000"}, hide_parameters=True)
        yield owner, runtime, schema, login
    finally:
        if runtime is not None:
            runtime.dispose()
        owner.dispose()
        with admin.begin() as conn:
            conn.execute(DropSchema(schema, cascade=True))
            conn.execute(DropSchema(private, cascade=True))
            conn.exec_driver_sql(f'DROP ROLE "{login}"')
            conn.exec_driver_sql(f'DROP ROLE "{cap}"')
        admin.dispose()


@pytest.mark.integration
def test_subject_capability_requires_no_patient_update(subject_environment):
    from app.services.patient_subject_lock import lock_patient_subject

    owner, runtime, schema, login = subject_environment
    with Session(owner) as db:
        patient = Patient(first_name="SYNTHETIC", last_name="SUBJECT")
        db.add(patient)
        db.flush()
        patient_id = patient.id
        db.commit()
    with Session(runtime) as db:
        from app.db.trusted_schema import pin_application_schema
        assert db.execute(sa.text("SELECT CURRENT_USER")).scalar_one() == login
        pin_application_schema(db, schema=settings.TRUSTED_DB_SCHEMA,
            expected_owner=settings.TRUSTED_DB_SCHEMA_OWNER, expected_runtime_role=login,
            expected_auth_owner=settings.TRUSTED_AUTH_TABLE_OWNER,
            expected_users_owner=settings.TRUSTED_AUTH_USERS_OWNER)
        assert lock_patient_subject(db, patient_id)
        with pytest.raises(sa.exc.DBAPIError), db.begin_nested():
            db.execute(sa.text("UPDATE patients SET id=id WHERE id=:id"), {"id": patient_id})
        db.rollback()
    with owner.connect() as conn:
        assert conn.execute(sa.text("SELECT relforcerowsecurity FROM pg_catalog.pg_class c JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname=:schema AND c.relname='patients'"), {"schema": schema}).scalar_one()


@pytest.mark.integration
@pytest.mark.parametrize("transfer_first", [False, True])
def test_owner_change_serializes_with_subject_lock(subject_environment, transfer_first):
    import threading
    from datetime import UTC, date, datetime, timedelta

    from app.services.patient_subject_lock import lock_patient_subject

    owner, runtime, _, _ = subject_environment
    with Session(owner) as db:
        old_owner = User(username="SYNTHETIC-old-" + uuid4().hex[:16], hashed_password="!", role="Patient", is_active=True)
        new_owner = User(username="SYNTHETIC-new-" + uuid4().hex[:16], hashed_password="!", role="Patient", is_active=True)
        db.add_all([old_owner, new_owner])
        db.flush()
        patient = Patient(first_name="SYNTHETIC", last_name="TRANSFER", user_id=old_owner.id)
        db.add(patient)
        db.flush()
        visit = Visit(patient_id=patient.id, visit_date=date(2099, 1, 1), status="pending_confirmation",
                      confirmation_channel="pwa", confirmation_token="SYNTHETIC-owner-change-token",
                      confirmation_expires_at=datetime.now(UTC) + timedelta(hours=1))
        db.add(visit)
        db.flush()
        patient_id, visit_id, new_owner_id = patient.id, visit.id, new_owner.id
        previous_owner_generation, previous_visit_epoch = patient.notification_owner_generation, visit.confirmation_context_epoch
        db.commit()
    entered = threading.Event()
    finished = threading.Event()
    errors = []
    with Session(owner if transfer_first else runtime) as first:
        if transfer_first:
            first.execute(sa.update(Patient).where(Patient.id == patient_id).values(user_id=new_owner_id))
        else:
            assert lock_patient_subject(first, patient_id)

        def competing():
            try:
                with Session(runtime if transfer_first else owner) as db:
                    entered.set()
                    if transfer_first:
                        assert lock_patient_subject(db, patient_id)
                        row = db.query(Visit).filter(Visit.id == visit_id).populate_existing().one()
                        assert row.confirmation_token is None and row.confirmation_context_epoch > previous_visit_epoch
                    else:
                        db.execute(sa.update(Patient).where(Patient.id == patient_id).values(user_id=new_owner_id))
                    db.commit()
                    finished.set()
            except Exception as exc:
                errors.append(exc)
                finished.set()

        thread = threading.Thread(target=competing)
        thread.start()
        assert entered.wait(5) and not finished.wait(0.2)
        first.commit()
        thread.join(10)
        assert not thread.is_alive() and finished.is_set() and not errors
    with Session(owner) as db:
        patient = db.get(Patient, patient_id)
        visit = db.get(Visit, visit_id)
        assert patient.user_id == new_owner_id and patient.notification_owner_generation > previous_owner_generation
        assert visit.confirmation_token is None and visit.confirmation_expires_at is None
        assert visit.confirmation_context_epoch > previous_visit_epoch


@pytest.mark.integration
def test_hidden_revoked_jti_fails_closed_before_subject_lock(subject_environment):
    from datetime import UTC, datetime, timedelta

    from app.services.patient_subject_lock import (
        PatientSubjectLockError,
        lock_patient_subject,
    )

    owner, runtime, schema, _ = subject_environment
    with Session(owner) as db:
        actor = User(username="SYNTHETIC-revoked-" + uuid4().hex[:16], hashed_password="!", role="Admin", is_active=True)
        patient = Patient(first_name="SYNTHETIC", last_name="HIDDEN")
        db.add_all([actor, patient])
        db.flush()
        db.add(TokenBlacklist(jti=str(uuid4()), user_id=actor.id,
                              expires_at=datetime.now(UTC) + timedelta(hours=1), reason="logout"))
        patient_id = patient.id
        db.commit()
    with owner.begin() as conn:
        qs = conn.dialect.identifier_preparer.quote_identifier(schema)
        conn.exec_driver_sql(f"ALTER POLICY synthetic_subject_select ON {qs}.token_blacklist USING (false)")
    with Session(runtime) as db:
        with pytest.raises(PatientSubjectLockError) as denied:
            lock_patient_subject(db, patient_id)
        assert denied.value.status_code == 503
        assert not db.in_transaction()


@pytest.mark.integration
@pytest.mark.parametrize("first_index", [0, 1])
def test_distinct_issuers_cannot_stage_concurrent_or_unknown_attempt(subject_environment, first_index):
    """A locked Visit serializes all keys, including an uncertain outcome."""
    import threading
    import time
    from datetime import UTC, date, datetime, timedelta

    from app.models.visit_invitation_delivery import VisitInvitationDelivery
    from app.services.profile_contact_security import ProfileBearerContext
    from app.services.visit_invitation_delivery import (
        InvitationContextChanged,
        InvitationRuntimeUnavailable,
        stage_visit_invitation,
    )
    from tests.integration.test_visit_invitation_delivery import (
        _approval_migration,
        _issuer_migration,
        _migration,
    )

    owner, runtime, schema, login = subject_environment
    with owner.begin() as conn:
        conn.execute(sa.text("CREATE TABLE doctor_price_overrides (id INTEGER PRIMARY KEY)"))
        migration = _migration()
        migration.op = Operations(MigrationContext.configure(conn, opts={"version_table_schema": schema}))
        migration.upgrade()
        _issuer_migration(conn)
        _approval_migration(conn)
    provision = _module(ROOT / "backend/scripts/provision_invitation_delivery_role.py")
    provision.provision(owner, schema, login)
    with Session(owner, expire_on_commit=False) as db:
        actors = [User(username="SYNTHETIC-invite-" + uuid4().hex, hashed_password="!", role="Admin", is_active=True)
                  for _ in range(2)]
        patient = Patient(first_name="SYNTHETIC", last_name="RACE", phone="+998900000000")
        db.add_all([*actors, patient])
        db.flush()
        visit = Visit(patient_id=patient.id, visit_date=date(2099, 1, 1), status="pending_confirmation",
                      confirmation_channel="pwa", confirmation_token="SYNTHETIC-token",
                      confirmation_expires_at=datetime.now(UTC) + timedelta(hours=1))
        db.add(visit)
        db.flush()
        patient_id, visit_id = patient.id, visit.id
        actor_ids = [actor.id for actor in actors]
        db.commit()
    bearers = [ProfileBearerContext(value, 0, str(uuid4()), int(time.time()) + 600, None) for value in actor_ids]

    def stage(db, index):
        return stage_visit_invitation(db, patient_id=patient_id, visit_id=visit_id, channel="pwa",
            issuer_actor_id=actor_ids[index], issuer_key_digest=(str(index + 1) * 64),
            issuer_fingerprint=(str(index + 3) * 64), bearer=bearers[index], requester_type="admin")

    entered = threading.Event()
    pids, outcomes = [], []
    with Session(runtime) as first:
        first_id = stage(first, first_index)
        assert first_id is not None

        def competing():
            with Session(runtime) as db:
                pids.append(db.execute(sa.text("SELECT pg_catalog.pg_backend_pid()" )).scalar_one())
                entered.set()
                try:
                    stage(db, 1 - first_index)
                    db.commit()
                    outcomes.append("unexpected-success")
                except InvitationContextChanged:
                    db.rollback()
                    outcomes.append("blocked")

        thread = threading.Thread(target=competing)
        thread.start()
        assert entered.wait(5)
        deadline = time.monotonic() + 1.5
        while time.monotonic() < deadline:
            with owner.connect() as conn:
                waiting = conn.execute(sa.text("SELECT wait_event_type FROM pg_catalog.pg_stat_activity WHERE pid=:pid"),
                                       {"pid": pids[0]}).scalar_one_or_none()
            if waiting == "Lock":
                break
            time.sleep(0.01)
        else:
            pytest.fail("Competing stage did not reach the PostgreSQL lock")
        first.commit()
        thread.join(10)
    assert not thread.is_alive() and outcomes == ["blocked"]
    with Session(owner) as db:
        rows = db.query(VisitInvitationDelivery).filter_by(visit_id_snapshot=visit_id).all()
        assert len(rows) == 1 and rows[0].state == "pending"
        rows[0].state = "unknown"
        db.commit()
    with Session(runtime) as db:
        with pytest.raises(InvitationContextChanged):
            stage(db, 1 - first_index)
        db.rollback()
    with Session(owner) as db:
        assert db.query(VisitInvitationDelivery).filter_by(visit_id_snapshot=visit_id).count() == 1
    quoted = owner.dialect.identifier_preparer.quote_identifier(schema)
    with owner.begin() as conn:
        conn.exec_driver_sql(f"ALTER POLICY invitation_backend_select ON {quoted}.visit_invitation_deliveries USING (false)")
    with Session(runtime) as db:
        with pytest.raises(InvitationRuntimeUnavailable):
            stage(db, 1 - first_index)
        db.rollback()


@pytest.mark.integration
@pytest.mark.parametrize("transfer_first", [False, True])
def test_http_invitation_task_serializes_owner_change_and_rejects_hidden_jti(
    subject_environment, monkeypatch, transfer_first,
):
    """Exercise actual ASGI routing/auth with a physical nonowner LOGIN."""
    import threading
    import time
    from datetime import UTC, date, datetime, timedelta

    import jwt
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from app.api.deps import get_db
    from app.api.v1.endpoints.notifications import router
    from app.models.notification import NotificationDelivery, NotificationEvent
    from app.models.patient_access_audit import PatientAccessAuditLog
    from app.models.visit_invitation_delivery import VisitInvitationDelivery
    from app.services import patient_access_audit, visit_invitation_delivery
    from app.services.visit_invitation_delivery import _digest
    from tests.conftest import mint_access_token
    from tests.integration.test_visit_invitation_delivery import (
        _approval_migration,
        _issuer_migration,
        _migration,
    )

    owner, runtime, schema, login = subject_environment
    quote = owner.dialect.identifier_preparer.quote_identifier
    qs, qr = quote(schema), quote(login)
    with owner.begin() as conn:
        for model in (NotificationEvent, NotificationDelivery, PatientAccessAuditLog):
            conn.execute(sa.schema.CreateTable(model.__table__, include_foreign_key_constraints=[]))
        conn.execute(sa.text("CREATE TABLE doctor_price_overrides (id INTEGER PRIMARY KEY)"))
        migration = _migration()
        migration.op = Operations(MigrationContext.configure(conn, opts={"version_table_schema": schema}))
        migration.upgrade()
        _issuer_migration(conn)
        _approval_migration(conn)
        for table in ("notification_events", "notification_deliveries", "patient_access_audit_logs"):
            conn.exec_driver_sql(f"GRANT SELECT, INSERT, UPDATE ON {qs}.{quote(table)} TO {qr}")
        conn.exec_driver_sql(f"GRANT USAGE ON ALL SEQUENCES IN SCHEMA {qs} TO {qr}")
    provision = _module(ROOT / "backend/scripts/provision_invitation_delivery_role.py")
    provision.provision(owner, schema, login)
    with Session(owner, expire_on_commit=False) as db:
        actor = User(username="SYNTHETIC-reg-" + uuid4().hex[:12], hashed_password="!", role="Registrar", is_active=True)
        before = User(username="SYNTHETIC-before-" + uuid4().hex[:12], hashed_password="!", role="Patient", is_active=True)
        after = User(username="SYNTHETIC-after-" + uuid4().hex[:12], hashed_password="!", role="Patient", is_active=True)
        db.add_all([actor, before, after])
        db.flush()
        patient = Patient(first_name="SYNTHETIC", last_name="HTTP", phone="+998900000000", user_id=before.id)
        db.add(patient)
        db.flush()
        visit = Visit(patient_id=patient.id, visit_date=date(2099, 1, 1), visit_time="10:30",
                      status="pending_confirmation", confirmation_channel="pwa",
                      confirmation_token="SYNTHETIC-HTTP-token", confirmation_expires_at=datetime.now(UTC) + timedelta(hours=1))
        db.add(visit)
        db.flush()
        intent = VisitInvitationDelivery(visit_id=visit.id, visit_id_snapshot=visit.id, patient_id=patient.id,
                patient_id_snapshot=patient.id, owner_generation=patient.notification_owner_generation,
                context_epoch=visit.confirmation_context_epoch, token_digest=_digest(visit.confirmation_token),
                channel="phone", state="sent")
        db.add(intent)
        db.flush()
        handle = str(uuid4())
        event = NotificationEvent(event_type="appointment_confirmation_task", correlation_id=handle,
                dedup_key="SYNTHETIC-" + uuid4().hex, source_module="visit_confirmation_secure",
                entity_type="visit_invitation_delivery", entity_id=str(intent.id), title="SYNTHETIC", message="SYNTHETIC")
        db.add(event)
        db.flush()
        db.add(NotificationDelivery(event_id=event.id, recipient_type="user", recipient_id=actor.id,
                role="registrar", channel="inbox", dedup_key="SYNTHETIC-" + uuid4().hex,
                sequence_id=1, delivery_status="delivered"))
        patient_id, new_owner_id = patient.id, after.id
        token = mint_access_token(actor)
        actor_id = actor.id
        db.commit()
    api = FastAPI()
    api.include_router(router, prefix="/api/v1/notifications")

    def runtime_db():
        with Session(runtime) as db:
            yield db

    api.dependency_overrides[get_db] = runtime_db
    url = f"/api/v1/notifications/visit-invitation-tasks/{handle}"
    headers = {"Authorization": f"Bearer {token}"}
    started, finished, entered, release = (threading.Event() for _ in range(4))
    lock_entered = threading.Event()
    lock_pids = []
    errors, responses = [], []
    original = patient_access_audit._build_patient_access_entry
    original_lock = visit_invitation_delivery._lock_invitation_patient

    def tracked_patient_lock(db, patient_id):
        if transfer_first:
            lock_pids.append(db.execute(sa.text("SELECT pg_catalog.pg_backend_pid()")).scalar_one())
            lock_entered.set()
        return original_lock(db, patient_id)

    monkeypatch.setattr(visit_invitation_delivery, "_lock_invitation_patient", tracked_patient_lock)

    def assert_waiting_for_pg_lock(pid):
        until = time.monotonic() + 5
        with owner.connect() as conn:
            while time.monotonic() < until:
                waiting = conn.execute(sa.text("SELECT wait_event_type FROM pg_catalog.pg_stat_activity WHERE pid=:pid"),
                                       {"pid": pid}).scalar_one_or_none()
                if waiting == "Lock":
                    return
                time.sleep(0.01)
        pytest.fail("Competing transaction never reached a PostgreSQL lock wait")

    def pause_audit(*args, **kwargs):
        entered.set()
        assert release.wait(8)
        return original(*args, **kwargs)

    monkeypatch.setattr(patient_access_audit, "_build_patient_access_entry", pause_audit)
    with TestClient(api) as client:
        def read():
            try:
                started.set()
                responses.append(client.get(url, headers=headers))
            except Exception as exc:
                errors.append(exc)
            finally:
                finished.set()

        def transfer():
            try:
                with Session(owner) as db:
                    lock_pids.append(db.execute(sa.text("SELECT pg_catalog.pg_backend_pid()")).scalar_one())
                    started.set()
                    db.execute(sa.update(Patient).where(Patient.id == patient_id).values(user_id=new_owner_id))
                    db.commit()
            except Exception as exc:
                errors.append(exc)
            finally:
                finished.set()

        if transfer_first:
            with Session(owner) as db:
                db.execute(sa.update(Patient).where(Patient.id == patient_id).values(user_id=new_owner_id))
                thread = threading.Thread(target=read)
                thread.start()
                assert started.wait(5) and lock_entered.wait(5)
                assert_waiting_for_pg_lock(lock_pids[0])
                assert not finished.is_set()
                db.commit()
                thread.join(10)
            assert not thread.is_alive() and not errors and len(responses) == 1
            assert responses[0].status_code == 404 and "SYNTHETIC" not in responses[0].text
        else:
            thread = threading.Thread(target=read)
            thread.start()
            assert entered.wait(8)
            started.clear()
            transfer_thread = threading.Thread(target=transfer)
            transfer_thread.start()
            assert started.wait(5)
            assert_waiting_for_pg_lock(lock_pids[0])
            assert not finished.is_set()
            release.set()
            thread.join(10)
            transfer_thread.join(10)
            assert not thread.is_alive() and not transfer_thread.is_alive() and not errors and len(responses) == 1
            assert responses[0].status_code == 200 and responses[0].json()["patient_name"] == "HTTP SYNTHETIC"
            stale = client.get(url, headers=headers)
            assert stale.status_code == 404 and "SYNTHETIC" not in stale.text
        assert responses[0].headers["cache-control"] == "private, no-store"
        claims = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        with Session(owner) as db:
            db.add(TokenBlacklist(jti=claims["jti"], user_id=actor_id,
                                  expires_at=datetime.now(UTC) + timedelta(hours=1), reason="logout"))
            db.commit()
        with owner.begin() as conn:
            conn.exec_driver_sql(f"ALTER POLICY synthetic_subject_select ON {qs}.token_blacklist USING (false)")
        hidden = client.get(url, headers=headers)
        assert hidden.status_code == 503 and "SYNTHETIC" not in hidden.text
        assert hidden.headers["cache-control"] == "private, no-store"
        with owner.begin() as conn:
            conn.exec_driver_sql(f"ALTER POLICY synthetic_subject_select ON {qs}.token_blacklist USING (true)")
        revoked = client.get(url, headers=headers)
        assert revoked.status_code == 401 and "SYNTHETIC" not in revoked.text
