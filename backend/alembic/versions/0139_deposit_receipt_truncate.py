"""Protect deposit receipts against statement-level PostgreSQL truncation."""

from alembic import op

revision = "0139_deposit_receipt_truncate"
down_revision = "0138_billing_payment_receipts"
branch_labels = None
depends_on = None


def _quoted_schema() -> str:
    context = op.get_context()
    name = context.opts.get("version_table_schema") or context.dialect.default_schema_name
    if not name:
        raise RuntimeError("Trusted application schema required")
    return context.dialect.identifier_preparer.quote_schema(name)


def upgrade() -> None:
    dialect = op.get_context().dialect.name
    if dialect == "sqlite":
        return
    if dialect != "postgresql":
        raise RuntimeError("Unsupported deposit receipt dialect")

    schema = _quoted_schema()
    op.execute(f"""
      CREATE FUNCTION {schema}.prevent_deposit_ledger_truncate() RETURNS trigger
      LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog AS $deposit_ledger$
      BEGIN
        RAISE EXCEPTION 'deposit receipt ledger cannot be truncated' USING ERRCODE='23514';
      END $deposit_ledger$
    """)
    op.execute(f"REVOKE ALL ON FUNCTION {schema}.prevent_deposit_ledger_truncate() FROM PUBLIC")
    op.execute(f"""
      CREATE TRIGGER trg_protect_deposit_receipt_truncate BEFORE TRUNCATE
      ON {schema}.deposit_transactions FOR EACH STATEMENT
      EXECUTE FUNCTION {schema}.prevent_deposit_ledger_truncate()
    """)


def downgrade() -> None:
    dialect = op.get_context().dialect.name
    if dialect == "sqlite":
        return
    if dialect != "postgresql":
        raise RuntimeError("Unsupported deposit receipt dialect")

    schema = _quoted_schema()
    delimiter = "$deposit_ledger_rollback$"
    while delimiter in schema:
        delimiter = delimiter[:-1] + "_x$"
    op.execute("SET LOCAL row_security=off")
    op.execute(f"LOCK TABLE {schema}.deposit_transactions IN ACCESS EXCLUSIVE MODE")
    op.execute(f"""DO {delimiter} BEGIN
      IF EXISTS (SELECT 1 FROM {schema}.deposit_transactions
          WHERE client_request_id IS NOT NULL OR refund_currency_snapshot IS NOT NULL) THEN
        RAISE EXCEPTION 'deposit receipts prevent downgrade';
      END IF;
    END {delimiter}""")
    op.execute(f"DROP TRIGGER trg_protect_deposit_receipt_truncate ON {schema}.deposit_transactions")
    op.execute(f"DROP FUNCTION {schema}.prevent_deposit_ledger_truncate()")
