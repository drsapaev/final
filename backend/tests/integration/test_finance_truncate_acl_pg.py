"""Exercise the finance ACL migration in an isolated PostgreSQL schema."""

from dataclasses import dataclass, replace
from os import getenv
from types import ModuleType
from uuid import uuid4

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine, make_url
from tests._pg_admin_guard import is_local_admin_dsn
from tests.integration.test_encounter_migration_pg import _migration

_REQUIRED_FINANCIAL_TABLES = {
    "click_callback_receipts",
    "encounter_benefit_events",
    "finance_transactions",
    "invoice_items",
    "loyalty_point_transactions",
    "payment_client_requests",
    "payment_refund_claims",
    "payment_visits",
    "provider_reconciliation_events",
    "service_audit_logs",
}


@dataclass(frozen=True)
class FinanceScope:
    engine: Engine
    migration: ModuleType
    schema: str
    gateway: str
    maintainer: str
    inherited: str

    def qualified(self, table):
        preparer = self.engine.dialect.identifier_preparer
        return (
            f"{preparer.quote_schema(self.schema)}.{preparer.quote_identifier(table)}"
        )


@pytest.fixture
def finance_scope(monkeypatch):
    raw = getenv("DATABASE_URL", "")
    if not is_local_admin_dsn(raw):
        pytest.skip("requires a disposable local PostgreSQL database")
    url = make_url(raw)
    if not (url.database or "").startswith("clinic_test"):
        pytest.skip("requires a disposable clinic_test database")
    engine = create_engine(url, hide_parameters=True)
    prefix = uuid4().hex[:16]
    schema = f"Finance ACL {prefix}"
    gateway = f"synthetic_gateway_{prefix}"
    maintainer = f"synthetic_maintainer_{prefix}"
    inherited = f"synthetic_inherited_{prefix}"
    migration = _migration("0154_finance_truncate_acl.py")
    monkeypatch.setattr(migration, "_GATEWAY_ROLES", (gateway,))
    scope = FinanceScope(engine, migration, schema, gateway, maintainer, inherited)
    quoted_schema = engine.dialect.identifier_preparer.quote_schema(schema)
    tables = (*migration._RELATIONS, "unrelated_inventory")
    try:
        with engine.begin() as connection:
            assert connection.scalar(text("SELECT current_database()")) == url.database
            connection.exec_driver_sql(f"CREATE SCHEMA {quoted_schema}")
            for role in (gateway, maintainer, inherited):
                connection.exec_driver_sql(f"CREATE ROLE {role} NOLOGIN INHERIT")
            connection.exec_driver_sql(
                f"GRANT USAGE ON SCHEMA {quoted_schema} TO {gateway}, {maintainer}"
            )
            for name in tables:
                connection.exec_driver_sql(
                    f"CREATE TABLE {scope.qualified(name)} (id integer)"
                )
            connection.exec_driver_sql(
                f"GRANT SELECT, INSERT, TRUNCATE ON ALL TABLES IN SCHEMA {quoted_schema} TO {gateway}, {maintainer}"
            )
            payment = scope.qualified("payments")
            connection.exec_driver_sql(f"GRANT TRUNCATE ON TABLE {payment} TO PUBLIC")
            connection.exec_driver_sql(
                f"ALTER TABLE {payment} ENABLE ROW LEVEL SECURITY"
            )
            connection.exec_driver_sql(
                f"CREATE POLICY synthetic_create_payment ON {payment} FOR INSERT TO {maintainer} WITH CHECK (true)"
            )
        try:
            yield scope
        finally:
            with engine.begin() as connection:
                connection.exec_driver_sql(f"DROP SCHEMA {quoted_schema} CASCADE")
                for role in (gateway, maintainer, inherited):
                    connection.exec_driver_sql(f"DROP ROLE {role}")
    finally:
        engine.dispose()


def _migrate(scope, connection, *, downgrade=False):
    context = MigrationContext.configure(
        connection, opts={"version_table_schema": scope.schema}
    )
    with Operations.context(context):
        if downgrade:
            scope.migration.downgrade()
        else:
            scope.migration.upgrade()


def _has(connection, scope, role, relation, privilege):
    return connection.scalar(
        text("""
        SELECT pg_catalog.has_table_privilege(:role, :relation, :privilege)
    """),
        {"role": role, "relation": scope.qualified(relation), "privilege": privilege},
    )


def _public_truncate(connection, scope):
    return connection.scalar(
        text("""
        SELECT EXISTS (
            SELECT 1
            FROM pg_catalog.pg_class c
            CROSS JOIN LATERAL pg_catalog.aclexplode(
                COALESCE(c.relacl, pg_catalog.acldefault('r', c.relowner))
            ) a
            WHERE c.oid = CAST(:relation AS regclass) AND a.grantee=0 AND a.privilege_type='TRUNCATE'
        )
    """),
        {"relation": scope.qualified("payments")},
    )


def test_revokes_only_truncate_for_gateway_and_public(finance_scope):
    scope = finance_scope
    assert _REQUIRED_FINANCIAL_TABLES.issubset(scope.migration._RELATIONS)
    with scope.engine.begin() as connection:
        assert _public_truncate(connection, scope)
        assert _has(connection, scope, scope.gateway, "payments", "TRUNCATE")
        _migrate(scope, connection)
        assert not _public_truncate(connection, scope)
        for relation in scope.migration._RELATIONS:
            assert not _has(connection, scope, scope.gateway, relation, "TRUNCATE")
            assert _has(connection, scope, scope.gateway, relation, "SELECT")
            assert _has(connection, scope, scope.gateway, relation, "INSERT")
            assert _has(connection, scope, scope.maintainer, relation, "TRUNCATE")
        assert _has(connection, scope, scope.gateway, "unrelated_inventory", "TRUNCATE")
        assert connection.scalar(
            text(
                "SELECT relrowsecurity FROM pg_class WHERE oid=CAST(:relation AS regclass)"
            ),
            {"relation": scope.qualified("payments")},
        )
        connection.exec_driver_sql(f"SET LOCAL ROLE {scope.maintainer}")
        connection.exec_driver_sql(
            f"INSERT INTO {scope.qualified('payments')} (id) VALUES (1)"
        )
    with scope.engine.begin() as connection:
        assert (
            connection.scalar(
                text(f"SELECT count(*) FROM {scope.qualified('payments')}")
            )
            == 1
        )
        _migrate(scope, connection, downgrade=True)
        assert not _has(connection, scope, scope.gateway, "payments", "TRUNCATE")
        _migrate(scope, connection)
        assert not _public_truncate(connection, scope)


def test_inherited_truncate_prevents_partial_revocation(finance_scope):
    scope = finance_scope
    with scope.engine.begin() as connection:
        connection.exec_driver_sql(f"GRANT {scope.inherited} TO {scope.gateway}")
        connection.exec_driver_sql(
            f"GRANT TRUNCATE ON {scope.qualified('payments')} TO {scope.inherited}"
        )
    with (
        pytest.raises(RuntimeError, match="Remaining financial TRUNCATE privileges"),
        scope.engine.begin() as connection,
    ):
        _migrate(scope, connection)
    with scope.engine.begin() as connection:
        assert _public_truncate(connection, scope)
        assert _has(connection, scope, scope.gateway, "refund_requests", "TRUNCATE")
        connection.exec_driver_sql(f"REVOKE {scope.inherited} FROM {scope.gateway}")
        _migrate(scope, connection)
        assert not _has(connection, scope, scope.gateway, "payments", "TRUNCATE")


def test_applies_public_boundary_when_gateway_roles_are_absent(
    finance_scope, monkeypatch
):
    scope = finance_scope
    monkeypatch.setattr(scope.migration, "_GATEWAY_ROLES", (f"missing_{uuid4().hex}",))
    with scope.engine.begin() as connection:
        _migrate(scope, connection)
        assert not _public_truncate(connection, scope)
        assert _has(connection, scope, scope.gateway, "payments", "TRUNCATE")


@pytest.mark.parametrize("owner", [False, True], ids=["granted-truncate", "ownership"])
def test_activatable_role_prevents_partial_revocation(finance_scope, owner):
    scope = finance_scope
    target = scope.qualified("payment_visits")
    with scope.engine.begin() as connection:
        if connection.dialect.server_version_info < (16,):
            pytest.skip("requires PostgreSQL 16 membership options")
        connection.exec_driver_sql(f"REVOKE TRUNCATE ON {target} FROM {scope.gateway}")
        if owner:
            connection.exec_driver_sql(
                f"ALTER TABLE {target} OWNER TO {scope.inherited}"
            )
            connection.exec_driver_sql(
                f"REVOKE TRUNCATE ON {target} FROM {scope.inherited}"
            )
        else:
            connection.exec_driver_sql(
                f"GRANT TRUNCATE ON {target} TO {scope.inherited}"
            )
        connection.exec_driver_sql(
            f"GRANT {scope.inherited} TO {scope.gateway} WITH INHERIT FALSE, SET TRUE"
        )
        assert not _has(connection, scope, scope.gateway, "payment_visits", "TRUNCATE")
        assert _has(
            connection, scope, scope.inherited, "payment_visits", "TRUNCATE"
        ) is (not owner)

    with (
        pytest.raises(RuntimeError, match="Remaining financial TRUNCATE privileges"),
        scope.engine.begin() as connection,
    ):
        _migrate(scope, connection)

    with scope.engine.begin() as connection:
        assert _public_truncate(connection, scope)
        assert _has(connection, scope, scope.gateway, "refund_requests", "TRUNCATE")
        connection.exec_driver_sql(
            f"GRANT {scope.inherited} TO {scope.gateway} WITH SET FALSE"
        )
        _migrate(scope, connection)
        assert not _has(connection, scope, scope.gateway, "payment_visits", "TRUNCATE")


@pytest.fixture(params=[
    "0155_finance_trigger_acl.py",
    "0158_finance_internal_exec_acl.py",
], ids=["0155", "0158"])
def finance_trigger_scope(finance_scope, monkeypatch, request):
    migration = _migration(request.param)
    scope = replace(finance_scope, migration=migration)
    monkeypatch.setattr(migration, "_GATEWAY_ROLES", (scope.gateway,))
    schema = scope.engine.dialect.identifier_preparer.quote_schema(scope.schema)

    with scope.engine.begin() as connection:
        connection.exec_driver_sql(
            f"ALTER DEFAULT PRIVILEGES IN SCHEMA {schema} "
            f"GRANT EXECUTE ON FUNCTIONS TO {scope.gateway}"
        )
        for name in migration._ROUTINES:
            function = scope.qualified(name)
            connection.exec_driver_sql(f"""
                CREATE FUNCTION {function}() RETURNS trigger
                LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog
                AS $$ BEGIN NEW.id := NEW.id + 1; RETURN NEW; END; $$
            """)
            connection.exec_driver_sql(
                f"REVOKE EXECUTE ON FUNCTION {function}() FROM PUBLIC"
            )
            connection.exec_driver_sql(
                f"GRANT EXECUTE ON FUNCTION {function}() TO {scope.maintainer}"
            )
        unrelated = scope.qualified("unrelated_routine")
        connection.exec_driver_sql(
            f"CREATE FUNCTION {unrelated}() RETURNS integer LANGUAGE sql AS 'SELECT 1'"
        )
        table = scope.qualified("unrelated_inventory")
        function = scope.qualified(migration._ROUTINES[0])
        connection.exec_driver_sql(
            f"CREATE TRIGGER synthetic_record BEFORE INSERT ON {table} "
            f"FOR EACH ROW EXECUTE FUNCTION {function}()"
        )

    return scope


def _can_execute(connection, scope, role, name):
    return connection.scalar(
        text("SELECT pg_catalog.has_function_privilege(:role, :routine, 'EXECUTE')"),
        {"role": role, "routine": f"{scope.qualified(name)}()"},
    )


def test_finance_trigger_revoke_preserves_trigger_writes_and_other_grants(finance_trigger_scope):
    scope = finance_trigger_scope
    with scope.engine.begin() as connection:
        for name in scope.migration._ROUTINES:
            assert _can_execute(connection, scope, scope.gateway, name)

        _migrate(scope, connection)

        for name in scope.migration._ROUTINES:
            assert not _can_execute(connection, scope, scope.gateway, name)
            assert _can_execute(connection, scope, scope.maintainer, name)
        assert _can_execute(connection, scope, scope.gateway, "unrelated_routine")

        table = scope.qualified("unrelated_inventory")
        connection.exec_driver_sql(f"SET LOCAL ROLE {scope.gateway}")
        assert connection.exec_driver_sql(
            f"INSERT INTO {table} (id) VALUES (7) RETURNING id"
        ).scalar_one() == 8


def test_finance_trigger_revoke_rolls_back_if_gateway_can_assume_executable_role(finance_trigger_scope):
    scope = finance_trigger_scope
    name = scope.migration._ROUTINES[0]
    function = scope.qualified(name)
    with scope.engine.begin() as connection:
        connection.exec_driver_sql(f"ALTER ROLE {scope.gateway} NOINHERIT")
        connection.exec_driver_sql(
            f"GRANT EXECUTE ON FUNCTION {function}() TO {scope.inherited}"
        )
        membership_options = (
            " WITH INHERIT FALSE, SET TRUE" if connection.dialect.server_version_info >= (16,) else ""
        )
        connection.exec_driver_sql(
            f"GRANT {scope.inherited} TO {scope.gateway}{membership_options}"
        )

        with pytest.raises(RuntimeError, match="Remaining financial trigger EXECUTE"):
            with connection.begin_nested():
                _migrate(scope, connection)

        assert _can_execute(connection, scope, scope.gateway, name)
        assert _can_execute(connection, scope, scope.inherited, name)


_FINANCE_LEDGER_TEST_TABLES = (
    "user_audit_logs", "provider_attempts", "provider_attempt_visits",
    "provider_active_visit_reservations",
)


@pytest.fixture
def finance_metadata_scope(finance_scope, monkeypatch):
    migration = _migration("0159_finance_metadata_acl.py")
    scope = replace(finance_scope, migration=migration)
    monkeypatch.setattr(migration, "_GATEWAY_ROLES", (scope.gateway,))
    audit = scope.qualified("user_audit_logs")
    version = scope.qualified("alembic_version")
    registry = scope.qualified("kaspi_issued_payment_refs")
    ledgers = [scope.qualified(name) for name in _FINANCE_LEDGER_TEST_TABLES]
    with scope.engine.begin() as connection:
        for table in (*ledgers, registry):
            connection.exec_driver_sql(f"CREATE TABLE {table} (id integer)")
        connection.exec_driver_sql(
            f"CREATE TABLE {version} (version_num varchar(32) PRIMARY KEY)"
        )
        connection.exec_driver_sql(f"ALTER TABLE {audit} ENABLE ROW LEVEL SECURITY")
        connection.exec_driver_sql(
            f"CREATE POLICY synthetic_audit_append ON {audit} "
            f"FOR INSERT TO {scope.maintainer} WITH CHECK (true)"
        )
        tables = ", ".join((*ledgers, version, registry))
        connection.exec_driver_sql(
            f"GRANT ALL PRIVILEGES ON TABLE {tables} TO {scope.gateway}, {scope.maintainer}"
        )
        connection.exec_driver_sql(f"GRANT SELECT ON TABLE {registry} TO PUBLIC")
        connection.exec_driver_sql(f"GRANT TRUNCATE, TRIGGER ON TABLE {audit} TO PUBLIC")
        connection.exec_driver_sql(
            f"GRANT INSERT, UPDATE, DELETE, TRUNCATE, REFERENCES ON TABLE {version} TO PUBLIC"
        )
    return scope


def test_metadata_acl_keeps_audit_appends_and_version_reads(finance_metadata_scope):
    scope = finance_metadata_scope
    table_admin = ("TRUNCATE", "REFERENCES", "TRIGGER")
    if scope.engine.dialect.server_version_info >= (17,):
        table_admin += ("MAINTAIN",)
    version_writes = (*table_admin, "INSERT", "UPDATE", "DELETE")
    with scope.engine.begin() as connection:
        assert _has(connection, scope, scope.gateway, "user_audit_logs", "TRUNCATE")
        assert _has(connection, scope, scope.gateway, "alembic_version", "UPDATE")

        _migrate(scope, connection)
        _migrate(scope, connection, downgrade=True)
        _migrate(scope, connection)

        for role in (scope.gateway, scope.inherited):
            for table in _FINANCE_LEDGER_TEST_TABLES:
                for privilege in table_admin:
                    assert not _has(connection, scope, role, table, privilege)
            for privilege in version_writes:
                assert not _has(connection, scope, role, "alembic_version", privilege)
            for privilege in ("SELECT", *version_writes):
                assert not _has(connection, scope, role, "kaspi_issued_payment_refs", privilege)

        for table in _FINANCE_LEDGER_TEST_TABLES:
            for privilege in ("SELECT", "INSERT", "UPDATE", "DELETE"):
                assert _has(connection, scope, scope.gateway, table, privilege)
        assert _has(connection, scope, scope.maintainer, "kaspi_issued_payment_refs", "INSERT")
        assert _has(connection, scope, scope.gateway, "alembic_version", "SELECT")
        assert _has(connection, scope, scope.gateway, "unrelated_inventory", "TRUNCATE")
        for privilege in version_writes:
            assert _has(connection, scope, scope.maintainer, "alembic_version", privilege)

        connection.exec_driver_sql(f"SET LOCAL ROLE {scope.maintainer}")
        connection.exec_driver_sql(
            f"INSERT INTO {scope.qualified('user_audit_logs')} (id) VALUES (1)"
        )
        connection.exec_driver_sql(
            f"INSERT INTO {scope.qualified('alembic_version')} (version_num) "
            "VALUES ('synthetic_revision')"
        )


def test_metadata_acl_rejects_reachable_column_write(finance_metadata_scope):
    scope = finance_metadata_scope
    version = scope.qualified("alembic_version")
    with scope.engine.begin() as connection:
        connection.exec_driver_sql(
            f"GRANT UPDATE (version_num) ON TABLE {version} TO {scope.inherited}"
        )
        membership_options = (
            "WITH INHERIT FALSE, SET TRUE"
            if connection.dialect.server_version_info >= (16,)
            else ""
        )
        connection.exec_driver_sql(
            f"GRANT {scope.inherited} TO {scope.gateway} {membership_options}"
        )
    with pytest.raises(RuntimeError, match="Remaining finance metadata write privileges"):
        with scope.engine.begin() as connection:
            _migrate(scope, connection)
    with scope.engine.connect() as connection:
        assert _has(connection, scope, scope.gateway, "user_audit_logs", "TRUNCATE")
        assert _has(connection, scope, scope.gateway, "alembic_version", "UPDATE")
