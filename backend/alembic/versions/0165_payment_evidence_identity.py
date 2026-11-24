"""Keep the identity and amount of stored payment evidence stable."""

import sqlalchemy as sa
from alembic import op

revision = "0165_payment_evidence_identity"
down_revision = "0164_payment_evidence_acl"
branch_labels = None
depends_on = None

_GATEWAY_ROLES = ("anon", "authenticated", "service_role")
_COMMON_COLUMNS = ("id", "provider", "transaction_id", "amount", "currency")
_EVIDENCE_COLUMNS = {
    "payment_webhooks": (*_COMMON_COLUMNS, "webhook_id"),
    "payment_transactions": _COMMON_COLUMNS,
}
_FUNCTION = "reject_payment_evidence_identity_change"


def _postgres_schema() -> str | None:
    context = op.get_context()
    if context.dialect.name == "sqlite":
        return None
    if context.dialect.name != "postgresql" or context.as_sql:
        raise RuntimeError("Payment evidence requires an online PostgreSQL catalog")
    name = context.opts.get("version_table_schema") or context.dialect.default_schema_name
    if not name:
        raise RuntimeError("Trusted payment evidence schema required")
    return context.dialect.identifier_preparer.quote_schema(name)


def upgrade() -> None:
    schema = _postgres_schema()
    if schema is None:
        return

    op.execute(f"""
        CREATE FUNCTION {schema}.{_FUNCTION}() RETURNS trigger
        LANGUAGE plpgsql SECURITY INVOKER SET search_path = pg_catalog
        AS $payment_identity$
        BEGIN
            RAISE EXCEPTION 'Payment evidence identity and amount are immutable'
                USING ERRCODE = '23514';
        END;
        $payment_identity$
    """)
    connection = op.get_bind()
    roles = connection.scalars(
        sa.text("""
            SELECT rolname FROM pg_catalog.pg_roles
            WHERE rolname IN :roles ORDER BY rolname
        """).bindparams(sa.bindparam("roles", expanding=True)),
        {"roles": _GATEWAY_ROLES},
    )
    quote = connection.dialect.identifier_preparer.quote_identifier
    grantees = ", ".join(("PUBLIC", *map(quote, roles)))
    op.execute(f"REVOKE ALL ON FUNCTION {schema}.{_FUNCTION}() FROM {grantees} RESTRICT")

    for table, columns in _EVIDENCE_COLUMNS.items():
        old = ", ".join(f"OLD.{column}" for column in columns)
        new = ", ".join(f"NEW.{column}" for column in columns)
        op.execute(f"""
            CREATE TRIGGER trg_{table}_evidence_identity
            AFTER UPDATE ON {schema}.{table} FOR EACH ROW
            WHEN (ROW({old}) IS DISTINCT FROM ROW({new}))
            EXECUTE FUNCTION {schema}.{_FUNCTION}()
        """)


def downgrade() -> None:
    schema = _postgres_schema()
    if schema is None:
        return
    for table in _EVIDENCE_COLUMNS:
        op.execute(f"DROP TRIGGER trg_{table}_evidence_identity ON {schema}.{table}")
    op.execute(f"DROP FUNCTION {schema}.{_FUNCTION}()")
