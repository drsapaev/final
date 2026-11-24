"""Protect refund reservations against whole-table truncation."""

from alembic import op

revision = "0152_refund_claim_truncate_guard"
down_revision = "0151_refund_claim_payment_pair"
branch_labels = None
depends_on = None

_TRIGGER = "payment_refund_claims_no_truncate"
_FUNCTION = "prevent_refund_claim_truncate"


def _postgres_schema() -> str | None:
    context = op.get_context()
    if context.dialect.name == "sqlite":
        return None
    if context.dialect.name != "postgresql":
        raise RuntimeError("Unsupported refund claim dialect")
    schema = context.opts.get("version_table_schema") or context.dialect.default_schema_name
    if not schema:
        raise RuntimeError("Trusted application schema required")
    return context.dialect.identifier_preparer.quote_schema(schema)


def upgrade() -> None:
    schema = _postgres_schema()
    if schema is None:
        return

    op.execute(f"""
        CREATE FUNCTION {schema}.{_FUNCTION}() RETURNS trigger
        LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog
        AS $refund_claim_guard$
        BEGIN
            RAISE EXCEPTION 'refund reservations cannot be truncated' USING ERRCODE='23514';
        END;
        $refund_claim_guard$
    """)
    op.execute(f"REVOKE ALL ON FUNCTION {schema}.{_FUNCTION}() FROM PUBLIC")
    op.execute(f"""
        CREATE TRIGGER {_TRIGGER} BEFORE TRUNCATE ON {schema}.payment_refund_claims
        FOR EACH STATEMENT EXECUTE FUNCTION {schema}.{_FUNCTION}()
    """)
    op.execute(f"ALTER TABLE {schema}.payment_refund_claims ENABLE ALWAYS TRIGGER {_TRIGGER}")


def downgrade() -> None:
    schema = _postgres_schema()
    if schema is None:
        return

    op.execute(f"DROP TRIGGER {_TRIGGER} ON {schema}.payment_refund_claims")
    op.execute(f"DROP FUNCTION {schema}.{_FUNCTION}()")
