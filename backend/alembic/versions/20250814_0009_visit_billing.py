"""visit billing summary

Revision ID: 20250814_0009
Revises: 20250814_0008
Create Date: 2025-08-14
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "20250814_0009"
down_revision = "20250814_0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Итог по визиту (агрегаты по услугам/платежам)
    op.create_table(
        "visit_billings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "visit_id",
            sa.Integer(),
            sa.ForeignKey("visits.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column(
            "subtotal_services", sa.Numeric(12, 2), nullable=False, server_default="0"
        ),
        sa.Column("discount", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("total_due", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("paid_amount", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column(
            "currency", sa.String(length=8), nullable=False, server_default="UZS"
        ),
        sa.Column(
            "status", sa.String(length=16), nullable=False, server_default="open"
        ),  # open|partial|paid
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ux_visit_billings_visit", "visit_billings", ["visit_id"], unique=True
    )
    op.create_index("ix_visit_billings_status", "visit_billings", ["status"])


def downgrade() -> None:
    op.drop_index("ix_visit_billings_status", table_name="visit_billings")
    op.drop_index("ux_visit_billings_visit", table_name="visit_billings")
    op.drop_table("visit_billings")
