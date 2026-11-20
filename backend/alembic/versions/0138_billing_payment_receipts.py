"""Keep committed legacy billing receipts immutable."""

from alembic import op

revision = "0138_billing_payment_receipts"
down_revision = "0137_deposit_manual_receipts"
branch_labels = None
depends_on = None


def _quoted_schema() -> str:
    context = op.get_context()
    schema = context.opts.get("version_table_schema") or context.dialect.default_schema_name
    if not schema:
        raise RuntimeError("Trusted application schema required")
    return context.dialect.identifier_preparer.quote_schema(schema)


def upgrade() -> None:
    dialect = op.get_context().dialect.name
    if dialect == "postgresql":
        schema = _quoted_schema()
        op.execute(f"""
          CREATE FUNCTION {schema}.protect_billing_payment_receipt() RETURNS trigger
          LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog AS $billing_receipt$
          BEGIN
            IF TG_OP='DELETE' THEN
              IF OLD.endpoint='billing' THEN
                RAISE EXCEPTION 'immutable billing payment receipt' USING ERRCODE='23514';
              END IF;
              RETURN OLD;
            END IF;
            IF TG_OP='UPDATE' THEN
              IF (OLD.endpoint='billing' OR NEW.endpoint='billing') AND NOT (
                OLD.endpoint='billing' AND OLD.created_by IS NOT NULL AND NEW.created_by IS NULL
                AND (pg_catalog.to_jsonb(NEW)-'created_by')=(pg_catalog.to_jsonb(OLD)-'created_by')
              ) THEN
                RAISE EXCEPTION 'immutable billing payment receipt' USING ERRCODE='23514';
              END IF;
            ELSIF NEW.endpoint='billing' AND (
                NEW.created_by IS NULL OR length(NEW.client_request_id)<>36
                OR NEW.request_fingerprint IS NULL OR length(NEW.request_fingerprint)<>64
                OR (NEW.response_payload->>'recorded_by') IS DISTINCT FROM NEW.created_by::text
            ) THEN
              RAISE EXCEPTION 'invalid billing payment receipt' USING ERRCODE='23514';
            END IF;
            RETURN NEW;
          END $billing_receipt$
        """)
        op.execute(f"REVOKE ALL ON FUNCTION {schema}.protect_billing_payment_receipt() FROM PUBLIC")
        op.execute(f"""
          CREATE TRIGGER trg_protect_billing_payment_receipt BEFORE INSERT OR UPDATE OR DELETE
          ON {schema}.payment_client_requests FOR EACH ROW
          EXECUTE FUNCTION {schema}.protect_billing_payment_receipt()
        """)
    elif dialect == "sqlite":
        op.execute("""
          CREATE TRIGGER trg_billing_payment_receipt_insert BEFORE INSERT ON payment_client_requests
          WHEN NEW.endpoint='billing' AND (
            NEW.created_by IS NULL OR length(NEW.client_request_id)<>36
            OR NEW.request_fingerprint IS NULL OR length(NEW.request_fingerprint)<>64
            OR json_extract(NEW.response_payload,'$.recorded_by') IS NOT NEW.created_by
          )
          BEGIN SELECT RAISE(ABORT,'invalid billing payment receipt'); END
        """)
        op.execute("""
          CREATE TRIGGER trg_billing_payment_receipt_update BEFORE UPDATE ON payment_client_requests
          WHEN (OLD.endpoint='billing' OR NEW.endpoint='billing') AND NOT (
            OLD.endpoint='billing' AND OLD.created_by IS NOT NULL AND NEW.created_by IS NULL
            AND NEW.id IS OLD.id AND NEW.endpoint IS OLD.endpoint AND NEW.created_at IS OLD.created_at
            AND NEW.client_request_id IS OLD.client_request_id AND NEW.response_payload IS OLD.response_payload
            AND NEW.request_fingerprint IS OLD.request_fingerprint
          )
          BEGIN SELECT RAISE(ABORT,'immutable billing payment receipt'); END
        """)
        op.execute("""
          CREATE TRIGGER trg_billing_payment_receipt_delete BEFORE DELETE ON payment_client_requests
          WHEN OLD.endpoint='billing'
          BEGIN SELECT RAISE(ABORT,'immutable billing payment receipt'); END
        """)
    else:
        raise RuntimeError("Unsupported billing payment receipt dialect")


def downgrade() -> None:
    dialect = op.get_context().dialect.name
    if dialect == "postgresql":
        schema = _quoted_schema()
        op.execute("SET LOCAL row_security=off")
        op.execute(f"LOCK TABLE {schema}.payment_client_requests IN ACCESS EXCLUSIVE MODE")
        delimiter = "$billing_receipt_rollback$"
        while delimiter in schema:
            delimiter = delimiter[:-1] + "_x$"
        op.execute(f"""DO {delimiter} BEGIN
          IF EXISTS (SELECT 1 FROM {schema}.payment_client_requests WHERE endpoint='billing') THEN
            RAISE EXCEPTION 'billing payment receipts prevent downgrade';
          END IF;
        END {delimiter}""")
        op.execute(f"DROP TRIGGER trg_protect_billing_payment_receipt ON {schema}.payment_client_requests")
        op.execute(f"DROP FUNCTION {schema}.protect_billing_payment_receipt()")
    elif dialect == "sqlite":
        op.execute("UPDATE payment_client_requests SET id=id WHERE 0")
        op.execute("CREATE TEMP TABLE billing_payment_downgrade_guard (valid INTEGER NOT NULL CHECK(valid=1))")
        op.execute("""INSERT INTO billing_payment_downgrade_guard SELECT CASE WHEN EXISTS (
          SELECT 1 FROM payment_client_requests WHERE endpoint='billing') THEN 0 ELSE 1 END""")
        op.execute("DROP TABLE billing_payment_downgrade_guard")
        for event in ("insert", "update", "delete"):
            op.execute(f"DROP TRIGGER trg_billing_payment_receipt_{event}")
    else:
        raise RuntimeError("Unsupported billing payment receipt dialect")
