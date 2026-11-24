"""Prevent duplicate allocation links for the same payment and visit."""

from alembic import op

revision = "0156_payment_visit_pair_unique"
down_revision = "0155_finance_trigger_acl"
branch_labels = None
depends_on = None

_INDEX = "uq_payment_visits_payment_visit"


def _postgres_schema() -> str | None:
    context = op.get_context()
    if context.dialect.name == "sqlite":
        return None
    if context.dialect.name != "postgresql" or context.as_sql:
        raise RuntimeError("Payment visit link uniqueness requires online PostgreSQL")
    schema = context.opts.get("version_table_schema") or context.dialect.default_schema_name
    if not schema:
        raise RuntimeError("Trusted financial schema required")
    return schema


def upgrade() -> None:
    schema = _postgres_schema()
    if schema is None:
        return
    quoted = op.get_context().dialect.identifier_preparer.quote_schema(schema)
    delimiter = "$payment_visit_unique$"
    while delimiter in quoted:
        delimiter = delimiter[:-1] + "_x$"

    op.execute(f"""
        DO {delimiter}
        DECLARE original_timeout text := pg_catalog.current_setting('lock_timeout');
        BEGIN
            IF (SELECT setting::integer FROM pg_catalog.pg_settings WHERE name = 'lock_timeout')
                NOT BETWEEN 1 AND 2000 THEN
                PERFORM pg_catalog.set_config('lock_timeout', '2s', true);
            END IF;
            BEGIN
                CREATE UNIQUE INDEX {_INDEX} ON {quoted}.payment_visits (payment_id, visit_id);
            EXCEPTION WHEN unique_violation THEN
                RAISE EXCEPTION USING ERRCODE = '23505',
                    MESSAGE = 'Payment visit links require reconciliation';
            END;
            PERFORM pg_catalog.set_config('lock_timeout', original_timeout, true);
        END {delimiter}
    """)


def downgrade() -> None:
    schema = _postgres_schema()
    if schema is not None:
        op.drop_index(_INDEX, table_name="payment_visits", schema=schema)
