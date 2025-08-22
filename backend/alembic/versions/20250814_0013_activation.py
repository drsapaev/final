"""activation table

Revision ID: 20250814_0013_activation
Revises: 20250814_0012_online_queue
Create Date: 2025-08-17 12:00:00.000000
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20250814_0013"
down_revision = "20250814_0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "activations",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column("key", sa.String(length=64), nullable=False, index=True),
        sa.Column("machine_hash", sa.String(length=128), nullable=True, index=True),
        sa.Column("expiry_date", sa.DateTime(), nullable=True, index=True),
        sa.Column("status", sa.Enum("issued", "trial", "active", "expired", "revoked", name="activation_status"), nullable=False, server_default="issued"),
        sa.Column("meta", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("key", name="uq_activation_key"),
    )


def downgrade() -> None:
    op.drop_table("activations")
    try:
        op.execute("DROP TYPE activation_status")
    except Exception:
        pass