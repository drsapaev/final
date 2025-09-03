"""key-value settings

Revision ID: 20250814_0007
Revises: 20250814_0006
Create Date: 2025-08-14
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20250814_0007"
down_revision = "20250814_0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "settings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "category", sa.String(length=64), nullable=False, server_default="default"
        ),
        sa.Column("key", sa.String(length=64), nullable=False),
        sa.Column("value", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_settings_category", "settings", ["category"])
    op.create_index("ux_settings_cat_key", "settings", ["category", "key"], unique=True)


def downgrade() -> None:
    op.drop_index("ux_settings_cat_key", table_name="settings")
    op.drop_index("ix_settings_category", table_name="settings")
    op.drop_table("settings")
