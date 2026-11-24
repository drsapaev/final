"""Real benefit ledger migrations on a minimal synthetic predecessor schema."""
from __future__ import annotations

import importlib.util
import os
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

_VERSIONS = Path(__file__).resolve().parents[2] / "alembic/versions"


def _migration(filename):
    spec = importlib.util.spec_from_file_location(filename.removesuffix(".py"), _VERSIONS / filename)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_MIGRATION = _migration("0106_encounter_benefit_ledger.py")
_GUARDS = _migration("0133_benefit_ledger_immutability.py")
_AUDIT_FIELDS = (
    ("encounter_benefit_applications", "benefit_total=0.11, net_total=0.19", "approved_by_user_id"),
    ("encounter_benefit_allocations", "benefit_amount=0.11, net_amount=0.19", "visit_service_id"),
    ("encounter_benefit_events", "reason_code='another_reason'", "actor_user_id"),
    ("encounter_benefit_quota_anchors", "benefit_id=5", None),
    ("encounter_benefit_visit_snapshots", "visit_context_epoch=13", "visit_id"),
)
_IMMUTABLE = r"benefit (visit )?evidence is immutable"


def _synthetic_predecessor(connection):
    """Create only required FK parents; not evidence that 0105 was upgraded."""
    meta = sa.MetaData()
    patients = sa.Table("patients", meta, sa.Column("id", sa.Integer, primary_key=True))
    users = sa.Table("users", meta, sa.Column("id", sa.Integer, primary_key=True))
    benefits = sa.Table("benefits", meta, sa.Column("id", sa.Integer, primary_key=True))
    assignments = sa.Table(
        "patient_benefits", meta,
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("patient_id", sa.Integer, sa.ForeignKey("patients.id", ondelete="CASCADE")),
        sa.Column("benefit_id", sa.Integer, sa.ForeignKey("benefits.id", ondelete="CASCADE")),
    )
    encounters = sa.Table(
        "encounters", meta,
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("patient_id", sa.Integer, sa.ForeignKey("patients.id", ondelete="SET NULL")),
        sa.UniqueConstraint("id", "patient_id", name="uq_synthetic_encounter_patient"),
    )
    visits = sa.Table(
        "visits", meta,
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("patient_id", sa.Integer, sa.ForeignKey("patients.id", ondelete="RESTRICT")),
        sa.Column("encounter_id", sa.Integer, sa.ForeignKey("encounters.id", ondelete="RESTRICT")),
    )
    lines = sa.Table(
        "visit_services", meta,
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("visit_id", sa.Integer, sa.ForeignKey("visits.id", ondelete="CASCADE")),
    )
    meta.create_all(connection)
    connection.execute(patients.insert(), [{"id": 1}, {"id": 2}])
    connection.execute(users.insert(), [{"id": 3}])
    connection.execute(benefits.insert(), [{"id": 4}, {"id": 5}])
    connection.execute(assignments.insert(), [{"id": 6, "patient_id": 1, "benefit_id": 4}])
    connection.execute(encounters.insert(), [{"id": 7, "patient_id": 1}, {"id": 8, "patient_id": 2}])
    connection.execute(visits.insert(), [{"id": 9, "patient_id": 1, "encounter_id": 7}])
    connection.execute(lines.insert(), [{"id": 10, "visit_id": 9}])


def _run_upgrade(connection):
    with Operations.context(MigrationContext.configure(connection)):
        _MIGRATION.upgrade()


def _run_downgrade(connection):
    with Operations.context(MigrationContext.configure(connection)):
        _MIGRATION.downgrade()


@pytest.fixture
def sqlite_engine(tmp_path):
    engine = sa.create_engine(f"sqlite:///{tmp_path / 'benefit.sqlite'}")

    @sa.event.listens_for(engine, "connect")
    def enable_fks(dbapi_connection, _):
        dbapi_connection.execute("PRAGMA foreign_keys=ON")

    try:
        with engine.begin() as connection:
            _synthetic_predecessor(connection)
            _run_upgrade(connection)
        yield engine
    finally:
        engine.dispose()


@pytest.fixture
def pg_engine():
    url = make_url(os.getenv("BENEFIT_LEDGER_TEST_DATABASE_URL") or os.getenv("DATABASE_URL", "sqlite://"))
    if url.get_backend_name() != "postgresql":
        pytest.skip("requires a disposable PostgreSQL database")
    if not os.getenv("CI") and not (url.database or "").startswith("clinic_test"):
        pytest.skip("requires an explicitly disposable clinic_test database")
    schema = "test_benefit_ledger_" + uuid4().hex
    admin = sa.create_engine(url)
    with admin.begin() as connection:
        connection.execute(CreateSchema(schema))
    engine = sa.create_engine(url, connect_args={"options": f"-csearch_path={schema} -cstatement_timeout=15000 -clock_timeout=10000"})
    try:
        with engine.begin() as connection:
            _synthetic_predecessor(connection)
            _run_upgrade(connection)
        yield engine, admin, schema
    finally:
        engine.dispose()
        with admin.begin() as connection:
            connection.execute(DropSchema(schema, cascade=True))
        admin.dispose()


def _insert_application(connection, *, ident=20, encounter=7, patient=1, benefit=4, assignment=6, period=False):
    period_columns = ", period_timezone, period_month, period_year" if period else ""
    period_values = ", 'Asia/Tashkent', '2026-11-01', 2026" if period else ""
    connection.execute(sa.text(f"""
        INSERT INTO encounter_benefit_applications
          (id, encounter_id, patient_id, patient_id_snapshot, patient_benefit_id,
           patient_benefit_id_snapshot, benefit_id, benefit_id_snapshot,
           approved_by_user_id, approved_by_user_id_snapshot, approved_by_role_snapshot,
           encounter_generation, percentage, monthly_used_before, yearly_used_before,
           gross_total, benefit_total, net_total{period_columns})
        VALUES (:ident,:encounter,:patient,:patient,:assignment,:assignment,:benefit,:benefit,
                3,3,'Admin',11,33.3333,0,0,0.30,0.10,0.20{period_values})
    """), {"ident": ident, "encounter": encounter, "patient": patient, "benefit": benefit, "assignment": assignment})


def _insert_allocation(connection):
    connection.execute(sa.text("""
        INSERT INTO encounter_benefit_allocations
          (id, application_id, visit_id, visit_id_snapshot, visit_service_id,
           visit_service_id_snapshot, service_id_snapshot, visit_context_epoch,
           quantity, unit_price, gross_amount, benefit_amount, net_amount)
        VALUES (30,20,9,9,10,10,50,12,3,0.10,0.30,0.10,0.20)
    """))


def _assert_unique_and_values(engine):
    with engine.begin() as connection:
        _insert_application(connection)
        _insert_allocation(connection)
        row = connection.execute(sa.text("""
            SELECT unit_price, gross_amount, benefit_amount, net_amount
            FROM encounter_benefit_allocations WHERE id=30
        """)).one()
        assert tuple(Decimal(str(x)).quantize(Decimal("0.01")) for x in row) == (
            Decimal("0.10"), Decimal("0.30"), Decimal("0.10"), Decimal("0.20")
        )
        connection.execute(sa.text("""
            INSERT INTO encounter_benefit_events
              (id,application_id,event_type,actor_user_id,actor_user_id_snapshot,
               actor_role_snapshot,reason_code)
            VALUES (40,20,'reversed',3,3,'Admin','synthetic_reversal')
        """))
    # Reversal does not free the encounter for a second benefit type.
    with pytest.raises(IntegrityError), engine.begin() as connection:
        _insert_application(connection, ident=21, benefit=5, assignment=6)
    with pytest.raises(IntegrityError), engine.begin() as connection:
        connection.execute(sa.text("""
            INSERT INTO encounter_benefit_allocations
              (id, application_id, visit_id, visit_id_snapshot, visit_service_id,
               visit_service_id_snapshot, service_id_snapshot, visit_context_epoch,
               quantity, unit_price, gross_amount, benefit_amount, net_amount)
            VALUES (31,20,9,9,10,10,50,12,3,0.10,0.30,0.10,0.20)
        """))


@pytest.mark.parametrize("kind", ["sqlite", "postgresql"])
def test_once_per_encounter_fractional_snapshot_and_reversal(kind, request):
    if kind == "sqlite":
        engine = request.getfixturevalue("sqlite_engine")
    else:
        engine = request.getfixturevalue("pg_engine")[0]
    _assert_unique_and_values(engine)


@pytest.mark.parametrize("kind", ["sqlite", "postgresql"])
def test_foreign_key_anonymization_preserves_snapshot_and_encounter_slot(kind, request):
    engine = request.getfixturevalue("sqlite_engine") if kind == "sqlite" else request.getfixturevalue("pg_engine")[0]
    with engine.begin() as connection:
        _insert_application(connection)
        _insert_allocation(connection)
        connection.execute(sa.text("DELETE FROM visit_services WHERE id=10"))
        connection.execute(sa.text("DELETE FROM visits WHERE id=9"))
        connection.execute(sa.text("DELETE FROM patients WHERE id=1"))
        connection.execute(sa.text("DELETE FROM benefits WHERE id=4"))
        connection.execute(sa.text("DELETE FROM users WHERE id=3"))
        header = connection.execute(sa.text("""
            SELECT patient_id, patient_id_snapshot, patient_benefit_id,
                   patient_benefit_id_snapshot, benefit_id, benefit_id_snapshot,
                   approved_by_user_id, approved_by_user_id_snapshot
            FROM encounter_benefit_applications WHERE id=20
        """)).one()
        assert tuple(header) == (None, 1, None, 6, None, 4, None, 3)
        line = connection.execute(sa.text("""
            SELECT visit_id, visit_id_snapshot, visit_service_id, visit_service_id_snapshot
            FROM encounter_benefit_allocations WHERE id=30
        """)).one()
        assert tuple(line) == (None, 9, None, 10)
    with pytest.raises(IntegrityError), engine.begin() as connection:
        connection.execute(sa.text("DELETE FROM encounters WHERE id=7"))


@pytest.mark.parametrize("kind", ["sqlite", "postgresql"])
def test_downgrade_refuses_data_and_preserves_it(kind, request):
    engine = request.getfixturevalue("sqlite_engine") if kind == "sqlite" else request.getfixturevalue("pg_engine")[0]
    with engine.begin() as connection:
        _insert_application(connection)
    with pytest.raises(DBAPIError), engine.begin() as connection:
        _run_downgrade(connection)
    with engine.connect() as connection:
        assert connection.execute(sa.text("SELECT count(*) FROM encounter_benefit_applications")).scalar_one() == 1


@pytest.mark.parametrize("kind", ["sqlite", "postgresql"])
def test_empty_downgrade_and_reupgrade(kind, request):
    engine = request.getfixturevalue("sqlite_engine") if kind == "sqlite" else request.getfixturevalue("pg_engine")[0]
    with engine.begin() as connection:
        _run_downgrade(connection)
    assert "encounter_benefit_applications" not in sa.inspect(engine).get_table_names()
    with engine.begin() as connection:
        _run_upgrade(connection)
    assert "encounter_benefit_applications" in sa.inspect(engine).get_table_names()


@pytest.mark.parametrize("kind", ["sqlite", "postgresql"])
@pytest.mark.parametrize("column,value", [
    ("percentage", "-1"), ("percentage", "101"), ("gross_total", "-0.01"),
    ("benefit_total", "0"), ("benefit_total", "0.31"), ("net_total", "0.19"),
    ("monthly_used_before", "-0.01"),
])
def test_invalid_header_values_are_rejected(kind, column, value, request):
    engine = request.getfixturevalue("sqlite_engine") if kind == "sqlite" else request.getfixturevalue("pg_engine")[0]
    with engine.begin() as connection:
        _insert_application(connection)
    with pytest.raises(IntegrityError), engine.begin() as connection:
        connection.execute(sa.text(f"UPDATE encounter_benefit_applications SET {column}={value} WHERE id=20"))


@pytest.mark.parametrize("kind", ["sqlite", "postgresql"])
@pytest.mark.parametrize("column,value", [
    ("quantity", "0"), ("unit_price", "-0.01"), ("gross_amount", "0.29"),
    ("benefit_amount", "0.31"), ("net_amount", "0.19"),
    ("visit_id_snapshot", "8"), ("visit_service_id_snapshot", "11"),
])
def test_invalid_line_values_are_rejected(kind, column, value, request):
    engine = request.getfixturevalue("sqlite_engine") if kind == "sqlite" else request.getfixturevalue("pg_engine")[0]
    with engine.begin() as connection:
        _insert_application(connection)
        _insert_allocation(connection)
    with pytest.raises(IntegrityError), engine.begin() as connection:
        connection.execute(sa.text(f"UPDATE encounter_benefit_allocations SET {column}={value} WHERE id=30"))


@pytest.mark.parametrize("kind", ["sqlite", "postgresql"])
def test_encounter_cannot_be_reassigned_to_another_patient(kind, request):
    engine = request.getfixturevalue("sqlite_engine") if kind == "sqlite" else request.getfixturevalue("pg_engine")[0]
    with engine.begin() as connection:
        _insert_application(connection)
    with pytest.raises(IntegrityError), engine.begin() as connection:
        connection.execute(sa.text("UPDATE encounters SET patient_id=2 WHERE id=7"))


def test_postgres_rls_is_enabled_and_nonowner_is_denied(pg_engine):
    engine, admin, schema = pg_engine
    role = "benefit_reader_" + uuid4().hex
    with engine.begin() as connection:
        _insert_application(connection)
    try:
        with admin.begin() as connection:
            connection.execute(sa.text(f'CREATE ROLE "{role}" NOLOGIN'))
            connection.execute(sa.text(f'GRANT USAGE ON SCHEMA "{schema}" TO "{role}"'))
            connection.execute(sa.text(f'GRANT SELECT, INSERT ON ALL TABLES IN SCHEMA "{schema}" TO "{role}"'))
            enabled = connection.execute(sa.text("""
                SELECT c.relname, c.relrowsecurity FROM pg_class c
                JOIN pg_namespace n ON n.oid=c.relnamespace
                WHERE n.nspname=:schema AND c.relname IN
                  ('encounter_benefit_applications','encounter_benefit_allocations','encounter_benefit_events')
            """), {"schema": schema}).all()
            assert len(enabled) == 3 and all(row.relrowsecurity for row in enabled)
            connection.execute(sa.text(f'SET LOCAL ROLE "{role}"'))
            assert connection.execute(sa.text(f'SELECT count(*) FROM "{schema}".encounter_benefit_applications')).scalar_one() == 0
            with pytest.raises(DBAPIError) as error, connection.begin_nested():
                connection.execute(sa.text(f"""
                    INSERT INTO "{schema}".encounter_benefit_events
                      (id, application_id, event_type, actor_user_id_snapshot, actor_role_snapshot, reason_code)
                    VALUES (91,20,'reversed',3,'Admin','synthetic')
                """))
            assert error.value.orig.sqlstate == "42501"
    finally:
        with admin.begin() as connection:
            connection.execute(sa.text(f'DROP OWNED BY "{role}"'))
            connection.execute(sa.text(f'DROP ROLE "{role}"'))


def test_postgres_forced_rls_cannot_hide_data_from_downgrade(pg_engine):
    engine, admin, schema = pg_engine
    role = "benefit_owner_" + uuid4().hex
    with engine.begin() as connection:
        _insert_application(connection)
    try:
        with admin.begin() as connection:
            connection.execute(sa.text(f'CREATE ROLE "{role}" NOLOGIN'))
            connection.execute(sa.text(f'GRANT USAGE ON SCHEMA "{schema}" TO "{role}"'))
            for table in ("encounter_benefit_applications", "encounter_benefit_allocations", "encounter_benefit_events"):
                connection.execute(sa.text(f'ALTER TABLE "{schema}".{table} OWNER TO "{role}"'))
                connection.execute(sa.text(f'ALTER TABLE "{schema}".{table} FORCE ROW LEVEL SECURITY'))
        with pytest.raises(DBAPIError) as error, engine.begin() as connection:
            connection.execute(sa.text(f'SET LOCAL ROLE "{role}"'))
            _run_downgrade(connection)
        assert error.value.orig.sqlstate == "42501"
        assert "row-level security" in str(error.value.orig)
        with engine.connect() as connection:
            assert connection.execute(sa.text("SELECT count(*) FROM encounter_benefit_applications")).scalar_one() == 1
    finally:
        with admin.begin() as connection:
            connection.execute(sa.text(f'DROP OWNED BY "{role}"'))
            connection.execute(sa.text(f'DROP ROLE "{role}"'))


@pytest.fixture
def guarded_ledger(kind, request):
    schema, private_schema = None, None
    visibility = _migration("0125_benefit_visibility.py")
    quota = _migration("0108_benefit_quota_anchor.py")
    if kind == "postgresql":
        engine, admin, schema = request.getfixturevalue("pg_engine")
        private_schema = visibility._capability_schema_name(schema)
    else:
        engine = request.getfixturevalue("sqlite_engine")

    try:
        with engine.begin() as connection:
            connection.execute(sa.text("CREATE UNIQUE INDEX uq_synthetic_visit_identity ON visits (id, patient_id, encounter_id)"))
            if schema:
                # The real 0125 quote compiles against these columns. This fixture only tests ledger writes.
                for statement in (
                    "ALTER TABLE encounters ADD COLUMN generation BIGINT, ADD COLUMN provenance TEXT",
                    "ALTER TABLE visits ADD COLUMN confirmation_context_epoch BIGINT",
                    "ALTER TABLE visit_services ADD COLUMN service_id INTEGER, ADD COLUMN qty INTEGER, "
                    "ADD COLUMN price NUMERIC(12,2), ADD COLUMN currency TEXT",
                    "CREATE TABLE all_free_requests (id INTEGER, visit_id INTEGER, status TEXT)",
                ):
                    connection.execute(sa.text(statement))
            with Operations.context(MigrationContext.configure(connection, opts={"version_table_schema": schema})):
                quota.upgrade()
                if schema:
                    _migration("0112_doctor_price_context.py")._bootstrap_capability_namespace(schema)
                visibility.upgrade()
                _GUARDS.upgrade()
        yield engine, schema
    finally:
        if private_schema:
            with admin.begin() as connection:
                connection.execute(DropSchema(private_schema, cascade=True, if_exists=True))


def _insert_guarded_evidence(connection):
    _insert_application(connection, period=True)
    _insert_allocation(connection)
    connection.execute(sa.text("""
        INSERT INTO encounter_benefit_events
          (id, application_id, event_type, actor_user_id, actor_user_id_snapshot, actor_role_snapshot, reason_code)
        VALUES (40,20,'reversed',3,3,'Admin','synthetic_reversal')
    """))
    connection.execute(sa.text("INSERT INTO encounter_benefit_quota_anchors (patient_id, benefit_id) VALUES (1,4)"))
    connection.execute(sa.text("""
        INSERT INTO encounter_benefit_visit_snapshots
          (id, application_id, visit_id, encounter_id, patient_id, visit_id_snapshot, visit_context_epoch)
        VALUES (60,20,9,7,1,9,12)
    """))


def _assert_recorded_evidence_is_immutable(connection):
    for table, mutation, live_link in _AUDIT_FIELDS:
        assert connection.execute(sa.text(f"SELECT count(*) FROM {table}")).scalar_one() == 1
        statements = [f"UPDATE {table} SET {mutation}", f"DELETE FROM {table}"]
        if live_link:
            statements.append(f"UPDATE {table} SET {live_link}=NULL")
        for statement in statements:
            with pytest.raises(DBAPIError, match=_IMMUTABLE), connection.begin_nested():
                connection.execute(sa.text(statement))


@pytest.mark.parametrize("kind", ["sqlite", "postgresql"])
def test_guards_preserve_evidence_and_foreign_key_anonymization(guarded_ledger):
    engine, _ = guarded_ledger
    with engine.begin() as connection:
        _insert_guarded_evidence(connection)
        _assert_recorded_evidence_is_immutable(connection)
        for table, ident in (("visit_services", 10), ("visits", 9), ("patients", 1), ("benefits", 4), ("users", 3)):
            connection.execute(sa.text(f"DELETE FROM {table} WHERE id=:ident"), {"ident": ident})
        assert tuple(connection.execute(sa.text("""
            SELECT patient_id, patient_id_snapshot, patient_benefit_id, patient_benefit_id_snapshot,
                   benefit_id, benefit_id_snapshot, approved_by_user_id, approved_by_user_id_snapshot
            FROM encounter_benefit_applications
        """)).one()) == (None, 1, None, 6, None, 4, None, 3)
        assert tuple(connection.execute(sa.text("""
            SELECT visit_id, visit_id_snapshot, visit_service_id, visit_service_id_snapshot
            FROM encounter_benefit_allocations
        """)).one()) == (None, 9, None, 10)
        assert tuple(connection.execute(sa.text("""
            SELECT event_type, reason_code, actor_user_id, actor_user_id_snapshot FROM encounter_benefit_events
        """)).one()) == ("reversed", "synthetic_reversal", None, 3)
        assert tuple(connection.execute(sa.text("""
            SELECT visit_id, visit_id_snapshot, patient_id, encounter_id, visit_context_epoch
            FROM encounter_benefit_visit_snapshots
        """)).one()) == (None, 9, None, 7, 12)
        assert tuple(connection.execute(sa.text("SELECT patient_id, benefit_id FROM encounter_benefit_quota_anchors")).one()) == (1, 4)


@pytest.mark.parametrize("kind", ["sqlite"])
def test_sqlite_conflict_replacement_preserves_protected_rows(guarded_ledger):
    engine, _ = guarded_ledger
    with engine.begin() as connection:
        connection.execute(sa.text("PRAGMA recursive_triggers=OFF"))
        _insert_guarded_evidence(connection)
        for table, _, _ in _AUDIT_FIELDS:
            with pytest.raises(IntegrityError, match=_IMMUTABLE), connection.begin_nested():
                connection.execute(sa.text(f"INSERT OR REPLACE INTO {table} SELECT * FROM {table}"))


@pytest.mark.parametrize("kind", ["postgresql"])
def test_postgres_limited_login_cannot_change_or_truncate_audit(guarded_ledger):
    engine, schema = guarded_ledger
    role = "benefit_ledger_dml_" + uuid4().hex
    password = "synthetic_" + uuid4().hex
    with engine.begin() as connection:
        _insert_guarded_evidence(connection)
    try:
        with engine.begin() as connection:
            connection.execute(sa.text(f"CREATE ROLE {role} LOGIN NOSUPERUSER NOBYPASSRLS PASSWORD '{password}'"))
            connection.execute(sa.text(f"GRANT USAGE ON SCHEMA {schema} TO {role}"))
            connection.execute(sa.text(f"GRANT SELECT, DELETE ON users TO {role}"))
            for table, _, _ in _AUDIT_FIELDS:
                connection.execute(sa.text(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY"))
                connection.execute(sa.text(f"CREATE POLICY synthetic_visible ON {table} TO {role} USING (true) WITH CHECK (true)"))
                connection.execute(sa.text(f"GRANT SELECT, UPDATE, DELETE, TRUNCATE ON {table} TO {role}"))
        runtime = sa.create_engine(
            engine.url.set(username=role, password=password),
            connect_args={"options": f"-csearch_path={schema} -cstatement_timeout=15000 -clock_timeout=10000"},
            hide_parameters=True,
        )
        try:
            with runtime.begin() as connection:
                assert connection.execute(sa.text("SELECT CURRENT_USER")).scalar_one() == role
                _assert_recorded_evidence_is_immutable(connection)
                for table, _, _ in _AUDIT_FIELDS:
                    with pytest.raises(DBAPIError, match=_IMMUTABLE), connection.begin_nested():
                        connection.execute(sa.text(f"TRUNCATE {table} CASCADE"))
                connection.execute(sa.text("DELETE FROM users WHERE id=3"))
                assert tuple(connection.execute(sa.text("""
                    SELECT approved_by_user_id, approved_by_user_id_snapshot FROM encounter_benefit_applications
                """)).one()) == (None, 3)
        finally:
            runtime.dispose()
    finally:
        with engine.begin() as connection:
            for table, _, _ in _AUDIT_FIELDS:
                connection.execute(sa.text(f"DROP POLICY IF EXISTS synthetic_visible ON {table}"))
            if connection.execute(sa.text("SELECT 1 FROM pg_roles WHERE rolname=:role"), {"role": role}).scalar():
                connection.execute(sa.text(f"DROP OWNED BY {role}"))
                connection.execute(sa.text(f"DROP ROLE {role}"))


@pytest.mark.parametrize("kind", ["sqlite", "postgresql"])
def test_guards_can_roll_back_before_use_only(guarded_ledger):
    engine, schema = guarded_ledger
    with engine.begin() as connection, Operations.context(MigrationContext.configure(connection, opts={"version_table_schema": schema})):
        _GUARDS.downgrade()
        _GUARDS.upgrade()
        _insert_guarded_evidence(connection)
        with pytest.raises(DBAPIError, match=r"evidence prevents downgrade|CHECK constraint failed"), connection.begin_nested():
            _GUARDS.downgrade()
        _assert_recorded_evidence_is_immutable(connection)
