"""Persist one subject-bound invitation attempt per confirmation context."""

import sqlalchemy as sa

from alembic import op

revision = "0117_visit_invitation_delivery"
down_revision = "0116_patient_owner_confirmation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    dialect = op.get_context().dialect.name
    if dialect not in {"postgresql", "sqlite"}:
        raise RuntimeError("Unsupported invitation delivery dialect")
    op.create_table(
        "visit_invitation_deliveries",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("visit_id", sa.Integer(), sa.ForeignKey("visits.id", ondelete="SET NULL")),
        sa.Column("visit_id_snapshot", sa.Integer(), nullable=False),
        sa.Column("patient_id", sa.Integer(), sa.ForeignKey("patients.id", ondelete="SET NULL")),
        sa.Column("patient_id_snapshot", sa.Integer(), nullable=False),
        sa.Column("owner_generation", sa.BigInteger(), nullable=False),
        sa.Column("context_epoch", sa.BigInteger(), nullable=False),
        sa.Column("token_digest", sa.String(64), nullable=False),
        sa.Column("dispatch_nonce_digest", sa.String(64)),
        sa.Column("issuer_actor_id", sa.Integer()),
        sa.Column("issuer_key_digest", sa.String(64)),
        sa.Column("issuer_fingerprint", sa.String(64)),
        sa.Column("channel", sa.String(16), nullable=False),
        sa.Column("telegram_link_id", sa.Integer()),
        sa.Column("telegram_link_epoch", sa.BigInteger()),
        sa.Column("state", sa.String(16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("visit_id_snapshot", "context_epoch", "token_digest", name="uq_visit_invitation_context"),
        sa.UniqueConstraint("issuer_actor_id", "issuer_key_digest", name="uq_invitation_issuer_key"),
        sa.CheckConstraint("visit_id IS NULL OR visit_id=visit_id_snapshot", name="ck_invitation_visit"),
        sa.CheckConstraint("patient_id IS NULL OR patient_id=patient_id_snapshot", name="ck_invitation_patient"),
        sa.CheckConstraint("visit_id_snapshot>0 AND patient_id_snapshot>0 AND owner_generation>0 AND context_epoch>0", name="ck_invitation_subject"),
        sa.CheckConstraint("length(token_digest)=64", name="ck_invitation_digest"),
        sa.CheckConstraint("channel IN ('telegram','pwa','phone')", name="ck_invitation_channel"),
        sa.CheckConstraint("state IN ('pending','unknown','sent','cancelled')", name="ck_invitation_state"),
        sa.CheckConstraint("(dispatch_nonce_digest IS NULL OR length(dispatch_nonce_digest)=64) AND (state='unknown' OR dispatch_nonce_digest IS NULL)", name="ck_invitation_nonce"),
        sa.CheckConstraint("(issuer_actor_id IS NULL AND issuer_key_digest IS NULL AND issuer_fingerprint IS NULL) OR (issuer_actor_id IS NOT NULL AND issuer_key_digest IS NOT NULL AND issuer_fingerprint IS NOT NULL AND issuer_actor_id>0 AND length(issuer_key_digest)=64 AND length(issuer_fingerprint)=64)", name="ck_invitation_issuer"),
        sa.CheckConstraint("(channel='telegram' AND telegram_link_id IS NOT NULL AND telegram_link_epoch IS NOT NULL) OR (channel<>'telegram' AND telegram_link_id IS NULL AND telegram_link_epoch IS NULL)", name="ck_invitation_telegram"),
    )
    if dialect == "postgresql":
        context = op.get_context()
        schema = context.opts.get("version_table_schema") or context.dialect.default_schema_name
        if not schema:
            raise RuntimeError("Trusted application schema required")
        qualified = context.dialect.identifier_preparer.quote_schema(schema)
        # Permissions/policy must be deliberately provisioned to the trusted
        # backend role; absence of a policy fails closed for non-owner roles.
        op.execute(f"ALTER TABLE {qualified}.visit_invitation_deliveries ENABLE ROW LEVEL SECURITY")
        op.execute(f"""
        CREATE FUNCTION {qualified}.protect_visit_invitation_delivery() RETURNS trigger
        LANGUAGE plpgsql SET search_path=pg_catalog AS $$
        BEGIN
          IF TG_OP='DELETE' THEN RAISE EXCEPTION 'invitation evidence is immutable'; END IF;
          IF ROW(NEW.visit_id_snapshot, NEW.patient_id_snapshot, NEW.owner_generation,
                 NEW.context_epoch, NEW.token_digest, NEW.channel, NEW.telegram_link_id,
                 NEW.telegram_link_epoch, NEW.issuer_actor_id, NEW.issuer_key_digest, NEW.issuer_fingerprint, NEW.created_at)
             IS DISTINCT FROM ROW(OLD.visit_id_snapshot, OLD.patient_id_snapshot, OLD.owner_generation,
                 OLD.context_epoch, OLD.token_digest, OLD.channel, OLD.telegram_link_id,
                 OLD.telegram_link_epoch, OLD.issuer_actor_id, OLD.issuer_key_digest, OLD.issuer_fingerprint, OLD.created_at)
             OR (NEW.visit_id IS DISTINCT FROM OLD.visit_id AND NEW.visit_id IS NOT NULL)
             OR (NEW.patient_id IS DISTINCT FROM OLD.patient_id AND NEW.patient_id IS NOT NULL)
             OR (NEW.state IS DISTINCT FROM OLD.state AND NOT
               ((OLD.state='pending' AND NEW.state IN ('unknown','sent','cancelled'))
                OR (OLD.state='unknown' AND NEW.state='sent'))) THEN
            RAISE EXCEPTION 'invalid invitation transition';
          END IF;
          RETURN NEW;
        END $$
        """)
        op.execute(f"CREATE TRIGGER trg_protect_visit_invitation BEFORE UPDATE OR DELETE ON {qualified}.visit_invitation_deliveries FOR EACH ROW EXECUTE FUNCTION {qualified}.protect_visit_invitation_delivery()")
    else:
        op.execute("""
        CREATE TRIGGER trg_protect_visit_invitation_delete BEFORE DELETE ON visit_invitation_deliveries
        BEGIN SELECT RAISE(ABORT, 'invitation evidence is immutable'); END
        """)
        op.execute("""
        CREATE TRIGGER trg_protect_visit_invitation_update BEFORE UPDATE ON visit_invitation_deliveries
        WHEN NEW.visit_id_snapshot IS NOT OLD.visit_id_snapshot OR NEW.patient_id_snapshot IS NOT OLD.patient_id_snapshot
          OR NEW.owner_generation IS NOT OLD.owner_generation OR NEW.context_epoch IS NOT OLD.context_epoch
          OR NEW.token_digest IS NOT OLD.token_digest OR NEW.channel IS NOT OLD.channel
          OR NEW.telegram_link_id IS NOT OLD.telegram_link_id OR NEW.telegram_link_epoch IS NOT OLD.telegram_link_epoch
          OR NEW.issuer_actor_id IS NOT OLD.issuer_actor_id OR NEW.issuer_key_digest IS NOT OLD.issuer_key_digest
          OR NEW.issuer_fingerprint IS NOT OLD.issuer_fingerprint
          OR NEW.created_at IS NOT OLD.created_at
          OR (NEW.visit_id IS NOT OLD.visit_id AND NEW.visit_id IS NOT NULL)
          OR (NEW.patient_id IS NOT OLD.patient_id AND NEW.patient_id IS NOT NULL)
          OR (NEW.state IS NOT OLD.state AND NOT
             ((OLD.state='pending' AND NEW.state IN ('unknown','sent','cancelled'))
               OR (OLD.state='unknown' AND NEW.state='sent')))
        BEGIN SELECT RAISE(ABORT, 'invalid invitation transition'); END
        """)


def downgrade() -> None:
    dialect = op.get_context().dialect.name
    if dialect == "postgresql":
        op.execute("SET LOCAL row_security=off")
        op.execute("LOCK TABLE visit_invitation_deliveries IN ACCESS EXCLUSIVE MODE")
        op.execute("DO $$ BEGIN IF EXISTS (SELECT 1 FROM visit_invitation_deliveries) THEN RAISE EXCEPTION 'invitation downgrade would lose delivery evidence'; END IF; END $$")
    elif dialect == "sqlite":
        op.execute("UPDATE visit_invitation_deliveries SET id=id WHERE 0")
        op.execute("CREATE TEMP TABLE invitation_downgrade_guard (valid INTEGER NOT NULL CHECK(valid=1))")
        op.execute("INSERT INTO invitation_downgrade_guard SELECT CASE WHEN EXISTS (SELECT 1 FROM visit_invitation_deliveries) THEN 0 ELSE 1 END")
        op.execute("DROP TABLE invitation_downgrade_guard")
    else:
        raise RuntimeError("Unsupported invitation delivery dialect")
    if dialect == "postgresql":
        context = op.get_context()
        schema = context.opts.get("version_table_schema") or context.dialect.default_schema_name
        if not schema:
            raise RuntimeError("Trusted application schema required")
        qualified = context.dialect.identifier_preparer.quote_schema(schema)
        op.execute(f"DROP TRIGGER trg_protect_visit_invitation ON {qualified}.visit_invitation_deliveries")
        op.execute(f"DROP FUNCTION {qualified}.protect_visit_invitation_delivery()")
    op.drop_table("visit_invitation_deliveries")
