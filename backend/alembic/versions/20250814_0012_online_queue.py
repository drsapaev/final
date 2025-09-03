"""online_days table (online queue day registry)

Revision ID: 20250814_0012_online_queue
Revises: 20250814_0011_scheduling
Create Date: 2025-08-14 12:12:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "20250814_0012"
down_revision = "20250814_0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "online_days",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("department", sa.String(length=64), nullable=False),
        sa.Column("date_str", sa.String(length=16), nullable=False),
        sa.Column("start_number", sa.Integer(), nullable=True),
        sa.Column("is_open", sa.Boolean(), nullable=False, server_default=sa.text("1")),
    )
    op.create_index("ix_online_days_dep", "online_days", ["department"])
    op.create_index("ix_online_days_date", "online_days", ["date_str"])

    # SQLite-safe unique constraint replacement
    _bind = op.get_bind()
    if _bind.dialect.name == "sqlite":
        op.create_index(
            "uq_online_day_dep_date__uniq_idx",
            "online_days",
            ["department", "date_str"],
            unique=True,
        )
    else:
        op.create_unique_constraint(
            "uq_online_day_dep_date",
            "online_days",
            ["department", "date_str"],
        )


def downgrade() -> None:
    _bind = op.get_bind()
    if _bind.dialect.name == "sqlite":
        op.drop_index("uq_online_day_dep_date__uniq_idx", table_name="online_days")
    else:
        op.drop_constraint("uq_online_day_dep_date", "online_days", type_="unique")

    op.drop_index("ix_online_days_date", table_name="online_days")
    op.drop_index("ix_online_days_dep", table_name="online_days")
    op.drop_table("online_days")
