"""Bind pending invitation deliveries to an encrypted issuer session."""

import sqlalchemy as sa

from alembic import op

revision = "0126_invitation_issuer_auth"
down_revision = "0125_benefit_visibility"
branch_labels = None
depends_on = None


def upgrade() -> None:
    dialect = op.get_context().dialect.name
    if dialect not in {"postgresql", "sqlite"}:
        raise RuntimeError("Unsupported invitation issuer dialect")
    op.create_index("ix_invitation_state_id", "visit_invitation_deliveries", ["state", "id"])
    op.create_table(
        "visit_invitation_issuer_auth",
        sa.Column("delivery_id", sa.Integer(), sa.ForeignKey("visit_invitation_deliveries.id", ondelete="RESTRICT"), primary_key=True),
        sa.Column("actor_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("actor_user_id_snapshot", sa.Integer(), nullable=False),
        sa.Column("actor_auth_epoch", sa.BigInteger(), nullable=False),
        sa.Column("requester_type", sa.String(12), nullable=False),
        sa.Column("doctor_id", sa.Integer(), sa.ForeignKey("doctors.id", ondelete="SET NULL")),
        sa.Column("doctor_id_snapshot", sa.Integer()),
        sa.Column("doctor_generation", sa.BigInteger()),
        sa.Column("expires_at", sa.BigInteger(), nullable=False),
        sa.Column("cipher_version", sa.Integer(), nullable=False),
        sa.Column("jti_ciphertext", sa.String(2048), nullable=False),
        sa.CheckConstraint("actor_user_id_snapshot>0 AND actor_auth_epoch>=0 AND expires_at>0", name="ck_invitation_issuer_identity"),
        sa.CheckConstraint("actor_user_id IS NULL OR actor_user_id=actor_user_id_snapshot", name="ck_invitation_issuer_actor"),
        sa.CheckConstraint("requester_type IN ('admin','doctor')", name="ck_invitation_issuer_type"),
        sa.CheckConstraint("(doctor_id_snapshot IS NULL AND doctor_id IS NULL AND doctor_generation IS NULL) OR (doctor_id_snapshot IS NOT NULL AND doctor_id_snapshot>0 AND doctor_generation IS NOT NULL AND doctor_generation>0 AND (doctor_id IS NULL OR doctor_id=doctor_id_snapshot))", name="ck_invitation_issuer_doctor"),
        sa.CheckConstraint("requester_type<>'doctor' OR doctor_id_snapshot IS NOT NULL", name="ck_invitation_issuer_doctor_required"),
        sa.CheckConstraint("cipher_version=1 AND length(jti_ciphertext) BETWEEN 100 AND 2048", name="ck_invitation_issuer_cipher"),
    )
    if dialect == "postgresql":
        context = op.get_context()
        schema = context.opts.get("version_table_schema") or context.dialect.default_schema_name
        if not schema:
            raise RuntimeError("Trusted application schema required")
        qualified = context.dialect.identifier_preparer.quote_schema(schema)
        op.execute(f"ALTER TABLE {qualified}.visit_invitation_issuer_auth ENABLE ROW LEVEL SECURITY")
        op.execute(f"""
        CREATE FUNCTION {qualified}.protect_visit_invitation_issuer_auth() RETURNS trigger
        LANGUAGE plpgsql SET search_path=pg_catalog AS $$
        BEGIN
          IF TG_OP='DELETE' THEN RAISE EXCEPTION 'invitation issuer evidence is immutable'; END IF;
          IF ROW(NEW.delivery_id,NEW.actor_user_id_snapshot,NEW.actor_auth_epoch,NEW.requester_type,
                 NEW.doctor_id_snapshot,NEW.doctor_generation,NEW.expires_at,NEW.cipher_version,NEW.jti_ciphertext)
             IS DISTINCT FROM ROW(OLD.delivery_id,OLD.actor_user_id_snapshot,OLD.actor_auth_epoch,OLD.requester_type,
                 OLD.doctor_id_snapshot,OLD.doctor_generation,OLD.expires_at,OLD.cipher_version,OLD.jti_ciphertext)
             OR (NEW.actor_user_id IS DISTINCT FROM OLD.actor_user_id AND NEW.actor_user_id IS NOT NULL)
             OR (NEW.doctor_id IS DISTINCT FROM OLD.doctor_id AND NEW.doctor_id IS NOT NULL) THEN
            RAISE EXCEPTION 'invalid invitation issuer mutation';
          END IF;
          RETURN NEW;
        END $$
        """)
        op.execute(f"CREATE TRIGGER trg_protect_invitation_issuer_auth BEFORE UPDATE OR DELETE ON {qualified}.visit_invitation_issuer_auth FOR EACH ROW EXECUTE FUNCTION {qualified}.protect_visit_invitation_issuer_auth()")
    else:
        op.execute("""
        CREATE TRIGGER trg_protect_invitation_issuer_delete BEFORE DELETE ON visit_invitation_issuer_auth
        BEGIN SELECT RAISE(ABORT, 'invitation issuer evidence is immutable'); END
        """)
        op.execute("""
        CREATE TRIGGER trg_protect_invitation_issuer_update BEFORE UPDATE ON visit_invitation_issuer_auth
        WHEN NEW.delivery_id IS NOT OLD.delivery_id OR NEW.actor_user_id_snapshot IS NOT OLD.actor_user_id_snapshot
          OR NEW.actor_auth_epoch IS NOT OLD.actor_auth_epoch OR NEW.requester_type IS NOT OLD.requester_type
          OR NEW.doctor_id_snapshot IS NOT OLD.doctor_id_snapshot OR NEW.doctor_generation IS NOT OLD.doctor_generation
          OR NEW.expires_at IS NOT OLD.expires_at OR NEW.cipher_version IS NOT OLD.cipher_version
          OR NEW.jti_ciphertext IS NOT OLD.jti_ciphertext
          OR (NEW.actor_user_id IS NOT OLD.actor_user_id AND NEW.actor_user_id IS NOT NULL)
          OR (NEW.doctor_id IS NOT OLD.doctor_id AND NEW.doctor_id IS NOT NULL)
        BEGIN SELECT RAISE(ABORT, 'invalid invitation issuer mutation'); END
        """)


def downgrade() -> None:
    dialect = op.get_context().dialect.name
    if dialect == "postgresql":
        context = op.get_context()
        schema = context.opts.get("version_table_schema") or context.dialect.default_schema_name
        if not schema:
            raise RuntimeError("Trusted application schema required")
        qualified = context.dialect.identifier_preparer.quote_schema(schema)
        op.execute("SET LOCAL row_security=off")
        op.execute(f"LOCK TABLE {qualified}.visit_invitation_issuer_auth IN ACCESS EXCLUSIVE MODE")
        op.execute(f"SELECT 1 / CASE WHEN EXISTS (SELECT 1 FROM {qualified}.visit_invitation_issuer_auth) THEN 0 ELSE 1 END")
        op.execute(f"DROP TRIGGER trg_protect_invitation_issuer_auth ON {qualified}.visit_invitation_issuer_auth")
        op.execute(f"DROP FUNCTION {qualified}.protect_visit_invitation_issuer_auth()")
    elif dialect == "sqlite":
        op.execute("UPDATE visit_invitation_issuer_auth SET delivery_id=delivery_id WHERE 0")
        op.execute("CREATE TEMP TABLE invitation_issuer_downgrade_guard (valid INTEGER NOT NULL CHECK(valid=1))")
        op.execute("INSERT INTO invitation_issuer_downgrade_guard SELECT CASE WHEN EXISTS (SELECT 1 FROM visit_invitation_issuer_auth) THEN 0 ELSE 1 END")
        op.execute("DROP TABLE invitation_issuer_downgrade_guard")
    else:
        raise RuntimeError("Unsupported invitation issuer dialect")
    op.drop_table("visit_invitation_issuer_auth", schema=schema if dialect == "postgresql" else None)
    op.drop_index("ix_invitation_state_id", table_name="visit_invitation_deliveries", schema=schema if dialect == "postgresql" else None)
