"""0107 migration on isolated PostgreSQL metadata; no real provider calls.

This is direct migrated 0107 with synthetic predecessor metadata, not a
complete production Alembic-chain test.
"""
from __future__ import annotations

import importlib.util
import os
import secrets
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
from fastapi import HTTPException
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session
from sqlalchemy.schema import CreateSchema, DropSchema

from app.db.base_class import Base
from app.models.all_free_request import AllFreeRequest
from app.models.encounter import Encounter
from app.models.patient import Patient
from app.models.payment import Payment
from app.models.service import Service
from app.models.user import User
from app.models.visit import Visit, VisitService
from app.services.all_free_guard import lock_visit_without_pending
from app.services.all_free_request_service import (
    AllFreeRequestError,
    AllFreeRequestService,
)
from app.services.payment_invariant_service import PaymentInvariantService
from app.services.profile_contact_security import ProfileBearerContext


@pytest.fixture
def pg_case():
    url = make_url(os.getenv("ALL_FREE_TEST_DATABASE_URL") or os.getenv("DATABASE_URL", "sqlite://"))
    if url.get_backend_name() != "postgresql" or not (url.database or "").startswith("clinic_test"):
        pytest.skip("requires disposable clinic_test PostgreSQL")
    suffix = uuid4().hex
    schema = "test_payment_guard_" + suffix
    runtime = "guard_runtime_" + suffix
    role_created = False
    runtime_engine = None
    admin = sa.create_engine(url)
    with admin.begin() as connection:
        connection.execute(CreateSchema(schema))
    engine = sa.create_engine(url, connect_args={"options": f"-csearch_path={schema} -cstatement_timeout=15000 -clock_timeout=10000"})
    try:
        import app.db.base  # noqa: F401
        Base.metadata.create_all(engine)
        path = Path(__file__).resolve().parents[2] / "alembic/versions/0107_all_free_requests.py"
        spec = importlib.util.spec_from_file_location("synthetic_payment_guard_0107", path)
        assert spec and spec.loader
        migration = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(migration)
        with engine.begin() as connection:
            for table in ("all_free_request_events", "all_free_request_lines", "all_free_requests"):
                connection.execute(sa.text(f"DROP TABLE {table}"))
            connection.execute(sa.text("DROP INDEX uq_visits_allfree_identity"))
            connection.execute(sa.text("DROP INDEX uq_visit_services_allfree_identity"))
            connection.execute(sa.text("ALTER TABLE visits DROP COLUMN allfree_encounter_identity"))
            with Operations.context(MigrationContext.configure(connection)):
                migration.upgrade()
                path_0114 = path.with_name("0114_all_free_visibility.py")
                spec_0114 = importlib.util.spec_from_file_location("synthetic_payment_guard_0114", path_0114)
                assert spec_0114 and spec_0114.loader
                migration_0114 = importlib.util.module_from_spec(spec_0114)
                spec_0114.loader.exec_module(migration_0114)
                migration_0114.upgrade()
        with admin.begin() as connection:
            password = secrets.token_urlsafe(24)
            create_role = connection.execute(sa.text("SELECT pg_catalog.format('CREATE ROLE %I LOGIN PASSWORD %L NOSUPERUSER NOBYPASSRLS', CAST(:role AS text), CAST(:password AS text))"), {"role": runtime, "password": password}).scalar_one()
            try:
                connection.exec_driver_sql(create_role)
            except sa.exc.DBAPIError:
                pytest.fail("Synthetic runtime role could not be created", pytrace=False)
            role_created = True
            connection.execute(sa.text(f'GRANT USAGE ON SCHEMA "{schema}" TO "{runtime}"'))
            for table in ("visits", "visit_services", "payment_invoices", "payment_invoice_visits", "payments", "payment_visits"):
                connection.execute(sa.text(f'GRANT SELECT, INSERT, UPDATE ON "{schema}".{table} TO "{runtime}"'))
            connection.execute(sa.text(f'GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA "{schema}" TO "{runtime}"'))
            connection.execute(sa.text(f'GRANT EXECUTE ON FUNCTION "{schema}".all_free_pending_exists(integer) TO "{runtime}"'))
        runtime_engine = sa.create_engine(url.set(username=runtime, password=password), connect_args={"options": f"-csearch_path={schema} -cstatement_timeout=15000 -clock_timeout=10000"}, hide_parameters=True)
        with Session(engine, expire_on_commit=False) as db:
            actor = User(username="synthetic-guard", hashed_password="!", role="Admin", is_active=True, auth_epoch=0)
            patient = Patient(first_name="Synthetic", last_name="Guard", birth_date=date(1990, 1, 1))
            service = Service(code="synthetic-guard", name="Synthetic", price=Decimal("5.00"), active=True, duration_minutes=10)
            db.add_all([actor, patient, service])
            db.flush()
            encounter = Encounter(patient_id=patient.id, provenance="new")
            db.add(encounter)
            db.flush()
            visit = Visit(patient_id=patient.id, encounter_id=encounter.id,
                          status="pending_confirmation", visit_date=date(2099, 1, 1), confirmation_context_epoch=7)
            db.add(visit)
            db.flush()
            db.add(VisitService(visit_id=visit.id, service_id=service.id, name="Synthetic", qty=2,
                                price=Decimal("5.00"), currency="UZS"))
            db.commit()
            ids = {"actor": actor.id, "visit": visit.id, "epoch": visit.confirmation_context_epoch, "runtime": runtime, "runtime_engine": runtime_engine}
        yield engine, admin, schema, ids
    finally:
        engine.dispose()
        if runtime_engine is not None:
            runtime_engine.dispose()
        with admin.begin() as connection:
            if role_created:
                connection.execute(sa.text(f'DROP OWNED BY "{runtime}"'))
                connection.execute(sa.text(f'DROP ROLE "{runtime}"'))
            connection.execute(DropSchema(schema, cascade=True))
        admin.dispose()


def _wait_blocked(engine, pid, future):
    deadline = time.monotonic() + 8
    while time.monotonic() < deadline:
        assert not future.done(), "competing transaction did not wait"
        with engine.connect() as connection:
            if connection.execute(sa.text("SELECT cardinality(pg_blocking_pids(:pid))"), {"pid": pid}).scalar_one():
                return
        time.sleep(0.02)
    pytest.fail("PostgreSQL transaction did not block")


def _bearer(ids):
    return ProfileBearerContext(ids["actor"], 0, "synthetic-jti", int(time.time()) + 600, None)


def _stage(db, ids):
    return AllFreeRequestService(db).stage_request(visit_id=ids["visit"], expected_epoch=ids["epoch"], bearer=_bearer(ids))


def _set_runtime(db, ids):
    assert db.execute(sa.text("SELECT current_user = session_user AND current_user = :role"), {"role": ids["runtime"]}).scalar_one()


def _pay(db, ids):
    _set_runtime(db, ids)
    return PaymentInvariantService(db).create_pending_payment(
        visit_id=ids["visit"], amount=Decimal("10.00"), currency="UZS", method="online",
        provider="payme", note="synthetic", current_user=SimpleNamespace(id=ids["actor"]), commit=False,
    )


@pytest.mark.parametrize("first", ["stage", "payment"])
def test_pg_stage_vs_payment_are_serialized(pg_case, first):
    engine, _admin, _schema, ids = pg_case
    started, pids = threading.Event(), []

    def competing():
        with Session(ids["runtime_engine"] if first == "stage" else engine) as db:
            pids.append(db.execute(sa.text("SELECT pg_backend_pid()")).scalar_one())
            started.set()
            try:
                (_pay if first == "stage" else _stage)(db, ids)
                db.commit()
                return None
            except (HTTPException, AllFreeRequestError) as error:
                db.rollback()
                return error.status_code

    with Session(engine if first == "stage" else ids["runtime_engine"]) as holder:
        (_stage if first == "stage" else _pay)(holder, ids)
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(competing)
            try:
                assert started.wait(5)
                _wait_blocked(engine, pids[0], future)
            finally:
                holder.commit()
            assert future.result(timeout=15) == 409
    with Session(engine) as observer:
        assert observer.query(AllFreeRequest).count() == (1 if first == "stage" else 0)
        assert observer.query(Payment).count() == (0 if first == "stage" else 1)


@pytest.mark.parametrize("isolation", ["REPEATABLE READ", "SERIALIZABLE"])
def test_pg_snapshot_isolation_is_unavailable(pg_case, isolation):
    engine, _admin, _schema, ids = pg_case
    with ids["runtime_engine"].connect().execution_options(isolation_level=isolation) as connection:
        with Session(connection) as db:
            _set_runtime(db, ids)
            with pytest.raises(HTTPException) as error:
                lock_visit_without_pending(db, ids["visit"])
            assert error.value.status_code == 503


def test_pg_nonowner_rls_cannot_hide_pending(pg_case):
    engine, admin, schema, ids = pg_case
    role = "guard_reader_" + uuid4().hex
    role_engine = None
    with Session(engine) as db:
        _stage(db, ids)
        db.commit()
    try:
        with admin.begin() as connection:
            password = secrets.token_urlsafe(24)
            create_role = connection.execute(sa.text("SELECT pg_catalog.format('CREATE ROLE %I LOGIN PASSWORD %L NOSUPERUSER NOBYPASSRLS', CAST(:role AS text), CAST(:password AS text))"), {"role": role, "password": password}).scalar_one()
            try:
                connection.exec_driver_sql(create_role)
            except sa.exc.DBAPIError:
                pytest.fail("Synthetic reader role could not be created", pytrace=False)
            connection.execute(sa.text(f'GRANT USAGE ON SCHEMA "{schema}" TO "{role}"'))
            connection.execute(sa.text(f'GRANT SELECT, UPDATE ON "{schema}".visits TO "{role}"'))
            connection.execute(sa.text(f'GRANT SELECT ON "{schema}".all_free_requests TO "{role}"'))
        role_engine = sa.create_engine(engine.url.set(username=role, password=password), connect_args={"options": f"-csearch_path={schema}"}, hide_parameters=True)
        with Session(role_engine) as db:
            assert db.execute(sa.text("SELECT current_user = session_user")).scalar_one()
            assert db.query(AllFreeRequest).count() == 0  # 0107's RLS hides it
            with pytest.raises(HTTPException) as error:
                lock_visit_without_pending(db, ids["visit"])
            assert error.value.status_code == 503
    finally:
        if role_engine is not None:
            role_engine.dispose()
        with admin.begin() as connection:
            connection.execute(sa.text(f'DROP OWNED BY "{role}"'))
            connection.execute(sa.text(f'DROP ROLE "{role}"'))


def test_pg_rls_change_waits_for_guard_transaction(pg_case):
    engine, _admin, _schema, ids = pg_case
    started, pids = threading.Event(), []
    def alter_security():
        with engine.begin() as connection:
            pids.append(connection.execute(sa.text("SELECT pg_backend_pid()")).scalar_one())
            started.set()
            connection.execute(sa.text("ALTER TABLE all_free_requests FORCE ROW LEVEL SECURITY"))
    with Session(ids["runtime_engine"]) as holder:
        _set_runtime(holder, ids)
        lock_visit_without_pending(holder, ids["visit"])
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(alter_security)
            try:
                assert started.wait(5)
                _wait_blocked(engine, pids[0], future)
            finally:
                holder.commit()
            future.result(timeout=15)


def test_pg_guard_table_lock_does_not_block_unrelated_stage(pg_case):
    engine, _admin, _schema, ids = pg_case
    with Session(engine, expire_on_commit=False) as db:
        first = db.get(Visit, ids["visit"])
        first_line = db.query(VisitService).filter_by(visit_id=first.id).one()
        other = Visit(patient_id=first.patient_id, encounter_id=first.encounter_id,
                      status="pending_confirmation", visit_date=date(2099, 1, 2), confirmation_context_epoch=8)
        db.add(other)
        db.flush()
        db.add(VisitService(visit_id=other.id, service_id=first_line.service_id, name="Synthetic", qty=1,
                            price=Decimal("5.00"), currency="UZS"))
        db.commit()
        other_ids = {"actor": ids["actor"], "visit": other.id, "epoch": other.confirmation_context_epoch}
    def stage_other():
        with Session(engine) as db:
            _stage(db, other_ids)
            db.commit()
    with Session(ids["runtime_engine"]) as holder:
        _set_runtime(holder, ids)
        lock_visit_without_pending(holder, ids["visit"])
        with ThreadPoolExecutor(max_workers=1) as pool:
            # Both transactions keep their locks until here; success demonstrates
            # ACCESS SHARE does not block INSERT/ROW EXCLUSIVE on another Visit.
            pool.submit(stage_other).result(timeout=10)
        holder.rollback()


def test_stage_and_guard_share_actual_restricted_backend_transaction(pg_case):
    """Exercise app staging and the visibility function under one LOGIN/tx.

    The broad grants to unrelated synthetic app tables are fixture setup, not
    a production grant recommendation. 0107 grants come solely from the
    operator provisioner under test.
    """
    engine, admin, schema, ids = pg_case
    protected = {"all_free_requests", "all_free_request_lines", "all_free_request_events"}
    quote = admin.dialect.identifier_preparer.quote_identifier
    with admin.begin() as connection:
        for table in sa.inspect(engine).get_table_names():
            if table not in protected:
                connection.exec_driver_sql(f'GRANT ALL ON TABLE {quote(schema)}.{quote(table)} TO {quote(ids["runtime"])}')
        for table in protected:
            sequence = connection.execute(sa.text("SELECT pg_catalog.pg_get_serial_sequence(:name,'id')"), {"name": f'{quote(schema)}.{quote(table)}'}).scalar_one()
            connection.exec_driver_sql(f'REVOKE SELECT ON SEQUENCE {sequence} FROM {quote(ids["runtime"])}')
    script = Path(__file__).resolve().parents[3] / "scripts/provision_all_free_backend_role.py"
    spec = importlib.util.spec_from_file_location("synthetic_role_provisioner", script)
    assert spec and spec.loader
    provisioner = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(provisioner)
    provisioner.provision(admin, schema, ids["runtime"])
    with Session(ids["runtime_engine"]) as db:
        _set_runtime(db, ids)
        request = _stage(db, ids)
        assert request.baseline_total == Decimal("10.00")
        with pytest.raises(HTTPException) as error:
            lock_visit_without_pending(db, ids["visit"])
        assert error.value.status_code == 409
        db.rollback()
    with Session(engine) as observer:
        assert observer.query(AllFreeRequest).count() == 0
    with Session(ids["runtime_engine"]) as db:
        _stage(db, ids)
        db.commit()
    with Session(ids["runtime_engine"]) as db:
        with pytest.raises(HTTPException) as error:
            lock_visit_without_pending(db, ids["visit"])
        assert error.value.status_code == 409
    # Comparing two policies alone would accept their identical weakening.
    # The migration's owner-only manifest must still reject both being changed.
    with admin.begin() as connection:
        connection.exec_driver_sql(f'ALTER POLICY allfree_template_insert ON {quote(schema)}.all_free_requests WITH CHECK (true)')
        connection.exec_driver_sql(f'ALTER POLICY allfree_backend_insert ON {quote(schema)}.all_free_requests WITH CHECK (true)')
    with Session(ids["runtime_engine"]) as db:
        with pytest.raises(HTTPException) as error:
            lock_visit_without_pending(db, ids["visit"])
        assert error.value.status_code == 503


def test_guard_on_fully_migrated_disposable_pg_database():
    """Fail closed on 0107-only; test capability when 0114 is present."""
    url = make_url(os.getenv("ALL_FREE_TEST_DATABASE_URL") or os.getenv("DATABASE_URL", "sqlite://"))
    if url.get_backend_name() != "postgresql" or not (url.database or "").startswith("clinic_test_allfree_"):
        pytest.skip("requires explicitly disposable clinic_test_allfree_* PostgreSQL")
    engine = sa.create_engine(url)
    ids = None
    runtime = "guard_smoke_" + uuid4().hex
    role_created = False
    runtime_engine = None
    try:
        with engine.connect() as connection:
            if connection.execute(sa.text("SELECT current_schema()")).scalar_one() != "public":
                pytest.skip("requires the disposable database's migrated public schema")
            if sa.inspect(connection).has_table("alembic_version") is False:
                pytest.skip("requires exact Alembic revision 0107")
            revisions = connection.execute(sa.text("SELECT version_num FROM alembic_version")).scalars().all()
            if revisions not in (["0107_all_free_requests"], ["0114_all_free_visibility"]):
                pytest.skip("requires exact Alembic revision 0107 or 0114")
        with engine.begin() as connection:
            password = secrets.token_urlsafe(24)
            create_role = connection.execute(sa.text("SELECT pg_catalog.format('CREATE ROLE %I LOGIN PASSWORD %L NOSUPERUSER NOBYPASSRLS', CAST(:role AS text), CAST(:password AS text))"), {"role": runtime, "password": password}).scalar_one()
            try:
                connection.exec_driver_sql(create_role)
            except sa.exc.DBAPIError:
                pytest.fail("Synthetic smoke role could not be created", pytrace=False)
            role_created = True
            connection.execute(sa.text(f'GRANT USAGE ON SCHEMA public TO "{runtime}"'))
            connection.execute(sa.text(f'GRANT SELECT, UPDATE ON public.visits TO "{runtime}"'))
            if revisions == ["0114_all_free_visibility"]:
                connection.execute(sa.text(f'GRANT EXECUTE ON FUNCTION public.all_free_pending_exists(integer) TO "{runtime}"'))
        runtime_engine = sa.create_engine(url.set(username=runtime, password=password), connect_args={"options": "-csearch_path=public"}, hide_parameters=True)
        with engine.begin() as connection:
            patient_id = connection.execute(sa.text("""
                INSERT INTO patients (first_name,last_name,created_at,is_deleted)
                VALUES ('Synthetic','GuardSmoke',CURRENT_TIMESTAMP,false) RETURNING id
            """)).scalar_one()
            encounter_ids = [connection.execute(sa.text("""
                INSERT INTO encounters (patient_id,provenance) VALUES (:patient,'new') RETURNING id
            """), {"patient": patient_id}).scalar_one() for _ in range(2)]
            visits = [connection.execute(sa.text("""
                INSERT INTO visits (patient_id,encounter_id,status,discount_mode,approval_status,source,created_at)
                VALUES (:patient,:encounter,'pending_confirmation','none','none','desk',CURRENT_TIMESTAMP)
                RETURNING id,confirmation_context_epoch
            """), {"patient": patient_id, "encounter": encounter}).one() for encounter in encounter_ids]
            request_id = connection.execute(sa.text("""
                INSERT INTO all_free_requests
                  (visit_id,patient_id,encounter_id,visit_id_snapshot,patient_id_snapshot,encounter_id_snapshot,
                   visit_context_epoch,encounter_generation,baseline_total,status,
                   requested_by_user_id_snapshot,requested_by_role_snapshot,policy_auto_approve)
                SELECT :visit,:patient,:encounter,:visit,:patient,:encounter,:epoch,e.generation,
                       1.00,'pending',1,'Admin',false
                FROM encounters e WHERE e.id=:encounter
                RETURNING id
            """), {"visit": visits[0].id, "patient": patient_id, "encounter": encounter_ids[0], "epoch": visits[0].confirmation_context_epoch}).scalar_one()
            ids = {"patient": patient_id, "encounters": encounter_ids,
                   "visits": [row.id for row in visits], "request": request_id}
        with Session(runtime_engine) as db:
            assert db.execute(sa.text("SELECT current_user = session_user")).scalar_one()
            with pytest.raises(HTTPException) as error:
                lock_visit_without_pending(db, ids["visits"][0])
            assert error.value.status_code == (409 if revisions == ["0114_all_free_visibility"] else 503)
            db.rollback()
            if revisions == ["0114_all_free_visibility"]:
                assert lock_visit_without_pending(db, ids["visits"][1]) is None
            else:
                with pytest.raises(HTTPException) as error:
                    lock_visit_without_pending(db, ids["visits"][1])
                assert error.value.status_code == 503
            db.rollback()
    finally:
        if runtime_engine is not None:
            runtime_engine.dispose()
        if ids is not None:
            with engine.begin() as connection:
                connection.execute(sa.text("DELETE FROM all_free_requests WHERE id=:id"), {"id": ids["request"]})
                for visit_id in ids["visits"]:
                    connection.execute(sa.text("DELETE FROM visits WHERE id=:id"), {"id": visit_id})
                for encounter_id in ids["encounters"]:
                    connection.execute(sa.text("DELETE FROM encounters WHERE id=:id"), {"id": encounter_id})
                connection.execute(sa.text("DELETE FROM patients WHERE id=:id"), {"id": ids["patient"]})
        if role_created:
            with engine.begin() as connection:
                connection.execute(sa.text(f'DROP OWNED BY "{runtime}"'))
                connection.execute(sa.text(f'DROP ROLE "{runtime}"'))
        engine.dispose()
