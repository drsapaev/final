"""Store immutable encrypted Click callback observations.

No payment settlement or provider ACK is enabled by this revision.
"""
import sqlalchemy as sa

from alembic import op

revision = "0119_click_receipt"
down_revision = "0118_encounter_financial_fence"
branch_labels = None
depends_on = None


def upgrade() -> None:
    dialect = op.get_context().dialect.name
    if dialect not in {"postgresql", "sqlite"}:
        raise RuntimeError("Unsupported Click receipt dialect")
    op.create_table(
        "click_receipt_key_versions",
        sa.Column("version", sa.String(32), primary_key=True),
        sa.Column("commitment", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("length(version) BETWEEN 1 AND 32", name="ck_click_key_version"),
        sa.CheckConstraint("length(commitment) = 64", name="ck_click_key_commitment"),
    )
    op.create_table(
        "click_callback_receipts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("event_key", sa.String(64), nullable=False),
        sa.Column("body_digest", sa.String(64), nullable=False),
        sa.Column("variant_slot", sa.Integer(), nullable=False),
        sa.Column("phase", sa.String(8), nullable=False),
        sa.Column("confidence", sa.String(16), nullable=False),
        sa.Column("media_type", sa.String(64), nullable=False),
        sa.Column("body_size", sa.Integer(), nullable=False),
        sa.Column("key_version", sa.String(32), sa.ForeignKey("click_receipt_key_versions.version", ondelete="RESTRICT"), nullable=False),
        sa.Column("ciphertext", sa.LargeBinary(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("event_key", "body_digest", name="uq_click_receipt_body"),
        sa.UniqueConstraint("event_key", "variant_slot", name="uq_click_receipt_slot"),
        sa.CheckConstraint("length(event_key) = 64 AND length(body_digest) = 64", name="ck_click_receipt_hashes"),
        sa.CheckConstraint("variant_slot >= 0 AND variant_slot < 32", name="ck_click_receipt_slot"),
        sa.CheckConstraint("phase IN ('prepare', 'complete')", name="ck_click_receipt_phase"),
        sa.CheckConstraint("confidence IN ('authenticated', 'probable')", name="ck_click_receipt_confidence"),
        sa.CheckConstraint("media_type IN ('application/json', 'application/x-www-form-urlencoded')", name="ck_click_receipt_media"),
        sa.CheckConstraint("body_size > 0 AND body_size <= 262144", name="ck_click_receipt_size"),
    )
    op.create_index("ix_click_callback_receipts_event_key", "click_callback_receipts", ["event_key"])
    if dialect == "postgresql":
        ctx = op.get_context()
        schema = ctx.opts.get("version_table_schema") or ctx.dialect.default_schema_name
        if not schema:
            raise RuntimeError("Trusted migration schema required")
        qualified = ctx.dialect.identifier_preparer.quote_schema(schema)
        schema_literal = schema.replace("'", "''")
        tag = "$click_receipt_owner$"
        while tag in schema_literal:
            tag = tag[:-1] + "_x$"
        op.execute(f"""
        CREATE FUNCTION {qualified}.click_receipt_immutable() RETURNS trigger
        LANGUAGE plpgsql SET search_path = pg_catalog AS $$
        BEGIN RAISE EXCEPTION 'Click receipt history is immutable'; END $$
        """)
        op.execute(f"REVOKE ALL ON FUNCTION {qualified}.click_receipt_immutable() FROM PUBLIC")
        op.execute(f"""DO {tag} DECLARE trusted_owner name; BEGIN
          SELECT r.rolname INTO STRICT trusted_owner FROM pg_catalog.pg_namespace n
            JOIN pg_catalog.pg_roles r ON r.oid=n.nspowner WHERE n.nspname='{schema_literal}';
          EXECUTE pg_catalog.format('ALTER FUNCTION %I.click_receipt_immutable() OWNER TO %I', '{schema_literal}', trusted_owner);
        END {tag}""")
        for table in ("click_receipt_key_versions", "click_callback_receipts"):
            op.execute(f"""DO {tag} DECLARE trusted_owner name; BEGIN
              SELECT r.rolname INTO STRICT trusted_owner FROM pg_catalog.pg_namespace n
                JOIN pg_catalog.pg_roles r ON r.oid=n.nspowner WHERE n.nspname='{schema_literal}';
              EXECUTE pg_catalog.format('ALTER TABLE %I.{table} OWNER TO %I', '{schema_literal}', trusted_owner);
            END {tag}""")
            op.execute(f"CREATE TRIGGER trg_{table}_immutable BEFORE UPDATE OR DELETE ON {qualified}.{table} FOR EACH ROW EXECUTE FUNCTION {qualified}.click_receipt_immutable()")
            op.execute(f"ALTER TABLE {qualified}.{table} ENABLE ROW LEVEL SECURITY")
            op.execute(f"ALTER TABLE {qualified}.{table} FORCE ROW LEVEL SECURITY")
            op.execute(f"REVOKE ALL ON {qualified}.{table} FROM PUBLIC")
            op.execute(f"""DO {tag} DECLARE trusted_owner name; BEGIN
              SELECT r.rolname INTO STRICT trusted_owner FROM pg_catalog.pg_namespace n
                JOIN pg_catalog.pg_roles r ON r.oid=n.nspowner WHERE n.nspname='{schema_literal}';
              EXECUTE pg_catalog.format('CREATE POLICY click_receipt_owner_select ON %I.{table} FOR SELECT TO %I USING (true)', '{schema_literal}', trusted_owner);
              EXECUTE pg_catalog.format('CREATE POLICY click_receipt_owner_insert ON %I.{table} FOR INSERT TO %I WITH CHECK (true)', '{schema_literal}', trusted_owner);
            END {tag}""")
        op.execute(f"REVOKE ALL ON SEQUENCE {qualified}.click_callback_receipts_id_seq FROM PUBLIC")
    else:
        for table in ("click_receipt_key_versions", "click_callback_receipts"):
            for event in ("UPDATE", "DELETE"):
                op.execute(f"CREATE TRIGGER trg_{table}_no_{event.lower()} BEFORE {event} ON {table} BEGIN SELECT RAISE(ABORT, 'Click receipt history is immutable'); END")


def downgrade() -> None:
    dialect = op.get_context().dialect.name
    if dialect == "postgresql":
        ctx = op.get_context()
        schema = ctx.opts.get("version_table_schema") or ctx.dialect.default_schema_name
        if not schema:
            raise RuntimeError("Trusted migration schema required")
        qualified = ctx.dialect.identifier_preparer.quote_schema(schema)
        receipts = f"{qualified}.click_callback_receipts"
        versions = f"{qualified}.click_receipt_key_versions"
        op.execute(f"LOCK TABLE {receipts}, {versions} IN ACCESS EXCLUSIVE MODE")
    elif dialect == "sqlite":
        receipts, versions = "click_callback_receipts", "click_receipt_key_versions"
        op.execute("UPDATE click_callback_receipts SET id=id WHERE 0")
    else:
        raise RuntimeError("Unsupported Click receipt dialect")
    op.execute("CREATE TEMPORARY TABLE click_receipt_downgrade_guard (valid INTEGER NOT NULL CHECK(valid=1))")
    op.execute(f"INSERT INTO click_receipt_downgrade_guard SELECT CASE WHEN EXISTS (SELECT 1 FROM {receipts}) OR EXISTS (SELECT 1 FROM {versions}) THEN 0 ELSE 1 END")
    op.execute("DROP TABLE click_receipt_downgrade_guard")
    if dialect == "postgresql":
        for table in ("click_callback_receipts", "click_receipt_key_versions"):
            op.execute(f"DROP TRIGGER trg_{table}_immutable ON {qualified}.{table}")
        op.execute(f"DROP FUNCTION {qualified}.click_receipt_immutable()")
    else:
        for table in ("click_callback_receipts", "click_receipt_key_versions"):
            for event in ("update", "delete"):
                op.execute(f"DROP TRIGGER trg_{table}_no_{event}")
    target_schema = schema if dialect == "postgresql" else None
    op.drop_index("ix_click_callback_receipts_event_key", table_name="click_callback_receipts", schema=target_schema)
    op.drop_table("click_callback_receipts", schema=target_schema)
    op.drop_table("click_receipt_key_versions", schema=target_schema)
