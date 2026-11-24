"""Restrict gateway execution of the remaining financial guard triggers."""

import sqlalchemy as sa
from alembic import op

revision = "0158_finance_internal_exec_acl"
down_revision = "0157_payme_cancel_receipt_guard"
branch_labels = None
depends_on = None

_GATEWAY_ROLES = ("anon", "authenticated", "service_role")
_ROUTINES = (
    "prevent_audit_log_truncate",
    "protect_payme_creation_receipt",
    "prevent_refund_claim_truncate",
    "protect_payme_cancel_receipt",
)


def upgrade() -> None:
    context = op.get_context()
    if context.dialect.name == "sqlite":
        return
    if context.dialect.name != "postgresql" or context.as_sql:
        raise RuntimeError("Finance routine privileges require an online PostgreSQL catalog")

    schema = (
        context.opts.get("version_table_schema") or context.dialect.default_schema_name
    )
    if not schema:
        raise RuntimeError("Trusted financial schema required")

    connection = op.get_bind()
    targets = tuple(
        connection.scalars(
            sa.text("""
                SELECT p.oid
                FROM pg_catalog.pg_proc p
                JOIN pg_catalog.pg_namespace n ON n.oid = p.pronamespace
                WHERE n.nspname = :schema AND p.proname IN :names
                  AND p.pronargs = 0 AND p.prorettype = 'pg_catalog.trigger'::regtype
            """).bindparams(sa.bindparam("names", expanding=True)),
            {"schema": schema, "names": _ROUTINES},
        )
    )
    if len(targets) != len(_ROUTINES):
        raise RuntimeError("Expected financial trigger functions are missing")

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
    qualified_schema = preparer.quote_schema(schema)
    functions = ", ".join(
        f"{qualified_schema}.{preparer.quote_identifier(name)}()" for name in _ROUTINES
    )
    grantees = ", ".join(("PUBLIC", *map(preparer.quote_identifier, roles)))
    op.execute(f"REVOKE EXECUTE ON FUNCTION {functions} FROM {grantees} RESTRICT")

    activation = "SET" if connection.dialect.server_version_info >= (16,) else "MEMBER"
    remaining = connection.scalar(
        sa.text("""
            WITH routines AS (
                SELECT oid, proacl, proowner
                FROM pg_catalog.pg_proc WHERE oid IN :targets
            ), gateway_access AS (
                SELECT DISTINCT reachable.oid
                FROM pg_catalog.pg_roles gateway
                JOIN pg_catalog.pg_roles reachable
                  ON reachable.oid = gateway.oid
                  OR pg_catalog.pg_has_role(gateway.oid, reachable.oid, :activation)
                WHERE gateway.rolname IN :roles
            )
            SELECT EXISTS (
                SELECT 1 FROM routines
                CROSS JOIN LATERAL pg_catalog.aclexplode(
                    COALESCE(proacl, pg_catalog.acldefault('f', proowner))
                ) acl
                WHERE acl.grantee = 0 AND acl.privilege_type = 'EXECUTE'
            ) OR EXISTS (
                SELECT 1 FROM routines CROSS JOIN gateway_access g
                WHERE pg_catalog.has_function_privilege(g.oid, routines.oid, 'EXECUTE')
                   OR pg_catalog.pg_has_role(g.oid, routines.proowner, 'USAGE')
            )
        """).bindparams(
            sa.bindparam("targets", expanding=True),
            sa.bindparam("roles", type_=sa.String(), expanding=True),
        ),
        {"targets": targets, "roles": roles, "activation": activation},
    )
    if remaining is not False:
        raise RuntimeError("Remaining financial trigger EXECUTE requires role reconciliation")


def downgrade() -> None:
    """Keep the internal functions restricted during application rollbacks."""
