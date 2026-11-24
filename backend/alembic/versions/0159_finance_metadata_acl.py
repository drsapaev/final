"""Restrict gateway grants on financial ledgers and schema bookkeeping."""

import sqlalchemy as sa
from alembic import op

revision = "0159_finance_metadata_acl"
down_revision = "0158_finance_internal_exec_acl"
branch_labels = None
depends_on = None

_GATEWAY_ROLES = ("anon", "authenticated", "service_role")
_LEDGER_TABLES = (
    "user_audit_logs",
    "provider_attempts",
    "provider_attempt_visits",
    "provider_active_visit_reservations",
)
_KASPI_REGISTRY = "kaspi_issued_payment_refs"
_TABLE_ADMIN = ("TRUNCATE", "REFERENCES", "TRIGGER")
_VERSION_WRITES = ("INSERT", "UPDATE", "DELETE")


def upgrade() -> None:
    context = op.get_context()
    if context.dialect.name == "sqlite":
        return
    if context.dialect.name != "postgresql" or context.as_sql:
        raise RuntimeError(
            "Finance metadata privileges require an online PostgreSQL catalog"
        )

    schema = (
        context.opts.get("version_table_schema") or context.dialect.default_schema_name
    )
    version_table = context.opts.get("version_table", "alembic_version")
    finance_tables = (*_LEDGER_TABLES, _KASPI_REGISTRY)
    if not schema or not version_table or version_table in finance_tables:
        raise RuntimeError("Trusted audit and schema bookkeeping tables required")

    connection = op.get_bind()
    roles = tuple(
        connection.scalars(
            sa.text("""
                SELECT rolname FROM pg_catalog.pg_roles
                WHERE rolname IN :roles ORDER BY rolname
            """).bindparams(sa.bindparam("roles", expanding=True)),
            {"roles": _GATEWAY_ROLES},
        )
    )
    preparer = context.dialect.identifier_preparer
    quoted_schema = preparer.quote_schema(schema)
    grantees = ", ".join(("PUBLIC", *map(preparer.quote_identifier, roles)))
    ledgers = ", ".join(
        f"{quoted_schema}.{preparer.quote_identifier(name)}" for name in _LEDGER_TABLES
    )
    bookkeeping = f"{quoted_schema}.{preparer.quote_identifier(version_table)}"
    registry = f"{quoted_schema}.{preparer.quote_identifier(_KASPI_REGISTRY)}"
    admin_privileges = _TABLE_ADMIN
    if connection.dialect.server_version_info >= (17,):
        admin_privileges += ("MAINTAIN",)
    ledger_denied = ",".join(admin_privileges)
    version_denied = ",".join((*admin_privileges, *_VERSION_WRITES))
    op.execute(f"REVOKE {ledger_denied} ON TABLE {ledgers} FROM {grantees} RESTRICT")
    op.execute(f"REVOKE {version_denied} ON TABLE {bookkeeping} FROM {grantees} RESTRICT")
    op.execute(f"REVOKE ALL PRIVILEGES ON TABLE {registry} FROM {grantees} RESTRICT")

    # Include roles a gateway can assume, even without inherited privileges.
    activation = "SET" if connection.dialect.server_version_info >= (16,) else "MEMBER"
    protected = connection.scalar(
        sa.text("""
            WITH targets AS (
                SELECT c.oid, c.relacl, c.relowner,
                    CASE c.relname
                        WHEN :version_table THEN :version_denied
                        WHEN :registry_table THEN :registry_denied
                        ELSE :ledger_denied
                    END AS denied,
                    CASE c.relname
                        WHEN :version_table THEN 'INSERT,UPDATE,REFERENCES'
                        WHEN :registry_table THEN 'SELECT,INSERT,UPDATE,REFERENCES'
                        ELSE 'REFERENCES'
                    END AS denied_columns
                FROM pg_catalog.pg_class AS c
                JOIN pg_catalog.pg_namespace AS n ON n.oid = c.relnamespace
                WHERE n.nspname = :schema AND c.relkind IN ('r', 'p')
                  AND c.relname IN :tables
            ), gateway_access AS (
                SELECT DISTINCT reachable.oid
                FROM pg_catalog.pg_roles AS gateway
                JOIN pg_catalog.pg_roles AS reachable
                  ON reachable.oid = gateway.oid
                  OR pg_catalog.pg_has_role(gateway.oid, reachable.oid, :activation)
                WHERE gateway.rolname IN :roles
            )
            SELECT (SELECT count(*) = :target_count FROM targets)
               AND NOT EXISTS (
                   SELECT 1 FROM targets
                   CROSS JOIN LATERAL pg_catalog.aclexplode(
                       COALESCE(relacl, pg_catalog.acldefault('r', relowner))
                   ) AS acl
                   WHERE acl.grantee = 0
                     AND acl.privilege_type = ANY(pg_catalog.string_to_array(denied, ','))
               )
               AND NOT EXISTS (
                   SELECT 1 FROM targets
                   JOIN pg_catalog.pg_attribute AS a ON a.attrelid = targets.oid
                   CROSS JOIN LATERAL pg_catalog.aclexplode(a.attacl) AS acl
                   WHERE a.attnum > 0 AND NOT a.attisdropped AND acl.grantee = 0
                     AND acl.privilege_type = ANY(pg_catalog.string_to_array(denied_columns, ','))
               )
               AND NOT EXISTS (
                   SELECT 1 FROM targets CROSS JOIN gateway_access AS gateway
                   WHERE pg_catalog.has_table_privilege(gateway.oid, targets.oid, targets.denied)
                      OR pg_catalog.pg_has_role(gateway.oid, targets.relowner, 'USAGE')
                      OR pg_catalog.has_any_column_privilege(
                          gateway.oid, targets.oid, targets.denied_columns
                      )
               )
        """).bindparams(
            sa.bindparam("roles", type_=sa.String(), expanding=True),
            sa.bindparam("tables", expanding=True),
        ),
        {
            "schema": schema,
            "tables": (*finance_tables, version_table),
            "target_count": len(finance_tables) + 1,
            "version_table": version_table,
            "registry_table": _KASPI_REGISTRY,
            "ledger_denied": ledger_denied,
            "version_denied": version_denied,
            "registry_denied": f"SELECT,{version_denied}",
            "activation": activation,
            "roles": roles,
        },
    )
    if protected is not True:
        raise RuntimeError(
            "Remaining finance metadata write privileges require role reconciliation"
        )


def downgrade() -> None:
    """Keep destructive privileges revoked during application rollbacks."""
