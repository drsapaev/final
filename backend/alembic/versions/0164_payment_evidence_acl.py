"""Protect callback and transaction evidence from destructive gateway grants."""

import sqlalchemy as sa

from alembic import op

revision = "0164_payment_evidence_acl"
down_revision = "0163_financial_seq_update_acl"
branch_labels = None
depends_on = None

_GATEWAY_ROLES = ("anon", "authenticated", "service_role")
_TABLES = ("payment_webhooks", "payment_transactions")
_DENIED = "DELETE,TRIGGER"


def upgrade() -> None:
    context = op.get_context()
    if context.dialect.name == "sqlite":
        return
    if context.dialect.name != "postgresql" or context.as_sql:
        raise RuntimeError(
            "Payment evidence privileges require an online PostgreSQL catalog"
        )

    schema = (
        context.opts.get("version_table_schema") or context.dialect.default_schema_name
    )
    if not schema:
        raise RuntimeError("Trusted payment evidence schema required")

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
    tables = ", ".join(
        f"{quoted_schema}.{preparer.quote_identifier(table)}" for table in _TABLES
    )
    # Callback handlers append rows and update lifecycle fields in place.
    op.execute(f"REVOKE {_DENIED} ON TABLE {tables} FROM {grantees} RESTRICT")

    activation = "SET" if connection.dialect.server_version_info >= (16,) else "MEMBER"
    protected = connection.scalar(
        sa.text("""
            WITH evidence AS (
                SELECT c.oid, c.relacl, c.relowner
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
            SELECT (SELECT count(*) = :table_count FROM evidence)
               AND NOT EXISTS (
                   SELECT 1 FROM evidence
                   CROSS JOIN LATERAL pg_catalog.aclexplode(relacl) AS acl
                   WHERE acl.grantee = 0 AND acl.privilege_type IN ('DELETE', 'TRIGGER')
               )
               AND NOT EXISTS (
                   SELECT 1 FROM evidence CROSS JOIN gateway_access AS gateway
                   WHERE pg_catalog.has_table_privilege(gateway.oid, evidence.oid, :denied)
                      OR pg_catalog.pg_has_role(gateway.oid, evidence.relowner, 'USAGE')
               )
        """).bindparams(
            sa.bindparam("roles", type_=sa.String(), expanding=True),
            sa.bindparam("tables", expanding=True),
        ),
        {
            "schema": schema,
            "tables": _TABLES,
            "table_count": len(_TABLES),
            "activation": activation,
            "roles": roles,
            "denied": _DENIED,
        },
    )
    if protected is not True:
        raise RuntimeError(
            "Remaining payment evidence privileges require role reconciliation"
        )


def downgrade() -> None:
    """Keep payment evidence privileges restricted during application rollbacks."""
