"""Record committed lab report creation without storing submitted data."""

import sqlalchemy as sa

from alembic import op

revision = "0109_lab_create_receipt"
down_revision = "0108_lab_draft_replay"
branch_labels = None
depends_on = None

TABLE = "lab_report_creation_receipts"


def upgrade() -> None:
    op.create_table(
        TABLE,
        sa.Column(
            "actor_user_id", sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True,
        ),
        sa.Column("key_digest", sa.String(64), primary_key=True),
        sa.Column("request_digest", sa.String(64), nullable=False),
        sa.Column(
            "instance_id", sa.Integer(),
            sa.ForeignKey("lab_report_instances.id", ondelete="CASCADE"), nullable=False,
        ),
    )
    op.create_index(f"ix_{TABLE}_instance_id", TABLE, ["instance_id"])
    if op.get_context().dialect.name == "postgresql":
        op.execute(f"ALTER TABLE public.{TABLE} ENABLE ROW LEVEL SECURITY")


def downgrade() -> None:
    op.drop_table(TABLE)
