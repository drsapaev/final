"""Store append-only human evidence reviews for Click callbacks.

These records alone never change a payment or authorize a refund. The guard
continues to block until a separately validated no-debit review is integrated.
"""
import hashlib

import sqlalchemy as sa

from alembic import op

revision = "0129_click_reconciliation"
down_revision = "0128_invitation_price_approval"
branch_labels = None
depends_on = None


def _capability_schema_name(schema: str) -> str:
    # Frozen v1, parity with 0112 and app.db.capability_namespace.
    if not isinstance(schema, str) or not schema or "\0" in schema:
        raise ValueError("Invalid application schema")
    raw = schema.encode("utf-8")
    if len(raw) > 63:
        raise ValueError("Application schema exceeds PostgreSQL identifier limit")
    return "clinic_internal_" + hashlib.sha256(b"clinic-capability-schema-v1\0" + raw).hexdigest()[:32]


def upgrade() -> None:
    context = op.get_context()
    dialect = context.dialect.name
    if dialect not in {"postgresql", "sqlite"}:
        raise RuntimeError("Unsupported Click review dialect")
    op.create_table(
        "click_reconciliation_reviews",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("receipt_id", sa.Integer(), sa.ForeignKey("click_callback_receipts.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("event_id", sa.Integer(), sa.ForeignKey("provider_reconciliation_events.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("issued_attempt_id", sa.Integer(), sa.ForeignKey("click_issued_attempts.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("prepare_id", sa.Integer(), sa.ForeignKey("click_prepares.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("actor_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("actor_user_id_snapshot", sa.Integer(), nullable=False),
        sa.Column("actor_role", sa.String(32), nullable=False),
        sa.Column("review_sequence", sa.Integer(), nullable=False),
        sa.Column("receipt_sha256", sa.String(64), nullable=False),
        sa.Column("event_snapshot_sha256", sa.String(64), nullable=False),
        sa.Column("target_context_sha256", sa.String(64), nullable=False),
        sa.Column("proof_sha256", sa.String(64), nullable=False),
        sa.Column("proof_key_version", sa.String(32), sa.ForeignKey("click_receipt_key_versions.version", ondelete="RESTRICT"), nullable=False),
        sa.Column("proof_ciphertext", sa.LargeBinary(), nullable=False),
        sa.Column("proof_size", sa.Integer(), nullable=False),
        sa.Column("source_kind", sa.String(24), nullable=False),
        sa.Column("result", sa.String(24), nullable=False),
        sa.Column("reason_code", sa.String(32), nullable=False),
        sa.Column("amount_minor", sa.String(128), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("receipt_id", "review_sequence", name="uq_click_review_sequence"),
        sa.CheckConstraint("actor_user_id_snapshot>0 AND (actor_user_id IS NULL OR actor_user_id=actor_user_id_snapshot)", name="ck_click_review_actor"),
        sa.CheckConstraint("review_sequence BETWEEN 1 AND 64", name="ck_click_review_sequence"),
        sa.CheckConstraint("length(receipt_sha256)=64 AND length(event_snapshot_sha256)=64 AND length(target_context_sha256)=64 AND length(proof_sha256)=64", name="ck_click_review_digests"),
        sa.CheckConstraint("proof_size BETWEEN 1 AND 262144 AND length(proof_ciphertext)=proof_size+16", name="ck_click_review_size"),
        sa.CheckConstraint("receipt_sha256 ~ '^[0-9a-f]{64}$' AND event_snapshot_sha256 ~ '^[0-9a-f]{64}$' AND target_context_sha256 ~ '^[0-9a-f]{64}$' AND proof_sha256 ~ '^[0-9a-f]{64}$'" if dialect == "postgresql" else "receipt_sha256 NOT GLOB '*[^0-9a-f]*' AND event_snapshot_sha256 NOT GLOB '*[^0-9a-f]*' AND target_context_sha256 NOT GLOB '*[^0-9a-f]*' AND proof_sha256 NOT GLOB '*[^0-9a-f]*'", name="ck_click_review_digest_format"),
        sa.CheckConstraint("source_kind IN ('provider_portal','official_document')", name="ck_click_review_source"),
        sa.CheckConstraint("(result='no_debit' AND reason_code IN ('provider_cancelled','provider_failed')) OR (result='debit_confirmed' AND reason_code='provider_confirmed_debit')", name="ck_click_review_result"),
        sa.CheckConstraint("currency='UZS' AND length(amount_minor) BETWEEN 1 AND 128", name="ck_click_review_amount"),
        sa.CheckConstraint("amount_minor ~ '^(0|[1-9][0-9]*)$'" if dialect == "postgresql" else "amount_minor NOT GLOB '*[^0-9]*' AND (length(amount_minor)=1 OR substr(amount_minor,1,1)<>'0')", name="ck_click_review_amount_digits"),
    )
    if dialect == "sqlite":
        op.execute("""CREATE TRIGGER reconciliation_event_no_delete BEFORE DELETE ON provider_reconciliation_events
          BEGIN SELECT RAISE(ABORT, 'Provider evidence is immutable'); END""")
        op.execute("""CREATE TRIGGER reconciliation_event_immutable BEFORE UPDATE ON provider_reconciliation_events
          WHEN NEW.id IS NOT OLD.id OR NEW.provider IS NOT OLD.provider OR NEW.source IS NOT OLD.source
            OR NEW.phase IS NOT OLD.phase OR NEW.event_key IS NOT OLD.event_key
            OR NEW.provider_transaction_id IS NOT OLD.provider_transaction_id
            OR NEW.provider_reference_digest IS NOT OLD.provider_reference_digest OR NEW.target_kind IS NOT OLD.target_kind
            OR NEW.payment_id_snapshot IS NOT OLD.payment_id_snapshot OR NEW.invoice_id_snapshot IS NOT OLD.invoice_id_snapshot
            OR NEW.webhook_id_snapshot IS NOT OLD.webhook_id_snapshot OR NEW.amount_minor IS NOT OLD.amount_minor
            OR NEW.currency IS NOT OLD.currency OR NEW.currency_exponent IS NOT OLD.currency_exponent
            OR NEW.observed_status IS NOT OLD.observed_status OR NEW.evidence_sha256 IS NOT OLD.evidence_sha256
            OR NEW.status IS NOT OLD.status OR NEW.verified_at IS NOT OLD.verified_at OR NEW.created_at IS NOT OLD.created_at
            OR (NEW.payment_id IS NOT OLD.payment_id AND NEW.payment_id IS NOT NULL)
            OR (NEW.invoice_id IS NOT OLD.invoice_id AND NEW.invoice_id IS NOT NULL)
            OR (NEW.webhook_id IS NOT OLD.webhook_id AND NEW.webhook_id IS NOT NULL)
          BEGIN SELECT RAISE(ABORT, 'Provider evidence is immutable'); END""")
        op.execute("""CREATE TRIGGER click_review_no_update BEFORE UPDATE ON click_reconciliation_reviews
          WHEN NOT (OLD.actor_user_id IS NOT NULL AND NEW.actor_user_id IS NULL
            AND NEW.id IS OLD.id AND NEW.receipt_id IS OLD.receipt_id AND NEW.event_id IS OLD.event_id
            AND NEW.issued_attempt_id IS OLD.issued_attempt_id AND NEW.prepare_id IS OLD.prepare_id
            AND NEW.actor_user_id_snapshot IS OLD.actor_user_id_snapshot AND NEW.actor_role IS OLD.actor_role
            AND NEW.review_sequence IS OLD.review_sequence AND NEW.receipt_sha256 IS OLD.receipt_sha256
            AND NEW.event_snapshot_sha256 IS OLD.event_snapshot_sha256 AND NEW.target_context_sha256 IS OLD.target_context_sha256
            AND NEW.proof_sha256 IS OLD.proof_sha256 AND NEW.proof_key_version IS OLD.proof_key_version
            AND NEW.proof_ciphertext IS OLD.proof_ciphertext AND NEW.proof_size IS OLD.proof_size
            AND NEW.source_kind IS OLD.source_kind AND NEW.result IS OLD.result AND NEW.reason_code IS OLD.reason_code
            AND NEW.amount_minor IS OLD.amount_minor AND NEW.currency IS OLD.currency
            AND NEW.reviewed_at IS OLD.reviewed_at AND NEW.created_at IS OLD.created_at)
          BEGIN SELECT RAISE(ABORT, 'Click review is immutable'); END""")
        op.execute("CREATE TRIGGER click_review_no_delete BEFORE DELETE ON click_reconciliation_reviews BEGIN SELECT RAISE(ABORT, 'Click review is immutable'); END")
        op.execute("""CREATE TRIGGER click_review_mutex BEFORE INSERT ON click_reconciliation_reviews
          BEGIN UPDATE provider_reconciliation_mutex SET id=id WHERE id=1; END""")
        return
    schema = context.opts.get("version_table_schema") or context.dialect.default_schema_name
    if not schema:
        raise RuntimeError("Trusted migration schema required")
    q = context.dialect.identifier_preparer.quote_schema(schema)
    private = _capability_schema_name(schema)
    qp = context.dialect.identifier_preparer.quote_schema(private)
    literal_schema = schema.replace("'", "''")
    literal_private = private.replace("'", "''")
    tag = "$click_review_owner$"
    while tag in q:
        tag = tag[:-1] + "_x$"
    op.execute(f"""CREATE FUNCTION {q}.reconciliation_event_immutable() RETURNS trigger
      LANGUAGE plpgsql SET search_path=pg_catalog AS $$
      BEGIN
        IF TG_OP='DELETE' THEN RAISE EXCEPTION 'Provider evidence is immutable'; END IF;
        IF ROW(NEW.id,NEW.provider,NEW.source,NEW.phase,NEW.event_key,NEW.provider_transaction_id,
          NEW.provider_reference_digest,NEW.target_kind,NEW.payment_id_snapshot,NEW.invoice_id_snapshot,
          NEW.webhook_id_snapshot,NEW.amount_minor,NEW.currency,NEW.currency_exponent,NEW.observed_status,
          NEW.evidence_sha256,NEW.status,NEW.verified_at,NEW.created_at) IS DISTINCT FROM
          ROW(OLD.id,OLD.provider,OLD.source,OLD.phase,OLD.event_key,OLD.provider_transaction_id,
          OLD.provider_reference_digest,OLD.target_kind,OLD.payment_id_snapshot,OLD.invoice_id_snapshot,
          OLD.webhook_id_snapshot,OLD.amount_minor,OLD.currency,OLD.currency_exponent,OLD.observed_status,
          OLD.evidence_sha256,OLD.status,OLD.verified_at,OLD.created_at)
          OR (NEW.payment_id IS DISTINCT FROM OLD.payment_id AND NEW.payment_id IS NOT NULL)
          OR (NEW.invoice_id IS DISTINCT FROM OLD.invoice_id AND NEW.invoice_id IS NOT NULL)
          OR (NEW.webhook_id IS DISTINCT FROM OLD.webhook_id AND NEW.webhook_id IS NOT NULL) THEN
          RAISE EXCEPTION 'Provider evidence is immutable'; END IF;
        RETURN NEW;
      END $$""")
    op.execute(f"REVOKE ALL ON FUNCTION {q}.reconciliation_event_immutable() FROM PUBLIC")
    op.execute(f"CREATE TRIGGER reconciliation_event_immutable BEFORE UPDATE OR DELETE ON {q}.provider_reconciliation_events FOR EACH ROW EXECUTE FUNCTION {q}.reconciliation_event_immutable()")
    op.execute(f"""CREATE FUNCTION {qp}.click_review_mutex_lock() RETURNS trigger
      LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog SET row_security=on AS {tag}
      DECLARE found_id integer; BEGIN
        SELECT id INTO found_id FROM {q}.provider_reconciliation_mutex WHERE id=1 FOR UPDATE NOWAIT;
        IF found_id IS DISTINCT FROM 1 THEN RAISE EXCEPTION 'Reconciliation mutex unavailable'; END IF;
        RETURN NEW;
      END {tag}""")
    op.execute(f"REVOKE ALL ON FUNCTION {qp}.click_review_mutex_lock() FROM PUBLIC")
    op.execute(f"""CREATE FUNCTION {q}.click_review_immutable() RETURNS trigger
      LANGUAGE plpgsql SET search_path=pg_catalog AS $$
      BEGIN
        IF TG_OP='UPDATE' AND OLD.actor_user_id IS NOT NULL AND NEW.actor_user_id IS NULL
          AND ROW(NEW.id,NEW.receipt_id,NEW.event_id,NEW.issued_attempt_id,NEW.prepare_id,NEW.actor_user_id_snapshot,
            NEW.actor_role,NEW.review_sequence,NEW.receipt_sha256,NEW.event_snapshot_sha256,NEW.target_context_sha256,NEW.proof_sha256,NEW.proof_key_version,
            NEW.proof_ciphertext,NEW.proof_size,NEW.source_kind,NEW.result,NEW.reason_code,NEW.amount_minor,
            NEW.currency,NEW.reviewed_at,NEW.created_at) IS NOT DISTINCT FROM
          ROW(OLD.id,OLD.receipt_id,OLD.event_id,OLD.issued_attempt_id,OLD.prepare_id,OLD.actor_user_id_snapshot,
            OLD.actor_role,OLD.review_sequence,OLD.receipt_sha256,OLD.event_snapshot_sha256,OLD.target_context_sha256,OLD.proof_sha256,OLD.proof_key_version,
            OLD.proof_ciphertext,OLD.proof_size,OLD.source_kind,OLD.result,OLD.reason_code,OLD.amount_minor,
            OLD.currency,OLD.reviewed_at,OLD.created_at) THEN RETURN NEW; END IF;
        RAISE EXCEPTION 'Click review is immutable';
      END $$""")
    op.execute(f"REVOKE ALL ON FUNCTION {q}.click_review_immutable() FROM PUBLIC")
    op.execute(f"""DO {tag} DECLARE trusted_owner name; BEGIN
      SELECT r.rolname INTO STRICT trusted_owner FROM pg_catalog.pg_namespace n
        JOIN pg_catalog.pg_roles r ON r.oid=n.nspowner WHERE n.nspname='{literal_schema}';
      EXECUTE pg_catalog.format('ALTER FUNCTION %I.click_review_immutable() OWNER TO %I', '{literal_schema}', trusted_owner);
      EXECUTE pg_catalog.format('ALTER FUNCTION %I.reconciliation_event_immutable() OWNER TO %I', '{literal_schema}', trusted_owner);
      EXECUTE pg_catalog.format('ALTER FUNCTION %I.click_review_mutex_lock() OWNER TO %I', '{literal_private}', trusted_owner);
      EXECUTE pg_catalog.format('ALTER TABLE %I.click_reconciliation_reviews OWNER TO %I', '{literal_schema}', trusted_owner);
      EXECUTE pg_catalog.format('CREATE POLICY click_review_owner_select ON %I.click_reconciliation_reviews FOR SELECT TO %I USING (true)', '{literal_schema}', trusted_owner);
      EXECUTE pg_catalog.format('CREATE POLICY click_review_owner_insert ON %I.click_reconciliation_reviews FOR INSERT TO %I WITH CHECK (true)', '{literal_schema}', trusted_owner);
    END {tag}""")
    op.execute(f"CREATE TRIGGER click_review_immutable BEFORE UPDATE OR DELETE ON {q}.click_reconciliation_reviews FOR EACH ROW EXECUTE FUNCTION {q}.click_review_immutable()")
    op.execute(f"CREATE TRIGGER click_review_mutex BEFORE INSERT ON {q}.click_reconciliation_reviews FOR EACH ROW EXECUTE FUNCTION {qp}.click_review_mutex_lock()")
    op.execute(f"ALTER TABLE {q}.click_reconciliation_reviews ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {q}.click_reconciliation_reviews FORCE ROW LEVEL SECURITY")
    op.execute(f"REVOKE ALL ON {q}.click_reconciliation_reviews FROM PUBLIC")
    op.execute(f"REVOKE ALL ON SEQUENCE {q}.click_reconciliation_reviews_id_seq FROM PUBLIC")


def downgrade() -> None:
    context = op.get_context()
    dialect = context.dialect.name
    if dialect == "postgresql":
        schema = context.opts.get("version_table_schema") or context.dialect.default_schema_name
        if not schema:
            raise RuntimeError("Trusted migration schema required")
        q = context.dialect.identifier_preparer.quote_schema(schema)
        qp = context.dialect.identifier_preparer.quote_schema(_capability_schema_name(schema))
        table = f"{q}.click_reconciliation_reviews"
        op.execute(f"LOCK TABLE {table} IN ACCESS EXCLUSIVE MODE")
        op.execute("SET LOCAL row_security=off")
    elif dialect == "sqlite":
        table = "click_reconciliation_reviews"
        op.execute("UPDATE click_reconciliation_reviews SET id=id WHERE 0")
    else:
        raise RuntimeError("Unsupported Click review dialect")
    op.execute("CREATE TEMPORARY TABLE click_review_downgrade_guard (valid integer NOT NULL CHECK(valid=1))")
    op.execute(f"INSERT INTO click_review_downgrade_guard SELECT CASE WHEN EXISTS(SELECT 1 FROM {table}) THEN 0 ELSE 1 END")
    op.execute("DROP TABLE click_review_downgrade_guard")
    if dialect == "postgresql":
        op.execute(f"DROP TRIGGER reconciliation_event_immutable ON {q}.provider_reconciliation_events")
        op.execute(f"DROP FUNCTION {q}.reconciliation_event_immutable()")
        op.execute(f"DROP TRIGGER click_review_mutex ON {table}")
        op.execute(f"DROP TRIGGER click_review_immutable ON {table}")
        op.execute(f"DROP FUNCTION {q}.click_review_immutable()")
        op.execute(f"DROP FUNCTION {qp}.click_review_mutex_lock()")
        op.drop_table("click_reconciliation_reviews", schema=schema)
    else:
        op.execute("DROP TRIGGER reconciliation_event_immutable")
        op.execute("DROP TRIGGER reconciliation_event_no_delete")
        for operation in ("update", "delete"):
            op.execute(f"DROP TRIGGER click_review_no_{operation}")
        op.execute("DROP TRIGGER click_review_mutex")
        op.drop_table("click_reconciliation_reviews")
