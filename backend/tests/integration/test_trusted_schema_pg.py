"""Real PostgreSQL role and search-path tests; no application data is used."""
from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import pytest
import sqlalchemy as sa
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session
from sqlalchemy.schema import DropSchema

from app.db.trusted_schema import TrustedSchemaUnavailable, pin_application_schema


@pytest.fixture
def trusted_pg():
    url = make_url(os.getenv("TRUSTED_SCHEMA_TEST_DATABASE_URL") or os.getenv("DATABASE_URL", "sqlite://"))
    if url.get_backend_name() != "postgresql" or not (url.database or "").startswith("clinic_test"):
        pytest.skip("requires disposable PostgreSQL")
    suffix = uuid4().hex[:12]
    schema = "test_schema_\"'_\\_" + suffix
    owner, runtime, group, operator = (prefix + suffix for prefix in (
        "test_schema_owner_", "test_schema_runtime_", "test_schema_group_", "test_schema_operator_"))
    engine = sa.create_engine(url)
    runtime_password = uuid4().hex + uuid4().hex
    engine._synthetic_runtime_password = runtime_password
    quote = engine.dialect.identifier_preparer.quote_identifier
    qs, qo, qr, qg, qu = map(quote, (schema, owner, runtime, group, operator))
    with engine.begin() as db:
        for name, login in ((owner, "NOLOGIN"), (runtime, "LOGIN"), (group, "NOLOGIN"), (operator, "LOGIN")):
            db.exec_driver_sql(f"CREATE ROLE {quote(name)} {login} NOSUPERUSER NOBYPASSRLS NOCREATEROLE NOCREATEDB NOREPLICATION")
        db.execute(sa.text("SELECT pg_catalog.set_config('test.runtime_password',:password,true)"), {"password": runtime_password})
        db.exec_driver_sql(f"DO $$ BEGIN EXECUTE pg_catalog.format('ALTER ROLE %%I PASSWORD %%L', '{runtime}', pg_catalog.current_setting('test.runtime_password')); END $$")
        db.exec_driver_sql(f"CREATE SCHEMA {qs} AUTHORIZATION {qo}")
        db.exec_driver_sql(f"CREATE TABLE {qs}.marker (value TEXT NOT NULL)")
        db.exec_driver_sql(f"INSERT INTO {qs}.marker VALUES ('trusted')")
        db.exec_driver_sql(f"CREATE TABLE {qs}.token_blacklist (id INTEGER PRIMARY KEY, jti TEXT NOT NULL)")
        db.exec_driver_sql(f"ALTER TABLE {qs}.token_blacklist OWNER TO {qo}")
        db.exec_driver_sql(f"CREATE TABLE {qs}.users (id INTEGER PRIMARY KEY, role TEXT NOT NULL, is_active BOOLEAN NOT NULL, is_superuser BOOLEAN NOT NULL, auth_epoch BIGINT NOT NULL)")
        db.exec_driver_sql(f"ALTER TABLE {qs}.users OWNER TO {qo}")
        db.exec_driver_sql(f"GRANT USAGE ON SCHEMA {qs} TO {qr}")
        db.exec_driver_sql(f"GRANT SELECT ON {qs}.marker TO {qr}")
        db.exec_driver_sql(f"GRANT SELECT ON {qs}.token_blacklist TO {qr}")
        db.exec_driver_sql(f"GRANT SELECT ON {qs}.users TO {qr}")
    try:
        yield engine, schema, owner, runtime, group, operator
    finally:
        engine.dispose()
        with engine.begin() as db:
            db.execute(DropSchema(schema, cascade=True, if_exists=True))
            for role in (runtime, operator, group, owner):
                db.exec_driver_sql(f"DROP OWNED BY {quote(role)}")
                db.exec_driver_sql(f"DROP ROLE IF EXISTS {quote(role)}")
        engine.dispose()


def _session_as(db, role):
    quote = db.get_bind().dialect.identifier_preparer.quote_identifier
    db.execute(sa.text(f"SET LOCAL SESSION AUTHORIZATION {quote(role)}"))


def _pin(db, schema, owner, runtime, members=()):
    return pin_application_schema(db, schema=schema, expected_owner=owner,
                                  expected_runtime_role=runtime, trusted_owner_members=members,
                                  expected_auth_owner=owner, trusted_auth_owner_members=members,
                                  expected_users_owner=owner, trusted_users_owner_members=members)


def test_actual_nonowner_login_with_force_rls_and_visible_jti(trusted_pg):
    engine, schema, owner, runtime, _, _ = trusted_pg
    quote = engine.dialect.identifier_preparer.quote_identifier
    table = f"{quote(schema)}.token_blacklist"
    with engine.begin() as db:
        db.exec_driver_sql(f"INSERT INTO {table} VALUES (1,'synthetic-revoked')")
        db.exec_driver_sql(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        db.exec_driver_sql(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        db.exec_driver_sql(f"CREATE POLICY synthetic_real_login ON {table} FOR SELECT TO {quote(runtime)} USING (true)")
    real_login = sa.create_engine(engine.url.set(username=runtime, password=engine._synthetic_runtime_password))
    try:
        with Session(real_login) as db:
            assert db.execute(sa.text("SELECT current_user,session_user")).one() == (runtime, runtime)
            _pin(db, schema, owner, runtime)
            assert db.execute(sa.text(f"SELECT count(*) FROM {table} WHERE jti='synthetic-revoked'")).scalar_one() == 1
    finally:
        real_login.dispose()


def test_runtime_pin_fences_temp_shadow_and_escapes_schema(trusted_pg):
    engine, schema, owner, runtime, _, _ = trusted_pg
    quote = engine.dialect.identifier_preparer.quote_identifier
    with engine.begin() as connection:
        connection.exec_driver_sql(f"CREATE FUNCTION {quote(schema)}.lower(text) RETURNS text LANGUAGE sql AS $$ SELECT 'shadow'::text $$")
    with Session(engine) as db:
        _session_as(db, runtime)
        db.execute(sa.text("CREATE TEMP TABLE marker(value TEXT NOT NULL)"))
        db.execute(sa.text("INSERT INTO pg_temp.marker VALUES ('shadow')"))
        assert db.execute(sa.text("SELECT value FROM marker")).scalar_one() == "shadow"
        _pin(db, schema, owner, runtime)
        assert db.execute(sa.text("SELECT value FROM marker")).scalar_one() == "trusted"
        assert db.execute(sa.text("SELECT lower('TRUSTED')")).scalar_one() == "trusted"
        path = db.execute(sa.text("SELECT pg_catalog.current_schemas(true)")).scalar_one()
        assert path[0:2] == ["pg_catalog", schema] and path[-1].startswith("pg_temp_")


@pytest.mark.parametrize("bad", ["schema", "owner", "runtime", "missing", "different_session"])
def test_wrong_trusted_anchor_or_session_fails_closed(trusted_pg, bad):
    engine, schema, owner, runtime, _, _ = trusted_pg
    with Session(engine) as db:
        if bad == "different_session":
            quote = db.get_bind().dialect.identifier_preparer.quote_identifier
            db.execute(sa.text(f"SET LOCAL ROLE {quote(runtime)}"))
        else:
            _session_as(db, runtime)
        arguments = {"schema": schema, "expected_owner": owner, "expected_runtime_role": runtime}
        if bad == "schema":
            arguments["schema"] = "untrusted_missing"
        elif bad == "owner":
            arguments["expected_owner"] = runtime
        elif bad == "runtime":
            arguments["expected_runtime_role"] = owner
        elif bad == "missing":
            arguments["schema"] = None
        with pytest.raises(TrustedSchemaUnavailable):
            pin_application_schema(db, **arguments)


def test_public_or_runtime_create_privilege_is_rejected(trusted_pg):
    engine, schema, owner, runtime, _, _ = trusted_pg
    quote = engine.dialect.identifier_preparer.quote_identifier
    with engine.begin() as db:
        db.exec_driver_sql(f"GRANT CREATE ON SCHEMA {quote(schema)} TO PUBLIC")
    try:
        with Session(engine) as db:
            _session_as(db, runtime)
            with pytest.raises(TrustedSchemaUnavailable):
                _pin(db, schema, owner, runtime)
    finally:
        with engine.begin() as db:
            db.exec_driver_sql(f"REVOKE CREATE ON SCHEMA {quote(schema)} FROM PUBLIC")


@pytest.mark.parametrize("direction", ["runtime_in_group", "group_in_runtime", "runtime_in_superuser"])
def test_runtime_role_memberships_are_rejected_in_both_directions(trusted_pg, direction):
    engine, schema, owner, runtime, group, _ = trusted_pg
    quote = engine.dialect.identifier_preparer.quote_identifier
    with engine.connect() as connection:
        transaction = connection.begin()
        try:
            administrator = connection.execute(sa.text("SELECT current_user")).scalar_one()
            if direction == "runtime_in_group":
                connection.exec_driver_sql(f"GRANT {quote(group)} TO {quote(runtime)}")
            elif direction == "group_in_runtime":
                connection.exec_driver_sql(f"GRANT {quote(runtime)} TO {quote(group)}")
            else:
                connection.exec_driver_sql(f"GRANT {quote(administrator)} TO {quote(runtime)}")
            with Session(bind=connection) as db:
                _session_as(db, runtime)
                with pytest.raises(TrustedSchemaUnavailable):
                    _pin(db, schema, owner, runtime)
        finally:
            transaction.rollback()


def test_owner_member_allowlist_checks_transitive_roles_and_runtime_exclusion(trusted_pg):
    engine, schema, owner, runtime, group, operator = trusted_pg
    quote = engine.dialect.identifier_preparer.quote_identifier
    with engine.begin() as db:
        db.exec_driver_sql(f"GRANT {quote(owner)} TO {quote(group)}")
        db.exec_driver_sql(f"GRANT {quote(group)} TO {quote(operator)}")
    try:
        with Session(engine) as db:
            _session_as(db, runtime)
            with pytest.raises(TrustedSchemaUnavailable):
                _pin(db, schema, owner, runtime, (group,))
            with pytest.raises(TrustedSchemaUnavailable):
                _pin(db, schema, owner, runtime, (group, operator, operator))
            _pin(db, schema, owner, runtime, (group, operator))
        with engine.begin() as db:
            db.exec_driver_sql(f"ALTER ROLE {quote(operator)} CREATEDB")
        try:
            with Session(engine) as db:
                _session_as(db, runtime)
                with pytest.raises(TrustedSchemaUnavailable):
                    _pin(db, schema, owner, runtime, (group, operator))
        finally:
            with engine.begin() as db:
                db.exec_driver_sql(f"ALTER ROLE {quote(operator)} NOCREATEDB")
        with engine.begin() as db:
            db.exec_driver_sql(f"GRANT {quote(owner)} TO {quote(runtime)}")
        with Session(engine) as db:
            _session_as(db, runtime)
            with pytest.raises(TrustedSchemaUnavailable):
                _pin(db, schema, owner, runtime, (group, operator, runtime))
    finally:
        with engine.begin() as db:
            db.exec_driver_sql(f"REVOKE {quote(owner)} FROM {quote(runtime)}")
            db.exec_driver_sql(f"REVOKE {quote(group)} FROM {quote(operator)}")
            db.exec_driver_sql(f"REVOKE {quote(owner)} FROM {quote(group)}")


def test_blacklist_force_rls_must_expose_every_jti(trusted_pg):
    engine, schema, owner, runtime, _, _ = trusted_pg
    quote = engine.dialect.identifier_preparer.quote_identifier
    table = f"{quote(schema)}.token_blacklist"
    with engine.begin() as db:
        db.exec_driver_sql(f"INSERT INTO {table} VALUES (1,'synthetic-revoked')")
        db.exec_driver_sql(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        db.exec_driver_sql(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        db.exec_driver_sql(f"CREATE POLICY synthetic_read ON {table} FOR SELECT TO {quote(runtime)} USING (false)")
    with Session(engine) as db:
        _session_as(db, runtime)
        assert db.execute(sa.text(f"SELECT count(*) FROM {table}")).scalar_one() == 0
        with pytest.raises(TrustedSchemaUnavailable):
            _pin(db, schema, owner, runtime)
    with engine.begin() as db:
        db.exec_driver_sql(f"ALTER POLICY synthetic_read ON {table} USING (true)")
    with Session(engine) as db:
        _session_as(db, runtime)
        _pin(db, schema, owner, runtime)
        assert db.execute(sa.text(f"SELECT count(*) FROM {table}")).scalar_one() == 1
    with engine.begin() as db:
        db.exec_driver_sql(f"CREATE POLICY synthetic_restrict ON {table} AS RESTRICTIVE FOR SELECT TO {quote(runtime)} USING (false)")
    with Session(engine) as db:
        _session_as(db, runtime)
        with pytest.raises(TrustedSchemaUnavailable):
            _pin(db, schema, owner, runtime)


@pytest.mark.parametrize("scope", ["table_public", "column_public", "unreviewed_role"])
def test_blacklist_public_column_or_unreviewed_select_is_rejected(trusted_pg, scope):
    engine, schema, owner, runtime, group, _ = trusted_pg
    quote = engine.dialect.identifier_preparer.quote_identifier
    table = f"{quote(schema)}.token_blacklist"
    with engine.begin() as db:
        if scope == "table_public":
            db.exec_driver_sql(f"GRANT SELECT ON {table} TO PUBLIC")
        elif scope == "column_public":
            db.exec_driver_sql(f"GRANT SELECT (jti) ON {table} TO PUBLIC")
        else:
            db.exec_driver_sql(f"GRANT SELECT ON {table} TO {quote(group)}")
    with Session(engine) as db:
        _session_as(db, runtime)
        with pytest.raises(TrustedSchemaUnavailable):
            _pin(db, schema, owner, runtime)
        if scope == "unreviewed_role":
            pin_application_schema(db, schema=schema, expected_owner=owner, expected_runtime_role=runtime,
                                   expected_auth_owner=owner, expected_users_owner=owner,
                                   trusted_auth_read_roles=(group,))


@pytest.mark.parametrize("table,column", [("token_blacklist", "jti"), ("users", "role")])
def test_auth_runtime_requires_full_table_select(trusted_pg, table, column):
    engine, schema, owner, runtime, _, _ = trusted_pg
    quote = engine.dialect.identifier_preparer.quote_identifier
    qualified = f"{quote(schema)}.{quote(table)}"
    with engine.begin() as db:
        db.exec_driver_sql(f"REVOKE SELECT ON {qualified} FROM {quote(runtime)}")
        db.exec_driver_sql(f"GRANT SELECT ({quote(column)}) ON {qualified} TO {quote(runtime)}")
    with Session(engine) as db:
        _session_as(db, runtime)
        with pytest.raises(TrustedSchemaUnavailable):
            _pin(db, schema, owner, runtime)


def test_blacklist_reader_membership_must_be_explicit(trusted_pg):
    engine, schema, owner, runtime, group, operator = trusted_pg
    quote = engine.dialect.identifier_preparer.quote_identifier
    table = f"{quote(schema)}.token_blacklist"
    with engine.begin() as db:
        db.exec_driver_sql(f"GRANT SELECT ON {table} TO {quote(group)}")
        db.exec_driver_sql(f"GRANT {quote(group)} TO {quote(operator)}")
    try:
        with Session(engine) as db:
            _session_as(db, runtime)
            with pytest.raises(TrustedSchemaUnavailable):
                pin_application_schema(db, schema=schema, expected_owner=owner, expected_runtime_role=runtime,
                                       expected_auth_owner=owner, expected_users_owner=owner,
                                       trusted_auth_read_roles=(group,))
            pin_application_schema(db, schema=schema, expected_owner=owner, expected_runtime_role=runtime,
                                   expected_auth_owner=owner, expected_users_owner=owner,
                                   trusted_auth_read_roles=(group, operator))
    finally:
        with engine.begin() as db:
            db.exec_driver_sql(f"REVOKE {quote(group)} FROM {quote(operator)}")


@pytest.mark.parametrize("grant", ["DELETE", "TRUNCATE", "TRIGGER", "UPDATE (jti)", "INSERT (jti)"])
def test_blacklist_unreviewed_mutation_grants_are_rejected(trusted_pg, grant):
    engine, schema, owner, runtime, group, _ = trusted_pg
    quote = engine.dialect.identifier_preparer.quote_identifier
    table = f"{quote(schema)}.token_blacklist"
    with engine.begin() as db:
        db.exec_driver_sql(f"GRANT {grant} ON {table} TO {quote(group)}")
    with Session(engine) as db:
        _session_as(db, runtime)
        with pytest.raises(TrustedSchemaUnavailable):
            _pin(db, schema, owner, runtime)
        pin_application_schema(db, schema=schema, expected_owner=owner, expected_runtime_role=runtime,
                               expected_auth_owner=owner, expected_users_owner=owner,
                               trusted_auth_write_roles=(group,))


def test_blacklist_grant_option_is_rejected_even_for_reviewed_reader(trusted_pg):
    engine, schema, owner, runtime, group, _ = trusted_pg
    quote = engine.dialect.identifier_preparer.quote_identifier
    with engine.begin() as db:
        db.exec_driver_sql(f"GRANT SELECT ON {quote(schema)}.token_blacklist TO {quote(group)} WITH GRANT OPTION")
    with Session(engine) as db:
        _session_as(db, runtime)
        with pytest.raises(TrustedSchemaUnavailable):
            pin_application_schema(db, schema=schema, expected_owner=owner, expected_runtime_role=runtime,
                                   expected_auth_owner=owner, expected_users_owner=owner,
                                   trusted_auth_read_roles=(group,))


@pytest.mark.parametrize("table,privilege", [("users", "UPDATE (role)"), ("token_blacklist", "DELETE")])
def test_public_auth_table_mutation_is_rejected(trusted_pg, table, privilege):
    engine, schema, owner, runtime, _, _ = trusted_pg
    quote = engine.dialect.identifier_preparer.quote_identifier
    with engine.begin() as db:
        db.exec_driver_sql(f"GRANT {privilege} ON {quote(schema)}.{quote(table)} TO PUBLIC")
    with Session(engine) as db:
        _session_as(db, runtime)
        with pytest.raises(TrustedSchemaUnavailable):
            _pin(db, schema, owner, runtime)


@pytest.mark.parametrize("grant", ["UPDATE (role)", "UPDATE (is_active)", "UPDATE (is_superuser)",
                                    "UPDATE (auth_epoch)", "UPDATE (id)", "INSERT (role)",
                                    "DELETE", "TRUNCATE", "TRIGGER", "REFERENCES"])
def test_users_unreviewed_security_mutation_grants_are_rejected(trusted_pg, grant):
    engine, schema, owner, runtime, group, _ = trusted_pg
    quote = engine.dialect.identifier_preparer.quote_identifier
    table = f"{quote(schema)}.users"
    with engine.begin() as db:
        db.exec_driver_sql(f"GRANT {grant} ON {table} TO {quote(group)}")
    with Session(engine) as db:
        _session_as(db, runtime)
        with pytest.raises(TrustedSchemaUnavailable):
            _pin(db, schema, owner, runtime)
        pin_application_schema(db, schema=schema, expected_owner=owner, expected_runtime_role=runtime,
                               expected_auth_owner=owner, expected_users_owner=owner,
                               trusted_users_write_roles=(group,))


def test_users_selective_rls_is_allowed_because_missing_actor_fails_closed(trusted_pg):
    engine, schema, owner, runtime, _, _ = trusted_pg
    quote = engine.dialect.identifier_preparer.quote_identifier
    table = f"{quote(schema)}.users"
    with engine.begin() as db:
        db.exec_driver_sql(f"INSERT INTO {table} VALUES (1,'doctor',true,false,0)")
        db.exec_driver_sql(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        db.exec_driver_sql(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        db.exec_driver_sql(f"CREATE POLICY synthetic_users ON {table} FOR SELECT TO {quote(runtime)} USING (false)")
    with Session(engine) as db:
        _session_as(db, runtime)
        _pin(db, schema, owner, runtime)
        assert db.execute(sa.text(f"SELECT count(*) FROM {table}")).scalar_one() == 0


def test_users_writer_inherited_members_require_explicit_review(trusted_pg):
    engine, schema, owner, runtime, group, operator = trusted_pg
    quote = engine.dialect.identifier_preparer.quote_identifier
    table = f"{quote(schema)}.users"
    with engine.begin() as db:
        db.exec_driver_sql(f"GRANT UPDATE (role) ON {table} TO {quote(group)}")
        db.exec_driver_sql(f"GRANT {quote(group)} TO {quote(operator)}")
    try:
        with Session(engine) as db:
            _session_as(db, runtime)
            with pytest.raises(TrustedSchemaUnavailable):
                pin_application_schema(db, schema=schema, expected_owner=owner, expected_runtime_role=runtime,
                                       expected_auth_owner=owner, expected_users_owner=owner,
                                       trusted_users_write_roles=(group,))
            pin_application_schema(db, schema=schema, expected_owner=owner, expected_runtime_role=runtime,
                                   expected_auth_owner=owner, expected_users_owner=owner,
                                   trusted_users_write_roles=(group, operator))
    finally:
        with engine.begin() as db:
            db.exec_driver_sql(f"REVOKE {quote(group)} FROM {quote(operator)}")


def test_users_owner_is_independently_configured(trusted_pg):
    engine, schema, owner, runtime, group, _ = trusted_pg
    quote = engine.dialect.identifier_preparer.quote_identifier
    with engine.begin() as db:
        db.exec_driver_sql(f"ALTER TABLE {quote(schema)}.users OWNER TO {quote(group)}")
    with Session(engine) as db:
        _session_as(db, runtime)
        with pytest.raises(TrustedSchemaUnavailable):
            _pin(db, schema, owner, runtime)
        pin_application_schema(db, schema=schema, expected_owner=owner, expected_runtime_role=runtime,
                               expected_auth_owner=owner, expected_users_owner=group)


def test_users_owner_ddl_waits_for_authenticated_transaction(trusted_pg):
    engine, schema, owner, runtime, group, _ = trusted_pg
    quote = engine.dialect.identifier_preparer.quote_identifier
    table = f"{quote(schema)}.users"
    statement = f"ALTER TABLE {table} OWNER TO {quote(group)}"
    with Session(engine) as db:
        _session_as(db, runtime)
        _pin(db, schema, owner, runtime)

        def competing_ddl():
            with engine.begin() as connection:
                connection.exec_driver_sql("SET LOCAL lock_timeout='250ms'")
                with pytest.raises(sa.exc.DBAPIError) as failure:
                    connection.exec_driver_sql(statement)
                return getattr(failure.value.orig, "sqlstate", None)

        with ThreadPoolExecutor(max_workers=1) as executor:
            assert executor.submit(competing_ddl).result(timeout=10) == "55P03"
        db.rollback()
    with engine.begin() as connection:
        connection.exec_driver_sql(statement)


def test_worker_can_verify_auth_visibility_while_holding_user_lock(trusted_pg):
    engine, schema, owner, runtime, _, _ = trusted_pg
    quote = engine.dialect.identifier_preparer.quote_identifier
    users = f"{quote(schema)}.users"
    with engine.begin() as db:
        db.exec_driver_sql(f"INSERT INTO {users} VALUES (1,'doctor',true,false,0)")
        db.exec_driver_sql(f"GRANT UPDATE ON {users} TO {quote(runtime)}")
    with Session(engine) as db:
        _session_as(db, runtime)
        assert db.execute(sa.text(f"SELECT id FROM {users} WHERE id=1 FOR UPDATE")).scalar_one() == 1
        _pin(db, schema, owner, runtime)
        assert db.execute(sa.text(f"SELECT auth_epoch FROM {users} WHERE id=1")).scalar_one() == 0


def test_visibility_locks_do_not_block_normal_logout_writes(trusted_pg):
    engine, schema, owner, runtime, _, _ = trusted_pg
    quote = engine.dialect.identifier_preparer.quote_identifier
    table = f"{quote(schema)}.token_blacklist"
    with Session(engine) as db:
        _session_as(db, runtime)
        _pin(db, schema, owner, runtime)

        def logout_write():
            with engine.begin() as connection:
                connection.exec_driver_sql("SET LOCAL lock_timeout='250ms'")
                connection.exec_driver_sql(f"INSERT INTO {table} VALUES (99,'synthetic-logout')")

        with ThreadPoolExecutor(max_workers=1) as executor:
            executor.submit(logout_write).result(timeout=10)
        db.rollback()
    with engine.begin() as connection:
        assert connection.exec_driver_sql(f"SELECT count(*) FROM {table} WHERE id=99").scalar_one() == 1


def test_blacklist_can_have_independently_trusted_owner(trusted_pg):
    engine, schema, owner, runtime, group, _ = trusted_pg
    quote = engine.dialect.identifier_preparer.quote_identifier
    table = f"{quote(schema)}.token_blacklist"
    with engine.begin() as db:
        db.exec_driver_sql(f"ALTER TABLE {table} OWNER TO {quote(group)}")
    with Session(engine) as db:
        _session_as(db, runtime)
        with pytest.raises(TrustedSchemaUnavailable):
            _pin(db, schema, owner, runtime)
        pin_application_schema(db, schema=schema, expected_owner=owner,
                               expected_runtime_role=runtime, expected_auth_owner=group, expected_users_owner=owner)


@pytest.mark.parametrize("ddl", ["enable_rls", "alter_policy", "change_owner"])
def test_blacklist_policy_ddl_waits_until_auth_transaction_ends(trusted_pg, ddl):
    engine, schema, owner, runtime, group, _ = trusted_pg
    quote = engine.dialect.identifier_preparer.quote_identifier
    table = f"{quote(schema)}.token_blacklist"
    if ddl == "alter_policy":
        with engine.begin() as connection:
            connection.exec_driver_sql(f"CREATE POLICY synthetic_ddl ON {table} FOR SELECT TO {quote(runtime)} USING (true)")
    statement = {"enable_rls": f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY",
                 "alter_policy": f"ALTER POLICY synthetic_ddl ON {table} USING (false)",
                 "change_owner": f"ALTER TABLE {table} OWNER TO {quote(group)}"}[ddl]
    with Session(engine) as db:
        _session_as(db, runtime)
        _pin(db, schema, owner, runtime)

        def competing_ddl():
            with engine.begin() as connection:
                connection.exec_driver_sql("SET LOCAL lock_timeout='250ms'")
                with pytest.raises(sa.exc.DBAPIError) as failure:
                    connection.exec_driver_sql(statement)
                return getattr(failure.value.orig, "sqlstate", None)

        with ThreadPoolExecutor(max_workers=1) as executor:
            assert executor.submit(competing_ddl).result(timeout=10) == "55P03"
        db.rollback()
    with engine.begin() as connection:
        connection.exec_driver_sql(statement)


def test_public_tables_and_data_not_read_before_pin(trusted_pg):
    engine, schema, owner, runtime, _, _ = trusted_pg
    observed = []

    @sa.event.listens_for(engine, "before_cursor_execute")
    def record(_conn, _cursor, statement, _parameters, _context, _many):
        observed.append(statement)

    try:
        with Session(engine) as db:
            _session_as(db, runtime)
            _pin(db, schema, owner, runtime)
            assert db.execute(sa.text("SELECT value FROM marker")).scalar_one() == "trusted"
        first_public_read = next(index for index, statement in enumerate(observed) if "SELECT value FROM marker" in statement)
        assert any("set_config('search_path'" in statement for statement in observed[:first_public_read])
    finally:
        sa.event.remove(engine, "before_cursor_execute", record)
