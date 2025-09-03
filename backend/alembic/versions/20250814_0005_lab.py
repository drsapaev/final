"""lab orders & results

Revision ID: 20250814_0005
Revises: 20250814_0004
Create Date: 2025-08-14
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "20250814_0005"
down_revision = "20250814_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # lab_orders
    op.create_table(
        "lab_orders",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "visit_id",
            sa.Integer(),
            sa.ForeignKey("visits.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "patient_id",
            sa.Integer(),
            sa.ForeignKey("patients.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "status", sa.String(length=16), nullable=False, server_default="ordered"
        ),  # ordered|in_progress|done|canceled
        sa.Column("notes", sa.String(length=1000), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_lab_orders_visit", "lab_orders", ["visit_id"])
    op.create_index("ix_lab_orders_patient", "lab_orders", ["patient_id"])
    op.create_index("ix_lab_orders_status", "lab_orders", ["status"])

    # lab_results (per-test rows)
    op.create_table(
        "lab_results",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "order_id",
            sa.Integer(),
            sa.ForeignKey("lab_orders.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("test_code", sa.String(length=64), nullable=True),
        sa.Column("test_name", sa.String(length=255), nullable=False),
        sa.Column("value", sa.String(length=128), nullable=True),
        sa.Column("unit", sa.String(length=32), nullable=True),
        sa.Column("ref_range", sa.String(length=64), nullable=True),
        sa.Column(
            "abnormal", sa.Boolean(), nullable=False, server_default=sa.text("0")
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_lab_results_order", "lab_results", ["order_id"])
    op.create_index("ix_lab_results_code", "lab_results", ["test_code"])


def downgrade() -> None:
    op.drop_index("ix_lab_results_code", table_name="lab_results")
    op.drop_index("ix_lab_results_order", table_name="lab_results")
    op.drop_table("lab_results")

    op.drop_index("ix_lab_orders_status", table_name="lab_orders")
    op.drop_index("ix_lab_orders_patient", table_name="lab_orders")
    op.drop_index("ix_lab_orders_visit", table_name="lab_orders")
    op.drop_table("lab_orders")
