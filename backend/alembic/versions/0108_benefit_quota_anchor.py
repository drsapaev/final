"""Add quota mutexes and immutable period evidence to benefit applications.

This migration does not authorize benefits. It refuses to invent periods for
applications recorded before this schema and refuses a destructive downgrade.
"""

import sqlalchemy as sa

from alembic import op

revision = "0108_benefit_quota_anchor"
down_revision = "0107_all_free_requests"
branch_labels = None
depends_on = None


def _require_empty(*tables: str) -> None:
    dialect = op.get_context().dialect.name
    if dialect == "postgresql":
        op.execute("SET LOCAL row_security = off")
        op.execute("LOCK TABLE " + ", ".join(tables) + " IN ACCESS EXCLUSIVE MODE")
        conditions = " OR ".join(f"EXISTS (SELECT 1 FROM {table})" for table in tables)
        op.execute(f"DO $$ BEGIN IF {conditions} THEN RAISE EXCEPTION 'benefit quota migration requires empty evidence'; END IF; END $$")
    elif dialect == "sqlite":
        op.execute(f"UPDATE {tables[0]} SET id=id WHERE 0")
        op.execute("CREATE TEMP TABLE _benefit_quota_guard (id INTEGER)")
        conditions = " OR ".join(f"EXISTS (SELECT 1 FROM {table})" for table in tables)
        op.execute(f"""
            CREATE TEMP TRIGGER _benefit_quota_guard_refuse
            BEFORE INSERT ON _benefit_quota_guard WHEN {conditions}
            BEGIN SELECT RAISE(ABORT, 'benefit quota migration requires empty evidence'); END
        """)
        op.execute("INSERT INTO _benefit_quota_guard VALUES (1)")
        op.execute("DROP TRIGGER _benefit_quota_guard_refuse")
        op.execute("DROP TABLE _benefit_quota_guard")
    else:
        raise RuntimeError("Unsupported benefit quota dialect")


def upgrade() -> None:
    _require_empty(
        "encounter_benefit_applications",
        "encounter_benefit_allocations",
        "encounter_benefit_events",
    )
    op.create_table(
        "encounter_benefit_quota_anchors",
        sa.Column("patient_id", sa.Integer(), primary_key=True),
        sa.Column("benefit_id", sa.Integer(), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("patient_id > 0 AND benefit_id > 0", name="ck_enc_benefit_anchor_positive"),
    )
    if op.get_context().dialect.name == "postgresql":
        op.execute("ALTER TABLE encounter_benefit_quota_anchors ENABLE ROW LEVEL SECURITY")
    op.add_column("encounter_benefit_applications", sa.Column("period_timezone", sa.String(64), nullable=False))
    op.add_column("encounter_benefit_applications", sa.Column("period_month", sa.Date(), nullable=False))
    op.add_column("encounter_benefit_applications", sa.Column("period_year", sa.Integer(), nullable=False))


def downgrade() -> None:
    _require_empty(
        "encounter_benefit_applications",
        "encounter_benefit_allocations",
        "encounter_benefit_events",
        "encounter_benefit_quota_anchors",
    )
    op.drop_column("encounter_benefit_applications", "period_year")
    op.drop_column("encounter_benefit_applications", "period_month")
    op.drop_column("encounter_benefit_applications", "period_timezone")
    op.drop_table("encounter_benefit_quota_anchors")
