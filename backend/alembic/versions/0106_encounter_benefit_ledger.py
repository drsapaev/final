"""Add schema-only encounter benefit snapshots and once-per-encounter key.

This is not a benefit workflow. Future writers must enforce authorization,
quota accounting, generation invalidation, allocation closure, append-only
state and concurrency before using these tables. No existing benefit rows
are backfilled or interpreted as encounter applications.
"""

import sqlalchemy as sa

from alembic import op

revision = "0106_encounter_benefit_ledger"
down_revision = "0105_price_override_binding"
branch_labels = None
depends_on = None


def upgrade() -> None:
    dialect = op.get_context().dialect.name
    if dialect not in {"postgresql", "sqlite"}:
        raise RuntimeError("Unsupported benefit-ledger migration dialect")
    op.create_table(
        "encounter_benefit_applications",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("encounter_id", sa.Integer(), sa.ForeignKey("encounters.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("patient_id", sa.Integer(), sa.ForeignKey("patients.id", ondelete="SET NULL"), nullable=True),
        sa.Column("patient_id_snapshot", sa.Integer(), nullable=False),
        sa.Column("patient_benefit_id", sa.Integer(), sa.ForeignKey("patient_benefits.id", ondelete="SET NULL"), nullable=True),
        sa.Column("patient_benefit_id_snapshot", sa.Integer(), nullable=False),
        sa.Column("benefit_id", sa.Integer(), sa.ForeignKey("benefits.id", ondelete="SET NULL"), nullable=True),
        sa.Column("benefit_id_snapshot", sa.Integer(), nullable=False),
        sa.Column("approved_by_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("approved_by_user_id_snapshot", sa.Integer(), nullable=False),
        sa.Column("approved_by_role_snapshot", sa.String(32), nullable=False),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("encounter_generation", sa.BigInteger(), nullable=False),
        sa.Column("percentage", sa.Numeric(7, 4), nullable=False),
        sa.Column("max_discount", sa.Numeric(12, 2), nullable=True),
        sa.Column("monthly_limit", sa.Numeric(12, 2), nullable=True),
        sa.Column("yearly_limit", sa.Numeric(12, 2), nullable=True),
        sa.Column("monthly_used_before", sa.Numeric(12, 2), nullable=False),
        sa.Column("yearly_used_before", sa.Numeric(12, 2), nullable=False),
        sa.Column("gross_total", sa.Numeric(12, 2), nullable=False),
        sa.Column("benefit_total", sa.Numeric(12, 2), nullable=False),
        sa.Column("net_total", sa.Numeric(12, 2), nullable=False),
        sa.UniqueConstraint("encounter_id", name="uq_encounter_benefit_once"),
        sa.ForeignKeyConstraint(
            ["encounter_id", "patient_id"], ["encounters.id", "encounters.patient_id"],
            name="fk_enc_benefit_encounter_patient", onupdate="CASCADE", deferrable=True, initially="DEFERRED",
        ),
        sa.CheckConstraint("patient_id IS NULL OR patient_id = patient_id_snapshot", name="ck_enc_benefit_patient_snapshot"),
        sa.CheckConstraint("patient_benefit_id IS NULL OR patient_benefit_id = patient_benefit_id_snapshot", name="ck_enc_benefit_assignment_snapshot"),
        sa.CheckConstraint("benefit_id IS NULL OR benefit_id = benefit_id_snapshot", name="ck_enc_benefit_benefit_snapshot"),
        sa.CheckConstraint("approved_by_user_id IS NULL OR approved_by_user_id = approved_by_user_id_snapshot", name="ck_enc_benefit_actor_snapshot"),
        sa.CheckConstraint("patient_id_snapshot > 0 AND patient_benefit_id_snapshot > 0 AND benefit_id_snapshot > 0 AND approved_by_user_id_snapshot > 0", name="ck_enc_benefit_snapshot_ids"),
        sa.CheckConstraint("encounter_generation > 0", name="ck_enc_benefit_generation"),
        sa.CheckConstraint("percentage >= 0 AND percentage <= 100", name="ck_enc_benefit_percentage"),
        sa.CheckConstraint("gross_total >= 0 AND gross_total <= 9999999999.99 AND gross_total = round(gross_total, 2)", name="ck_enc_benefit_gross"),
        sa.CheckConstraint("benefit_total > 0 AND benefit_total <= gross_total AND benefit_total = round(benefit_total, 2)", name="ck_enc_benefit_discount"),
        sa.CheckConstraint("net_total >= 0 AND net_total <= 9999999999.99 AND net_total = round(net_total, 2) AND round(gross_total - benefit_total, 2) = net_total", name="ck_enc_benefit_net"),
        sa.CheckConstraint("max_discount IS NULL OR (max_discount >= 0 AND max_discount <= 9999999999.99 AND max_discount = round(max_discount, 2))", name="ck_enc_benefit_max"),
        sa.CheckConstraint("monthly_limit IS NULL OR (monthly_limit >= 0 AND monthly_limit <= 9999999999.99 AND monthly_limit = round(monthly_limit, 2))", name="ck_enc_benefit_monthly_limit"),
        sa.CheckConstraint("yearly_limit IS NULL OR (yearly_limit >= 0 AND yearly_limit <= 9999999999.99 AND yearly_limit = round(yearly_limit, 2))", name="ck_enc_benefit_yearly_limit"),
        sa.CheckConstraint("monthly_used_before >= 0 AND monthly_used_before <= 9999999999.99 AND monthly_used_before = round(monthly_used_before, 2)", name="ck_enc_benefit_monthly_before"),
        sa.CheckConstraint("yearly_used_before >= 0 AND yearly_used_before <= 9999999999.99 AND yearly_used_before = round(yearly_used_before, 2)", name="ck_enc_benefit_yearly_before"),
        sa.CheckConstraint("length(trim(approved_by_role_snapshot)) > 0", name="ck_enc_benefit_actor_role"),
    )
    op.create_table(
        "encounter_benefit_allocations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("application_id", sa.Integer(), sa.ForeignKey("encounter_benefit_applications.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("visit_id", sa.Integer(), sa.ForeignKey("visits.id", ondelete="SET NULL"), nullable=True),
        sa.Column("visit_id_snapshot", sa.Integer(), nullable=False),
        sa.Column("visit_service_id", sa.Integer(), sa.ForeignKey("visit_services.id", ondelete="SET NULL"), nullable=True),
        sa.Column("visit_service_id_snapshot", sa.Integer(), nullable=False),
        sa.Column("service_id_snapshot", sa.Integer(), nullable=False),
        sa.Column("visit_context_epoch", sa.BigInteger(), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("unit_price", sa.Numeric(12, 2), nullable=False),
        sa.Column("gross_amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("benefit_amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("net_amount", sa.Numeric(12, 2), nullable=False),
        sa.UniqueConstraint("application_id", "visit_service_id_snapshot", name="uq_enc_benefit_alloc_line"),
        sa.CheckConstraint("visit_id IS NULL OR visit_id = visit_id_snapshot", name="ck_enc_benefit_alloc_visit_snapshot"),
        sa.CheckConstraint("visit_service_id IS NULL OR visit_service_id = visit_service_id_snapshot", name="ck_enc_benefit_alloc_line_snapshot"),
        sa.CheckConstraint("visit_id_snapshot > 0 AND visit_service_id_snapshot > 0 AND service_id_snapshot > 0", name="ck_enc_benefit_alloc_snapshot_ids"),
        sa.CheckConstraint("visit_context_epoch > 0", name="ck_enc_benefit_alloc_epoch"),
        sa.CheckConstraint("quantity > 0 AND quantity <= 2147483647 AND quantity = CAST(quantity AS INTEGER)", name="ck_enc_benefit_alloc_qty"),
        sa.CheckConstraint("unit_price >= 0 AND unit_price <= 9999999999.99 AND unit_price = round(unit_price, 2)", name="ck_enc_benefit_alloc_unit"),
        sa.CheckConstraint("gross_amount >= 0 AND gross_amount <= 9999999999.99 AND gross_amount = round(gross_amount, 2) AND round(unit_price * quantity, 2) = gross_amount", name="ck_enc_benefit_alloc_gross"),
        sa.CheckConstraint("benefit_amount >= 0 AND benefit_amount <= gross_amount AND benefit_amount = round(benefit_amount, 2)", name="ck_enc_benefit_alloc_discount"),
        sa.CheckConstraint("net_amount >= 0 AND net_amount <= 9999999999.99 AND net_amount = round(net_amount, 2) AND round(gross_amount - benefit_amount, 2) = net_amount", name="ck_enc_benefit_alloc_net"),
    )
    op.create_index("ix_encounter_benefit_allocations_application_id", "encounter_benefit_allocations", ["application_id"])
    op.create_table(
        "encounter_benefit_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("application_id", sa.Integer(), sa.ForeignKey("encounter_benefit_applications.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("event_type", sa.String(16), nullable=False),
        sa.Column("actor_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("actor_user_id_snapshot", sa.Integer(), nullable=False),
        sa.Column("actor_role_snapshot", sa.String(32), nullable=False),
        sa.Column("reason_code", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("event_type IN ('reversed', 'voided', 'corrected')", name="ck_enc_benefit_event_type"),
        sa.CheckConstraint("actor_user_id IS NULL OR actor_user_id = actor_user_id_snapshot", name="ck_enc_benefit_event_actor_snapshot"),
        sa.CheckConstraint("actor_user_id_snapshot > 0 AND length(trim(actor_role_snapshot)) > 0", name="ck_enc_benefit_event_actor"),
        sa.CheckConstraint("length(trim(reason_code)) > 0", name="ck_enc_benefit_event_reason"),
    )
    op.create_index("ix_encounter_benefit_events_application_id", "encounter_benefit_events", ["application_id"])
    if dialect == "postgresql":
        for table in ("encounter_benefit_applications", "encounter_benefit_allocations", "encounter_benefit_events"):
            op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")


def downgrade() -> None:
    dialect = op.get_context().dialect.name
    tables = ("encounter_benefit_applications", "encounter_benefit_allocations", "encounter_benefit_events")
    if dialect == "postgresql":
        # If forced RLS would hide rows, error instead of mistaking the ledger
        # for an empty one. A bypass-capable migration owner can still check it.
        op.execute("SET LOCAL row_security = off")
        op.execute("LOCK TABLE " + ", ".join(tables) + " IN ACCESS EXCLUSIVE MODE")
        op.execute("""
        DO $$ BEGIN
          IF EXISTS (SELECT 1 FROM encounter_benefit_applications)
             OR EXISTS (SELECT 1 FROM encounter_benefit_allocations)
             OR EXISTS (SELECT 1 FROM encounter_benefit_events) THEN
            RAISE EXCEPTION 'benefit ledger contains data; downgrade refused';
          END IF;
        END $$
        """)
    elif dialect == "sqlite":
        # Acquire the main-database write reservation before checking so no
        # concurrent writer can add evidence between the check and DDL.
        op.execute("UPDATE encounter_benefit_applications SET id=id WHERE 0")
        op.execute("CREATE TEMP TABLE _benefit_ledger_downgrade_guard (id INTEGER)")
        op.execute("""
        CREATE TEMP TRIGGER _benefit_ledger_downgrade_refuse
        BEFORE INSERT ON _benefit_ledger_downgrade_guard
        WHEN EXISTS (SELECT 1 FROM encounter_benefit_applications)
          OR EXISTS (SELECT 1 FROM encounter_benefit_allocations)
          OR EXISTS (SELECT 1 FROM encounter_benefit_events)
        BEGIN SELECT RAISE(ABORT, 'benefit ledger contains data; downgrade refused'); END
        """)
        op.execute("INSERT INTO _benefit_ledger_downgrade_guard VALUES (1)")
        op.execute("DROP TRIGGER _benefit_ledger_downgrade_refuse")
        op.execute("DROP TABLE _benefit_ledger_downgrade_guard")
    else:
        raise RuntimeError("Unsupported benefit-ledger migration dialect")
    op.drop_index("ix_encounter_benefit_events_application_id", table_name="encounter_benefit_events")
    op.drop_table("encounter_benefit_events")
    op.drop_index("ix_encounter_benefit_allocations_application_id", table_name="encounter_benefit_allocations")
    op.drop_table("encounter_benefit_allocations")
    op.drop_table("encounter_benefit_applications")
