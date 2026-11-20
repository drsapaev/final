"""Add immutable Click prepare and encrypted-receipt reconciliation links.

This schema does not authorize checkout, settle payments, or acknowledge Click.
Issuance, receipt-first dispatch and reviewed reconciliation remain prerequisites.
"""
import sqlalchemy as sa

from alembic import op

revision = "0127_click_phase_binding"
down_revision = "0126_invitation_issuer_auth"
branch_labels = None
depends_on = None


def upgrade() -> None:
    context = op.get_context()
    dialect = context.dialect.name
    if dialect not in {"sqlite", "postgresql"}:
        raise RuntimeError("Unsupported Click phase binding dialect")
    # The marker is issued only after the application locks/rechecks the full
    # attempt and all Visit allocations. No historical attempt is backfilled.
    binding_columns = ("id", "order_ref", "merchant_hash", "fingerprint", "amount_minor",
                       "currency", "currency_exponent", "provider", "target_kind", "actor_user_id_snapshot")
    op.create_index("uq_click_attempt_snapshot", "provider_attempts", list(binding_columns), unique=True)
    op.create_table(
        "click_issued_attempts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("attempt_id", sa.Integer(), nullable=False, unique=True),
        sa.Column("order_ref", sa.String(128), nullable=False),
        sa.Column("merchant_hash", sa.String(64), nullable=False),
        sa.Column("fingerprint", sa.String(64), nullable=False),
        sa.Column("amount_minor", sa.String(128), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("currency_exponent", sa.SmallInteger(), nullable=False),
        sa.Column("provider", sa.String(32), nullable=False),
        sa.Column("target_kind", sa.String(16), nullable=False),
        sa.Column("actor_user_id_snapshot", sa.Integer(), nullable=False),
        sa.Column("allocations_sha256", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(
            ["attempt_id", *binding_columns[1:]],
            [f"provider_attempts.{name}" for name in binding_columns],
            name="fk_click_issued_attempt_snapshot", ondelete="RESTRICT"),
        sa.CheckConstraint("provider='click' AND currency='UZS' AND currency_exponent=2", name="ck_click_issued_provider"),
        sa.CheckConstraint("length(allocations_sha256)=64", name="ck_click_issued_allocations"),
    )
    op.create_table(
        "click_prepares",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("attempt_id", sa.Integer(), sa.ForeignKey("click_issued_attempts.attempt_id", ondelete="RESTRICT"), nullable=False, unique=True),
        sa.Column("receipt_id", sa.Integer(), sa.ForeignKey("click_callback_receipts.id", ondelete="RESTRICT"), nullable=False, unique=True),
        sa.Column("click_trans_id", sa.String(128), nullable=False),
        sa.Column("service_id", sa.String(128), nullable=False),
        sa.Column("merchant_hash", sa.String(64), nullable=False),
        sa.Column("order_ref", sa.String(128), nullable=False),
        sa.Column("amount_minor", sa.String(128), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("service_id", "click_trans_id", name="uq_click_prepare_service_transaction"),
        sa.CheckConstraint("length(click_trans_id) BETWEEN 1 AND 128 AND length(service_id) BETWEEN 1 AND 128", name="ck_click_prepare_identifiers"),
        sa.CheckConstraint("length(order_ref) BETWEEN 1 AND 128 AND length(merchant_hash)=64", name="ck_click_prepare_order"),
        sa.CheckConstraint("length(amount_minor) BETWEEN 1 AND 128 AND (length(amount_minor)=1 OR substr(amount_minor,1,1)<>'0')", name="ck_click_prepare_amount"),
        sa.CheckConstraint("currency='UZS'", name="ck_click_prepare_currency"),
        sa.CheckConstraint("amount_minor ~ '^[0-9]+$'" if dialect == "postgresql" else "amount_minor NOT GLOB '*[^0-9]*'", name="ck_click_prepare_amount_digits"),
    )
    op.create_table(
        "click_receipt_reconciliation_links",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("receipt_id", sa.Integer(), sa.ForeignKey("click_callback_receipts.id", ondelete="RESTRICT"), nullable=False, unique=True),
        sa.Column("event_id", sa.Integer(), sa.ForeignKey("provider_reconciliation_events.id", ondelete="RESTRICT"), nullable=False, unique=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    if dialect == "sqlite":
        # A write reservation precedes the marker check; SQLite serializes all
        # competing writers. The PG implementation uses the parent row lock.
        op.execute("""CREATE TRIGGER click_issued_lock_attempt BEFORE INSERT ON click_issued_attempts
            BEGIN UPDATE provider_attempts SET id=id WHERE id=NEW.attempt_id; END""")
        for operation in ("INSERT", "UPDATE", "DELETE"):
            ref = "NEW" if operation == "INSERT" else "OLD"
            nullification = "" if operation != "UPDATE" else """ AND NOT (
                OLD.visit_id IS NOT NULL AND NEW.visit_id IS NULL
                AND NEW.id IS OLD.id AND NEW.attempt_id IS OLD.attempt_id
                AND NEW.visit_id_snapshot IS OLD.visit_id_snapshot AND NEW.patient_id_snapshot IS OLD.patient_id_snapshot
                AND NEW.context_epoch IS OLD.context_epoch AND NEW.amount_minor IS OLD.amount_minor
                AND NEW.created_at IS OLD.created_at)"""
            op.execute(f"""CREATE TRIGGER click_attempt_visit_{operation.lower()} BEFORE {operation} ON provider_attempt_visits
              WHEN EXISTS (SELECT 1 FROM click_issued_attempts WHERE attempt_id={ref}.attempt_id){nullification}
              BEGIN SELECT RAISE(ABORT, 'Issued allocation is immutable'); END""")
        op.execute("""CREATE TRIGGER click_attempt_snapshot_immutable BEFORE UPDATE ON provider_attempts
          WHEN (NEW.payment_id_snapshot IS NOT OLD.payment_id_snapshot OR NEW.invoice_id_snapshot IS NOT OLD.invoice_id_snapshot
            OR NEW.actor_user_id_snapshot IS NOT OLD.actor_user_id_snapshot OR NEW.public_id IS NOT OLD.public_id
            OR NEW.order_ref IS NOT OLD.order_ref OR NEW.fingerprint IS NOT OLD.fingerprint OR NEW.merchant_hash IS NOT OLD.merchant_hash
            OR NEW.amount_minor IS NOT OLD.amount_minor OR NEW.currency IS NOT OLD.currency OR NEW.currency_exponent IS NOT OLD.currency_exponent
            OR NEW.provider IS NOT OLD.provider OR NEW.target_kind IS NOT OLD.target_kind OR NEW.client_key_hash IS NOT OLD.client_key_hash
            OR (NEW.payment_id IS NOT OLD.payment_id AND NEW.payment_id IS NOT NULL)
            OR (NEW.invoice_id IS NOT OLD.invoice_id AND NEW.invoice_id IS NOT NULL)
            OR (NEW.actor_user_id IS NOT OLD.actor_user_id AND NEW.actor_user_id IS NOT NULL))
          BEGIN SELECT RAISE(ABORT, 'Attempt snapshot is immutable'); END""")
        for table in ("click_issued_attempts", "click_prepares", "click_receipt_reconciliation_links"):
            for operation in ("UPDATE", "DELETE"):
                op.execute(f"CREATE TRIGGER {table}_no_{operation.lower()} BEFORE {operation} ON {table} BEGIN SELECT RAISE(ABORT, 'Click binding is immutable'); END")
        return
    schema = context.opts.get("version_table_schema") or context.dialect.default_schema_name
    if not schema:
        raise RuntimeError("Trusted migration schema required")
    q = context.dialect.identifier_preparer.quote_schema(schema)
    literal_q = q.replace("'", "''")
    literal_schema = schema.replace("'", "''")
    tag_number = 0
    while True:
        tag = f"$click_binding_{tag_number}$"
        if tag not in q:
            break
        tag_number += 1
    # These invoker triggers require a provisioned RLS-visible backend; they
    # fail closed if that role cannot see every issued marker.
    op.execute(f"""
      CREATE FUNCTION {q}.click_binding_attempt_lock() RETURNS trigger
      LANGUAGE plpgsql SET search_path=pg_catalog SET row_security=on AS {tag}
      DECLARE attempt integer; visible boolean; is_issued boolean;
      BEGIN
        IF pg_catalog.current_setting('transaction_isolation') <> 'read committed' THEN
          RAISE EXCEPTION 'Issued allocation requires read committed'; END IF;
        IF TG_TABLE_NAME='click_issued_attempts' THEN attempt := NEW.attempt_id;
        ELSIF TG_OP='INSERT' THEN attempt := NEW.attempt_id;
        ELSE attempt := OLD.attempt_id; END IF;
        IF TG_TABLE_NAME='provider_attempt_visits' AND TG_OP='UPDATE'
          AND NEW.attempt_id IS DISTINCT FROM OLD.attempt_id THEN
          RAISE EXCEPTION 'Allocation attempt is immutable'; END IF;
        PERFORM id FROM {q}.click_issued_attempts WHERE false;
        SELECT NOT c.relrowsecurity OR (EXISTS (SELECT 1 FROM pg_catalog.pg_policy p
          WHERE p.polrelid=c.oid AND p.polpermissive AND p.polcmd IN ('r','*')
          AND (SELECT oid FROM pg_catalog.pg_roles WHERE rolname=CURRENT_USER)=ANY(p.polroles)
          AND pg_catalog.pg_get_expr(p.polqual,p.polrelid)='true')
          AND NOT EXISTS (SELECT 1 FROM pg_catalog.pg_policy p WHERE p.polrelid=c.oid
            AND NOT p.polpermissive AND p.polcmd IN ('r','*')
            AND EXISTS (SELECT 1 FROM pg_catalog.unnest(p.polroles) r
              WHERE r=0 OR pg_catalog.pg_has_role(CURRENT_USER,r,'MEMBER')))) INTO visible
          FROM pg_catalog.pg_class c WHERE c.oid='{literal_q}.click_issued_attempts'::pg_catalog.regclass;
        IF visible IS NOT TRUE THEN RAISE EXCEPTION 'Issued allocation visibility unavailable'; END IF;
        PERFORM id FROM {q}.provider_attempts WHERE id=attempt FOR UPDATE NOWAIT;
        IF NOT FOUND THEN RAISE EXCEPTION 'Attempt unavailable'; END IF;
        IF TG_TABLE_NAME='provider_attempt_visits' THEN
          SELECT EXISTS (SELECT 1 FROM {q}.click_issued_attempts WHERE attempt_id=attempt) INTO is_issued;
          IF is_issued THEN
            IF TG_OP='UPDATE' AND OLD.visit_id IS NOT NULL AND NEW.visit_id IS NULL
              AND ROW(NEW.id,NEW.attempt_id,NEW.visit_id_snapshot,NEW.patient_id_snapshot,NEW.context_epoch,NEW.amount_minor,NEW.created_at)
              IS NOT DISTINCT FROM ROW(OLD.id,OLD.attempt_id,OLD.visit_id_snapshot,OLD.patient_id_snapshot,OLD.context_epoch,OLD.amount_minor,OLD.created_at)
              THEN RETURN NEW; END IF;
            RAISE EXCEPTION 'Issued allocation is immutable';
          END IF;
        END IF;
        IF TG_OP='DELETE' THEN RETURN OLD; END IF;
        RETURN NEW;
      END {tag}
    """)
    op.execute(f"REVOKE ALL ON FUNCTION {q}.click_binding_attempt_lock() FROM PUBLIC")
    op.execute(f"CREATE TRIGGER click_issued_lock_attempt BEFORE INSERT ON {q}.click_issued_attempts FOR EACH ROW EXECUTE FUNCTION {q}.click_binding_attempt_lock()")
    op.execute(f"CREATE TRIGGER click_attempt_visit_lock BEFORE INSERT OR UPDATE OR DELETE ON {q}.provider_attempt_visits FOR EACH ROW EXECUTE FUNCTION {q}.click_binding_attempt_lock()")
    op.execute(f"""
      CREATE FUNCTION {q}.click_attempt_snapshot_immutable() RETURNS trigger
      LANGUAGE plpgsql SET search_path=pg_catalog AS $$
      BEGIN
        IF ROW(NEW.payment_id_snapshot,NEW.invoice_id_snapshot,NEW.actor_user_id_snapshot,NEW.public_id,
          NEW.order_ref,NEW.fingerprint,NEW.merchant_hash,NEW.amount_minor,NEW.currency,NEW.currency_exponent,
          NEW.provider,NEW.target_kind,NEW.client_key_hash) IS DISTINCT FROM
          ROW(OLD.payment_id_snapshot,OLD.invoice_id_snapshot,OLD.actor_user_id_snapshot,OLD.public_id,
          OLD.order_ref,OLD.fingerprint,OLD.merchant_hash,OLD.amount_minor,OLD.currency,OLD.currency_exponent,
          OLD.provider,OLD.target_kind,OLD.client_key_hash)
          OR (NEW.payment_id IS DISTINCT FROM OLD.payment_id AND NEW.payment_id IS NOT NULL)
          OR (NEW.invoice_id IS DISTINCT FROM OLD.invoice_id AND NEW.invoice_id IS NOT NULL)
          OR (NEW.actor_user_id IS DISTINCT FROM OLD.actor_user_id AND NEW.actor_user_id IS NOT NULL) THEN
          RAISE EXCEPTION 'Attempt snapshot is immutable'; END IF;
        RETURN NEW;
      END $$
    """)
    op.execute(f"REVOKE ALL ON FUNCTION {q}.click_attempt_snapshot_immutable() FROM PUBLIC")
    op.execute(f"CREATE TRIGGER click_attempt_snapshot_immutable BEFORE UPDATE ON {q}.provider_attempts FOR EACH ROW EXECUTE FUNCTION {q}.click_attempt_snapshot_immutable()")
    op.execute(f"""
      CREATE FUNCTION {q}.click_phase_binding_immutable() RETURNS trigger
      LANGUAGE plpgsql SET search_path=pg_catalog AS $$
      BEGIN RAISE EXCEPTION 'Click binding is immutable'; END $$
    """)
    op.execute(f"REVOKE ALL ON FUNCTION {q}.click_phase_binding_immutable() FROM PUBLIC")
    for signature in ("click_binding_attempt_lock()", "click_attempt_snapshot_immutable()", "click_phase_binding_immutable()"):
        op.execute(f"""DO {tag} DECLARE trusted_owner name; BEGIN
          SELECT r.rolname INTO STRICT trusted_owner FROM pg_catalog.pg_namespace n
            JOIN pg_catalog.pg_roles r ON r.oid=n.nspowner WHERE n.nspname='{literal_schema}';
          EXECUTE pg_catalog.format('ALTER FUNCTION %I.{signature} OWNER TO %I', '{literal_schema}', trusted_owner);
        END {tag}""")
    for table in ("click_issued_attempts", "click_prepares", "click_receipt_reconciliation_links"):
        op.execute(f"""DO {tag} DECLARE trusted_owner name; BEGIN
          SELECT r.rolname INTO STRICT trusted_owner FROM pg_catalog.pg_namespace n
            JOIN pg_catalog.pg_roles r ON r.oid=n.nspowner WHERE n.nspname='{literal_schema}';
          EXECUTE pg_catalog.format('ALTER TABLE %I.{table} OWNER TO %I', '{literal_schema}', trusted_owner);
          EXECUTE pg_catalog.format('CREATE POLICY click_binding_owner_select ON %I.{table} FOR SELECT TO %I USING (true)', '{literal_schema}', trusted_owner);
          EXECUTE pg_catalog.format('CREATE POLICY click_binding_owner_insert ON %I.{table} FOR INSERT TO %I WITH CHECK (true)', '{literal_schema}', trusted_owner);
        END {tag}""")
        op.execute(f"CREATE TRIGGER {table}_immutable BEFORE UPDATE OR DELETE ON {q}.{table} FOR EACH ROW EXECUTE FUNCTION {q}.click_phase_binding_immutable()")
        op.execute(f"ALTER TABLE {q}.{table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {q}.{table} FORCE ROW LEVEL SECURITY")
        op.execute(f"REVOKE ALL ON {q}.{table} FROM PUBLIC")
        op.execute(f"REVOKE ALL ON SEQUENCE {q}.{table}_id_seq FROM PUBLIC")


def downgrade() -> None:
    context = op.get_context()
    dialect = context.dialect.name
    if dialect == "postgresql":
        schema = context.opts.get("version_table_schema") or context.dialect.default_schema_name
        if not schema:
            raise RuntimeError("Trusted migration schema required")
        q = context.dialect.identifier_preparer.quote_schema(schema)
        issued, prepares, links = f"{q}.click_issued_attempts", f"{q}.click_prepares", f"{q}.click_receipt_reconciliation_links"
        op.execute(f"LOCK TABLE {issued}, {prepares}, {links} IN ACCESS EXCLUSIVE MODE")
        op.execute("SET LOCAL row_security=off")
    elif dialect == "sqlite":
        issued, prepares, links = "click_issued_attempts", "click_prepares", "click_receipt_reconciliation_links"
        op.execute("UPDATE click_prepares SET id=id WHERE 0")
    else:
        raise RuntimeError("Unsupported Click phase binding dialect")
    op.execute("CREATE TEMPORARY TABLE click_binding_downgrade_guard (valid integer NOT NULL CHECK(valid=1))")
    op.execute(f"INSERT INTO click_binding_downgrade_guard SELECT CASE WHEN EXISTS(SELECT 1 FROM {issued}) OR EXISTS(SELECT 1 FROM {prepares}) OR EXISTS(SELECT 1 FROM {links}) THEN 0 ELSE 1 END")
    op.execute("DROP TABLE click_binding_downgrade_guard")
    if dialect == "postgresql":
        op.execute(f"DROP TRIGGER click_attempt_visit_lock ON {q}.provider_attempt_visits")
        op.execute(f"DROP TRIGGER click_attempt_snapshot_immutable ON {q}.provider_attempts")
        op.execute(f"DROP TRIGGER click_issued_lock_attempt ON {q}.click_issued_attempts")
        op.execute(f"DROP FUNCTION {q}.click_binding_attempt_lock()")
        op.execute(f"DROP FUNCTION {q}.click_attempt_snapshot_immutable()")
        for table in ("click_issued_attempts", "click_prepares", "click_receipt_reconciliation_links"):
            op.execute(f"DROP TRIGGER {table}_immutable ON {q}.{table}")
        op.execute(f"DROP FUNCTION {q}.click_phase_binding_immutable()")
        op.drop_table("click_receipt_reconciliation_links", schema=schema)
        op.drop_table("click_prepares", schema=schema)
        op.drop_table("click_issued_attempts", schema=schema)
        op.drop_index("uq_click_attempt_snapshot", table_name="provider_attempts", schema=schema)
    else:
        op.execute("DROP TRIGGER click_issued_lock_attempt")
        op.execute("DROP TRIGGER click_attempt_snapshot_immutable")
        for operation in ("insert", "update", "delete"):
            op.execute(f"DROP TRIGGER click_attempt_visit_{operation}")
        for table in ("click_issued_attempts", "click_prepares", "click_receipt_reconciliation_links"):
            for operation in ("update", "delete"):
                op.execute(f"DROP TRIGGER {table}_no_{operation}")
        op.drop_table("click_receipt_reconciliation_links")
        op.drop_table("click_prepares")
        op.drop_table("click_issued_attempts")
        op.drop_index("uq_click_attempt_snapshot", table_name="provider_attempts")
