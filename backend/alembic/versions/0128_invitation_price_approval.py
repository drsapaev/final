"""Bind automatic invitation and admin recovery to one approved price line."""

import sqlalchemy as sa

from alembic import op

revision = "0128_invitation_price_approval"
down_revision = "0127_click_phase_binding"
branch_labels = None
depends_on = None


def upgrade() -> None:
    dialect = op.get_context().dialect.name
    if dialect not in {"postgresql", "sqlite"}:
        raise RuntimeError("Unsupported approval invitation dialect")
    op.create_table(
        "visit_invitation_price_approval_auth",
        sa.Column("delivery_id", sa.Integer(), sa.ForeignKey("visit_invitation_deliveries.id", ondelete="RESTRICT"), primary_key=True),
        sa.Column("actor_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("actor_user_id_snapshot", sa.Integer(), nullable=False),
        sa.Column("actor_auth_epoch", sa.BigInteger(), nullable=False),
        sa.Column("override_id", sa.Integer(), sa.ForeignKey("doctor_price_overrides.id", ondelete="SET NULL")),
        sa.Column("override_id_snapshot", sa.Integer(), nullable=False),
        sa.Column("line_id", sa.Integer(), sa.ForeignKey("visit_services.id", ondelete="SET NULL")),
        sa.Column("line_id_snapshot", sa.Integer(), nullable=False),
        sa.Column("line_generation", sa.BigInteger(), nullable=False),
        sa.Column("unit_price", sa.Numeric(12, 2), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("expires_at", sa.BigInteger(), nullable=False),
        sa.Column("cipher_version", sa.Integer(), nullable=False),
        sa.Column("jti_ciphertext", sa.String(2048), nullable=False),
        sa.CheckConstraint("actor_user_id_snapshot>0 AND actor_auth_epoch>=0 AND expires_at>0", name="ck_invite_price_actor"),
        sa.CheckConstraint("actor_user_id IS NULL OR actor_user_id=actor_user_id_snapshot", name="ck_invite_price_actor_live"),
        sa.CheckConstraint("override_id_snapshot>0 AND (override_id IS NULL OR override_id=override_id_snapshot)", name="ck_invite_price_override"),
        sa.CheckConstraint("line_id_snapshot>0 AND line_generation>0 AND (line_id IS NULL OR line_id=line_id_snapshot)", name="ck_invite_price_line"),
        sa.CheckConstraint("quantity>0 AND unit_price>=0 AND cipher_version=1 AND length(jti_ciphertext) BETWEEN 100 AND 2048", name="ck_invite_price_snapshot"),
    )
    op.create_table(
        "visit_invitation_approval_recoveries",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("visit_id", sa.Integer(), sa.ForeignKey("visits.id", ondelete="SET NULL")),
        sa.Column("visit_id_snapshot", sa.Integer(), nullable=False),
        sa.Column("patient_id", sa.Integer(), sa.ForeignKey("patients.id", ondelete="SET NULL")),
        sa.Column("patient_id_snapshot", sa.Integer(), nullable=False),
        sa.Column("override_id", sa.Integer(), sa.ForeignKey("doctor_price_overrides.id", ondelete="SET NULL")),
        sa.Column("override_id_snapshot", sa.Integer(), nullable=False),
        sa.Column("actor_user_id_snapshot", sa.Integer(), nullable=False),
        sa.Column("owner_generation", sa.BigInteger(), nullable=False),
        sa.Column("context_epoch", sa.BigInteger(), nullable=False),
        sa.Column("previous_token_digest", sa.String(64)),
        sa.Column("state", sa.String(16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("override_id_snapshot", name="uq_invite_recovery_override"),
        sa.CheckConstraint("state IN ('pending','dispatched','resolved')", name="ck_invite_recovery_state"),
        sa.CheckConstraint("previous_token_digest IS NULL OR length(previous_token_digest)=64", name="ck_invite_recovery_token"),
        sa.CheckConstraint("visit_id_snapshot>0 AND patient_id_snapshot>0 AND override_id_snapshot>0 AND owner_generation>0 AND context_epoch>0 AND actor_user_id_snapshot>0", name="ck_invite_recovery_identity"),
        sa.CheckConstraint("(visit_id IS NULL OR visit_id=visit_id_snapshot) AND (patient_id IS NULL OR patient_id=patient_id_snapshot) AND (override_id IS NULL OR override_id=override_id_snapshot)", name="ck_invite_recovery_live"),
    )
    op.create_index("ix_invite_recovery_state_id", "visit_invitation_approval_recoveries", ["state", "id"])
    if dialect == "postgresql":
        context = op.get_context()
        schema = context.opts.get("version_table_schema") or context.dialect.default_schema_name
        if not schema:
            raise RuntimeError("Trusted application schema required")
        q = context.dialect.identifier_preparer.quote_schema(schema)
        for table in ("visit_invitation_price_approval_auth", "visit_invitation_approval_recoveries"):
            op.execute(f"ALTER TABLE {q}.{table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"""
        CREATE FUNCTION {q}.protect_invite_price_auth() RETURNS trigger LANGUAGE plpgsql SET search_path=pg_catalog AS $$
        BEGIN
          IF TG_OP='DELETE' THEN RAISE EXCEPTION 'approval invitation evidence is immutable'; END IF;
          IF ROW(NEW.delivery_id,NEW.actor_user_id_snapshot,NEW.actor_auth_epoch,NEW.override_id_snapshot,
                 NEW.line_id_snapshot,NEW.line_generation,NEW.unit_price,NEW.quantity,NEW.expires_at,NEW.cipher_version,NEW.jti_ciphertext)
             IS DISTINCT FROM ROW(OLD.delivery_id,OLD.actor_user_id_snapshot,OLD.actor_auth_epoch,OLD.override_id_snapshot,
                 OLD.line_id_snapshot,OLD.line_generation,OLD.unit_price,OLD.quantity,OLD.expires_at,OLD.cipher_version,OLD.jti_ciphertext)
             OR (NEW.actor_user_id IS DISTINCT FROM OLD.actor_user_id AND NEW.actor_user_id IS NOT NULL)
             OR (NEW.override_id IS DISTINCT FROM OLD.override_id AND NEW.override_id IS NOT NULL)
             OR (NEW.line_id IS DISTINCT FROM OLD.line_id AND NEW.line_id IS NOT NULL) THEN
            RAISE EXCEPTION 'invalid approval invitation mutation';
          END IF;
          RETURN NEW;
        END $$
        """)
        op.execute(f"CREATE TRIGGER trg_protect_invite_price_auth BEFORE UPDATE OR DELETE ON {q}.visit_invitation_price_approval_auth FOR EACH ROW EXECUTE FUNCTION {q}.protect_invite_price_auth()")
        op.execute(f"""
        CREATE FUNCTION {q}.protect_invite_recovery() RETURNS trigger LANGUAGE plpgsql SET search_path=pg_catalog AS $$
        BEGIN
          IF TG_OP='DELETE' THEN RAISE EXCEPTION 'approval recovery evidence is immutable'; END IF;
          IF ROW(NEW.id,NEW.visit_id_snapshot,NEW.patient_id_snapshot,NEW.override_id_snapshot,NEW.actor_user_id_snapshot,
                 NEW.owner_generation,NEW.context_epoch,NEW.previous_token_digest,NEW.created_at)
             IS DISTINCT FROM ROW(OLD.id,OLD.visit_id_snapshot,OLD.patient_id_snapshot,OLD.override_id_snapshot,OLD.actor_user_id_snapshot,
                 OLD.owner_generation,OLD.context_epoch,OLD.previous_token_digest,OLD.created_at)
             OR (NEW.visit_id IS DISTINCT FROM OLD.visit_id AND NEW.visit_id IS NOT NULL)
             OR (NEW.patient_id IS DISTINCT FROM OLD.patient_id AND NEW.patient_id IS NOT NULL)
             OR (NEW.override_id IS DISTINCT FROM OLD.override_id AND NEW.override_id IS NOT NULL)
             OR (NEW.state IS DISTINCT FROM OLD.state AND NOT ((OLD.state='pending' AND NEW.state IN ('dispatched','resolved')) OR (OLD.state='dispatched' AND NEW.state='resolved'))) THEN
            RAISE EXCEPTION 'invalid approval recovery mutation';
          END IF;
          RETURN NEW;
        END $$
        """)
        op.execute(f"CREATE TRIGGER trg_protect_invite_recovery BEFORE UPDATE OR DELETE ON {q}.visit_invitation_approval_recoveries FOR EACH ROW EXECUTE FUNCTION {q}.protect_invite_recovery()")
    else:
        op.execute("CREATE TRIGGER trg_invite_price_delete BEFORE DELETE ON visit_invitation_price_approval_auth BEGIN SELECT RAISE(ABORT, 'immutable approval invitation'); END")
        op.execute("""
        CREATE TRIGGER trg_invite_price_update BEFORE UPDATE ON visit_invitation_price_approval_auth
        WHEN NEW.delivery_id IS NOT OLD.delivery_id OR NEW.actor_user_id_snapshot IS NOT OLD.actor_user_id_snapshot
          OR NEW.actor_auth_epoch IS NOT OLD.actor_auth_epoch OR NEW.override_id_snapshot IS NOT OLD.override_id_snapshot
          OR NEW.line_id_snapshot IS NOT OLD.line_id_snapshot OR NEW.line_generation IS NOT OLD.line_generation
          OR NEW.unit_price IS NOT OLD.unit_price OR NEW.quantity IS NOT OLD.quantity OR NEW.expires_at IS NOT OLD.expires_at
          OR NEW.cipher_version IS NOT OLD.cipher_version OR NEW.jti_ciphertext IS NOT OLD.jti_ciphertext
          OR (NEW.actor_user_id IS NOT OLD.actor_user_id AND NEW.actor_user_id IS NOT NULL)
          OR (NEW.override_id IS NOT OLD.override_id AND NEW.override_id IS NOT NULL)
          OR (NEW.line_id IS NOT OLD.line_id AND NEW.line_id IS NOT NULL)
        BEGIN SELECT RAISE(ABORT, 'invalid approval invitation mutation'); END
        """)
        op.execute("CREATE TRIGGER trg_invite_recovery_delete BEFORE DELETE ON visit_invitation_approval_recoveries BEGIN SELECT RAISE(ABORT, 'immutable approval recovery'); END")
        op.execute("""
        CREATE TRIGGER trg_invite_recovery_update BEFORE UPDATE ON visit_invitation_approval_recoveries
        WHEN NEW.id IS NOT OLD.id OR NEW.visit_id_snapshot IS NOT OLD.visit_id_snapshot OR NEW.patient_id_snapshot IS NOT OLD.patient_id_snapshot
          OR NEW.override_id_snapshot IS NOT OLD.override_id_snapshot OR NEW.actor_user_id_snapshot IS NOT OLD.actor_user_id_snapshot
          OR NEW.owner_generation IS NOT OLD.owner_generation OR NEW.context_epoch IS NOT OLD.context_epoch OR NEW.previous_token_digest IS NOT OLD.previous_token_digest OR NEW.created_at IS NOT OLD.created_at
          OR (NEW.visit_id IS NOT OLD.visit_id AND NEW.visit_id IS NOT NULL)
          OR (NEW.patient_id IS NOT OLD.patient_id AND NEW.patient_id IS NOT NULL)
          OR (NEW.override_id IS NOT OLD.override_id AND NEW.override_id IS NOT NULL)
          OR (NEW.state IS NOT OLD.state AND NOT ((OLD.state='pending' AND NEW.state IN ('dispatched','resolved')) OR (OLD.state='dispatched' AND NEW.state='resolved')))
        BEGIN SELECT RAISE(ABORT, 'invalid approval recovery mutation'); END
        """)


def downgrade() -> None:
    dialect = op.get_context().dialect.name
    tables = ("visit_invitation_price_approval_auth", "visit_invitation_approval_recoveries")
    if dialect == "postgresql":
        context = op.get_context()
        schema = context.opts.get("version_table_schema") or context.dialect.default_schema_name
        if not schema:
            raise RuntimeError("Trusted application schema required")
        q = context.dialect.identifier_preparer.quote_schema(schema)
        op.execute("SET LOCAL row_security=off")
        op.execute(f"LOCK TABLE {q}.{tables[0]}, {q}.{tables[1]} IN ACCESS EXCLUSIVE MODE")
        op.execute(f"SELECT 1 / CASE WHEN EXISTS (SELECT 1 FROM {q}.{tables[0]}) OR EXISTS (SELECT 1 FROM {q}.{tables[1]}) THEN 0 ELSE 1 END")
        op.execute(f"DROP TRIGGER trg_protect_invite_recovery ON {q}.{tables[1]}")
        op.execute(f"DROP FUNCTION {q}.protect_invite_recovery()")
        op.execute(f"DROP TRIGGER trg_protect_invite_price_auth ON {q}.{tables[0]}")
        op.execute(f"DROP FUNCTION {q}.protect_invite_price_auth()")
    elif dialect == "sqlite":
        schema = None
        op.execute("UPDATE visit_invitation_approval_recoveries SET id=id WHERE 0")
        op.execute("CREATE TEMP TABLE invite_approval_downgrade_guard (valid INTEGER NOT NULL CHECK(valid=1))")
        op.execute("INSERT INTO invite_approval_downgrade_guard SELECT CASE WHEN EXISTS (SELECT 1 FROM visit_invitation_price_approval_auth) OR EXISTS (SELECT 1 FROM visit_invitation_approval_recoveries) THEN 0 ELSE 1 END")
        op.execute("DROP TABLE invite_approval_downgrade_guard")
    else:
        raise RuntimeError("Unsupported approval invitation dialect")
    op.drop_index("ix_invite_recovery_state_id", table_name=tables[1], schema=schema)
    op.drop_table(tables[1], schema=schema)
    op.drop_table(tables[0], schema=schema)
