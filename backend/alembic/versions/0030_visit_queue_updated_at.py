"""Add updated_at to visits and queue entries.

Revision ID: 0030_visit_queue_updated_at
Revises: 0029_tg_patient_onboarding
Create Date: 2026-06-01 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "0030_visit_queue_updated_at"
down_revision = "0029_tg_patient_onboarding"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "visits",
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=True,
        ),
    )
    op.add_column(
        "queue_entries",
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=True,
        ),
    )
    op.execute(
        "UPDATE visits SET updated_at = COALESCE(updated_at, created_at, CURRENT_TIMESTAMP)"
    )
    op.execute(
        "UPDATE queue_entries SET updated_at = COALESCE(updated_at, created_at, CURRENT_TIMESTAMP)"
    )


def downgrade() -> None:
    op.drop_column("queue_entries", "updated_at")
    op.drop_column("visits", "updated_at")
