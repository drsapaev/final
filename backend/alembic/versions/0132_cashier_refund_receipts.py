"""Protect durable cashier refund receipts without changing purchase anchors."""

from alembic import op

revision = "0132_cashier_refund_receipts"
down_revision = "0131_bank_refund_currency"
branch_labels = None
depends_on = None


def _postgres_schema() -> str:
    context = op.get_context()
    schema = context.opts.get("version_table_schema") or context.dialect.default_schema_name
    if not schema:
        raise RuntimeError("Trusted application schema required")
    return context.dialect.identifier_preparer.quote_schema(schema)


def upgrade() -> None:
    dialect = op.get_context().dialect.name
    if dialect == "postgresql":
        schema = _postgres_schema()
        op.execute(f"""
          CREATE FUNCTION {schema}.protect_cashier_refund_receipt() RETURNS trigger
          LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog AS $refund_receipt$
          BEGIN
            IF TG_OP='DELETE' THEN
              IF OLD.endpoint='refund' THEN RAISE EXCEPTION 'immutable cashier refund receipt'; END IF;
              RETURN OLD;
            END IF;
            IF TG_OP='UPDATE' THEN
              IF (NEW.endpoint='refund' OR OLD.endpoint='refund') AND NOT (
                OLD.endpoint='refund' AND OLD.created_by IS NOT NULL AND NEW.created_by IS NULL
                AND (pg_catalog.to_jsonb(NEW)-'created_by')=(pg_catalog.to_jsonb(OLD)-'created_by')
              ) THEN RAISE EXCEPTION 'immutable cashier refund receipt'; END IF;
            ELSIF NEW.endpoint='refund' AND (NEW.created_by IS NULL OR length(NEW.client_request_id)<>36
                  OR NEW.request_fingerprint IS NULL OR length(NEW.request_fingerprint)<>64) THEN
              RAISE EXCEPTION 'invalid cashier refund receipt';
            END IF;
            RETURN NEW;
          END $refund_receipt$
        """)
        op.execute(f"""
          CREATE TRIGGER trg_protect_cashier_refund_receipt BEFORE INSERT OR UPDATE OR DELETE
          ON {schema}.payment_client_requests FOR EACH ROW EXECUTE FUNCTION {schema}.protect_cashier_refund_receipt()
        """)
    elif dialect == "sqlite":
        op.execute("""
          CREATE TRIGGER trg_cashier_refund_receipt_insert BEFORE INSERT ON payment_client_requests
          WHEN NEW.endpoint='refund' AND (NEW.created_by IS NULL OR length(NEW.client_request_id)<>36
            OR NEW.request_fingerprint IS NULL OR length(NEW.request_fingerprint)<>64)
          BEGIN SELECT RAISE(ABORT,'invalid cashier refund receipt'); END
        """)
        op.execute("""
          CREATE TRIGGER trg_cashier_refund_receipt_update BEFORE UPDATE ON payment_client_requests
          WHEN (NEW.endpoint='refund' OR OLD.endpoint='refund') AND NOT (
            OLD.endpoint='refund' AND OLD.created_by IS NOT NULL AND NEW.created_by IS NULL
            AND NEW.id IS OLD.id AND NEW.endpoint IS OLD.endpoint AND NEW.created_at IS OLD.created_at
            AND NEW.client_request_id IS OLD.client_request_id AND NEW.response_payload IS OLD.response_payload
            AND NEW.request_fingerprint IS OLD.request_fingerprint)
          BEGIN SELECT RAISE(ABORT,'immutable cashier refund receipt'); END
        """)
        op.execute("""
          CREATE TRIGGER trg_cashier_refund_receipt_delete BEFORE DELETE ON payment_client_requests
          WHEN OLD.endpoint='refund' BEGIN SELECT RAISE(ABORT,'immutable cashier refund receipt'); END
        """)
    else:
        raise RuntimeError("Unsupported cashier refund receipt dialect")


def downgrade() -> None:
    dialect = op.get_context().dialect.name
    if dialect == "postgresql":
        schema = _postgres_schema()
        op.execute("SET LOCAL row_security=off")
        op.execute(f"LOCK TABLE {schema}.payment_client_requests IN ACCESS EXCLUSIVE MODE")
        delimiter = "$refund_receipt_rollback$"
        while delimiter in schema:
            delimiter = delimiter[:-1] + "_x$"
        op.execute(f"""DO {delimiter} BEGIN
          IF EXISTS (SELECT 1 FROM {schema}.payment_client_requests WHERE endpoint='refund') THEN
            RAISE EXCEPTION 'cashier refund receipts prevent downgrade';
          END IF;
        END {delimiter}""")
        op.execute(f"DROP TRIGGER trg_protect_cashier_refund_receipt ON {schema}.payment_client_requests")
        op.execute(f"DROP FUNCTION {schema}.protect_cashier_refund_receipt()")
    elif dialect == "sqlite":
        op.execute("UPDATE payment_client_requests SET id=id WHERE 0")
        op.execute("CREATE TEMP TABLE cashier_refund_downgrade_guard (valid INTEGER NOT NULL CHECK(valid=1))")
        op.execute("""INSERT INTO cashier_refund_downgrade_guard SELECT CASE WHEN EXISTS (
          SELECT 1 FROM payment_client_requests WHERE endpoint='refund') THEN 0 ELSE 1 END""")
        op.execute("DROP TABLE cashier_refund_downgrade_guard")
        for event in ("insert", "update", "delete"):
            op.execute(f"DROP TRIGGER trg_cashier_refund_receipt_{event}")
    else:
        raise RuntimeError("Unsupported cashier refund receipt dialect")
