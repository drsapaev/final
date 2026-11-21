"""Disposable PostgreSQL checks for the private capability bootstrap."""
from __future__ import annotations

import importlib.util
import json
import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest
import sqlalchemy as sa
from sqlalchemy.engine import make_url
from sqlalchemy.schema import CreateSchema, DropSchema

from app.db.capability_namespace import capability_schema_name

ROOT = Path(__file__).resolve().parents[3]


def _module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def capability_pg():
    url = make_url(os.getenv("DOCTOR_PRICE_TEST_DATABASE_URL") or os.getenv("DATABASE_URL", "sqlite://"))
    if url.get_backend_name() != "postgresql" or not (url.database or "").startswith("clinic_test"):
        pytest.skip("requires explicitly disposable PostgreSQL")
    schema = "test_capability_" + uuid4().hex
    private = capability_schema_name(schema)
    backend = "cap_backend_" + uuid4().hex
    capability = "cap_owner_" + uuid4().hex
    admin = sa.create_engine(url)
    quote = admin.dialect.identifier_preparer.quote_identifier
    with admin.begin() as db:
        db.execute(CreateSchema(schema))
        db.exec_driver_sql(f"CREATE ROLE {quote(backend)} LOGIN NOSUPERUSER NOBYPASSRLS NOCREATEROLE NOCREATEDB NOREPLICATION")
        db.exec_driver_sql(f"CREATE ROLE {quote(capability)} NOLOGIN NOSUPERUSER NOBYPASSRLS NOCREATEROLE NOCREATEDB NOREPLICATION")
        owner = db.execute(sa.text("SELECT pg_catalog.pg_get_userbyid(nspowner) FROM pg_catalog.pg_namespace WHERE nspname=:n"), {"n": schema}).scalar_one()
    engine = sa.create_engine(url, connect_args={"options": f"-csearch_path={schema} -cstatement_timeout=15000 -clock_timeout=10000"})
    migration_test = _module("capability_fixture_migration", Path(__file__).with_name("test_doctor_price_context_migration.py"))
    helper = _module("capability_provision_helper", ROOT / "scripts/provision_capability_namespace.py")
    try:
        with engine.begin() as db:
            migration_test._predecessor(db)
            migration_test._migrate(db, "upgrade")
        yield engine, schema, private, owner, backend, capability, helper, migration_test
    finally:
        engine.dispose()
        with admin.begin() as db:
            db.execute(DropSchema(schema, cascade=True, if_exists=True))
            db.execute(DropSchema(private, cascade=True, if_exists=True))
            for role in (backend, capability):
                db.exec_driver_sql(f"DROP OWNED BY {quote(role)}")
                db.exec_driver_sql(f"DROP ROLE IF EXISTS {quote(role)}")
        admin.dispose()


@pytest.mark.parametrize("name", ["public", "A'\"$;schema", "клиника", "a" * 63])
def test_frozen_migration_helper_namespace_parity(name):
    migration = _module("capability_parity_migration", ROOT / "backend/alembic/versions/0112_doctor_price_context.py")
    helper = _module("capability_parity_helper", ROOT / "scripts/provision_capability_namespace.py")
    assert migration._capability_schema_name(name) == helper.capability_schema_name(name) == capability_schema_name(name)


@pytest.mark.parametrize("name", ["", "\0", "a" * 64, "ы" * 32])
def test_namespace_rejects_invalid_identifiers(name):
    migration = _module("capability_invalid_migration", ROOT / "backend/alembic/versions/0112_doctor_price_context.py")
    helper = _module("capability_invalid_helper", ROOT / "scripts/provision_capability_namespace.py")
    with pytest.raises(ValueError):
        migration._capability_schema_name(name)
    with pytest.raises((ValueError, helper.CapabilityNamespaceError)):
        helper.capability_schema_name(name)


def test_profile_provisioning_and_trigger_are_nonowner_safe(capability_pg):
    engine, schema, private, owner, backend, capability, helper, _ = capability_pg
    quote = engine.dialect.identifier_preparer.quote_identifier
    qs, qp, qr = quote(schema), quote(private), quote(backend)
    with engine.begin() as db:
        assert helper.validate_namespace(db, schema, expected_owner=owner) == private
        functions = db.execute(sa.text("""
          SELECT p.proname,p.prosecdef,r.rolname FROM pg_catalog.pg_proc p
          JOIN pg_catalog.pg_namespace n ON n.oid=p.pronamespace
          JOIN pg_catalog.pg_roles r ON r.oid=p.proowner
          WHERE n.nspname=:n ORDER BY p.proname
        """), {"n": private}).all()
        assert len(functions) == 3 and all(row.prosecdef and row.rolname == owner for row in functions)
        db.exec_driver_sql(f"GRANT USAGE ON SCHEMA {qs} TO {qr}")
        db.exec_driver_sql(f"GRANT SELECT,UPDATE ON {qs}.doctors TO {qr}")
        helper.reconcile_namespace_roles(db, schema, expected_owner=owner,
                                         backend_roles=(backend,), capability_owner_roles=(capability,))
    with engine.begin() as db:
        db.exec_driver_sql(f"SET LOCAL SESSION AUTHORIZATION {qr}")
        assert db.execute(sa.text("SELECT pg_catalog.has_schema_privilege(current_user,:n,'USAGE')"), {"n": private}).scalar_one()
        assert not db.execute(sa.text("SELECT pg_catalog.has_table_privilege(current_user,:t,'SELECT')"),
                              {"t": f"{qp}.clinic_capability_namespace"}).scalar_one()
        # Neither direct sequence access nor direct function EXECUTE is needed
        # by a real DML trigger invocation.
        assert not db.execute(sa.text("SELECT pg_catalog.has_sequence_privilege(current_user,:s,'USAGE')"),
                              {"s": f"{qs}.doctor_price_generation_seq"}).scalar_one()
        db.exec_driver_sql(f"UPDATE {qs}.doctors SET specialty='derma' WHERE id=10")
    with engine.begin() as db:
        assert helper.validate_namespace(db, schema, expected_owner=owner) == private


@pytest.mark.parametrize("tamper", ["marker", "namespace_acl", "marker_acl", "profile_acl", "untrusted_function"])
def test_validation_rejects_tampered_marker_acl_and_functions(capability_pg, tamper):
    engine, schema, private, owner, backend, _, helper, _ = capability_pg
    quote = engine.dialect.identifier_preparer.quote_identifier
    qp, qr = quote(private), quote(backend)
    with engine.connect() as db:
        tx = db.begin()
        try:
            if tamper == "marker":
                db.exec_driver_sql(f"UPDATE {qp}.clinic_capability_namespace SET application_schema='wrong'")
            elif tamper == "namespace_acl":
                db.exec_driver_sql(f"GRANT USAGE ON SCHEMA {qp} TO PUBLIC")
            elif tamper == "marker_acl":
                db.exec_driver_sql(f"GRANT SELECT ON {qp}.clinic_capability_namespace TO {qr}")
            elif tamper == "profile_acl":
                db.exec_driver_sql(f"GRANT SELECT ON {qp}.clinic_capability_role_profile TO {qr}")
            else:
                db.exec_driver_sql(f"GRANT EXECUTE ON FUNCTION {qp}.doctor_price_gen_doctors() TO PUBLIC")
            with pytest.raises(helper.CapabilityNamespaceError):
                helper.validate_namespace(db, schema, expected_owner=owner)
        finally:
            tx.rollback()
    with engine.begin() as db:
        assert helper.validate_namespace(db, schema, expected_owner=owner) == private


def test_invalid_reconciliation_does_not_partially_grant(capability_pg):
    engine, schema, private, owner, backend, _, helper, _ = capability_pg
    quote = engine.dialect.identifier_preparer.quote_identifier
    with engine.begin() as db:
        with pytest.raises(helper.CapabilityNamespaceError):
            helper.reconcile_namespace_roles(db, schema, expected_owner=owner,
                                             backend_roles=(backend,), capability_owner_roles=("missing_" + uuid4().hex,))
        assert db.execute(sa.text(f"SELECT count(*) FROM {quote(private)}.clinic_capability_role_profile")).scalar_one() == 0
        assert not db.execute(sa.text("SELECT pg_catalog.has_schema_privilege(:role,:schema,'USAGE')"),
                              {"role": backend, "schema": private}).scalar_one()


def test_downgrade_rejects_tampered_namespace_marker(capability_pg):
    engine, schema, private, owner, _, _, helper, migration_test = capability_pg
    quote = engine.dialect.identifier_preparer.quote_identifier
    with engine.connect() as db:
        tx = db.begin()
        try:
            db.exec_driver_sql(f"UPDATE {quote(private)}.clinic_capability_namespace SET application_schema='wrong'")
            with pytest.raises(sa.exc.DBAPIError, match="marker mismatch"):
                migration_test._migrate(db, "downgrade")
        finally:
            tx.rollback()
    with engine.begin() as db:
        assert helper.validate_namespace(db, schema, expected_owner=owner) == private


def test_profile_rollback_role_rename_and_membership_fail_closed(capability_pg):
    engine, schema, private, owner, backend, capability, helper, _ = capability_pg
    quote = engine.dialect.identifier_preparer.quote_identifier
    qp, qb, qc = quote(private), quote(backend), quote(capability)
    with engine.connect() as db:
        tx = db.begin()
        helper.reconcile_namespace_roles(db, schema, expected_owner=owner,
                                         backend_roles=(backend,), capability_owner_roles=(capability,))
        tx.rollback()
    with engine.begin() as db:
        assert db.execute(sa.text(f"SELECT count(*) FROM {qp}.clinic_capability_role_profile")).scalar_one() == 0
        helper.reconcile_namespace_roles(db, schema, expected_owner=owner,
                                         backend_roles=(backend,), capability_owner_roles=(capability,))
    with engine.connect() as db:
        tx = db.begin()
        try:
            db.exec_driver_sql(f"ALTER ROLE {qb} RENAME TO {quote('renamed_' + uuid4().hex)}")
            with pytest.raises(helper.CapabilityNamespaceError):
                helper.validate_namespace(db, schema, expected_owner=owner)
        finally:
            tx.rollback()
    with engine.connect() as db:
        tx = db.begin()
        try:
            db.exec_driver_sql(f"GRANT {qc} TO {qb}")
            with pytest.raises(helper.CapabilityNamespaceError):
                helper.validate_namespace(db, schema, expected_owner=owner)
        finally:
            tx.rollback()
    with engine.begin() as db:
        assert helper.validate_namespace(db, schema, expected_owner=owner) == private


def test_profile_rejects_membership_in_trusted_owner(capability_pg):
    engine, schema, _, owner, backend, _, helper, _ = capability_pg
    quote = engine.dialect.identifier_preparer.quote_identifier
    with engine.connect() as db:
        tx = db.begin()
        try:
            db.exec_driver_sql(f"GRANT {quote(owner)} TO {quote(backend)}")
            with pytest.raises(helper.CapabilityNamespaceError):
                helper.reconcile_namespace_roles(db, schema, expected_owner=owner,
                                                 backend_roles=(backend,), capability_owner_roles=())
        finally:
            tx.rollback()


def test_profile_reconciliation_serializes_and_rollback_releases_lock(capability_pg):
    engine, schema, _, owner, backend, capability, helper, _ = capability_pg
    with engine.connect() as first:
        tx = first.begin()
        helper.reconcile_namespace_roles(first, schema, expected_owner=owner,
                                         backend_roles=(backend,), capability_owner_roles=())

        def competing_provision():
            with engine.begin() as second:
                second.exec_driver_sql("SET LOCAL lock_timeout = '250ms'")
                with pytest.raises(sa.exc.DBAPIError) as failure:
                    helper.reconcile_namespace_roles(second, schema, expected_owner=owner,
                                                     backend_roles=(), capability_owner_roles=(capability,))
                return getattr(failure.value.orig, "sqlstate", None)

        with ThreadPoolExecutor(max_workers=1) as executor:
            assert executor.submit(competing_provision).result(timeout=10) == "55P03"
        tx.rollback()
    with engine.begin() as db:
        helper.reconcile_namespace_roles(db, schema, expected_owner=owner,
                                         backend_roles=(), capability_owner_roles=(capability,))
        helper.validate_namespace(db, schema, expected_owner=owner)


def test_unicode_and_quoted_role_provisioning(capability_pg):
    engine, schema, _, owner, _, _, helper, _ = capability_pg
    role = "сотрудник_\"'_" + uuid4().hex[:6]
    quote = engine.dialect.identifier_preparer.quote_identifier
    with engine.connect() as db:
        tx = db.begin()
        try:
            db.exec_driver_sql(f"CREATE ROLE {quote(role)} LOGIN NOSUPERUSER NOBYPASSRLS NOCREATEROLE NOCREATEDB NOREPLICATION")
            helper.reconcile_namespace_roles(db, schema, expected_owner=owner,
                                             backend_roles=(role,), capability_owner_roles=())
            helper.validate_namespace(db, schema, expected_owner=owner)
        finally:
            tx.rollback()


def test_merge_preserves_other_consumers_and_rejects_kind_conflicts(capability_pg):
    engine, schema, private, owner, backend, capability, helper, _ = capability_pg
    quote = engine.dialect.identifier_preparer.quote_identifier
    with engine.begin() as db:
        helper.merge_namespace_roles(db, schema, expected_owner=owner,
                                     backend_roles=(backend,), capability_owner_roles=())
        helper.merge_namespace_roles(db, schema, expected_owner=owner,
                                     backend_roles=(), capability_owner_roles=(capability,))
        rows = db.execute(sa.text(f"SELECT role_name,role_kind FROM {quote(private)}.clinic_capability_role_profile")).all()
        assert set(map(tuple, rows)) == {(backend, "backend"), (capability, "capability_owner")}
        with pytest.raises(helper.CapabilityNamespaceError, match="Conflicting"):
            helper.merge_namespace_roles(db, schema, expected_owner=owner,
                                         backend_roles=(capability,), capability_owner_roles=())
        helper.validate_namespace(db, schema, expected_owner=owner)


def test_competing_merge_retries_against_current_profile(capability_pg):
    engine, schema, private, owner, backend, capability, helper, _ = capability_pg
    quote = engine.dialect.identifier_preparer.quote_identifier
    with engine.connect() as first:
        tx = first.begin()
        helper.merge_namespace_roles(first, schema, expected_owner=owner,
                                     backend_roles=(backend,), capability_owner_roles=())

        def concurrent_attempt():
            with engine.begin() as second:
                second.exec_driver_sql("SET LOCAL lock_timeout='250ms'")
                with pytest.raises(sa.exc.DBAPIError) as failure:
                    helper.merge_namespace_roles(second, schema, expected_owner=owner,
                                                 backend_roles=(), capability_owner_roles=(capability,))
                return getattr(failure.value.orig, "sqlstate", None)

        with ThreadPoolExecutor(max_workers=1) as executor:
            assert executor.submit(concurrent_attempt).result(timeout=10) == "55P03"
        tx.commit()
    with engine.begin() as db:
        helper.merge_namespace_roles(db, schema, expected_owner=owner,
                                     backend_roles=(), capability_owner_roles=(capability,))
        rows = db.execute(sa.text(f"SELECT role_name,role_kind FROM {quote(private)}.clinic_capability_role_profile")).all()
        assert set(map(tuple, rows)) == {(backend, "backend"), (capability, "capability_owner")}


@pytest.mark.parametrize("forged_marker", [False, True])
def test_precreated_derived_namespace_is_never_adopted(capability_pg, forged_marker):
    engine, _, _, _, _, _, _, migration_test = capability_pg
    schema = "test_cap_precreated_" + uuid4().hex[:16]
    private = capability_schema_name(schema)
    quote = engine.dialect.identifier_preparer.quote_identifier
    try:
        with engine.begin() as db:
            db.execute(CreateSchema(schema))
            db.execute(CreateSchema(private))
            if forged_marker:
                db.exec_driver_sql(f"CREATE TABLE {quote(private)}.clinic_capability_namespace (id smallint, application_schema text)")
                db.exec_driver_sql(f"INSERT INTO {quote(private)}.clinic_capability_namespace VALUES (1,'forged')")
            db.exec_driver_sql(f"SET LOCAL search_path TO {quote(schema)}, pg_catalog, pg_temp")
            migration_test._predecessor(db)
        with pytest.raises(sa.exc.DBAPIError), engine.begin() as db:
            db.exec_driver_sql(f"SET LOCAL search_path TO {quote(schema)}, pg_catalog, pg_temp")
            # The migration anchor is explicitly supplied; no search-path guess.
            migration = migration_test._module("capability_precreated_migration", ROOT / "backend/alembic/versions/0112_doctor_price_context.py")
            migration.op = migration_test.Operations(migration_test.MigrationContext.configure(db, opts={"version_table_schema": schema}))
            migration.upgrade()
    finally:
        with engine.begin() as db:
            db.execute(DropSchema(schema, cascade=True, if_exists=True))
            db.execute(DropSchema(private, cascade=True, if_exists=True))


def test_unicode_and_quoted_schema_bootstrap(capability_pg):
    engine, _, _, owner, _, _, helper, migration_test = capability_pg
    schema = "клиника_\\\"'_$capability_bootstrap$_" + uuid4().hex[:6]
    private = capability_schema_name(schema)
    quote = engine.dialect.identifier_preparer.quote_identifier
    try:
        with engine.begin() as db:
            db.execute(CreateSchema(schema))
            db.exec_driver_sql(f"SET LOCAL search_path TO {quote(schema)}, pg_catalog, pg_temp")
            migration_test._predecessor(db)
            migration = migration_test._module("capability_unicode_migration", ROOT / "backend/alembic/versions/0112_doctor_price_context.py")
            migration.op = migration_test.Operations(migration_test.MigrationContext.configure(db, opts={"version_table_schema": schema}))
            db.exec_driver_sql("SET LOCAL standard_conforming_strings = off")
            migration.upgrade()
            assert db.exec_driver_sql("SHOW standard_conforming_strings").scalar_one() == "off"
            assert helper.validate_namespace(db, schema, expected_owner=owner) == private
    finally:
        with engine.begin() as db:
            db.execute(DropSchema(schema, cascade=True, if_exists=True))
            db.execute(DropSchema(private, cascade=True, if_exists=True))


@pytest.mark.parametrize("kind", ["TABLES", "SEQUENCES", "FUNCTIONS"])
def test_migration_rejects_broader_default_privileges_atomically(capability_pg, kind):
    engine, _, _, _, backend, _, _, migration_test = capability_pg
    schema = "test_cap_defaults_" + uuid4().hex[:12]
    private = capability_schema_name(schema)
    quote = engine.dialect.identifier_preparer.quote_identifier
    with engine.connect() as db:
        tx = db.begin()
        try:
            db.execute(CreateSchema(schema))
            db.exec_driver_sql(f"SET LOCAL search_path TO {quote(schema)}, pg_catalog, pg_temp")
            migration_test._predecessor(db)
            privilege = {"TABLES": "SELECT", "SEQUENCES": "USAGE", "FUNCTIONS": "EXECUTE"}[kind]
            db.exec_driver_sql(f"ALTER DEFAULT PRIVILEGES GRANT {privilege} ON {kind} TO {quote(backend)}")
            migration = migration_test._module("capability_defaults_migration", ROOT / "backend/alembic/versions/0112_doctor_price_context.py")
            migration.op = migration_test.Operations(migration_test.MigrationContext.configure(db, opts={"version_table_schema": schema}))
            with pytest.raises(sa.exc.DBAPIError, match="default grants are unsafe"):
                migration.upgrade()
        finally:
            tx.rollback()
    with engine.begin() as db:
        assert db.execute(sa.text("SELECT count(*) FROM pg_catalog.pg_namespace WHERE nspname IN (:app,:private)"),
                          {"app": schema, "private": private}).scalar_one() == 0


@pytest.mark.parametrize("raw", ['not-json', '{}', '"user"', '["dup","dup"]', '["anon"]', '["x",5]'])
def test_migration_owner_member_configuration_fails_closed(capability_pg, raw):
    engine, _, _, _, _, _, _, migration_test = capability_pg
    migration = migration_test._module("capability_bad_member_config", ROOT / "backend/alembic/versions/0112_doctor_price_context.py")
    with engine.begin() as db:
        migration.op = migration_test.Operations(migration_test.MigrationContext.configure(db))
        migration.alembic_context = SimpleNamespace(get_x_argument=lambda: ["capability_owner_members=" + raw])
        with pytest.raises(RuntimeError, match="allowlist"):
            migration._trusted_owner_members()


def test_migration_rejects_duplicate_owner_member_flags(capability_pg):
    engine, _, _, _, _, _, _, migration_test = capability_pg
    migration = migration_test._module("capability_duplicate_member_flags", ROOT / "backend/alembic/versions/0112_doctor_price_context.py")
    with engine.begin() as db:
        migration.op = migration_test.Operations(migration_test.MigrationContext.configure(db))
        migration.alembic_context = SimpleNamespace(get_x_argument=lambda: [
            "capability_owner_members=[]", "capability_owner_members=[]",
        ])
        with pytest.raises(RuntimeError, match="allowlist"):
            migration._trusted_owner_members()


def test_transitive_owner_members_and_explicit_non_super_operator(capability_pg):
    engine, _, _, _, backend, _, helper, migration_test = capability_pg
    suffix = uuid4().hex[:8]
    schema, owner, group = f"test_cap_nested_{suffix}", f"test_cap_owner_{suffix}", f"test_cap_group_{suffix}"
    operator = f"operator_\\\"'_$doctor_price_guard$_{suffix}"
    private = capability_schema_name(schema)
    quote = engine.dialect.identifier_preparer.quote_identifier
    qs, qo, qg, qu = map(quote, (schema, owner, group, operator))
    migration = migration_test._module("capability_nested_migration", ROOT / "backend/alembic/versions/0112_doctor_price_context.py")
    try:
        with engine.begin() as db:
            db.exec_driver_sql(f"CREATE ROLE {qo} NOLOGIN NOSUPERUSER NOBYPASSRLS NOCREATEROLE NOCREATEDB NOREPLICATION")
            db.exec_driver_sql(f"CREATE ROLE {qg} NOLOGIN NOSUPERUSER NOBYPASSRLS NOCREATEROLE NOCREATEDB NOREPLICATION")
            db.exec_driver_sql(f"CREATE ROLE {qu} LOGIN NOSUPERUSER NOBYPASSRLS NOCREATEROLE NOCREATEDB NOREPLICATION")
            db.exec_driver_sql(f"GRANT {qo} TO {qg}")
            db.exec_driver_sql(f"GRANT {qg} TO {qu}")
            db.exec_driver_sql(f"CREATE SCHEMA {qs} AUTHORIZATION {qo}")
            db.exec_driver_sql(f"SET LOCAL search_path TO {qs}, pg_catalog, pg_temp")
            migration_test._predecessor(db)
            tables = db.execute(sa.text("""
              SELECT c.relname FROM pg_catalog.pg_class c JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace
              WHERE n.nspname=:schema AND c.relkind IN ('r','p')
            """), {"schema": schema}).scalars().all()
            for table in tables:
                db.exec_driver_sql(f"ALTER TABLE {qs}.{quote(table)} OWNER TO {qo}")
            database = db.execute(sa.text("SELECT current_database()")).scalar_one()
            db.exec_driver_sql(f"GRANT CREATE ON DATABASE {quote(database)} TO {qo}")
        # Empty or incomplete lists cannot silently bless an owner member.
        for members in ((), (group,), (group, operator, "unknown")):
            with pytest.raises(sa.exc.DBAPIError, match="schema is not trusted"), engine.begin() as db:
                migration.op = migration_test.Operations(migration_test.MigrationContext.configure(
                    db, opts={"version_table_schema": schema, "trusted_capability_owner_members": members}))
                migration.upgrade()
        with engine.begin() as db:
            migration.op = migration_test.Operations(migration_test.MigrationContext.configure(
                db, opts={"version_table_schema": schema}))
            migration.alembic_context = SimpleNamespace(get_x_argument=lambda: [
                "capability_owner_members=" + json.dumps([group, operator]),
            ])
            db.exec_driver_sql(f"SET LOCAL SESSION AUTHORIZATION {qu}")
            migration.upgrade()
            assert helper.validate_namespace(db, schema, expected_owner=owner,
                                             trusted_owner_members=(group, operator)) == private
            assert helper.validate_namespace(db, schema, expected_owner=owner,
                                             trusted_owner_members=(operator, group)) == private
        with engine.connect() as db:
            tx = db.begin()
            try:
                db.exec_driver_sql(f"ALTER ROLE {qu} CREATEDB")
                with pytest.raises(helper.CapabilityNamespaceError, match="Owner membership"):
                    helper.validate_namespace(db, schema, expected_owner=owner, trusted_owner_members=(group, operator))
            finally:
                tx.rollback()
        with engine.connect() as db:
            tx = db.begin()
            try:
                db.exec_driver_sql(f"GRANT {qo} TO {quote(backend)}")
                with pytest.raises(helper.CapabilityNamespaceError, match="Owner membership"):
                    helper.validate_namespace(db, schema, expected_owner=owner, trusted_owner_members=(group, operator))
            finally:
                tx.rollback()
        with engine.connect() as db:
            tx = db.begin()
            try:
                db.exec_driver_sql(f"REVOKE {qg} FROM {qu}")
                with pytest.raises(helper.CapabilityNamespaceError, match="Owner membership"):
                    helper.validate_namespace(db, schema, expected_owner=owner, trusted_owner_members=(group, operator))
            finally:
                tx.rollback()
    finally:
        with engine.begin() as db:
            db.execute(DropSchema(schema, cascade=True, if_exists=True))
            db.execute(DropSchema(private, cascade=True, if_exists=True))
            db.exec_driver_sql(f"REVOKE {qg} FROM {qu}")
            db.exec_driver_sql(f"REVOKE {qo} FROM {qg}")
            for role in (operator, group, owner):
                db.exec_driver_sql(f"DROP OWNED BY {quote(role)}")
                db.exec_driver_sql(f"DROP ROLE IF EXISTS {quote(role)}")
