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
from sqlalchemy.exc import IntegrityError
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


@pytest.fixture
def service_catalog_audit_scope(finance_scope, monkeypatch):
    migration = _migration("0160_service_catalog_audit_acl.py")
    scope = replace(finance_scope, migration=migration)
    monkeypatch.setattr(migration, "_GATEWAY_ROLES", (scope.gateway,))
    catalog = scope.qualified("services")
    audit = scope.qualified("service_audit_logs")
    with scope.engine.begin() as connection:
        connection.exec_driver_sql(
            f"CREATE TABLE {catalog} (id integer PRIMARY KEY, price integer, active boolean)"
        )
        connection.exec_driver_sql(
            f"ALTER TABLE {audit} ADD COLUMN service_id integer REFERENCES "
            f"{catalog} (id) ON DELETE CASCADE, ADD COLUMN action text"
        )
        connection.exec_driver_sql(f"INSERT INTO {catalog} VALUES (1, 200, true)")
        connection.exec_driver_sql(
            f"INSERT INTO {audit} (id, service_id, action) VALUES (1, 1, 'create')"
        )
        connection.exec_driver_sql(
            f"GRANT ALL PRIVILEGES ON TABLE {catalog}, {audit} "
            f"TO {scope.gateway}, {scope.maintainer}"
        )
        connection.exec_driver_sql(
            f"GRANT DELETE, TRUNCATE, TRIGGER ON TABLE {catalog}, {audit} TO PUBLIC"
        )
        connection.exec_driver_sql(f"GRANT UPDATE ON TABLE {audit} TO PUBLIC")
        connection.exec_driver_sql(f"GRANT UPDATE (action) ON TABLE {audit} TO PUBLIC")
        for table in (catalog, audit):
            connection.exec_driver_sql(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
            connection.exec_driver_sql(
                f"CREATE POLICY synthetic_writer ON {table} TO {scope.gateway} "
                "USING (true) WITH CHECK (true)"
            )
    return scope


def test_service_audit_acl_preserves_catalogue_writer_and_audit_history(
    service_catalog_audit_scope,
):
    scope = service_catalog_audit_scope
    catalog = scope.qualified("services")
    audit = scope.qualified("service_audit_logs")
    denied = {
        "services": ("DELETE", "TRUNCATE", "TRIGGER"),
        "service_audit_logs": ("UPDATE", "DELETE", "TRUNCATE", "TRIGGER"),
    }
    with scope.engine.begin() as connection:
        for table, privileges in denied.items():
            for privilege in privileges:
                assert _has(connection, scope, scope.inherited, table, privilege)

        _migrate(scope, connection)
        _migrate(scope, connection, downgrade=True)
        _migrate(scope, connection)

        for table, privileges in denied.items():
            for privilege in privileges:
                assert not _has(connection, scope, scope.gateway, table, privilege)
                assert not _has(connection, scope, scope.inherited, table, privilege)
                assert _has(connection, scope, scope.maintainer, table, privilege)
            assert connection.scalar(
                text("""
                    SELECT relrowsecurity FROM pg_catalog.pg_class
                    WHERE oid = CAST(:relation AS regclass)
                """),
                {"relation": scope.qualified(table)},
            )
        for role in (scope.gateway, scope.inherited):
            assert not connection.scalar(
                text("""
                    SELECT pg_catalog.has_any_column_privilege(
                        :role, :relation, 'UPDATE'
                    )
                """),
                {"role": role, "relation": audit},
            )
        assert _has(connection, scope, scope.gateway, "services", "INSERT")
        assert _has(connection, scope, scope.gateway, "unrelated_inventory", "TRUNCATE")
        connection.exec_driver_sql(f"SET LOCAL ROLE {scope.gateway}")
        connection.exec_driver_sql(
            f"UPDATE {catalog} SET price = 150, active = false WHERE id = 1"
        )
        connection.exec_driver_sql(
            f"INSERT INTO {audit} (id, service_id, action) VALUES (2, 1, 'deactivate')"
        )
        assert connection.exec_driver_sql(
            f"SELECT s.price, s.active, a.action FROM {catalog} AS s "
            f"JOIN {audit} AS a ON a.service_id = s.id ORDER BY a.id"
        ).all() == [(150, False, "create"), (150, False, "deactivate")]


@pytest.mark.parametrize("remaining_grant", ["DELETE", "UPDATE (action)"])
def test_service_audit_acl_rolls_back_on_remaining_write_privileges(
    service_catalog_audit_scope,
    remaining_grant,
):
    scope = service_catalog_audit_scope
    catalog = scope.qualified("services")
    audit = scope.qualified("service_audit_logs")
    with scope.engine.begin() as connection:
        target = catalog if remaining_grant == "DELETE" else audit
        connection.exec_driver_sql(
            f"GRANT {remaining_grant} ON TABLE {target} TO {scope.inherited}"
        )
        membership_options = (
            "WITH INHERIT FALSE, SET TRUE"
            if connection.dialect.server_version_info >= (16,)
            else ""
        )
        connection.exec_driver_sql(
            f"GRANT {scope.inherited} TO {scope.gateway} {membership_options}"
        )

    with (
        pytest.raises(RuntimeError, match="Remaining service audit write privileges"),
        scope.engine.begin() as connection,
    ):
        _migrate(scope, connection)

    with scope.engine.connect() as connection:
        assert _has(connection, scope, scope.gateway, "services", "TRUNCATE")
        assert _has(connection, scope, scope.gateway, "service_audit_logs", "UPDATE")


_PROTECTED_SEQUENCES = (
    "finance_transactions_generated_id_seq",
    "service_audit_logs_generated_id_seq",
    "encounter_financial_generation_seq",
)


@pytest.fixture
def finance_sequence_scope(finance_scope, monkeypatch):
    migration = _migration("0163_financial_seq_update_acl.py")
    scope = replace(finance_scope, migration=migration)
    monkeypatch.setattr(migration, "_GATEWAY_ROLES", (scope.gateway,))
    schema = scope.engine.dialect.identifier_preparer.quote_schema(scope.schema)
    with scope.engine.begin() as connection:
        for table in ("finance_transactions", "unrelated_inventory"):
            connection.exec_driver_sql(
                f"ALTER TABLE {scope.qualified(table)} ADD COLUMN generated_id bigserial"
            )
        connection.exec_driver_sql(
            f"ALTER TABLE {scope.qualified('service_audit_logs')} "
            "ADD COLUMN generated_id bigint GENERATED BY DEFAULT AS IDENTITY"
        )
        connection.exec_driver_sql(
            f"CREATE SEQUENCE {scope.qualified('encounter_financial_generation_seq')} AS bigint"
        )
        connection.exec_driver_sql(
            f"GRANT SELECT, UPDATE, USAGE ON ALL SEQUENCES IN SCHEMA {schema} "
            f"TO {scope.gateway}, {scope.maintainer}"
        )
        connection.exec_driver_sql(
            f"GRANT UPDATE ON SEQUENCE {scope.qualified(_PROTECTED_SEQUENCES[0])} TO PUBLIC"
        )
    return scope


def _has_sequence(connection, scope, role, name, privilege):
    return connection.scalar(
        text("SELECT pg_catalog.has_sequence_privilege(:role, :sequence, :privilege)"),
        {"role": role, "sequence": scope.qualified(name), "privilege": privilege},
    )


def test_financial_sequence_acl_preserves_identifier_generation(finance_sequence_scope):
    scope = finance_sequence_scope
    with scope.engine.begin() as connection:
        assert _has_sequence(
            connection, scope, scope.inherited, _PROTECTED_SEQUENCES[0], "UPDATE"
        )

        _migrate(scope, connection)
        _migrate(scope, connection, downgrade=True)
        _migrate(scope, connection)

        for sequence in _PROTECTED_SEQUENCES:
            assert not _has_sequence(
                connection, scope, scope.gateway, sequence, "UPDATE"
            )
            assert not _has_sequence(
                connection, scope, scope.inherited, sequence, "UPDATE"
            )
            assert _has_sequence(connection, scope, scope.gateway, sequence, "USAGE")
            assert _has_sequence(connection, scope, scope.gateway, sequence, "SELECT")
            assert _has_sequence(
                connection, scope, scope.maintainer, sequence, "UPDATE"
            )
        assert _has_sequence(
            connection,
            scope,
            scope.gateway,
            "unrelated_inventory_generated_id_seq",
            "UPDATE",
        )

        connection.exec_driver_sql(f"SET LOCAL ROLE {scope.gateway}")
        table = scope.qualified("finance_transactions")
        values = (
            connection.exec_driver_sql(
                f"INSERT INTO {table} (id) VALUES (1), (2) RETURNING generated_id"
            )
            .scalars()
            .all()
        )
        assert values == [1, 2]


def test_financial_sequence_acl_rolls_back_on_assumable_update(finance_sequence_scope):
    scope = finance_sequence_scope
    with scope.engine.begin() as connection:
        sequence = scope.qualified(_PROTECTED_SEQUENCES[1])
        connection.exec_driver_sql(
            f"GRANT UPDATE ON SEQUENCE {sequence} TO {scope.inherited}"
        )
        opts = (
            "WITH INHERIT FALSE, SET TRUE"
            if connection.dialect.server_version_info >= (16,)
            else ""
        )
        connection.exec_driver_sql(f"GRANT {scope.inherited} TO {scope.gateway} {opts}")

    with (
        pytest.raises(
            RuntimeError, match="Remaining financial sequence UPDATE privileges"
        ),
        scope.engine.begin() as connection,
    ):
        _migrate(scope, connection)

    with scope.engine.connect() as connection:
        assert _has_sequence(
            connection, scope, scope.gateway, _PROTECTED_SEQUENCES[0], "UPDATE"
        )
        assert _has_sequence(
            connection, scope, scope.inherited, _PROTECTED_SEQUENCES[0], "UPDATE"
        )


@pytest.fixture
def payment_evidence_scope(finance_scope, monkeypatch):
    migration = _migration("0164_payment_evidence_acl.py")
    scope = replace(finance_scope, migration=migration)
    monkeypatch.setattr(migration, "_GATEWAY_ROLES", (scope.gateway,))
    with scope.engine.begin() as connection:
        connection.exec_driver_sql(f"ALTER ROLE {scope.gateway} BYPASSRLS")
        for relation in ("payment_webhooks", "payment_transactions"):
            table = scope.qualified(relation)
            connection.exec_driver_sql(f"ALTER TABLE {table} ADD COLUMN status text")
            connection.exec_driver_sql(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
            connection.exec_driver_sql(
                f"GRANT UPDATE, DELETE, TRIGGER ON {table} TO {scope.gateway}, {scope.maintainer}"
            )
            connection.exec_driver_sql(f"GRANT DELETE, TRIGGER ON {table} TO PUBLIC")
        connection.exec_driver_sql(
            f"GRANT DELETE, TRIGGER ON {scope.qualified('unrelated_inventory')} TO {scope.gateway}"
        )
    return scope


def test_payment_evidence_revocation_preserves_callback_workflow(payment_evidence_scope):
    scope = payment_evidence_scope
    final_states = {"payment_webhooks": "processed", "payment_transactions": "completed"}
    with scope.engine.begin() as connection:
        for relation in final_states:
            for privilege in ("DELETE", "TRIGGER"):
                assert _has(connection, scope, scope.gateway, relation, privilege)
                assert _has(connection, scope, scope.inherited, relation, privilege)

        _migrate(scope, connection)

        for relation in final_states:
            for privilege in ("DELETE", "TRIGGER"):
                assert not _has(connection, scope, scope.gateway, relation, privilege)
                assert not _has(connection, scope, scope.inherited, relation, privilege)
                assert _has(connection, scope, scope.maintainer, relation, privilege)
        for privilege in ("DELETE", "TRIGGER"):
            assert _has(
                connection, scope, scope.gateway, "unrelated_inventory", privilege
            )

        connection.exec_driver_sql(f"SET LOCAL ROLE {scope.gateway}")
        for relation in final_states:
            table = scope.qualified(relation)
            connection.exec_driver_sql(
                f"INSERT INTO {table} (id, status) VALUES (1, 'pending')"
            )
            locked_status = connection.scalar(
                text(f"SELECT status FROM {table} WHERE id = 1 FOR UPDATE")
            )
            assert locked_status == "pending"
            connection.execute(
                text(f"UPDATE {table} SET status = :status WHERE id = 1"),
                {"status": final_states[relation]},
            )

    with scope.engine.begin() as connection:
        _migrate(scope, connection, downgrade=True)
        for relation in final_states:
            for privilege in ("DELETE", "TRIGGER"):
                assert not _has(connection, scope, scope.gateway, relation, privilege)
        _migrate(scope, connection)
        for relation, status in final_states.items():
            assert (
                connection.scalar(
                    text(f"SELECT status FROM {scope.qualified(relation)} WHERE id = 1")
                )
                == status
            )


@pytest.mark.parametrize("privilege", ["DELETE", "TRIGGER"])
def test_payment_evidence_rejects_assumable_destructive_grants(
    payment_evidence_scope, privilege
):
    scope = payment_evidence_scope
    table = scope.qualified("payment_transactions")
    with scope.engine.begin() as connection:
        if connection.dialect.server_version_info < (16,):
            connection.exec_driver_sql(f"GRANT {scope.inherited} TO {scope.gateway}")
        else:
            connection.exec_driver_sql(
                f"GRANT {scope.inherited} TO {scope.gateway} WITH INHERIT FALSE, SET TRUE"
            )
        connection.exec_driver_sql(f"GRANT {privilege} ON {table} TO {scope.inherited}")

    with (
        pytest.raises(RuntimeError, match="Remaining payment evidence privileges"),
        scope.engine.begin() as connection,
    ):
        _migrate(scope, connection)

    with scope.engine.begin() as connection:
        assert _has(connection, scope, scope.gateway, "payment_webhooks", privilege)
        connection.exec_driver_sql(f"REVOKE {scope.inherited} FROM {scope.gateway}")
        _migrate(scope, connection)
        assert not _has(connection, scope, scope.gateway, "payment_transactions", privilege)


@pytest.mark.parametrize("relation", ["payment_webhooks", "payment_transactions"])
def test_payment_evidence_keeps_original_identity_and_amount(
    payment_evidence_scope, monkeypatch, relation
):
    scope = payment_evidence_scope
    migration = _migration("0165_payment_evidence_identity.py")
    monkeypatch.setattr(migration, "_GATEWAY_ROLES", (scope.gateway,))
    identity_scope = replace(scope, migration=migration)
    table = scope.qualified(relation)
    original = {
        "id": 1,
        "provider": "synthetic_provider",
        "transaction_id": "equipment_test_receipt",
        "amount": 1100,
        "currency": "UZS",
    }
    proposed = {
        "id": 7,
        "provider": "synthetic_archive",
        "transaction_id": "equipment_test_revision",
        "amount": 1200,
        "currency": "USD",
    }
    if relation == "payment_webhooks":
        original["webhook_id"] = "synthetic_original_event"
        proposed["webhook_id"] = "synthetic_other_event"
    columns = ", ".join(original)
    placeholders = ", ".join(f":{column}" for column in original)
    values = text(f"INSERT INTO {table} ({columns}, status) VALUES ({placeholders}, 'pending')")
    by_identity = text(f"SELECT {columns}, status FROM {table} WHERE id = 1 FOR UPDATE")

    with scope.engine.begin() as connection:
        for name in ("payment_webhooks", "payment_transactions"):
            evidence = scope.qualified(name)
            webhook_id_type = "text" if name == "payment_webhooks" else "integer"
            connection.exec_driver_sql(f"""
                ALTER TABLE {evidence}
                ADD COLUMN provider text, ADD COLUMN transaction_id text,
                ADD COLUMN amount integer, ADD COLUMN currency text,
                ADD COLUMN webhook_id {webhook_id_type}
            """)
        schema = connection.dialect.identifier_preparer.quote_schema(scope.schema)
        connection.exec_driver_sql(
            f"ALTER DEFAULT PRIVILEGES IN SCHEMA {schema} "
            f"GRANT EXECUTE ON FUNCTIONS TO {scope.gateway}"
        )
        connection.execute(values, original)
        _migrate(scope, connection)
        _migrate(identity_scope, connection)
        assert not connection.scalar(
            text("SELECT pg_catalog.has_function_privilege(:role, :function, 'EXECUTE')"),
            {
                "role": scope.gateway,
                "function": f"{schema}.reject_payment_evidence_identity_change()",
            },
        )

        connection.exec_driver_sql(f"SET LOCAL ROLE {scope.gateway}")
        locked = dict(connection.execute(by_identity).mappings().one())
        assert locked == {**original, "status": "pending"}
        followup = {**original, "id": 2, "transaction_id": "equipment_test_followup"}
        if "webhook_id" in followup:
            followup["webhook_id"] = "synthetic_followup_event"
        connection.execute(values, followup)
        connection.execute(
            text(f"UPDATE {table} SET status = 'processed', amount = amount WHERE id = 1")
        )
        if relation == "payment_transactions":
            connection.execute(text(f"UPDATE {table} SET webhook_id = 2 WHERE id = 1"))
            assert connection.scalar(
                text(f"SELECT webhook_id FROM {table} WHERE id = 1")
            ) == 2
        for column, value in proposed.items():
            with (
                pytest.raises(IntegrityError, match="Payment evidence identity and amount"),
                connection.begin_nested(),
            ):
                connection.execute(
                    text(f"UPDATE {table} SET {column} = :value, status = 'corrected' WHERE id = 1"),
                    {"value": value},
                )
        assert dict(connection.execute(by_identity).mappings().one()) == {
            **original,
            "status": "processed",
        }

    with scope.engine.begin() as connection:
        _migrate(identity_scope, connection, downgrade=True)
        assert not _has(connection, scope, scope.gateway, relation, "DELETE")
        _migrate(identity_scope, connection)
        assert dict(connection.execute(by_identity).mappings().one()) == {
            **original,
            "status": "processed",
        }


def test_payment_webhook_preserves_original_payload_signature_and_time(
    payment_evidence_scope, monkeypatch
):
    scope = payment_evidence_scope
    table = scope.qualified("payment_webhooks")
    migration = _migration("0166_payment_webhook_evidence.py")
    monkeypatch.setattr(migration, "_GATEWAY_ROLES", (scope.gateway,))
    webhook_scope = replace(scope, migration=migration)
    original_payload = '{"receipt": "synthetic\\u0000", "attempt": 1}'
    received = "2030-01-02 11:12:13"
    insert_receipt = text(f"""
        INSERT INTO {table} (id, status, raw_data, signature, created_at)
        VALUES (:id, 'pending', CAST(:payload AS json), :signature, CAST(:received AS timestamp))
    """)
    read_receipt = text(f"""
        SELECT raw_data::text, signature, created_at::text, status, processed_at::text, error_message
        FROM {table}
        WHERE id = 1
        FOR UPDATE
    """)
    first_receipt = {"id": 1, "payload": original_payload, "signature": "synthetic", "received": received}
    function = text("SELECT pg_catalog.to_regprocedure(:function)")

    with scope.engine.begin() as connection:
        schema = connection.dialect.identifier_preparer.quote_schema(scope.schema)
        function_name = f"{schema}.reject_payment_webhook_evidence_change()"
        connection.exec_driver_sql(f"""
            ALTER TABLE {table} ADD COLUMN raw_data json NOT NULL,
            ADD COLUMN signature varchar(500), ADD COLUMN created_at timestamp NOT NULL,
            ADD COLUMN processed_at timestamp, ADD COLUMN error_message text
        """)
        connection.exec_driver_sql(
            f"ALTER DEFAULT PRIVILEGES IN SCHEMA {schema} "
            f"GRANT EXECUTE ON FUNCTIONS TO {scope.gateway}"
        )
        connection.execute(insert_receipt, first_receipt)
        _migrate(scope, connection)
        _migrate(webhook_scope, connection)
        assert not connection.scalar(
            text("SELECT pg_catalog.has_function_privilege(:role, :function, 'EXECUTE')"),
            {"role": scope.gateway, "function": function_name},
        )

        connection.exec_driver_sql(f"SET LOCAL ROLE {scope.gateway}")
        assert tuple(connection.execute(read_receipt).one()) == (
            original_payload, "synthetic", received, "pending", None, None,
        )
        connection.execute(insert_receipt, {**first_receipt, "id": 2, "signature": None})
        processed = "2030-01-02 11:13:00"
        connection.execute(
            text(f"""
                UPDATE {table}
                SET status = 'processed', processed_at = CAST(:processed AS timestamp),
                    error_message = NULL, raw_data = raw_data
                WHERE id = 1
            """),
            {"processed": processed},
        )
        for assignment, value, evidence_id in (
            ("raw_data = CAST(:value AS json)", '{"receipt":"synthetic_updated"}', 1),
            ("signature = :value", None, 1),
            ("signature = :value", "synthetic_added", 2),
            ("created_at = CAST(:value AS timestamp)", "2030-01-03 11:12:13", 1),
        ):
            with (
                pytest.raises(IntegrityError, match="Stored payment webhook evidence is immutable"),
                connection.begin_nested(),
            ):
                connection.execute(
                    text(f"UPDATE {table} SET {assignment}, status = 'failed' WHERE id = :id"),
                    {"value": value, "id": evidence_id},
                )
        assert tuple(connection.execute(read_receipt).one()) == (
            original_payload, "synthetic", received, "processed", processed, None,
        )
        assert tuple(
            connection.execute(text(f"SELECT signature, status FROM {table} WHERE id = 2")).one()
        ) == (None, "pending")

    with scope.engine.begin() as connection:
        _migrate(webhook_scope, connection, downgrade=True)
        assert connection.scalar(function, {"function": function_name}) is None
        assert not _has(connection, scope, scope.gateway, "payment_webhooks", "DELETE")
        _migrate(webhook_scope, connection)
        assert connection.scalar(function, {"function": function_name}) is not None
        assert tuple(connection.execute(read_receipt).one()) == (
            original_payload, "synthetic", received, "processed", processed, None,
        )
