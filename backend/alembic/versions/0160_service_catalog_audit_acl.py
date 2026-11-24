"""Preserve service catalogue audit history across gateway role operations."""

import sqlalchemy as sa

from alembic import op

revision = "0160_service_catalog_audit_acl"
down_revision = "0159_finance_metadata_acl"
branch_labels = None
depends_on = None

_GATEWAY_ROLES = ("anon", "authenticated", "service_role")
_CATALOG = "services"
_AUDIT = "service_audit_logs"
_CATALOG_DENIED = "DELETE,TRUNCATE,TRIGGER"
_AUDIT_DENIED = f"UPDATE,{_CATALOG_DENIED}"


def upgrade() -> None:
    context = op.get_context()
    if context.dialect.name == "sqlite":
        return
    if context.dialect.name != "postgresql" or context.as_sql:
        raise RuntimeError(
            "Service audit privileges require an online PostgreSQL catalog"
        )

    schema = (
        context.opts.get("version_table_schema") or context.dialect.default_schema_name
    )
    if not schema:
        raise RuntimeError("Trusted service catalogue schema required")

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
    # The catalogue writer only deactivates services. Physical parent removal
    # would also erase audit rows by the existing foreign-key cascade.
    for table, denied in ((_CATALOG, _CATALOG_DENIED), (_AUDIT, _AUDIT_DENIED)):
        qualified = f"{quoted_schema}.{preparer.quote_identifier(table)}"
        op.execute(f"REVOKE {denied} ON TABLE {qualified} FROM {grantees} RESTRICT")

    activation = "SET" if connection.dialect.server_version_info >= (16,) else "MEMBER"
    protected = connection.scalar(
        sa.text("""
            WITH targets AS (
                SELECT c.oid, c.relname, c.relacl, c.relowner,
                       CASE WHEN c.relname = :audit_table THEN :audit_denied
                            ELSE :catalog_denied END AS denied
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
            SELECT (SELECT count(*) = 2 FROM targets)
               AND NOT EXISTS (
                   SELECT 1 FROM targets
                   CROSS JOIN LATERAL pg_catalog.aclexplode(relacl) AS acl
                   WHERE acl.grantee = 0
                     AND acl.privilege_type = ANY(pg_catalog.string_to_array(denied, ','))
               )
               AND NOT EXISTS (
                   SELECT 1 FROM targets
                   JOIN pg_catalog.pg_attribute AS a ON a.attrelid = targets.oid
                   CROSS JOIN LATERAL pg_catalog.aclexplode(a.attacl) AS acl
                   WHERE targets.relname = :audit_table
                     AND a.attnum > 0 AND NOT a.attisdropped
                     AND acl.grantee = 0 AND acl.privilege_type = 'UPDATE'
               )
               AND NOT EXISTS (
                   SELECT 1 FROM targets CROSS JOIN gateway_access AS gateway
                   WHERE pg_catalog.has_table_privilege(gateway.oid, targets.oid, targets.denied)
                      OR pg_catalog.pg_has_role(gateway.oid, targets.relowner, 'USAGE')
                      OR (targets.relname = :audit_table AND pg_catalog.has_any_column_privilege(
                          gateway.oid, targets.oid, 'UPDATE'
                      ))
               )
        """).bindparams(
            sa.bindparam("roles", type_=sa.String(), expanding=True),
            sa.bindparam("tables", expanding=True),
        ),
        {
            "schema": schema,
            "tables": (_CATALOG, _AUDIT),
            "audit_table": _AUDIT,
            "catalog_denied": _CATALOG_DENIED,
            "audit_denied": _AUDIT_DENIED,
            "activation": activation,
            "roles": roles,
        },
    )
    if protected is not True:
        raise RuntimeError(
            "Remaining service audit write privileges require role reconciliation"
        )


def downgrade() -> None:
    """Keep destructive privileges revoked during application rollbacks."""
