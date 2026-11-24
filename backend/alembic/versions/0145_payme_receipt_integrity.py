"""Preserve the original evidence for Payme creation receipts."""

from alembic import op

revision = "0145_payme_receipt_integrity"
down_revision = "0144_audit_log_truncate_guard"
branch_labels = None
depends_on = None


def _postgres_target() -> tuple[str, str] | None:
    context = op.get_context()
    if context.dialect.name == "sqlite":
        return None
    if context.dialect.name != "postgresql":
        raise RuntimeError("Unsupported Payme receipt dialect")
    name = context.opts.get("version_table_schema") or context.dialect.default_schema_name
    if not name:
        raise RuntimeError("Trusted application schema required")
    schema = context.dialect.identifier_preparer.quote_schema(name)
    delimiter = "$payme_receipt$"
    while delimiter in schema:
        delimiter = delimiter[:-1] + "_x$"
    return schema, delimiter


def upgrade() -> None:
    target = _postgres_target()
    if target is None:
        return
    schema, delimiter = target
    op.execute(f"""
      CREATE FUNCTION {schema}.protect_payme_creation_receipt() RETURNS trigger
      LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog SET row_security=off AS {delimiter}
      BEGIN
        IF TG_OP = 'TRUNCATE' THEN
          -- Fail closed if the caller cannot inspect the complete table under RLS.
          IF EXISTS (
            SELECT 1 FROM {schema}.payment_webhooks
            WHERE provider = 'payme' AND status = 'processed' AND raw_data->>'method' = 'CreateTransaction'
          ) THEN
            RAISE EXCEPTION 'Payme creation receipt evidence is immutable' USING ERRCODE='23514';
          END IF;
          RETURN NULL;
        END IF;

        IF TG_OP = 'DELETE' THEN
          IF OLD.provider = 'payme' AND OLD.status = 'processed' AND OLD.raw_data->>'method' = 'CreateTransaction' THEN
            RAISE EXCEPTION 'Payme creation receipt evidence is immutable' USING ERRCODE='23514';
          END IF;
          RETURN OLD;
        END IF;

        IF (OLD.provider = 'payme' AND OLD.raw_data->>'method' = 'CreateTransaction')
           OR (NEW.provider = 'payme' AND NEW.raw_data->>'method' = 'CreateTransaction') THEN
          IF ROW(OLD.id, OLD.provider, OLD.webhook_id, OLD.transaction_id, OLD.amount,
                 OLD.currency, OLD.raw_data::text, OLD.signature, OLD.created_at)
             IS DISTINCT FROM
             ROW(NEW.id, NEW.provider, NEW.webhook_id, NEW.transaction_id, NEW.amount,
                 NEW.currency, NEW.raw_data::text, NEW.signature, NEW.created_at)
             OR (OLD.status = 'processed' AND
                 ROW(OLD.status, OLD.processed_at) IS DISTINCT FROM ROW(NEW.status, NEW.processed_at)) THEN
            RAISE EXCEPTION 'Payme creation receipt evidence is immutable' USING ERRCODE='23514';
          END IF;
        END IF;
        RETURN NEW;
      END {delimiter}
    """)
    op.execute(f"REVOKE ALL ON FUNCTION {schema}.protect_payme_creation_receipt() FROM PUBLIC")
    op.execute(f"""
      CREATE TRIGGER trg_payme_receipt_integrity BEFORE UPDATE OR DELETE
      ON {schema}.payment_webhooks FOR EACH ROW
      EXECUTE FUNCTION {schema}.protect_payme_creation_receipt()
    """)
    op.execute(f"""
      CREATE TRIGGER trg_payme_receipt_truncate BEFORE TRUNCATE
      ON {schema}.payment_webhooks FOR EACH STATEMENT
      EXECUTE FUNCTION {schema}.protect_payme_creation_receipt()
    """)


def downgrade() -> None:
    target = _postgres_target()
    if target is None:
        return
    schema, _ = target
    op.execute(f"DROP TRIGGER trg_payme_receipt_truncate ON {schema}.payment_webhooks")
    op.execute(f"DROP TRIGGER trg_payme_receipt_integrity ON {schema}.payment_webhooks")
    op.execute(f"DROP FUNCTION {schema}.protect_payme_creation_receipt()")
