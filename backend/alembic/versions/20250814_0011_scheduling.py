"""schedule templates

Revision ID: 20250814_0011_scheduling
Revises: 20250814_0010_service_catalog
Create Date: 2025-08-14 12:11:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "20250814_0011"
down_revision = "20250814_0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "schedule_templates",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("department", sa.String(length=64), nullable=True),
        sa.Column("doctor_id", sa.Integer(), nullable=True),
        sa.Column("weekday", sa.Integer(), nullable=False),
        sa.Column("start_time", sa.String(length=5), nullable=False),
        sa.Column("end_time", sa.String(length=5), nullable=False),
        sa.Column("room", sa.String(length=64), nullable=True),
        sa.Column("capacity_per_hour", sa.Integer(), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text("1")),
    )
    op.create_index("ix_sched_dep", "schedule_templates", ["department"])
    op.create_index("ix_sched_doc", "schedule_templates", ["doctor_id"])
    op.create_index("ix_sched_wd", "schedule_templates", ["weekday"])


def downgrade() -> None:
    op.drop_index("ix_sched_wd", table_name="schedule_templates")
    op.drop_index("ix_sched_doc", table_name="schedule_templates")
    op.drop_index("ix_sched_dep", table_name="schedule_templates")
    op.drop_table("schedule_templates")
