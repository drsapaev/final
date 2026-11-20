"""Direct synthetic DDL checks for 0107, not a full Alembic-chain test.

All databases and identities are synthetic. PostgreSQL requires an explicitly
configured disposable database; no provider or live user is contacted.
"""
from __future__ import annotations

import importlib.util
import os
import secrets
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy.engine import make_url
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.schema import CreateSchema, DropSchema

REVISION = Path(__file__).resolve().parents[2] / "alembic/versions/0107_all_free_requests.py"


def _migration():
    spec = importlib.util.spec_from_file_location("synthetic_0107_all_free", REVISION)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _upgrade(connection, *, owner_members=None):
    opts = {} if owner_members is None else {"trusted_capability_owner_members": owner_members}
    with Operations.context(MigrationContext.configure(connection, opts=opts)):
        _migration().upgrade()


def _downgrade(connection):
    with Operations.context(MigrationContext.configure(connection)):
        _migration().downgrade()


def _synthetic_predecessor(connection):
    """Only 0107's required FK parents; this does not run 0106."""
    metadata = sa.MetaData()
    patients = sa.Table("patients", metadata, sa.Column("id", sa.Integer, primary_key=True))
    users = sa.Table("users", metadata, sa.Column("id", sa.Integer, primary_key=True))
    encounters = sa.Table(
        "encounters", metadata, sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("patient_id", sa.Integer, sa.ForeignKey("patients.id", ondelete="SET NULL")),
        sa.Column("generation", sa.BigInteger, nullable=False, server_default="1"),
        sa.UniqueConstraint("id", "patient_id", name="uq_encounters_id_patient"),
    )
    visits = sa.Table(
        "visits", metadata, sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("patient_id", sa.Integer, sa.ForeignKey("patients.id", ondelete="RESTRICT")),
        sa.Column("encounter_id", sa.Integer, sa.ForeignKey("encounters.id", ondelete="RESTRICT")),
        sa.Column("confirmation_context_epoch", sa.BigInteger, nullable=False, server_default="1"),
        sa.UniqueConstraint("id", "patient_id", name="uq_visits_id_patient"),
        sa.UniqueConstraint("id", "patient_id", "encounter_id", name="uq_visits_id_patient_encounter"),
    )
    lines = sa.Table(
        "visit_services", metadata, sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("visit_id", sa.Integer, sa.ForeignKey("visits.id", ondelete="CASCADE")),
        sa.Column("service_id", sa.Integer),
    )
    metadata.create_all(connection)
    connection.execute(patients.insert(), [{"id": 1}, {"id": 2}])
    connection.execute(users.insert(), [{"id": 3}, {"id": 4}])
    connection.execute(encounters.insert(), [
        {"id": 7, "patient_id": 1, "generation": 11},
        {"id": 8, "patient_id": 2, "generation": 12},
        {"id": 17, "patient_id": 1, "generation": 13},
    ])
    connection.execute(visits.insert(), [
        {"id": 9, "patient_id": 1, "encounter_id": 7},
        {"id": 19, "patient_id": 1, "encounter_id": 17},
        {"id": 29, "patient_id": 2, "encounter_id": 8},
    ])
    connection.execute(lines.insert(), [{"id": 10, "visit_id": 9, "service_id": 50}, {"id": 20, "visit_id": 19, "service_id": 51}])


@pytest.fixture
def sqlite_engine(tmp_path):
    engine = sa.create_engine(f"sqlite:///{tmp_path / 'all_free.sqlite'}")

    @sa.event.listens_for(engine, "connect")
    def _foreign_keys(connection, _record):
        connection.execute("PRAGMA foreign_keys=ON")

    try:
        with engine.begin() as connection:
            _synthetic_predecessor(connection)
            _upgrade(connection)
        yield engine
    finally:
        engine.dispose()


@pytest.fixture
def pg_engine():
    url = make_url(os.getenv("ALL_FREE_TEST_DATABASE_URL") or os.getenv("DATABASE_URL", "sqlite://"))
    if url.get_backend_name() != "postgresql":
        pytest.skip("requires a disposable PostgreSQL database")
    if not (url.database or "").startswith("clinic_test"):
        pytest.skip("requires an explicitly disposable clinic_test database")
    schema = "test_all_free_" + uuid4().hex
    admin = sa.create_engine(url)
    with admin.begin() as connection:
        connection.execute(CreateSchema(schema))
    engine = sa.create_engine(url, connect_args={
        "options": f"-csearch_path={schema} -cstatement_timeout=15000 -clock_timeout=10000"
    })
    try:
        with engine.begin() as connection:
            _synthetic_predecessor(connection)
            _upgrade(connection)
        yield engine, admin, schema
    finally:
        engine.dispose()
        with admin.begin() as connection:
            connection.execute(DropSchema(schema, cascade=True))
        admin.dispose()


def test_pg_migration_login_differs_from_trusted_table_and_sequence_owner():
    url = make_url(os.getenv("ALL_FREE_TEST_DATABASE_URL") or os.getenv("DATABASE_URL", "sqlite://"))
    if url.get_backend_name() != "postgresql" or not (url.database or "").startswith("clinic_test"):
        pytest.skip("requires disposable clinic_test PostgreSQL")
    suffix = uuid4().hex
    schema, owner, operator = "free_owner_" + suffix, "free_owner_role_" + suffix, "free_operator_" + suffix
    from app.db.capability_namespace import capability_schema_name
    private = capability_schema_name(schema)
    password = secrets.token_urlsafe(24)
    admin = sa.create_engine(url, hide_parameters=True)
    operator_engine = None
    roles_created = []
    try:
        with admin.begin() as connection:
            connection.execute(sa.text(f'CREATE ROLE "{owner}" NOLOGIN NOSUPERUSER NOBYPASSRLS'))
            roles_created.append(owner)
            statement = connection.execute(sa.text("SELECT pg_catalog.format('CREATE ROLE %I LOGIN PASSWORD %L NOSUPERUSER NOBYPASSRLS', CAST(:role AS text),CAST(:password AS text))"),
                                           {"role": operator, "password": password}).scalar_one()
            connection.exec_driver_sql(statement)
            roles_created.append(operator)
            connection.execute(sa.text(f'GRANT "{owner}" TO "{operator}"'))
            database = admin.dialect.identifier_preparer.quote_identifier(url.database)
            connection.execute(sa.text(f'GRANT CREATE ON DATABASE {database} TO "{operator}"'))
            connection.execute(sa.text(f'CREATE SCHEMA "{schema}" AUTHORIZATION "{owner}"'))
        admin_schema = sa.create_engine(url, hide_parameters=True, connect_args={"options": f"-csearch_path={schema}"})
        try:
            with admin_schema.begin() as connection:
                _synthetic_predecessor(connection)
                # 0114's real predecessor VisitService contains these fields;
                # the smaller 0107-only fixture deliberately omits them.
                connection.execute(sa.text("ALTER TABLE visit_services ADD COLUMN qty integer, ADD COLUMN price numeric(12,2), ADD COLUMN currency text"))
                for table in ("patients", "users", "encounters", "visits", "visit_services"):
                    connection.execute(sa.text(f'ALTER TABLE "{schema}"."{table}" OWNER TO "{owner}"'))
        finally:
            admin_schema.dispose()
        operator_engine = sa.create_engine(url.set(username=operator, password=password), hide_parameters=True,
                                           connect_args={"options": f"-csearch_path={schema} -cstatement_timeout=15000"})
        with operator_engine.begin() as connection:
            assert connection.execute(sa.text("SELECT current_user=session_user AND NOT rolsuper FROM pg_catalog.pg_roles WHERE rolname=current_user")).scalar_one()
            with pytest.raises(DBAPIError), connection.begin_nested():
                _upgrade(connection)
            _upgrade(connection, owner_members=[operator])
            bootstrap_path = REVISION.parent / "0112_doctor_price_context.py"
            bootstrap_spec = importlib.util.spec_from_file_location("synthetic_bootstrap_0112", bootstrap_path)
            assert bootstrap_spec and bootstrap_spec.loader
            bootstrap = importlib.util.module_from_spec(bootstrap_spec)
            bootstrap_spec.loader.exec_module(bootstrap)
            with Operations.context(MigrationContext.configure(connection, opts={"version_table_schema": schema})):
                bootstrap._bootstrap_capability_namespace(schema)
            visibility_path = REVISION.parent / "0114_all_free_visibility.py"
            visibility_spec = importlib.util.spec_from_file_location("synthetic_visibility_0114", visibility_path)
            assert visibility_spec and visibility_spec.loader
            visibility = importlib.util.module_from_spec(visibility_spec)
            visibility_spec.loader.exec_module(visibility)
            with Operations.context(MigrationContext.configure(connection, opts={"version_table_schema": schema})):
                visibility.upgrade()
            decision_path = REVISION.parent / "0120_all_free_decision_capability.py"
            decision_spec = importlib.util.spec_from_file_location("synthetic_decision_0120", decision_path)
            assert decision_spec and decision_spec.loader
            decision = importlib.util.module_from_spec(decision_spec)
            decision_spec.loader.exec_module(decision)
            with Operations.context(MigrationContext.configure(connection, opts={"version_table_schema": schema,
                                      "trusted_capability_owner_members": [operator]})):
                decision.upgrade()
        with admin.connect() as connection:
            rows = connection.execute(sa.text("""SELECT c.relname,r.rolname,
              pg_catalog.pg_get_serial_sequence(pg_catalog.format('%I.%I',CAST(:schema AS text),c.relname),'id') AS seq
              FROM pg_catalog.pg_class c JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace
              JOIN pg_catalog.pg_roles r ON r.oid=c.relowner
              WHERE n.nspname=:schema AND c.relname IN ('all_free_requests','all_free_request_lines','all_free_request_events')"""), {"schema": schema}).all()
            assert len(rows) == 3 and all(row.rolname == owner and row.seq for row in rows)
            for row in rows:
                assert connection.execute(sa.text("SELECT r.rolname FROM pg_catalog.pg_class c JOIN pg_catalog.pg_roles r ON r.oid=c.relowner WHERE c.oid=pg_catalog.to_regclass(:seq)"), {"seq": row.seq}).scalar_one() == owner
            assert connection.execute(sa.text("""SELECT count(*) FROM pg_catalog.pg_trigger t JOIN pg_catalog.pg_class c ON c.oid=t.tgrelid
              JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname=:schema
                AND c.relname IN ('all_free_requests','all_free_request_lines','all_free_request_events') AND NOT t.tgisinternal"""), {"schema": schema}).scalar_one() == 0
            assert connection.execute(sa.text("""SELECT r.rolname FROM pg_catalog.pg_proc p JOIN pg_catalog.pg_roles r ON r.oid=p.proowner
              WHERE p.oid=pg_catalog.to_regprocedure(:name)"""),
              {"name": f'"{private}".all_free_pending_exists(integer)'}).scalar_one() == owner
            assert connection.execute(sa.text("""SELECT r.rolname FROM pg_catalog.pg_proc p JOIN pg_catalog.pg_roles r ON r.oid=p.proowner
              WHERE p.oid=pg_catalog.to_regprocedure(:name)"""),
              {"name": f'"{private}".decide_all_free(integer,text,text,integer,bigint,integer,integer,integer,bigint,bigint,bigint)'}).scalar_one() == owner
            assert connection.execute(sa.text("""SELECT count(*) FROM pg_catalog.pg_policy p JOIN pg_catalog.pg_class c ON c.oid=p.polrelid
              JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace JOIN pg_catalog.pg_roles r ON r.rolname=:owner
              WHERE n.nspname=:schema AND p.polname LIKE 'allfree_template_%' AND p.polroles=ARRAY[r.oid]::oid[]"""),
              {"owner": owner, "schema": schema}).scalar_one() == 6
    finally:
        if operator_engine is not None:
            operator_engine.dispose()
        with admin.begin() as connection:
            connection.execute(sa.text(f'DROP SCHEMA IF EXISTS "{private}" CASCADE'))
            connection.execute(sa.text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
            for role in reversed(roles_created):
                connection.execute(sa.text(f'DROP OWNED BY "{role}"'))
                connection.execute(sa.text(f'DROP ROLE "{role}"'))
        admin.dispose()


def _engine(kind, request):
    return request.getfixturevalue("sqlite_engine") if kind == "sqlite" else request.getfixturevalue("pg_engine")[0]


def _header(connection, *, ident=30, visit=9, patient=1, encounter=7, status="pending"):
    connection.execute(sa.text("""
        INSERT INTO all_free_requests
          (id, visit_id, patient_id, encounter_id, visit_id_snapshot, patient_id_snapshot,
           encounter_id_snapshot, visit_context_epoch, encounter_generation, baseline_total,
           status, requested_by_user_id, requested_by_user_id_snapshot, requested_by_role_snapshot,
           policy_auto_approve)
        VALUES (:ident, :visit, :patient, :encounter, :visit, :patient, :encounter,
                5, 11, 0.30, :status, 3, 3, 'Registrar', false)
    """), {"ident": ident, "visit": visit, "patient": patient, "encounter": encounter, "status": status})


def _line(connection, *, ident=40, request_id=30, line_id=10):
    connection.execute(sa.text("""
        INSERT INTO all_free_request_lines
          (id, request_id, visit_service_id, visit_service_id_snapshot,
           service_id_snapshot, visit_id_snapshot, quantity, unit_price, gross_amount, currency)
        VALUES (:ident, :request_id, :line_id, :line_id, 50, 9, 3, 0.10, 0.30, 'UZS')
    """), {"ident": ident, "request_id": request_id, "line_id": line_id})


def _force_constraints(connection):
    if connection.dialect.name == "postgresql":
        connection.execute(sa.text("SET CONSTRAINTS ALL IMMEDIATE"))


@pytest.mark.parametrize("kind", ["sqlite", "postgresql"])
def test_snapshot_money_and_active_unique(kind, request):
    engine = _engine(kind, request)
    with engine.begin() as connection:
        _header(connection)
        _line(connection)
        actual = connection.execute(sa.text("SELECT unit_price,gross_amount FROM all_free_request_lines WHERE id=40")).one()
        assert tuple(Decimal(str(v)).quantize(Decimal("0.01")) for v in actual) == (Decimal("0.10"), Decimal("0.30"))
        _force_constraints(connection)
    with pytest.raises(IntegrityError), engine.begin() as connection:
        _header(connection, ident=31)
        _force_constraints(connection)


@pytest.mark.parametrize("kind", ["sqlite", "postgresql"])
def test_target_deletion_preserves_snapshots(kind, request):
    engine = _engine(kind, request)
    with engine.begin() as connection:
        _header(connection)
        _line(connection)
        connection.execute(sa.text("DELETE FROM visit_services WHERE id=10"))
        line = connection.execute(sa.text("SELECT visit_service_id,visit_service_id_snapshot,quantity,unit_price,gross_amount FROM all_free_request_lines WHERE id=40")).one()
        assert tuple(line[:3]) == (None, 10, 3)
        assert tuple(Decimal(str(v)).quantize(Decimal("0.01")) for v in line[3:]) == (Decimal("0.10"), Decimal("0.30"))
        connection.execute(sa.text("DELETE FROM visits WHERE id=9"))
        header = connection.execute(sa.text("SELECT visit_id,visit_id_snapshot,patient_id_snapshot FROM all_free_requests WHERE id=30")).one()
        assert tuple(header) == (None, 9, 1)
        _force_constraints(connection)


@pytest.mark.parametrize("kind", ["sqlite", "postgresql"])
@pytest.mark.parametrize("column,value", [
    ("visit_context_epoch", "0"), ("baseline_total", "-0.01"),
    ("status", "'unknown'"), ("visit_id_snapshot", "0"),
])
def test_invalid_header_is_rejected(kind, column, value, request):
    engine = _engine(kind, request)
    with engine.begin() as connection:
        _header(connection)
    with pytest.raises(DBAPIError), engine.begin() as connection:
        connection.execute(sa.text(f"UPDATE all_free_requests SET {column}={value} WHERE id=30"))
        _force_constraints(connection)


@pytest.mark.parametrize("kind", ["sqlite", "postgresql"])
@pytest.mark.parametrize("column,value", [
    ("quantity", "0"), ("unit_price", "-0.01"), ("gross_amount", "0.29"),
    ("visit_service_id_snapshot", "0"), ("service_id_snapshot", "0"),
])
def test_invalid_line_is_rejected(kind, column, value, request):
    engine = _engine(kind, request)
    with engine.begin() as connection:
        _header(connection)
        _line(connection)
    with pytest.raises(DBAPIError), engine.begin() as connection:
        connection.execute(sa.text(f"UPDATE all_free_request_lines SET {column}={value} WHERE id=40"))
        _force_constraints(connection)


@pytest.mark.parametrize("kind", ["sqlite", "postgresql"])
def test_downgrade_refuses_data_and_empty_roundtrip(kind, request):
    engine = _engine(kind, request)
    with engine.begin() as connection:
        _header(connection)
        _line(connection)
    with pytest.raises(DBAPIError), engine.begin() as connection:
        _downgrade(connection)
    with engine.connect() as connection:
        assert connection.execute(sa.text("SELECT count(*) FROM all_free_requests")).scalar_one() == 1
        assert connection.execute(sa.text("SELECT count(*) FROM all_free_request_lines")).scalar_one() == 1
    with engine.begin() as connection:
        connection.execute(sa.text("DELETE FROM all_free_request_lines"))
        connection.execute(sa.text("DELETE FROM all_free_requests"))
    with engine.begin() as connection:
        _downgrade(connection)
    assert "all_free_requests" not in sa.inspect(engine).get_table_names()
    with engine.begin() as connection:
        _upgrade(connection)
    assert "all_free_requests" in sa.inspect(engine).get_table_names()


@pytest.mark.parametrize("kind", ["sqlite", "postgresql"])
@pytest.mark.parametrize("patient,encounter", [(2, 8), (1, 17)])
def test_request_cannot_target_different_patient_or_encounter(kind, patient, encounter, request):
    engine = _engine(kind, request)
    with pytest.raises(DBAPIError), engine.begin() as connection:
        _header(connection, visit=9, patient=patient, encounter=encounter)
        _force_constraints(connection)


@pytest.mark.parametrize("kind", ["sqlite", "postgresql"])
def test_visit_target_move_cannot_silently_rebind_request(kind, request):
    engine = _engine(kind, request)
    with engine.begin() as connection:
        _header(connection)
    with pytest.raises(DBAPIError), engine.begin() as connection:
        connection.execute(sa.text("UPDATE visits SET encounter_id=17 WHERE id=9"))
        _force_constraints(connection)
    with engine.connect() as connection:
        assert connection.execute(sa.text("SELECT encounter_id FROM visits WHERE id=9")).scalar_one() == 7
        assert connection.execute(sa.text("SELECT encounter_id_snapshot FROM all_free_requests WHERE id=30")).scalar_one() == 7


def test_postgres_rls_nonowner_denied_and_forced_rls_downgrade_fails(pg_engine):
    engine, admin, schema = pg_engine
    role = "all_free_test_" + uuid4().hex
    tables = ("all_free_requests", "all_free_request_lines", "all_free_request_events")
    with engine.begin() as connection:
        _header(connection)
        _line(connection)
    try:
        with admin.begin() as connection:
            connection.execute(sa.text(f'CREATE ROLE "{role}" NOLOGIN'))
            connection.execute(sa.text(f'GRANT USAGE ON SCHEMA "{schema}" TO "{role}"'))
            connection.execute(sa.text(f'GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA "{schema}" TO "{role}"'))
            enabled = connection.execute(sa.text("""
                SELECT c.relname,c.relrowsecurity FROM pg_class c
                JOIN pg_namespace n ON n.oid=c.relnamespace
                WHERE n.nspname=:schema AND c.relname IN
                  ('all_free_requests','all_free_request_lines','all_free_request_events')
            """), {"schema": schema}).all()
            assert len(enabled) == 3 and all(row.relrowsecurity for row in enabled)
            connection.execute(sa.text(f'SET LOCAL ROLE "{role}"'))
            assert connection.execute(sa.text(f'SELECT count(*) FROM "{schema}".all_free_requests')).scalar_one() == 0
            updated = connection.execute(sa.text(f'UPDATE "{schema}".all_free_requests SET status=status WHERE id=30'))
            assert updated.rowcount == 0
            connection.execute(sa.text(f'SET LOCAL search_path TO "{schema}"'))
            with pytest.raises(DBAPIError) as error, connection.begin_nested():
                _header(connection, ident=31, visit=19, patient=1, encounter=17)
            assert error.value.orig.sqlstate == "42501"
    finally:
        with admin.begin() as connection:
            connection.execute(sa.text(f'DROP OWNED BY "{role}"'))
            connection.execute(sa.text(f'DROP ROLE "{role}"'))


@pytest.mark.parametrize("kind", ["sqlite", "postgresql"])
def test_live_service_without_visit_snapshot_cannot_bypass_binding(kind, request):
    engine = _engine(kind, request)
    with engine.begin() as connection:
        _header(connection)
    with pytest.raises(DBAPIError), engine.begin() as connection:
        connection.execute(sa.text("""
            INSERT INTO all_free_request_lines
              (id, request_id, visit_id_snapshot, visit_service_id, visit_service_id_snapshot,
               service_id_snapshot, quantity, unit_price, gross_amount, currency)
            VALUES (40,30,NULL,10,10,50,3,0.10,0.30,'UZS')
        """))
        _force_constraints(connection)


def _wait_until_blocked(engine, worker_pid, future):
    deadline = time.monotonic() + 8
    while time.monotonic() < deadline:
        assert not future.done(), "conflicting operation did not wait for transaction"
        with engine.connect() as inspector:
            blocked = inspector.execute(
                sa.text("SELECT cardinality(pg_blocking_pids(:pid))"), {"pid": worker_pid}
            ).scalar_one()
        if blocked:
            return
        time.sleep(0.02)
    pytest.fail("conflicting PostgreSQL transaction did not block")


@pytest.mark.parametrize("isolation", ["READ COMMITTED", "REPEATABLE READ"])
@pytest.mark.parametrize("first", ["insert", "move"])
@pytest.mark.parametrize("commit_first", [True, False])
@pytest.mark.parametrize("null_encounter", [False, True])
def test_pg_request_target_move_race(pg_engine, isolation, first, commit_first, null_encounter):
    engine, _admin, _schema = pg_engine
    if null_encounter:
        with engine.begin() as connection:
            connection.execute(sa.text("UPDATE visits SET encounter_id=NULL WHERE id=9"))
    original_encounter = None if null_encounter else 7
    worker_started = threading.Event()
    pids = []

    def operation(connection, action):
        if action == "insert":
            _header(connection, encounter=original_encounter)
        else:
            connection.execute(sa.text("UPDATE visits SET encounter_id=17 WHERE id=9"))
        _force_constraints(connection)

    def run_worker():
        try:
            with engine.connect().execution_options(isolation_level=isolation) as connection:
                with connection.begin():
                    # Establish an RR snapshot before releasing the competing writer.
                    connection.execute(sa.text("SELECT count(*) FROM visits")).scalar_one()
                    pids.append(connection.execute(sa.text("SELECT pg_backend_pid()")).scalar_one())
                    worker_started.set()
                    operation(connection, "move" if first == "insert" else "insert")
            return None
        except DBAPIError as error:
            return error.orig.sqlstate

    with engine.connect() as holder:
        transaction = holder.begin()
        operation(holder, first)
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(run_worker)
            try:
                assert worker_started.wait(5)
                _wait_until_blocked(engine, pids[0], future)
            finally:
                if commit_first:
                    transaction.commit()
                else:
                    transaction.rollback()
            result = future.result(timeout=15)
    assert result is None or result in {"23503", "40001", "40P01", "P0001"}
    if commit_first:
        assert result is not None
    with engine.connect() as connection:
        encounter = connection.execute(sa.text("SELECT encounter_id FROM visits WHERE id=9")).scalar_one()
        rows = connection.execute(sa.text("SELECT encounter_id FROM all_free_requests WHERE visit_id=9")).all()
        assert not rows or (len(rows) == 1 and rows[0][0] == encounter == original_encounter)
        if rows:
            assert encounter != 17


@pytest.mark.parametrize("isolation", ["READ COMMITTED", "REPEATABLE READ"])
@pytest.mark.parametrize("first", ["insert", "move"])
@pytest.mark.parametrize("commit_first", [True, False])
def test_pg_line_reparent_race(pg_engine, isolation, first, commit_first):
    engine, _admin, _schema = pg_engine
    with engine.begin() as connection:
        _header(connection)
    worker_started = threading.Event()
    pids = []

    def operation(connection, action):
        if action == "insert":
            _line(connection)
        else:
            connection.execute(sa.text("UPDATE visit_services SET visit_id=19 WHERE id=10"))
        _force_constraints(connection)

    def run_worker():
        try:
            with engine.connect().execution_options(isolation_level=isolation) as connection:
                with connection.begin():
                    connection.execute(sa.text("SELECT count(*) FROM visit_services")).scalar_one()
                    pids.append(connection.execute(sa.text("SELECT pg_backend_pid()")).scalar_one())
                    worker_started.set()
                    operation(connection, "move" if first == "insert" else "insert")
            return None
        except DBAPIError as error:
            return error.orig.sqlstate

    with engine.connect() as holder:
        transaction = holder.begin()
        operation(holder, first)
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(run_worker)
            try:
                assert worker_started.wait(5)
                _wait_until_blocked(engine, pids[0], future)
            finally:
                if commit_first:
                    transaction.commit()
                else:
                    transaction.rollback()
            result = future.result(timeout=15)
    assert result is None or result in {"23503", "40001", "40P01", "P0001"}
    if commit_first:
        assert result is not None
    with engine.connect() as connection:
        visit_id = connection.execute(sa.text("SELECT visit_id FROM visit_services WHERE id=10")).scalar_one()
        rows = connection.execute(sa.text("SELECT visit_id_snapshot FROM all_free_request_lines WHERE visit_service_id=10")).all()
        assert not rows or (len(rows) == 1 and rows[0][0] == visit_id == 9)


@pytest.mark.parametrize("kind", ["sqlite", "postgresql"])
def test_visit_delete_cascades_live_references_without_erasing_snapshot(kind, request):
    engine = _engine(kind, request)
    with engine.begin() as connection:
        _header(connection)
        _line(connection)
    with engine.begin() as connection:
        connection.execute(sa.text("DELETE FROM visits WHERE id=9"))
        _force_constraints(connection)
    with engine.connect() as connection:
        header = connection.execute(sa.text("SELECT visit_id,visit_id_snapshot,patient_id_snapshot FROM all_free_requests WHERE id=30")).one()
        line = connection.execute(sa.text("SELECT visit_id_snapshot,visit_service_id,visit_service_id_snapshot,service_id_snapshot FROM all_free_request_lines WHERE id=40")).one()
        assert tuple(header) == (None, 9, 1)
        assert tuple(line) == (9, None, 10, 50)


def test_postgres_forced_rls_cannot_hide_history_from_downgrade(pg_engine):
    engine, admin, schema = pg_engine
    role = "all_free_owner_" + uuid4().hex
    tables = ("all_free_requests", "all_free_request_lines", "all_free_request_events")
    with engine.begin() as connection:
        _header(connection)
    with admin.connect() as connection:
        old_owner = connection.execute(sa.text("""SELECT r.rolname FROM pg_catalog.pg_namespace n
          JOIN pg_catalog.pg_roles r ON r.oid=n.nspowner WHERE n.nspname=:schema"""), {"schema": schema}).scalar_one()
    try:
        with admin.begin() as connection:
            connection.execute(sa.text(f'CREATE ROLE "{role}" NOLOGIN'))
            connection.execute(sa.text(f'ALTER SCHEMA "{schema}" OWNER TO "{role}"'))
            connection.execute(sa.text(f'GRANT USAGE ON SCHEMA "{schema}" TO "{role}"'))
            for table in tables:
                connection.execute(sa.text(f'ALTER TABLE "{schema}".{table} OWNER TO "{role}"'))
                connection.execute(sa.text(f'ALTER TABLE "{schema}".{table} FORCE ROW LEVEL SECURITY'))
        with pytest.raises(DBAPIError) as error, engine.begin() as connection:
            connection.execute(sa.text(f'SET LOCAL ROLE "{role}"'))
            _downgrade(connection)
        assert error.value.orig.sqlstate == "42501"
        with engine.connect() as connection:
            assert connection.execute(sa.text("SELECT count(*) FROM all_free_requests")).scalar_one() == 1
    finally:
        with admin.begin() as connection:
            quoted_owner = admin.dialect.identifier_preparer.quote_identifier(old_owner)
            connection.exec_driver_sql(f'ALTER SCHEMA "{schema}" OWNER TO {quoted_owner}')
            connection.execute(sa.text(f'DROP OWNED BY "{role}"'))
            connection.execute(sa.text(f'DROP ROLE "{role}"'))


@pytest.mark.parametrize("kind", ["sqlite", "postgresql"])
def test_approved_request_also_holds_unique_active_slot(kind, request):
    engine = _engine(kind, request)
    with engine.begin() as connection:
        _header(connection)
        connection.execute(sa.text("""
            UPDATE all_free_requests SET status='approved', decision_kind='admin',
              decided_by_user_id=4, decided_by_user_id_snapshot=4,
              decided_by_role_snapshot='Admin', decided_at=CURRENT_TIMESTAMP
            WHERE id=30
        """))
    with pytest.raises(IntegrityError), engine.begin() as connection:
        _header(connection, ident=31)
        _force_constraints(connection)


@pytest.mark.parametrize("kind", ["sqlite", "postgresql"])
def test_line_cannot_attach_other_visit_or_service(kind, request):
    engine = _engine(kind, request)
    with engine.begin() as connection:
        _header(connection)
    with pytest.raises(DBAPIError), engine.begin() as connection:
        _line(connection, line_id=20)
        _force_constraints(connection)


@pytest.mark.parametrize("isolation", ["READ COMMITTED", "REPEATABLE READ"])
@pytest.mark.parametrize("commit_first", [True, False])
def test_pg_active_request_unique_race(pg_engine, isolation, commit_first):
    engine, _admin, _schema = pg_engine
    started = threading.Event()
    pids = []

    def competitor():
        try:
            with engine.connect().execution_options(isolation_level=isolation) as connection:
                with connection.begin():
                    connection.execute(sa.text("SELECT count(*) FROM visits")).scalar_one()
                    pids.append(connection.execute(sa.text("SELECT pg_backend_pid()")).scalar_one())
                    started.set()
                    _header(connection, ident=31)
                    _force_constraints(connection)
            return None
        except DBAPIError as error:
            return error.orig.sqlstate

    with engine.connect() as holder:
        transaction = holder.begin()
        _header(holder)
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(competitor)
            try:
                assert started.wait(5)
                _wait_until_blocked(engine, pids[0], future)
            finally:
                if commit_first:
                    transaction.commit()
                else:
                    transaction.rollback()
            result = future.result(timeout=15)
    assert result in ({"23505", "40001", "40P01"} if commit_first else {None, "40001", "40P01"})
    with engine.connect() as connection:
        rows = connection.execute(sa.text("SELECT id FROM all_free_requests WHERE visit_id=9 AND status='pending'")).scalars().all()
        assert len(rows) <= 1
        if commit_first:
            assert rows == [30]
        elif result is None:
            assert rows == [31]


@pytest.mark.parametrize("isolation", ["READ COMMITTED", "REPEATABLE READ"])
@pytest.mark.parametrize("first", ["insert", "delete"])
@pytest.mark.parametrize("commit_first", [True, False])
@pytest.mark.parametrize("target", ["visit", "line"])
def test_pg_insert_against_target_delete_race(pg_engine, isolation, first, commit_first, target):
    engine, _admin, _schema = pg_engine
    if target == "line":
        with engine.begin() as connection:
            _header(connection)
    started = threading.Event()
    pids = []

    def operation(connection, action):
        if action == "insert":
            if target == "visit":
                _header(connection)
            else:
                _line(connection)
        elif target == "visit":
            connection.execute(sa.text("DELETE FROM visits WHERE id=9"))
        else:
            connection.execute(sa.text("DELETE FROM visit_services WHERE id=10"))
        _force_constraints(connection)

    def competitor():
        try:
            with engine.connect().execution_options(isolation_level=isolation) as connection:
                with connection.begin():
                    connection.execute(sa.text("SELECT count(*) FROM visits")).scalar_one()
                    pids.append(connection.execute(sa.text("SELECT pg_backend_pid()")).scalar_one())
                    started.set()
                    operation(connection, "delete" if first == "insert" else "insert")
            return None
        except DBAPIError as error:
            return error.orig.sqlstate

    with engine.connect() as holder:
        transaction = holder.begin()
        operation(holder, first)
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(competitor)
            try:
                assert started.wait(5)
                _wait_until_blocked(engine, pids[0], future)
            finally:
                if commit_first:
                    transaction.commit()
                else:
                    transaction.rollback()
            result = future.result(timeout=15)
    assert result in {None, "23503", "40001", "40P01", "P0001"}
    if first == "delete" and commit_first:
        assert result is not None
    with engine.connect() as connection:
        if target == "visit":
            exists = connection.execute(sa.text("SELECT count(*) FROM visits WHERE id=9")).scalar_one()
            rows = connection.execute(sa.text("SELECT visit_id,visit_id_snapshot FROM all_free_requests WHERE id=30")).all()
            assert not rows or (len(rows) == 1 and rows[0].visit_id_snapshot == 9 and rows[0].visit_id == (9 if exists else None))
        else:
            exists = connection.execute(sa.text("SELECT count(*) FROM visit_services WHERE id=10")).scalar_one()
            rows = connection.execute(sa.text("SELECT visit_service_id,visit_service_id_snapshot FROM all_free_request_lines WHERE id=40")).all()
            assert not rows or (len(rows) == 1 and rows[0].visit_service_id_snapshot == 10 and rows[0].visit_service_id == (10 if exists else None))


def test_real_0102_child_then_visit_deadlock_aborts_safely():
    """A real legacy child-first update can deadlock a Visit-first writer.

    This intentionally uses the already fully migrated disposable database,
    unlike the minimal predecessor fixture above. Both candidate transactions
    own synthetic rows only, and the loser is rolled back by PostgreSQL.
    """
    url = make_url(os.environ.get("DATABASE_URL", "sqlite://"))
    if url.get_backend_name() != "postgresql" or not (url.database or "").startswith("clinic_test_allfree_"):
        pytest.skip("requires a fully migrated disposable clinic_test_allfree database")
    engine = sa.create_engine(url, connect_args={"options": "-cstatement_timeout=12000 -cdeadlock_timeout=300ms"})
    patient_id = None
    visit_id = None
    try:
        with engine.begin() as connection:
            revision = connection.execute(sa.text("SELECT version_num FROM alembic_version")).scalar_one()
            if revision != "0107_all_free_requests":
                pytest.skip("requires the real migration chain through 0107")
            patient_id = connection.execute(sa.text("""
                INSERT INTO patients(first_name,last_name,created_at,is_deleted)
                VALUES ('Synthetic',:name,now(),false) RETURNING id
            """), {"name": f"Deadlock{uuid4().hex[:10]}"}).scalar_one()
            visit_id = connection.execute(sa.text("""
                INSERT INTO visits(patient_id,visit_date,status,created_at,discount_mode,approval_status,source)
                VALUES (:patient,CURRENT_DATE,'pending_confirmation',now(),'none','none','desk') RETURNING id
            """), {"patient": patient_id}).scalar_one()
            line_id = connection.execute(sa.text("""
                INSERT INTO visit_services(visit_id,service_id,name,qty,price,currency,created_at)
                VALUES (:visit,1,'Synthetic',1,1,'UZS',now()) RETURNING id
            """), {"visit": visit_id}).scalar_one()

        started = threading.Event()
        worker_pids = []

        def update_child():
            try:
                with engine.begin() as connection:
                    worker_pids.append(connection.execute(sa.text("SELECT pg_backend_pid()")).scalar_one())
                    started.set()
                    # 0102 AFTER UPDATE acquires the parent Visit lock.
                    connection.execute(sa.text("UPDATE visit_services SET qty=2 WHERE id=:id"), {"id": line_id})
                return None
            except DBAPIError as exc:
                return exc.orig.sqlstate

        with engine.connect() as parent:
            transaction = parent.begin()
            parent.execute(sa.text("SELECT id FROM visits WHERE id=:id FOR UPDATE"), {"id": visit_id})
            with ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(update_child)
                assert started.wait(5)
                try:
                    _wait_until_blocked(engine, worker_pids[0], future)
                    try:
                        parent.execute(sa.text("SELECT id FROM visit_services WHERE id=:id FOR UPDATE"), {"id": line_id})
                        parent_result = None
                    except DBAPIError as exc:
                        parent_result = exc.orig.sqlstate
                finally:
                    transaction.rollback()
                worker_result = future.result(timeout=15)
        assert "40P01" in (parent_result, worker_result)
        with engine.connect() as connection:
            assert connection.execute(sa.text("SELECT qty FROM visit_services WHERE id=:id"), {"id": line_id}).scalar_one() in (1, 2)
    finally:
        if visit_id is not None:
            with engine.begin() as connection:
                connection.execute(sa.text("DELETE FROM visits WHERE id=:id"), {"id": visit_id})
                connection.execute(sa.text("DELETE FROM patients WHERE id=:id"), {"id": patient_id})
        engine.dispose()
