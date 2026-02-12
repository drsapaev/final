"""auth/session additions

Revision ID: 20250814_0002
Revises: 20250814_0001
Create Date: 2025-08-14
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20250814_0002"
down_revision = "20250814_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # user profile/auth extras
    op.add_column(
        "users", sa.Column("last_login", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column(
        "users",
        sa.Column("password_changed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column(
            "email_verified", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
    )

    # sessions / refresh tokens
    op.create_table(
        "user_sessions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("refresh_token", sa.String(length=128), nullable=False),
        sa.Column("user_agent", sa.String(length=512), nullable=True),
        sa.Column("ip", sa.String(length=64), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.create_index(
        "ux_user_sessions_token", "user_sessions", ["refresh_token"], unique=True
    )
    op.create_index("ix_user_sessions_user", "user_sessions", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_user_sessions_user", table_name="user_sessions")
    op.drop_index("ux_user_sessions_token", table_name="user_sessions")
    op.drop_table("user_sessions")

    op.drop_column("users", "email_verified")
    op.drop_column("users", "password_changed_at")
    op.drop_column("users", "last_login")
