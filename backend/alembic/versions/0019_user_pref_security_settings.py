"""add security settings json to user_preferences

Revision ID: 0019_user_pref_security_settings
Revises: 0018_display_config_tables
Create Date: 2026-03-28 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0019_user_pref_security_settings"
down_revision = "0018_display_config_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "user_preferences",
        sa.Column("security_settings", sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("user_preferences", "security_settings")
