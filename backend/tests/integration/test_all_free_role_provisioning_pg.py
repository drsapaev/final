"""Synthetic 0114 policy provisioning: atomic, idempotent and least privilege."""
from __future__ import annotations

import importlib.util
import os
from pathlib import Path
from uuid import uuid4

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
from fastapi import HTTPException
from sqlalchemy.engine import make_url
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session
from sqlalchemy.schema import CreateSchema, DropSchema

from app.core.config import settings
from app.db.capability_namespace import capability_schema_name
from app.services.all_free_guard import (
    lock_visit_without_pending,
    require_all_free_decision_capability,
)

_ROOT = Path(__file__).resolve().parents[3]
_PROVISION_PATH = _ROOT / "scripts/provision_all_free_backend_role.py"
_spec = importlib.util.spec_from_file_location("synthetic_allfree_provision", _PROVISION_PATH)
assert _spec and _spec.loader
provisioner = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(provisioner)


@pytest.fixture
def setup_db():
    url = make_url(os.getenv("ALL_FREE_TEST_DATABASE_URL") or os.getenv("DATABASE_URL", "sqlite://"))
    if url.get_backend_name() != "postgresql" or not (url.database or "").startswith("clinic_test"):
        pytest.skip("requires disposable clinic_test PostgreSQL")
    suffix = uuid4().hex
    schema, owner, runtime, other = ("provision_" + suffix, "provision_owner_" + suffix,
                                      "provision_backend_" + suffix, "provision_other_" + suffix)
    private = capability_schema_name(schema)
    admin = sa.create_engine(url, hide_parameters=True)
    with admin.begin() as connection:
        connection.execute(CreateSchema(schema))
    engine = sa.create_engine(url, hide_parameters=True, connect_args={"options": f"-csearch_path={schema} -cstatement_timeout=15000 -clock_timeout=10000"})
    roles = []
    runtime_engine = None
    runtime_secret = uuid4().hex + uuid4().hex
    try:
        with admin.begin() as connection:
            for role, login in ((owner, "NOLOGIN"), (runtime, "LOGIN"), (other, "NOLOGIN")):
                if role == runtime:
                    create_role = connection.execute(sa.text(
                        "SELECT pg_catalog.format('CREATE ROLE %I LOGIN PASSWORD %L NOSUPERUSER NOBYPASSRLS', CAST(:role AS text), CAST(:password AS text))"
                    ), {"role": role, "password": runtime_secret}).scalar_one()
                    connection.exec_driver_sql(create_role)
                else:
                    connection.execute(sa.text(f'CREATE ROLE "{role}" {login} NOSUPERUSER NOBYPASSRLS'))
                roles.append(role)
            connection.execute(sa.text(f'ALTER SCHEMA "{schema}" OWNER TO "{owner}"'))
            connection.execute(sa.text(f'CREATE SCHEMA "{private}" AUTHORIZATION "{owner}"'))
            connection.execute(sa.text(f'''CREATE TABLE "{private}".clinic_capability_namespace (
                id SMALLINT PRIMARY KEY CHECK (id=1), format_version SMALLINT NOT NULL CHECK (format_version=1),
                application_schema TEXT NOT NULL CHECK (pg_catalog.octet_length(application_schema) BETWEEN 1 AND 63),
                private_schema TEXT NOT NULL CHECK (pg_catalog.octet_length(private_schema) BETWEEN 1 AND 63))'''))
            connection.execute(sa.text(f'''CREATE TABLE "{private}".clinic_capability_role_profile (
                role_name TEXT PRIMARY KEY CHECK (pg_catalog.octet_length(role_name) BETWEEN 1 AND 63),
                role_kind TEXT NOT NULL CHECK (role_kind IN ('backend','capability_owner')))'''))
            for table in ("clinic_capability_namespace", "clinic_capability_role_profile"):
                connection.execute(sa.text(f'ALTER TABLE "{private}".{table} OWNER TO "{owner}"'))
            connection.execute(sa.text(f'INSERT INTO "{private}".clinic_capability_namespace VALUES (1,1,:app,:private)'), {"app": schema, "private": private})
            connection.execute(sa.text(f'GRANT USAGE, CREATE ON SCHEMA "{schema}" TO "{owner}"'))
        with engine.begin() as connection:
            connection.execute(sa.text("CREATE TABLE visits (id integer PRIMARY KEY)"))
            connection.execute(sa.text("CREATE SEQUENCE visit_confirmation_generation_seq AS bigint"))
            connection.execute(sa.text(f'ALTER SEQUENCE visit_confirmation_generation_seq OWNER TO "{owner}"'))
            connection.execute(sa.text("INSERT INTO visits (id) VALUES (1),(2)"))
            connection.execute(sa.text(f'GRANT SELECT, UPDATE ON visits TO "{runtime}"'))
            connection.execute(sa.text("""CREATE TABLE visit_services
                (id serial PRIMARY KEY, visit_id integer, service_id integer, qty integer, price numeric(12,2), currency text)"""))
            connection.execute(sa.text("""CREATE TABLE all_free_requests
                (id serial PRIMARY KEY, visit_id integer, patient_id integer, encounter_id integer,
                 visit_id_snapshot integer, requested_by_user_id integer, requested_by_user_id_snapshot integer,
                 requested_by_role_snapshot text, status text, decision_kind text, decision_context_epoch bigint,
                 decided_by_user_id integer, decided_by_user_id_snapshot integer, decided_by_role_snapshot text,
                 decided_at timestamp)"""))
            connection.execute(sa.text("""CREATE TABLE all_free_request_lines
                (id serial PRIMARY KEY, request_id integer, visit_id_snapshot integer, visit_service_id integer,
                 service_id_snapshot integer, quantity integer, unit_price numeric(12,2), currency text)"""))
            connection.execute(sa.text("""CREATE TABLE all_free_request_events
                (id serial PRIMARY KEY, request_id integer, event_type text, actor_user_id integer,
                 actor_user_id_snapshot integer, actor_role_snapshot text)"""))
            for table in provisioner.TABLES:
                connection.execute(sa.text(f'ALTER TABLE {table} ENABLE ROW LEVEL SECURITY'))
                connection.execute(sa.text(f'ALTER TABLE {table} OWNER TO "{owner}"'))
            connection.execute(sa.text("INSERT INTO visit_services (id,visit_id,service_id,qty,price,currency) VALUES (10,1,20,2,5.00,'UZS')"))
            connection.execute(sa.text(f'GRANT SELECT ON visit_services TO "{runtime}"'))
            connection.execute(sa.text(f'SET LOCAL ROLE "{owner}"'))
            path = _ROOT / "backend/alembic/versions/0114_all_free_visibility.py"
            spec = importlib.util.spec_from_file_location("synthetic_role_0114", path)
            assert spec and spec.loader
            migration = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(migration)
            with Operations.context(MigrationContext.configure(connection)):
                migration.upgrade()
        with admin.begin() as connection:
            connection.execute(sa.text(f'REVOKE CREATE ON SCHEMA "{schema}" FROM "{owner}"'))
        runtime_engine = sa.create_engine(
            url.set(username=runtime, password=runtime_secret), hide_parameters=True,
            connect_args={"options": f"-csearch_path={schema} -cstatement_timeout=15000 -clock_timeout=10000"},
        )
        yield engine, admin, schema, owner, runtime, other, runtime_engine
    finally:
        if runtime_engine is not None:
            runtime_engine.dispose()
        engine.dispose()
        with admin.begin() as connection:
            connection.execute(DropSchema(private, cascade=True))
            connection.execute(DropSchema(schema, cascade=True))
            for role in reversed(roles):
                if connection.execute(sa.text("SELECT EXISTS (SELECT 1 FROM pg_roles WHERE rolname=:role)"), {"role": role}).scalar_one():
                    connection.execute(sa.text(f'DROP OWNED BY "{role}"'))
                    connection.execute(sa.text(f'DROP ROLE "{role}"'))
        admin.dispose()


def _insert_request(connection, *, state="pending"):
    return connection.execute(sa.text("""
        INSERT INTO all_free_requests
          (visit_id,patient_id,encounter_id,visit_id_snapshot,requested_by_user_id,
           requested_by_user_id_snapshot,requested_by_role_snapshot,status)
        VALUES (1,2,3,1,7,7,'admin',:state) RETURNING id
    """), {"state": state}).scalar_one()


def test_provision_is_idempotent_and_enforces_snapshot_provenance(setup_db):
    engine, _admin, schema, _owner, runtime, _other, runtime_engine = setup_db
    provisioner.provision(engine, schema, runtime, expected_owner=_owner)
    provisioner.provision(engine, schema, runtime, expected_owner=_owner)
    with runtime_engine.begin() as connection:
        identity = connection.execute(sa.text("SELECT current_user,session_user")).one()
        assert identity[0] == identity[1] == runtime
        assert connection.execute(sa.text(
            "SELECT pg_catalog.has_sequence_privilege('visit_confirmation_generation_seq','USAGE')"
        )).scalar_one() is False
        request_id = _insert_request(connection)
        connection.execute(sa.text("""
            INSERT INTO all_free_request_lines
              (request_id,visit_id_snapshot,visit_service_id,service_id_snapshot,quantity,unit_price,currency)
            VALUES (:request_id,1,10,20,2,5.00,'UZS')
        """), {"request_id": request_id})
        connection.execute(sa.text("""
            INSERT INTO all_free_request_events
              (request_id,event_type,actor_user_id,actor_user_id_snapshot,actor_role_snapshot)
            VALUES (:request_id,'requested',7,7,'admin')
        """), {"request_id": request_id})
        with pytest.raises(DBAPIError), connection.begin_nested():
            _insert_request(connection, state="approved")
        with pytest.raises(DBAPIError), connection.begin_nested():
            connection.execute(sa.text("""
                INSERT INTO all_free_requests
                  (visit_id,patient_id,encounter_id,visit_id_snapshot,requested_by_user_id,
                   requested_by_user_id_snapshot,requested_by_role_snapshot,status,decision_kind)
                VALUES (1,2,3,1,7,7,'admin','pending','admin')
            """))
        with pytest.raises(DBAPIError), connection.begin_nested():
            connection.execute(sa.text("""
                INSERT INTO all_free_request_lines
                  (request_id,visit_id_snapshot,visit_service_id,service_id_snapshot,quantity,unit_price,currency)
                VALUES (:request_id,1,10,20,2,0.01,'UZS')
            """), {"request_id": request_id})
        with pytest.raises(DBAPIError), connection.begin_nested():
            connection.execute(sa.text("""
                INSERT INTO all_free_request_events
                  (request_id,event_type,actor_user_id,actor_user_id_snapshot,actor_role_snapshot)
                VALUES (:request_id,'requested',8,8,'admin')
            """), {"request_id": request_id})
        with pytest.raises(DBAPIError), connection.begin_nested():
            connection.execute(sa.text("UPDATE all_free_requests SET status='approved' WHERE id=:id"), {"id": request_id})
    with Session(runtime_engine) as db:
        with pytest.raises(HTTPException) as error:
            lock_visit_without_pending(db, 1)
        assert error.value.status_code == 409
        with pytest.raises(HTTPException) as unavailable:
            require_all_free_decision_capability(db, 1)
        assert unavailable.value.status_code == 503
        assert lock_visit_without_pending(db, 2) is None


def test_force_rls_stage_guard_and_decision_use_one_restricted_backend(setup_db):
    engine, admin, schema, owner, runtime, other, runtime_engine = setup_db
    private = capability_schema_name(schema)
    capability = "allfree_decision_" + uuid4().hex
    with admin.begin() as connection:
        connection.execute(sa.text(f'CREATE ROLE "{capability}" NOLOGIN NOSUPERUSER NOBYPASSRLS'))
    try:
        with engine.begin() as connection:
            connection.execute(sa.text("CREATE TABLE users (id integer PRIMARY KEY, role text, is_active boolean, is_superuser boolean, auth_epoch bigint)"))
            connection.execute(sa.text("CREATE TABLE patients (id integer PRIMARY KEY, is_deleted boolean)"))
            connection.execute(sa.text("CREATE TABLE encounters (id integer PRIMARY KEY, patient_id integer, generation bigint)"))
            connection.execute(sa.text("ALTER TABLE visits ADD COLUMN patient_id integer, ADD COLUMN encounter_id integer, ADD COLUMN confirmation_context_epoch bigint"))
            connection.execute(sa.text("ALTER TABLE all_free_requests ADD COLUMN patient_id_snapshot integer, ADD COLUMN encounter_id_snapshot integer, ADD COLUMN visit_context_epoch bigint, ADD COLUMN encounter_generation bigint, ADD COLUMN policy_auto_approve boolean"))
            connection.execute(sa.text("INSERT INTO users VALUES (7,'Admin',true,false,4)"))
            connection.execute(sa.text("INSERT INTO patients VALUES (2,false)"))
            connection.execute(sa.text("INSERT INTO encounters VALUES (3,2,6)"))
            connection.execute(sa.text("UPDATE visits SET patient_id=2,encounter_id=3,confirmation_context_epoch=9 WHERE id=1"))
            for table in ("users", "patients", "encounters", "visits", *provisioner.TABLES):
                connection.execute(sa.text(f'ALTER TABLE "{schema}".{table} ENABLE ROW LEVEL SECURITY'))
                connection.execute(sa.text(f'ALTER TABLE "{schema}".{table} FORCE ROW LEVEL SECURITY'))
            connection.execute(sa.text(f'CREATE POLICY synthetic_backend_visit_read ON visits FOR SELECT TO "{runtime}" USING (true)'))
            connection.execute(sa.text(f'CREATE POLICY synthetic_backend_visit_lock ON visits FOR UPDATE TO "{runtime}" USING (true) WITH CHECK (true)'))
            connection.execute(sa.text(f'SET LOCAL ROLE "{owner}"'))
            path = _ROOT / "backend/alembic/versions/0120_all_free_decision_capability.py"
            spec = importlib.util.spec_from_file_location("synthetic_role_0120", path)
            assert spec and spec.loader
            migration = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(migration)
            with Operations.context(MigrationContext.configure(connection, opts={"version_table_schema": schema})):
                migration.upgrade()
        provisioner.provision(engine, schema, runtime, expected_owner=owner, decision_role=capability)
        provisioner.provision(engine, schema, runtime, expected_owner=owner, decision_role=capability)
        with runtime_engine.begin() as connection:
            sequence_privileges = connection.execute(sa.text("""
                SELECT pg_catalog.has_sequence_privilege('visit_confirmation_generation_seq','USAGE'),
                       pg_catalog.has_sequence_privilege('visit_confirmation_generation_seq','SELECT, UPDATE, USAGE WITH GRANT OPTION'),
                       pg_catalog.has_sequence_privilege(:other,'visit_confirmation_generation_seq','USAGE')
            """), {"other": other}).one()
            assert tuple(sequence_privileges) == (True, False, False)
            request_id = connection.execute(sa.text("""INSERT INTO all_free_requests
              (visit_id,patient_id,encounter_id,visit_id_snapshot,patient_id_snapshot,encounter_id_snapshot,
               visit_context_epoch,encounter_generation,policy_auto_approve,requested_by_user_id,
               requested_by_user_id_snapshot,requested_by_role_snapshot,status)
              VALUES (1,2,3,1,2,3,8,6,false,7,7,'admin','pending') RETURNING id""")).scalar_one()
            with pytest.raises(DBAPIError), connection.begin_nested():
                connection.execute(sa.text("UPDATE all_free_requests SET status='approved' WHERE id=:id"), {"id": request_id})
        with Session(runtime_engine) as db:
            with pytest.raises(HTTPException) as error:
                lock_visit_without_pending(db, 1)
            assert error.value.status_code == 409
            assert require_all_free_decision_capability(db, 1) == f'"{private}"'
        with admin.begin() as connection:
            connection.execute(sa.text(f'GRANT UPDATE (patient_id) ON "{schema}".all_free_requests TO "{capability}"'))
        with Session(runtime_engine) as db:
            with pytest.raises(HTTPException) as error:
                lock_visit_without_pending(db, 1)
            assert error.value.status_code == 503
        with admin.begin() as connection:
            connection.execute(sa.text(f'REVOKE UPDATE (patient_id) ON "{schema}".all_free_requests FROM "{capability}"'))
        with Session(runtime_engine) as db:
            result = db.execute(sa.text(f'''SELECT "{private}".decide_all_free(
                :id,'approve','admin',7,4,1,2,3,8,6,9)'''), {"id": request_id}).scalar_one()
            assert result > 0
            db.commit()
            assert lock_visit_without_pending(db, 1) is None
        with engine.connect() as connection:
            assert connection.execute(sa.text("SELECT status FROM all_free_requests WHERE id=:id"), {"id": request_id}).scalar_one() == "approved"
        # A later decision in a savepoint must not survive rollback.
        with runtime_engine.begin() as connection:
            second = connection.execute(sa.text("""INSERT INTO all_free_requests
              (visit_id,patient_id,encounter_id,visit_id_snapshot,patient_id_snapshot,encounter_id_snapshot,
               visit_context_epoch,encounter_generation,policy_auto_approve,requested_by_user_id,
               requested_by_user_id_snapshot,requested_by_role_snapshot,status)
              VALUES (1,2,3,1,2,3,8,6,false,7,7,'admin','pending') RETURNING id""")).scalar_one()
            savepoint = connection.begin_nested()
            connection.execute(sa.text(f'''SELECT "{private}".decide_all_free(
                :id,'reject','admin',7,4,1,2,3,8,6,9)'''), {"id": second}).scalar_one()
            savepoint.rollback()
        with Session(runtime_engine) as db:
            with pytest.raises(HTTPException) as error:
                lock_visit_without_pending(db, 1)
            assert error.value.status_code == 409
        with admin.begin() as connection:
            connection.execute(sa.text(f'GRANT "{other}" TO "{capability}"'))
        with Session(runtime_engine) as db:
            with pytest.raises(HTTPException) as error:
                lock_visit_without_pending(db, 1)
            assert error.value.status_code == 503
        with admin.begin() as connection:
            connection.execute(sa.text(f'REVOKE "{other}" FROM "{capability}"'))
        # The runtime must never be able to assume the capability owner.
        with admin.begin() as connection:
            connection.execute(sa.text(f'GRANT "{capability}" TO "{runtime}"'))
        with Session(runtime_engine) as db:
            with pytest.raises(HTTPException) as error:
                lock_visit_without_pending(db, 1)
            assert error.value.status_code == 503
        with admin.begin() as connection:
            connection.execute(sa.text(f'REVOKE "{capability}" FROM "{runtime}"'))
            connection.execute(sa.text(f'CREATE POLICY synthetic_hide_decision ON "{schema}".all_free_requests AS RESTRICTIVE FOR SELECT TO "{capability}" USING (false)'))
        with Session(runtime_engine) as db:
            with pytest.raises(HTTPException) as error:
                lock_visit_without_pending(db, 1)
            assert error.value.status_code == 503
    finally:
        with admin.begin() as connection:
            connection.execute(sa.text(f'DROP OWNED BY "{capability}" CASCADE'))
            connection.execute(sa.text(f'DROP ROLE "{capability}"'))


def test_missing_decision_function_rolls_back_staging_grants(setup_db):
    engine, admin, schema, owner, runtime, _other, _runtime_engine = setup_db
    private = capability_schema_name(schema)
    capability = "allfree_missing_" + uuid4().hex
    with admin.begin() as connection:
        connection.execute(sa.text(f'CREATE ROLE "{capability}" NOLOGIN NOSUPERUSER NOBYPASSRLS'))
    try:
        with pytest.raises(provisioner.ProvisionError, match="Decision capability unavailable"):
            provisioner.provision(engine, schema, runtime, expected_owner=owner, decision_role=capability)
        with admin.connect() as connection:
            assert connection.execute(sa.text(f'SELECT count(*) FROM "{private}".clinic_capability_role_profile')).scalar_one() == 0
            assert connection.execute(sa.text("SELECT pg_catalog.has_function_privilege(:role,:function,'EXECUTE')"),
                                      {"role": runtime, "function": f'"{private}".all_free_pending_exists(integer)'}).scalar_one() is False
    finally:
        with admin.begin() as connection:
            connection.execute(sa.text(f'DROP OWNED BY "{capability}"'))
            connection.execute(sa.text(f'DROP ROLE "{capability}"'))


def test_owner_members_require_matching_explicit_provision_and_runtime_profiles(setup_db, monkeypatch):
    engine, admin, schema, owner, runtime, other, runtime_engine = setup_db
    with admin.begin() as connection:
        connection.execute(sa.text(f'GRANT "{owner}" TO "{other}"'))
    with pytest.raises(provisioner.ProvisionError):
        provisioner.provision(engine, schema, runtime, expected_owner=owner)
    provisioner.provision(engine, schema, runtime, expected_owner=owner, trusted_owner_members=(other,))
    with Session(runtime_engine) as db:
        with pytest.raises(HTTPException) as error:
            lock_visit_without_pending(db, 2)
        assert error.value.status_code == 503
    monkeypatch.setattr(settings, "TRUSTED_DB_OWNER_MEMBERS", (other,))
    with Session(runtime_engine) as db:
        assert lock_visit_without_pending(db, 2) is None


def test_existing_unknown_policy_refuses_without_grant(setup_db):
    engine, _admin, schema, _owner, runtime, _other, _runtime_engine = setup_db
    with engine.begin() as connection:
        connection.execute(sa.text("CREATE POLICY rogue ON all_free_requests FOR SELECT TO PUBLIC USING (true)"))
    with pytest.raises(provisioner.ProvisionError):
        provisioner.provision(engine, schema, runtime, expected_owner=_owner)
    with engine.connect() as connection:
        assert connection.execute(sa.text("SELECT has_function_privilege(:role,:fn,'EXECUTE')"),
                                  {"role": runtime, "fn": f'"{capability_schema_name(schema)}".all_free_pending_exists(integer)'}).scalar_one() is False
        assert connection.execute(sa.text("SELECT count(*) FROM pg_policy WHERE polname LIKE 'allfree_backend_%' AND polrelid IN (SELECT oid FROM pg_class WHERE relnamespace = (SELECT oid FROM pg_namespace WHERE nspname=:schema))"), {"schema": schema}).scalar_one() == 0


@pytest.mark.parametrize("unsafe", ["column_update", "table_delete", "schema_create", "backend_member", "nologin", "assume_bypass"])
def test_unsafe_existing_access_is_refused(setup_db, unsafe):
    engine, admin, schema, _owner, runtime, other, _runtime_engine = setup_db
    with admin.begin() as connection:
        if unsafe == "column_update":
            connection.execute(sa.text(f'GRANT UPDATE (status) ON "{schema}".all_free_requests TO "{runtime}"'))
        elif unsafe == "table_delete":
            connection.execute(sa.text(f'GRANT DELETE ON "{schema}".all_free_requests TO "{runtime}"'))
        elif unsafe == "schema_create":
            connection.execute(sa.text(f'GRANT CREATE ON SCHEMA "{schema}" TO "{runtime}"'))
        elif unsafe == "backend_member":
            connection.execute(sa.text(f'GRANT "{runtime}" TO "{other}"'))
        elif unsafe == "assume_bypass":
            connection.execute(sa.text(f'ALTER ROLE "{other}" BYPASSRLS'))
            connection.execute(sa.text(f'GRANT "{other}" TO "{runtime}"'))
        else:
            connection.execute(sa.text(f'ALTER ROLE "{runtime}" NOLOGIN'))
    with pytest.raises(provisioner.ProvisionError):
        provisioner.provision(engine, schema, runtime, expected_owner=_owner)


def test_failure_after_first_policy_rolls_back_all_grants(setup_db):
    engine, _admin, schema, _owner, runtime, _other, _runtime_engine = setup_db
    def fail_midway(_conn, _cursor, statement, _params, _context, _many):
        if "CREATE POLICY allfree_backend_insert" in statement:
            raise RuntimeError("synthetic provision failure")
    sa.event.listen(engine, "before_cursor_execute", fail_midway)
    try:
        with pytest.raises(RuntimeError, match="synthetic"):
            provisioner.provision(engine, schema, runtime, expected_owner=_owner)
    finally:
        sa.event.remove(engine, "before_cursor_execute", fail_midway)
    with engine.connect() as connection:
        assert connection.execute(sa.text("SELECT count(*) FROM pg_policy WHERE polname LIKE 'allfree_backend_%' AND polrelid IN (SELECT oid FROM pg_class WHERE relnamespace = (SELECT oid FROM pg_namespace WHERE nspname=:schema))"), {"schema": schema}).scalar_one() == 0
        assert connection.execute(sa.text("SELECT has_function_privilege(:role,:fn,'EXECUTE')"),
                                  {"role": runtime, "fn": f'"{capability_schema_name(schema)}".all_free_pending_exists(integer)'}).scalar_one() is False


def test_tampered_template_predicate_is_refused_without_grants(setup_db):
    engine, _admin, schema, _owner, runtime, _other, _runtime_engine = setup_db
    with engine.begin() as connection:
        connection.execute(sa.text("ALTER POLICY allfree_template_insert ON all_free_requests WITH CHECK (true)"))
    with pytest.raises(provisioner.ProvisionError, match="reviewed policy"):
        provisioner.provision(engine, schema, runtime, expected_owner=_owner)
    with engine.connect() as connection:
        assert connection.execute(sa.text("SELECT has_function_privilege(:role,:fn,'EXECUTE')"),
                                  {"role": runtime, "fn": f'"{capability_schema_name(schema)}".all_free_pending_exists(integer)'}).scalar_one() is False
        assert connection.execute(sa.text("SELECT count(*) FROM pg_policy WHERE polname LIKE 'allfree_backend_%' AND polrelid IN (SELECT oid FROM pg_class WHERE relnamespace=(SELECT oid FROM pg_namespace WHERE nspname=:schema))"), {"schema": schema}).scalar_one() == 0


def test_foreign_column_only_grant_is_refused(setup_db):
    engine, admin, schema, _owner, runtime, other, _runtime_engine = setup_db
    with admin.begin() as connection:
        connection.execute(sa.text(f'GRANT SELECT (status) ON "{schema}".all_free_requests TO "{other}"'))
    with pytest.raises(provisioner.ProvisionError, match="column ACL"):
        provisioner.provision(engine, schema, runtime, expected_owner=_owner)


def test_tampered_existing_backend_policy_is_not_replaced(setup_db):
    engine, _admin, schema, _owner, runtime, _other, _runtime_engine = setup_db
    provisioner.provision(engine, schema, runtime, expected_owner=_owner)
    with engine.begin() as connection:
        connection.execute(sa.text("ALTER POLICY allfree_backend_insert ON all_free_requests WITH CHECK (true)"))
    with pytest.raises(provisioner.ProvisionError, match="differs"):
        provisioner.provision(engine, schema, runtime, expected_owner=_owner)
    with engine.connect() as connection:
        expression = connection.execute(sa.text("SELECT pg_get_expr(polwithcheck,polrelid) FROM pg_policy WHERE polname='allfree_backend_insert' AND polrelid='all_free_requests'::regclass")).scalar_one()
        assert expression == "true"  # no silent replacement or destructive repair


def test_identifier_quoting_does_not_interpret_role_name_as_sql(setup_db):
    engine, admin, schema, _owner, _runtime, _other, _runtime_engine = setup_db
    weird_role = 'backend"; SELECT 1; --' + uuid4().hex[:8]
    quoted = admin.dialect.identifier_preparer.quote_identifier(weird_role)
    try:
        with admin.begin() as connection:
            connection.exec_driver_sql(f"CREATE ROLE {quoted} LOGIN NOSUPERUSER NOBYPASSRLS")
        provisioner.provision(engine, schema, weird_role, expected_owner=_owner)
        with engine.connect() as connection:
            assert connection.execute(sa.text("SELECT has_function_privilege(:role,:fn,'EXECUTE')"),
                                      {"role": weird_role, "fn": f'"{capability_schema_name(schema)}".all_free_pending_exists(integer)'}).scalar_one() is True
            assert connection.execute(sa.text("SELECT to_regclass(:table) IS NOT NULL"), {"table": f'"{schema}".all_free_requests'}).scalar_one() is True
    finally:
        with admin.begin() as connection:
            connection.exec_driver_sql(f"DROP OWNED BY {quoted}")
            connection.exec_driver_sql(f"DROP ROLE {quoted}")


def test_powershell_operator_wrapper_provisions_explicit_role(setup_db):
    import shutil
    import subprocess

    _engine, admin, schema, _owner, runtime, _other, _runtime_engine = setup_db
    powershell = shutil.which("pwsh")
    if not powershell:
        pytest.skip("requires PowerShell for the operator wrapper")
    env = os.environ.copy()
    env["DATABASE_URL"] = env.get("ALL_FREE_TEST_DATABASE_URL") or env.get("DATABASE_URL", "")
    assert (make_url(env["DATABASE_URL"]).database or "").startswith("clinic_test")
    result = subprocess.run(
        [powershell, "-NoProfile", "-File", str(_ROOT / "scripts/provision_all_free_backend_role.ps1"),
         "-Schema", schema, "-Role", runtime, "-ExpectedOwner", _owner],
        env=env, capture_output=True, text=True, timeout=30, check=False,
    )
    assert result.returncode == 0, "synthetic operator wrapper failed"
    with admin.connect() as connection:
        assert connection.execute(sa.text("SELECT has_function_privilege(:role,:fn,'EXECUTE')"),
                                  {"role": runtime, "fn": f'"{capability_schema_name(schema)}".all_free_pending_exists(integer)'}).scalar_one() is True


@pytest.mark.parametrize("grant", ["function", "table", "column"])
def test_public_access_prevents_provision_without_rewriting_it(setup_db, grant):
    engine, admin, schema, _owner, runtime, _other, _runtime_engine = setup_db
    with admin.begin() as connection:
        if grant == "function":
            connection.execute(sa.text(f'GRANT EXECUTE ON FUNCTION "{capability_schema_name(schema)}".all_free_pending_exists(integer) TO PUBLIC'))
        elif grant == "table":
            connection.execute(sa.text(f'GRANT SELECT ON "{schema}".all_free_requests TO PUBLIC'))
        else:
            connection.execute(sa.text(f'GRANT SELECT (status) ON "{schema}".all_free_requests TO PUBLIC'))
    with pytest.raises(provisioner.ProvisionError):
        provisioner.provision(engine, schema, runtime, expected_owner=_owner)
    with engine.connect() as connection:
        assert connection.execute(sa.text("SELECT count(*) FROM pg_policy WHERE polname LIKE 'allfree_backend_%' AND polrelid IN (SELECT oid FROM pg_class WHERE relnamespace=(SELECT oid FROM pg_namespace WHERE nspname=:schema))"), {"schema": schema}).scalar_one() == 0
