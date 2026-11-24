"""Check creator and schema isolation for financial default privileges."""

from dataclasses import dataclass
from importlib.util import module_from_spec, spec_from_file_location
from os import getenv
from pathlib import Path
from uuid import uuid4

import pytest
from psycopg import sql
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine, make_url
from tests._pg_admin_guard import is_local_admin_dsn

SCRIPT_PATH = (
    Path(__file__).resolve().parents[3] / "scripts/provision_finance_default_acl.py"
)
SPEC = spec_from_file_location("finance_default_acl", SCRIPT_PATH)
assert SPEC and SPEC.loader
provisioner = module_from_spec(SPEC)
SPEC.loader.exec_module(provisioner)


@dataclass
class AclScope:
    admin: Engine
    owner: Engine
    database: str
    schema: str
    other_schema: str
    creator: str
    other_creator: str
    gateway: str
    staff: str
    transit: str
    delegate: str

    @staticmethod
    def quote(identifier: str) -> str:
        return sql.Identifier(identifier).as_string()

    def reconcile(self, **overrides):
        target = {
            "database": self.database,
            "schema": self.schema,
            "creator": self.creator,
        }
        provisioner.provision(self.owner, **(target | overrides))

    def new_table(self, name, *, schema=None, creator=None):
        qualified = f"{self.quote(schema or self.schema)}.{self.quote(name)}"
        with self.admin.begin() as db:
            db.exec_driver_sql(f"SET LOCAL ROLE {self.quote(creator or self.creator)}")
            db.exec_driver_sql(
                f"CREATE TABLE {qualified} (id integer)",
                execution_options={"no_parameters": True},
            )
        return qualified

    def new_sequence(self, name, *, schema=None, creator=None):
        qualified = f"{self.quote(schema or self.schema)}.{self.quote(name)}"
        with self.admin.begin() as db:
            db.exec_driver_sql(f"SET LOCAL ROLE {self.quote(creator or self.creator)}")
            db.exec_driver_sql(
                f"CREATE SEQUENCE {qualified}",
                execution_options={"no_parameters": True},
            )
        return qualified

    def sequence_privileges(self, role, sequence):
        with self.admin.connect() as db:
            return tuple(
                db.execute(
                    text("""
                    SELECT
                        pg_catalog.has_sequence_privilege(:role, :sequence, 'SELECT'),
                        pg_catalog.has_sequence_privilege(:role, :sequence, 'UPDATE'),
                        pg_catalog.has_sequence_privilege(:role, :sequence, 'USAGE')
                """),
                    {"role": role, "sequence": sequence},
                ).one()
            )

    def has_privilege(self, role, table, privilege):
        with self.admin.connect() as db:
            return db.scalar(
                text("""
                SELECT pg_catalog.has_table_privilege(:role, :table, :privilege)
            """),
                {"role": role, "table": table, "privilege": privilege},
            )

    def scoped_truncate_grantees(self):
        with self.admin.connect() as db:
            return set(
                db.scalars(
                    text("""
                SELECT CASE WHEN acl.grantee = 0 THEN 'PUBLIC'
                       ELSE pg_catalog.pg_get_userbyid(acl.grantee) END
                FROM pg_catalog.pg_default_acl defaults
                JOIN pg_catalog.pg_namespace ns ON ns.oid = defaults.defaclnamespace
                CROSS JOIN LATERAL pg_catalog.aclexplode(defaults.defaclacl) acl
                WHERE ns.nspname = :schema AND defaults.defaclobjtype = 'r'
                  AND pg_catalog.pg_get_userbyid(defaults.defaclrole) = :creator
                  AND acl.privilege_type = 'TRUNCATE'
            """),
                    {"schema": self.schema, "creator": self.creator},
                )
            )


@pytest.fixture
def acl_scope(monkeypatch):
    raw = getenv("DATABASE_URL", "")
    if not is_local_admin_dsn(raw):
        pytest.skip("requires a disposable local PostgreSQL database")
    url = make_url(raw)
    if not (url.database or "").startswith("clinic_test"):
        pytest.skip("requires a disposable clinic_test database")

    suffix = uuid4().hex[:12]
    roles = tuple(
        f"synthetic_{name}_{suffix}"
        for name in (
            "creator",
            "other_creator",
            "gateway",
            "staff",
            "transit",
            "delegate",
        )
    )
    creator, other_creator, gateway, staff, _, _ = roles
    schema = f'Finance "default" {suffix} %'
    other_schema = f"synthetic_other_{suffix}"
    admin = create_engine(url, hide_parameters=True)
    owner = create_engine(
        url, connect_args={"options": f"-c role={creator}"}, hide_parameters=True
    )
    scope = AclScope(admin, owner, url.database, schema, other_schema, *roles)
    quote = scope.quote
    monkeypatch.setattr(provisioner, "_GATEWAY_ROLES", (gateway,))
    try:
        with admin.begin() as db:
            assert db.scalar(text("SELECT current_database()")) == url.database
            for role in roles:
                db.exec_driver_sql(f"CREATE ROLE {quote(role)} NOLOGIN")
            for name in (schema, other_schema):
                db.exec_driver_sql(
                    f"CREATE SCHEMA {quote(name)}",
                    execution_options={"no_parameters": True},
                )
                db.exec_driver_sql(
                    f"GRANT USAGE, CREATE ON SCHEMA {quote(name)} TO {quote(creator)}, {quote(other_creator)}",
                    execution_options={"no_parameters": True},
                )
                db.exec_driver_sql(
                    f"GRANT USAGE ON SCHEMA {quote(name)} TO {quote(gateway)}",
                    execution_options={"no_parameters": True},
                )
                for actor in (creator, other_creator):
                    db.exec_driver_sql(
                        f"ALTER DEFAULT PRIVILEGES FOR ROLE {quote(actor)} IN SCHEMA {quote(name)} "
                        f"GRANT SELECT, INSERT, TRUNCATE ON TABLES TO {quote(gateway)}, {quote(staff)}",
                        execution_options={"no_parameters": True},
                    )
            db.exec_driver_sql(
                f"ALTER DEFAULT PRIVILEGES FOR ROLE {quote(creator)} IN SCHEMA {quote(schema)} "
                "GRANT TRUNCATE ON TABLES TO PUBLIC",
                execution_options={"no_parameters": True},
            )
        try:
            with owner.connect() as db:
                assert db.scalar(text("SELECT current_user")) == creator
                assert db.scalar(
                    text("""
                    SELECT pg_catalog.has_schema_privilege(current_user, oid, 'CREATE')
                    FROM pg_catalog.pg_namespace WHERE nspname = :schema
                """),
                    {"schema": schema},
                )
            yield scope
        finally:
            owner.dispose()
            with admin.begin() as db:
                for name in (schema, other_schema):
                    db.exec_driver_sql(
                        f"DROP SCHEMA {quote(name)} CASCADE",
                        execution_options={"no_parameters": True},
                    )
                for role in roles:
                    db.exec_driver_sql(f"DROP OWNED BY {quote(role)}")
                for role in reversed(roles):
                    db.exec_driver_sql(f"DROP ROLE {quote(role)}")
    finally:
        admin.dispose()


def test_future_tables_keep_ordinary_grants_and_only_the_selected_creator_changes(
    acl_scope,
):
    scope = acl_scope
    before = scope.new_table("synthetic_before")
    assert scope.has_privilege(scope.gateway, before, "TRUNCATE")
    assert scope.has_privilege(scope.delegate, before, "TRUNCATE")
    scope.reconcile()
    scope.reconcile()

    after = scope.new_table("synthetic_after")
    assert scope.scoped_truncate_grantees() == {scope.staff}
    assert scope.has_privilege(scope.gateway, before, "TRUNCATE")
    assert not scope.has_privilege(scope.gateway, after, "TRUNCATE")
    assert not scope.has_privilege(scope.delegate, after, "TRUNCATE")
    assert scope.has_privilege(scope.staff, after, "TRUNCATE")
    assert scope.has_privilege(scope.gateway, after, "SELECT")
    with scope.admin.begin() as db:
        db.exec_driver_sql(f"SET LOCAL ROLE {scope.quote(scope.gateway)}")
        db.exec_driver_sql(
            f"INSERT INTO {after} VALUES (1)", execution_options={"no_parameters": True}
        )
        assert (
            db.exec_driver_sql(
                f"SELECT id FROM {after}", execution_options={"no_parameters": True}
            ).scalar_one()
            == 1
        )

    for table in (
        scope.new_table("synthetic_other_creator", creator=scope.other_creator),
        scope.new_table("synthetic_other_schema", schema=scope.other_schema),
    ):
        assert scope.has_privilege(scope.gateway, table, "TRUNCATE")


@pytest.mark.parametrize("target", ("database", "creator", "schema"))
def test_wrong_target_leaves_default_acl_unchanged(acl_scope, target):
    before = acl_scope.scoped_truncate_grantees()
    with pytest.raises(
        provisioner.DefaultAclError, match="Expected database, active creator"
    ):
        acl_scope.reconcile(**{target: "synthetic_unexpected"})
    assert acl_scope.scoped_truncate_grantees() == before


def test_global_grant_rolls_back_scoped_revoke(acl_scope):
    scope = acl_scope
    with scope.admin.begin() as db:
        db.exec_driver_sql(
            f"ALTER DEFAULT PRIVILEGES FOR ROLE {scope.quote(scope.creator)} "
            f"GRANT TRUNCATE ON TABLES TO {scope.quote(scope.gateway)}"
        )
    before = scope.scoped_truncate_grantees()
    scope.owner = scope.owner.execution_options(isolation_level="AUTOCOMMIT")
    with scope.owner.connect() as db:
        assert db.connection.driver_connection.autocommit
    with pytest.raises(provisioner.DefaultAclError, match="Global default TRUNCATE"):
        scope.reconcile()
    assert scope.scoped_truncate_grantees() == before


def test_public_default_is_removed_even_when_gateway_roles_are_absent(
    acl_scope, monkeypatch
):
    scope = acl_scope
    monkeypatch.setattr(provisioner, "_GATEWAY_ROLES", (f"missing_{uuid4().hex}",))
    scope.reconcile()

    assert scope.scoped_truncate_grantees() == {scope.staff, scope.gateway}
    table = scope.new_table("synthetic_public_removed")
    assert not scope.has_privilege(scope.delegate, table, "TRUNCATE")
    assert scope.has_privilege(scope.gateway, table, "TRUNCATE")


def test_role_can_assume_creator_causes_rollback(acl_scope):
    scope = acl_scope
    with scope.admin.begin() as db:
        db.exec_driver_sql(
            f"GRANT {scope.quote(scope.creator)} TO {scope.quote(scope.gateway)}"
        )
    before = scope.scoped_truncate_grantees()
    with pytest.raises(provisioner.DefaultAclError, match="act as the table creator"):
        scope.reconcile()
    assert scope.scoped_truncate_grantees() == before


@pytest.mark.parametrize(
    "activation_chain", (False, True), ids=("inherited", "assumed-then-inherited")
)
def test_indirect_schema_grant_causes_rollback(acl_scope, activation_chain):
    scope = acl_scope
    quote = scope.quote
    with scope.admin.begin() as db:
        if activation_chain:
            if db.dialect.server_version_info < (16,):
                pytest.skip("requires PostgreSQL 16 membership options")
            db.exec_driver_sql(
                f"GRANT {quote(scope.transit)} TO {quote(scope.gateway)} WITH SET TRUE, INHERIT FALSE"
            )
            db.exec_driver_sql(
                f"GRANT {quote(scope.delegate)} TO {quote(scope.transit)} WITH SET FALSE, INHERIT TRUE"
            )
            for privilege in ("SET", "USAGE"):
                assert not db.scalar(
                    text("""
                    SELECT pg_catalog.pg_has_role(:gateway, :delegate, :privilege)
                """),
                    {
                        "gateway": scope.gateway,
                        "delegate": scope.delegate,
                        "privilege": privilege,
                    },
                )
        else:
            db.exec_driver_sql(
                f"GRANT {quote(scope.delegate)} TO {quote(scope.gateway)}"
            )
        db.exec_driver_sql(
            f"ALTER DEFAULT PRIVILEGES FOR ROLE {quote(scope.creator)} IN SCHEMA {quote(scope.schema)} "
            f"GRANT TRUNCATE ON TABLES TO {quote(scope.delegate)}",
            execution_options={"no_parameters": True},
        )
    before = scope.scoped_truncate_grantees()
    with pytest.raises(provisioner.DefaultAclError, match="Indirect default TRUNCATE"):
        scope.reconcile()
    assert scope.scoped_truncate_grantees() == before


def test_sequence_defaults_are_scoped_to_new_sequences_from_the_selected_creator(
    acl_scope,
):
    scope = acl_scope
    quote = scope.quote
    with scope.admin.begin() as db:
        for creator, schema in (
            (scope.creator, scope.schema),
            (scope.creator, scope.other_schema),
            (scope.other_creator, scope.schema),
        ):
            db.exec_driver_sql(
                f"ALTER DEFAULT PRIVILEGES FOR ROLE {quote(creator)} IN SCHEMA {quote(schema)} "
                f"GRANT SELECT, UPDATE, USAGE ON SEQUENCES TO PUBLIC, {quote(scope.gateway)}",
                execution_options={"no_parameters": True},
            )

    existing = scope.new_sequence("synthetic_existing")
    assert scope.sequence_privileges(scope.gateway, existing) == (True, True, True)
    scope.reconcile(sequences=True)
    scope.reconcile(sequences=True)

    protected = scope.new_sequence("synthetic_protected")
    assert scope.sequence_privileges(scope.gateway, protected) == (False, False, False)
    assert scope.sequence_privileges(scope.delegate, protected) == (False, False, False)
    assert scope.sequence_privileges(scope.gateway, existing) == (True, True, True)

    for sequence in (
        scope.new_sequence("synthetic_other_schema", schema=scope.other_schema),
        scope.new_sequence("synthetic_other_creator", creator=scope.other_creator),
    ):
        assert scope.sequence_privileges(scope.gateway, sequence) == (True, True, True)

    unrelated_table = scope.new_table("synthetic_unrelated_table")
    assert scope.has_privilege(scope.gateway, unrelated_table, "TRUNCATE")

    with scope.admin.begin() as db:
        db.exec_driver_sql(
            f"GRANT USAGE ON SEQUENCE {protected} TO {quote(scope.staff)}",
            execution_options={"no_parameters": True},
        )
    assert scope.sequence_privileges(scope.staff, protected) == (False, False, True)


@pytest.mark.parametrize(
    ("global_default", "reason"),
    (
        (True, "Global default sequence access"),
        (False, "Unreviewed default sequence access"),
    ),
    ids=("global", "unreviewed-schema-grantee"),
)
def test_sequence_default_scope_rolls_back_on_unreviewed_access(
    acl_scope, global_default, reason
):
    scope = acl_scope
    quote = scope.quote
    defaults = f"ALTER DEFAULT PRIVILEGES FOR ROLE {quote(scope.creator)}"
    schema = f"IN SCHEMA {quote(scope.schema)}"
    unreviewed = defaults if global_default else f"{defaults} {schema}"
    with scope.admin.begin() as db:
        db.exec_driver_sql(
            f"{defaults} {schema} GRANT SELECT, UPDATE, USAGE ON SEQUENCES TO {quote(scope.gateway)}",
            execution_options={"no_parameters": True},
        )
        db.exec_driver_sql(
            f"{unreviewed} GRANT USAGE ON SEQUENCES TO {quote(scope.staff)}",
            execution_options={"no_parameters": True},
        )

    scope.owner = scope.owner.execution_options(isolation_level="AUTOCOMMIT")
    with pytest.raises(provisioner.DefaultAclError, match=reason):
        scope.reconcile(sequences=True)

    sequence = scope.new_sequence("synthetic_after_rejected_change")
    assert scope.sequence_privileges(scope.gateway, sequence) == (True, True, True)
    assert scope.sequence_privileges(scope.staff, sequence) == (False, False, True)
