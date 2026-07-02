"""payments

Revision ID: 20250814_0006
Revises: 20250814_0005
Create Date: 2025-08-14
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20250814_0006"
down_revision = "20250814_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "payments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "visit_id",
            sa.Integer(),
            sa.ForeignKey("visits.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "cashier_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column(
            "currency", sa.String(length=8), nullable=False, server_default="UZS"
        ),
        sa.Column(
            "method", sa.String(length=16), nullable=False, server_default="cash"
        ),  # cash|card|transfer
        sa.Column(
            "status", sa.String(length=16), nullable=False, server_default="paid"
        ),  # paid|void|refunded
        sa.Column("receipt_no", sa.String(length=64), nullable=True),
        sa.Column("note", sa.String(length=512), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_payments_visit", "payments", ["visit_id"])
    op.create_index("ix_payments_cashier", "payments", ["cashier_id"])
    op.create_index("ix_payments_status", "payments", ["status"])
    op.create_index("ux_payments_receipt", "payments", ["receipt_no"], unique=True)


def downgrade() -> None:
    op.drop_index("ux_payments_receipt", table_name="payments")
    op.drop_index("ix_payments_status", table_name="payments")
    op.drop_index("ix_payments_cashier", table_name="payments")
    op.drop_index("ix_payments_visit", table_name="payments")
    op.drop_table("payments")
