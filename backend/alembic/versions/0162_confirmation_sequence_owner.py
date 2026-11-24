"""Align the confirmation generation sequence owner and gateway privileges."""

import sqlalchemy as sa

from alembic import op

revision = "0162_confirmation_sequence_owner"
down_revision = "0161_booking_lock_owner"
branch_labels = None
depends_on = None

_SEQUENCE = "visit_confirmation_generation_seq"
_GATEWAY_ROLES = ("anon", "authenticated", "service_role")


def upgrade() -> None:
    context = op.get_context()
    if context.dialect.name == "sqlite":
        return
    if context.dialect.name != "postgresql" or context.as_sql:
        raise RuntimeError(
            "Confirmation sequence ownership requires an online PostgreSQL catalog"
        )

    schema = (
        context.opts.get("version_table_schema") or context.dialect.default_schema_name
    )
    if not schema:
        raise RuntimeError("Trusted confirmation sequence schema required")

    connection = op.get_bind()
    sequence = (
        connection.execute(
            sa.text("""
            SELECT c.oid, c.relowner IN (n.nspowner, requests.relowner) AS owner_aligned,
                   schema_owner.rolname AS schema_owner
            FROM pg_catalog.pg_class c
            JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
            JOIN pg_catalog.pg_roles schema_owner ON schema_owner.oid = n.nspowner
            JOIN pg_catalog.pg_sequence s ON s.seqrelid = c.oid
            JOIN pg_catalog.pg_class requests ON requests.relnamespace = n.oid
                AND requests.relname = 'all_free_requests' AND requests.relkind IN ('r', 'p')
            WHERE n.nspname = :schema AND c.relname = :sequence AND c.relkind = 'S'
              AND s.seqtypid = 'pg_catalog.int8'::pg_catalog.regtype
              AND NOT EXISTS (
                  SELECT 1 FROM pg_catalog.pg_depend d
                  WHERE d.classid = 'pg_catalog.pg_class'::pg_catalog.regclass
                    AND d.objid = c.oid AND d.objsubid = 0
                    AND d.refclassid = 'pg_catalog.pg_class'::pg_catalog.regclass
                    AND d.deptype IN ('a', 'i')
              )
        """),
            {"schema": schema, "sequence": _SEQUENCE},
        )
        .mappings()
        .one_or_none()
    )
    if sequence is None:
        raise RuntimeError(
            "Trusted standalone confirmation generation sequence required"
        )

    preparer = context.dialect.identifier_preparer
    qualified = (
        f"{preparer.quote_schema(schema)}.{preparer.quote_identifier(_SEQUENCE)}"
    )
    if not sequence["owner_aligned"]:
        owner = preparer.quote_identifier(sequence["schema_owner"])
        op.execute(f"ALTER SEQUENCE {qualified} OWNER TO {owner}")

    roles = tuple(
        connection.scalars(
            sa.text("""
                SELECT rolname FROM pg_catalog.pg_roles
                WHERE rolname IN :roles ORDER BY rolname
            """).bindparams(sa.bindparam("roles", expanding=True)),
            {"roles": _GATEWAY_ROLES},
        )
    )
    grantees = ", ".join(("PUBLIC", *map(preparer.quote_identifier, roles)))
    op.execute(
        f"REVOKE ALL PRIVILEGES ON SEQUENCE {qualified} FROM {grantees} RESTRICT"
    )

    activation = "SET" if connection.dialect.server_version_info >= (16,) else "MEMBER"
    protected = connection.scalar(
        sa.text("""
            WITH gateway_access AS (
                SELECT DISTINCT reachable.oid
                FROM pg_catalog.pg_roles gateway
                JOIN pg_catalog.pg_roles reachable
                  ON reachable.oid = gateway.oid
                  OR pg_catalog.pg_has_role(gateway.oid, reachable.oid, :activation)
                WHERE gateway.rolname IN :roles
            )
            SELECT NOT EXISTS (
                SELECT 1 FROM pg_catalog.pg_class c
                CROSS JOIN LATERAL pg_catalog.aclexplode(c.relacl) acl
                WHERE c.oid = :sequence AND acl.grantee = 0
            ) AND NOT EXISTS (
                SELECT 1 FROM pg_catalog.pg_class c CROSS JOIN gateway_access gateway
                WHERE c.oid = :sequence
                  AND (pg_catalog.has_sequence_privilege(gateway.oid, c.oid, 'SELECT,UPDATE,USAGE')
                       OR pg_catalog.pg_has_role(gateway.oid, c.relowner, 'USAGE'))
            )
        """).bindparams(sa.bindparam("roles", type_=sa.String(), expanding=True)),
        {"sequence": sequence["oid"], "activation": activation, "roles": roles},
    )
    if protected is not True:
        raise RuntimeError(
            "Remaining confirmation generation sequence grants require role reconciliation"
        )


def downgrade() -> None:
    """Keep the trusted owner, allocated generations and gateway restrictions."""
