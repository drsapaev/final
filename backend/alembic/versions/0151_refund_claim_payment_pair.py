"""Require a refund reservation and its linked request to cover the same payment."""

from alembic import op

revision = "0151_refund_claim_payment_pair"
down_revision = "0150_refund_deposit_amounts"
branch_labels = None
depends_on = None

_INDEX = "uq_refund_requests_id_payment"
_CONSTRAINT = "fk_payment_refund_claims_request_payment"


def _postgres_schema() -> str | None:
    context = op.get_context()
    if context.dialect.name == "sqlite":
        return None
    if context.dialect.name != "postgresql":
        raise RuntimeError("Unsupported refund claim dialect")
    schema = context.opts.get("version_table_schema") or context.dialect.default_schema_name
    if not schema:
        raise RuntimeError("Trusted application schema required")
    return schema


def upgrade() -> None:
    schema = _postgres_schema()
    if schema is None:
        return

    quoted = op.get_context().dialect.identifier_preparer.quote_schema(schema)
    delimiter = "$refund_claim_payment$"
    while delimiter in quoted:
        delimiter = delimiter[:-1] + "_x$"

    # Keep the existing ON DELETE SET NULL on refund_request_id only. It
    # clears the reference before the new pair is rechecked at commit.
    # Build and validate in one transaction so dirty data cannot leave
    # a partially installed constraint or return identifiers in the error.
    op.execute(f"""
        DO {delimiter}
        DECLARE original_timeout text := pg_catalog.current_setting('lock_timeout');
        BEGIN
            IF (SELECT setting::integer FROM pg_catalog.pg_settings WHERE name = 'lock_timeout')
                NOT BETWEEN 1 AND 2000 THEN
                PERFORM pg_catalog.set_config('lock_timeout', '2s', true);
            END IF;
            CREATE UNIQUE INDEX {_INDEX} ON {quoted}.refund_requests (id, payment_id);
            ALTER TABLE {quoted}.payment_refund_claims
                ADD CONSTRAINT {_CONSTRAINT}
                FOREIGN KEY (refund_request_id, payment_id)
                REFERENCES {quoted}.refund_requests (id, payment_id)
                DEFERRABLE INITIALLY DEFERRED NOT VALID;
            BEGIN
                ALTER TABLE {quoted}.payment_refund_claims VALIDATE CONSTRAINT {_CONSTRAINT};
            EXCEPTION WHEN foreign_key_violation THEN
                RAISE EXCEPTION USING
                    ERRCODE = '23503',
                    MESSAGE = 'Refund claims require payment reconciliation';
            END;
            PERFORM pg_catalog.set_config('lock_timeout', original_timeout, true);
        END {delimiter}
    """)


def downgrade() -> None:
    schema = _postgres_schema()
    if schema is None:
        return
    op.drop_constraint(_CONSTRAINT, "payment_refund_claims", schema=schema, type_="foreignkey")
    op.drop_index(_INDEX, table_name="refund_requests", schema=schema)
