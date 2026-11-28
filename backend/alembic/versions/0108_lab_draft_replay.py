"""Record committed lab draft operations without storing request bodies."""

import sqlalchemy as sa

from alembic import op

revision = "0108_lab_draft_replay"
down_revision = "0107_lab_rejection_reason"
branch_labels = None
depends_on = None

TABLE = "lab_draft_mutation_receipts"


def upgrade() -> None:
    op.create_table(
        TABLE,
        sa.Column(
            "instance_id", sa.Integer(),
            sa.ForeignKey("lab_report_instances.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "actor_user_id", sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("operation", sa.String(8), primary_key=True),
        sa.Column("request_id", sa.Uuid(), primary_key=True),
        sa.Column("request_digest", sa.String(64), nullable=False),
        sa.Column("applied_version", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "operation IN ('metadata', 'values')",
            name="ck_lab_draft_receipt_operation",
        ),
    )
    op.create_index(f"ix_{TABLE}_actor_user_id", TABLE, ["actor_user_id"])
    if op.get_context().dialect.name == "postgresql":
        op.execute(f"ALTER TABLE public.{TABLE} ENABLE ROW LEVEL SECURITY")


def downgrade() -> None:
    op.drop_table(TABLE)
