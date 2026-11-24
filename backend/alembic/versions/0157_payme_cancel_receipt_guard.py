"""Store the original Payme cancellation outcome with the payment transaction."""

import sqlalchemy as sa
from alembic import op

revision = "0157_payme_cancel_receipt_guard"
down_revision = "0156_payment_visit_pair_unique"
branch_labels = None
depends_on = None

_TABLE = "payment_transactions"
_COLUMN = "payme_cancel_receipt"


def _postgres_schema() -> tuple[str, str] | None:
    context = op.get_context()
    if context.dialect.name == "sqlite":
        return None
    if context.dialect.name != "postgresql" or context.as_sql:
        raise RuntimeError("Payme cancellation receipt protection requires online PostgreSQL")
    schema = context.opts.get("version_table_schema") or context.dialect.default_schema_name
    if not schema:
        raise RuntimeError("Trusted financial schema required")
    return schema, context.dialect.identifier_preparer.quote_schema(schema)


def upgrade() -> None:
    target = _postgres_schema()
    op.add_column(_TABLE, sa.Column(_COLUMN, sa.JSON(none_as_null=True), nullable=True),
                  schema=target[0] if target else None)
    if target is None:
        return

    _, schema = target
    delimiter = "$payme_cancel_receipt$"
    while delimiter in schema:
        delimiter = delimiter[:-1] + "_x$"
    op.execute(f"""
        CREATE FUNCTION {schema}.protect_payme_cancel_receipt() RETURNS trigger
        LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog SET row_security=off AS {delimiter}
        BEGIN
            IF TG_OP = 'TRUNCATE' THEN
                IF EXISTS (SELECT 1 FROM {schema}.{_TABLE} WHERE {_COLUMN} IS NOT NULL) THEN
                    RAISE EXCEPTION 'Payme cancellation evidence is immutable' USING ERRCODE = '23514';
                END IF;
                RETURN NULL;
            END IF;

            IF TG_OP = 'DELETE' THEN
                IF OLD.{_COLUMN} IS NOT NULL THEN
                    RAISE EXCEPTION 'Payme cancellation evidence is immutable' USING ERRCODE = '23514';
                END IF;
                RETURN OLD;
            END IF;

            IF TG_OP = 'UPDATE' AND OLD.{_COLUMN} IS NOT NULL AND (
                OLD.{_COLUMN}::jsonb IS DISTINCT FROM NEW.{_COLUMN}::jsonb OR
                ROW(OLD.id, OLD.provider, OLD.transaction_id) IS DISTINCT FROM
                ROW(NEW.id, NEW.provider, NEW.transaction_id)
            ) THEN
                RAISE EXCEPTION 'Payme cancellation evidence is immutable' USING ERRCODE = '23514';
            END IF;
            IF NEW.{_COLUMN} IS NOT NULL AND (
                NEW.provider IS DISTINCT FROM 'payme' OR
                pg_catalog.json_typeof(NEW.{_COLUMN}) IS DISTINCT FROM 'object'
            ) THEN
                RAISE EXCEPTION 'Invalid Payme cancellation evidence' USING ERRCODE = '23514';
            END IF;
            RETURN NEW;
        END {delimiter}
    """)
    op.execute(f"REVOKE ALL ON FUNCTION {schema}.protect_payme_cancel_receipt() FROM PUBLIC")
    op.execute(f"""
        CREATE TRIGGER trg_payme_cancel_receipt_row BEFORE INSERT OR UPDATE OR DELETE
        ON {schema}.{_TABLE} FOR EACH ROW EXECUTE FUNCTION {schema}.protect_payme_cancel_receipt()
    """)
    op.execute(f"""
        CREATE TRIGGER trg_payme_cancel_receipt_truncate BEFORE TRUNCATE
        ON {schema}.{_TABLE} FOR EACH STATEMENT EXECUTE FUNCTION {schema}.protect_payme_cancel_receipt()
    """)


def downgrade() -> None:
    target = _postgres_schema()
    table = _TABLE
    if target is not None:
        _, schema = target
        table = f"{schema}.{_TABLE}"
        op.execute("SET LOCAL row_security = off")
        op.execute(f"LOCK TABLE {table} IN ACCESS EXCLUSIVE MODE")

    if op.get_bind().execute(sa.text(f"SELECT 1 FROM {table} WHERE {_COLUMN} IS NOT NULL LIMIT 1")).first():
        raise RuntimeError("Reconcile Payme cancellation evidence before downgrading")

    if target is not None:
        op.execute(f"DROP TRIGGER trg_payme_cancel_receipt_truncate ON {table}")
        op.execute(f"DROP TRIGGER trg_payme_cancel_receipt_row ON {table}")
        op.execute(f"DROP FUNCTION {schema}.protect_payme_cancel_receipt()")
    op.drop_column(_TABLE, _COLUMN, schema=target[0] if target else None)
