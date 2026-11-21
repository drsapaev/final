"""Persist revocable Telegram patient sessions independently of staff users."""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0103_telegram_mini_app_sessions"
down_revision = "0102_visit_confirm_context"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "telegram_mini_app_sessions",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("patient_id", sa.Integer(), nullable=False),
        sa.Column("telegram_user_id", sa.Integer(), nullable=False),
        sa.Column("patient_link_epoch", sa.BigInteger(), nullable=False),
        # Uniqueness consumes signed initData once across workers and restarts.
        sa.Column("init_data_hash", sa.String(64), nullable=False),
        sa.Column("refresh_token_hash", sa.String(64), nullable=False),
        sa.Column("device_label", sa.String(64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_active_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["patient_id"], ["patients.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["telegram_user_id"],
            ["telegram_users.id"],
            ondelete="CASCADE",
        ),
        sa.CheckConstraint(
            "patient_link_epoch >= 0", name="ck_tg_mini_session_link_epoch"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_telegram_mini_app_sessions"),
        sa.UniqueConstraint("init_data_hash", name="uq_tg_mini_session_init_data"),
        sa.UniqueConstraint("refresh_token_hash", name="uq_tg_mini_session_refresh"),
        sa.CheckConstraint(
            "expires_at > created_at",
            name="ck_tg_mini_session_expiry",
        ),
    )
    op.create_index(
        "ix_tg_mini_sessions_patient_active",
        "telegram_mini_app_sessions",
        ["patient_id", "revoked_at", "expires_at"],
    )
    op.create_index(
        "ix_tg_mini_sessions_telegram_user",
        "telegram_mini_app_sessions",
        ["telegram_user_id"],
    )
    # Match the repository's backend-only RLS boundary; no browser policies.
    op.execute(
        sa.text(
            "ALTER TABLE public.telegram_mini_app_sessions ENABLE ROW LEVEL SECURITY"
        )
    )


def downgrade() -> None:
    op.drop_index(
        "ix_tg_mini_sessions_telegram_user",
        table_name="telegram_mini_app_sessions",
    )
    op.drop_index(
        "ix_tg_mini_sessions_patient_active",
        table_name="telegram_mini_app_sessions",
    )
    op.drop_table("telegram_mini_app_sessions")
