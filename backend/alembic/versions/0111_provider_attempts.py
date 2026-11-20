"""Add provider intent snapshots and per-visit active reservations.

No provider dispatch, authorization, immutable-ledger enforcement or verified
reservation release is implemented by this schema.
"""
import sqlalchemy as sa

from alembic import op

revision = "0111_provider_attempts"
down_revision = "0110_patient_birth_precision"
branch_labels = None
depends_on = None


def _minor_constraints(prefix: str, dialect: str, *, positive: bool):
    checks = [sa.CheckConstraint(
        "length(amount_minor) BETWEEN 1 AND 128 AND "
        "(length(amount_minor) = 1 OR substr(amount_minor, 1, 1) <> '0')"
        + (" AND amount_minor <> '0'" if positive else ""),
        name=f"ck_{prefix}_minor_format",
    )]
    if dialect == "postgresql":
        checks.append(sa.CheckConstraint("amount_minor ~ '^[0-9]+$'", name=f"ck_{prefix}_minor_digits_pg"))
    elif dialect == "sqlite":
        checks.append(sa.CheckConstraint("amount_minor NOT GLOB '*[^0-9]*'", name=f"ck_{prefix}_minor_digits_sqlite"))
    else:
        raise RuntimeError(f"Unsupported provider attempt dialect: {dialect}")
    return checks


def upgrade() -> None:
    dialect = op.get_context().dialect.name
    if dialect not in {"postgresql", "sqlite"}:
        raise RuntimeError(f"Unsupported provider attempt dialect: {dialect}")
    hash_check = (
        sa.CheckConstraint("merchant_hash ~ '^[0-9a-f]{64}$' AND fingerprint ~ '^[0-9a-f]{64}$'", name="ck_provider_attempt_hash_pg")
        if dialect == "postgresql" else
        sa.CheckConstraint("merchant_hash NOT GLOB '*[^0-9a-f]*' AND fingerprint NOT GLOB '*[^0-9a-f]*'", name="ck_provider_attempt_hash_sqlite")
    )
    op.create_table(
        "provider_attempts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("public_id", sa.String(36), nullable=False),
        sa.Column("target_kind", sa.String(16), nullable=False),
        sa.Column("payment_id", sa.Integer(), sa.ForeignKey("payments.id", ondelete="SET NULL")),
        sa.Column("payment_id_snapshot", sa.Integer()),
        sa.Column("invoice_id", sa.Integer(), sa.ForeignKey("payment_invoices.id", ondelete="SET NULL")),
        sa.Column("invoice_id_snapshot", sa.Integer()),
        sa.Column("actor_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("actor_user_id_snapshot", sa.Integer(), nullable=False),
        sa.Column("provider", sa.String(32), nullable=False),
        sa.Column("merchant_hash", sa.String(64), nullable=False),
        sa.Column("order_ref", sa.String(128), nullable=False),
        sa.Column("fingerprint", sa.String(64), nullable=False),
        sa.Column("client_key_hash", sa.String(64), nullable=True),
        sa.Column("amount_minor", sa.String(128), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("currency_exponent", sa.SmallInteger(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("public_id", name="uq_provider_attempt_public_id"),
        sa.UniqueConstraint("provider", "merchant_hash", "order_ref", name="uq_provider_attempt_order"),
        sa.UniqueConstraint("actor_user_id_snapshot", "client_key_hash", name="uq_provider_attempt_actor_key"),
        sa.CheckConstraint("length(public_id) = 36", name="ck_provider_attempt_public_id"),
        sa.CheckConstraint("length(provider) BETWEEN 1 AND 32 AND provider = lower(provider)", name="ck_provider_attempt_provider"),
        sa.CheckConstraint("length(order_ref) BETWEEN 1 AND 128 AND length(trim(order_ref)) > 0", name="ck_provider_attempt_order"),
        sa.CheckConstraint("length(merchant_hash) = 64 AND length(fingerprint) = 64", name="ck_provider_attempt_hash_lengths"),
        sa.CheckConstraint("client_key_hash IS NULL OR length(client_key_hash) = 64", name="ck_provider_attempt_client_key_length"),
        (sa.CheckConstraint("client_key_hash IS NULL OR client_key_hash ~ '^[0-9a-f]{64}$'", name="ck_provider_attempt_client_key_pg")
         if dialect == "postgresql" else
         sa.CheckConstraint("client_key_hash IS NULL OR client_key_hash NOT GLOB '*[^0-9a-f]*'", name="ck_provider_attempt_client_key_sqlite")),
        hash_check,
        sa.CheckConstraint("length(currency) = 3 AND currency = upper(currency) AND currency_exponent BETWEEN 0 AND 9", name="ck_provider_attempt_currency"),
        sa.CheckConstraint("status IN ('prepared', 'dispatching', 'unknown')", name="ck_provider_attempt_status"),
        sa.CheckConstraint(
            "(target_kind = 'payment' AND payment_id_snapshot IS NOT NULL AND payment_id_snapshot > 0 "
            "AND invoice_id_snapshot IS NULL AND invoice_id IS NULL) OR "
            "(target_kind = 'payment_invoice' AND invoice_id_snapshot IS NOT NULL AND invoice_id_snapshot > 0 "
            "AND payment_id_snapshot IS NULL AND payment_id IS NULL)", name="ck_provider_attempt_target"),
        sa.CheckConstraint("payment_id IS NULL OR payment_id = payment_id_snapshot", name="ck_provider_attempt_payment_snapshot"),
        sa.CheckConstraint("invoice_id IS NULL OR invoice_id = invoice_id_snapshot", name="ck_provider_attempt_invoice_snapshot"),
        sa.CheckConstraint("actor_user_id_snapshot > 0 AND (actor_user_id IS NULL OR actor_user_id = actor_user_id_snapshot)", name="ck_provider_attempt_actor_snapshot"),
        *_minor_constraints("provider_attempt", dialect, positive=True),
    )
    op.create_table(
        "provider_attempt_visits",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("attempt_id", sa.Integer(), sa.ForeignKey("provider_attempts.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("visit_id", sa.Integer(), sa.ForeignKey("visits.id", ondelete="SET NULL")),
        sa.Column("visit_id_snapshot", sa.Integer(), nullable=False),
        sa.Column("patient_id_snapshot", sa.Integer(), nullable=False),
        sa.Column("context_epoch", sa.BigInteger(), nullable=False),
        sa.Column("amount_minor", sa.String(128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("attempt_id", "visit_id_snapshot", name="uq_provider_attempt_visit_snapshot"),
        sa.UniqueConstraint("id", "attempt_id", "visit_id", name="uq_provider_attempt_visit_live"),
        sa.CheckConstraint("visit_id IS NULL OR visit_id = visit_id_snapshot", name="ck_provider_attempt_visit_live_snapshot"),
        sa.CheckConstraint("visit_id_snapshot > 0 AND patient_id_snapshot > 0 AND context_epoch > 0", name="ck_provider_attempt_visit_snapshot"),
        *_minor_constraints("provider_attempt_visit", dialect, positive=False),
    )
    op.create_index("ix_provider_attempt_visits_attempt_id", "provider_attempt_visits", ["attempt_id"])
    op.create_index("ix_provider_attempt_visits_visit_id", "provider_attempt_visits", ["visit_id"])
    op.create_table(
        "provider_active_visit_reservations",
        sa.Column("visit_id", sa.Integer(), sa.ForeignKey("visits.id", ondelete="RESTRICT"), primary_key=True),
        sa.Column("attempt_id", sa.Integer(), sa.ForeignKey("provider_attempts.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("attempt_visit_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["attempt_visit_id", "attempt_id", "visit_id"],
                                ["provider_attempt_visits.id", "provider_attempt_visits.attempt_id", "provider_attempt_visits.visit_id"],
                                name="fk_provider_active_reservation_history", ondelete="RESTRICT"),
        sa.UniqueConstraint("attempt_visit_id", name="uq_provider_active_history"),
        sa.CheckConstraint("visit_id > 0", name="ck_provider_active_visit_id"),
    )
    op.create_index("ix_provider_active_visit_reservations_attempt_id", "provider_active_visit_reservations", ["attempt_id"])
    if dialect == "postgresql":
        for table in ("provider_attempts", "provider_attempt_visits", "provider_active_visit_reservations"):
            op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")


def downgrade() -> None:
    dialect = op.get_context().dialect.name
    tables = ("provider_attempts", "provider_attempt_visits", "provider_active_visit_reservations")
    unsafe = " OR ".join(f"EXISTS (SELECT 1 FROM {table})" for table in tables)
    if dialect == "postgresql":
        op.execute("SET LOCAL row_security = off")
        op.execute("LOCK TABLE " + ", ".join(tables) + " IN ACCESS EXCLUSIVE MODE")
        op.execute(f"DO $$ BEGIN IF {unsafe} THEN RAISE EXCEPTION 'provider attempt downgrade would discard evidence'; END IF; END $$")
    elif dialect == "sqlite":
        op.execute("UPDATE provider_active_visit_reservations SET visit_id=visit_id WHERE 0")
        op.execute("CREATE TEMP TABLE provider_attempt_downgrade_guard_0111 (value INTEGER NOT NULL CHECK (value=0))")
        op.execute(f"INSERT INTO provider_attempt_downgrade_guard_0111 SELECT CASE WHEN {unsafe} THEN 1 ELSE 0 END")
        op.execute("DROP TABLE provider_attempt_downgrade_guard_0111")
    else:
        raise RuntimeError(f"Unsupported provider attempt dialect: {dialect}")
    op.drop_index("ix_provider_active_visit_reservations_attempt_id", table_name="provider_active_visit_reservations")
    op.drop_table("provider_active_visit_reservations")
    op.drop_index("ix_provider_attempt_visits_visit_id", table_name="provider_attempt_visits")
    op.drop_index("ix_provider_attempt_visits_attempt_id", table_name="provider_attempt_visits")
    op.drop_table("provider_attempt_visits")
    op.drop_table("provider_attempts")
