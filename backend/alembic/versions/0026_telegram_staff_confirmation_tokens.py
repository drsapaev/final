"""Create Telegram staff confirmation token storage.

Revision ID: 0026_telegram_staff_confirmation_tokens
Revises: 0025_telegram_staff_link_tokens
Create Date: 2026-05-18 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "0026_telegram_staff_confirmation_tokens"
down_revision = "0025_telegram_staff_link_tokens"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "telegram_staff_confirmation_tokens",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("token_hash", sa.String(length=96), nullable=False),
        sa.Column("staff_user_id", sa.Integer(), nullable=False),
        sa.Column("telegram_chat_id", sa.BigInteger(), nullable=False),
        sa.Column("operation_key", sa.String(length=96), nullable=False),
        sa.Column("command_key", sa.String(length=64), nullable=True),
        sa.Column("action_payload_hash", sa.String(length=96), nullable=False),
        sa.Column("target_type", sa.String(length=64), nullable=True),
        sa.Column("target_reference_hash", sa.String(length=96), nullable=True),
        sa.Column("idempotency_key_hash", sa.String(length=96), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=True,
        ),
        sa.Column("request_id", sa.String(length=64), nullable=True),
        sa.CheckConstraint(
            "expires_at > created_at",
            name="ck_telegram_staff_confirmation_tokens_expires_after_created",
        ),
        sa.CheckConstraint(
            "consumed_at IS NULL OR consumed_at <= expires_at",
            name="ck_telegram_staff_confirmation_tokens_consumed_before_expiry",
        ),
        sa.CheckConstraint(
            "operation_key <> ''",
            name="ck_telegram_staff_confirmation_tokens_operation_not_empty",
        ),
        sa.CheckConstraint(
            "action_payload_hash <> ''",
            name="ck_telegram_staff_confirmation_tokens_payload_hash_not_empty",
        ),
        sa.ForeignKeyConstraint(
            ["staff_user_id"],
            ["users.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_telegram_staff_confirmation_tokens_id"),
        "telegram_staff_confirmation_tokens",
        ["id"],
        unique=False,
    )
    op.create_index(
        "ix_telegram_staff_confirmation_tokens_token_hash",
        "telegram_staff_confirmation_tokens",
        ["token_hash"],
        unique=True,
    )
    op.create_index(
        "ix_telegram_staff_confirmation_tokens_staff_user_id",
        "telegram_staff_confirmation_tokens",
        ["staff_user_id"],
        unique=False,
    )
    op.create_index(
        "ix_telegram_staff_confirmation_tokens_telegram_chat_id",
        "telegram_staff_confirmation_tokens",
        ["telegram_chat_id"],
        unique=False,
    )
    op.create_index(
        "ix_telegram_staff_confirmation_tokens_operation_key",
        "telegram_staff_confirmation_tokens",
        ["operation_key"],
        unique=False,
    )
    op.create_index(
        "ix_telegram_staff_confirmation_tokens_unconsumed_expires",
        "telegram_staff_confirmation_tokens",
        ["expires_at"],
        unique=False,
        postgresql_where=sa.text("consumed_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index(
        "ix_telegram_staff_confirmation_tokens_unconsumed_expires",
        table_name="telegram_staff_confirmation_tokens",
        postgresql_where=sa.text("consumed_at IS NULL"),
    )
    op.drop_index(
        "ix_telegram_staff_confirmation_tokens_operation_key",
        table_name="telegram_staff_confirmation_tokens",
    )
    op.drop_index(
        "ix_telegram_staff_confirmation_tokens_telegram_chat_id",
        table_name="telegram_staff_confirmation_tokens",
    )
    op.drop_index(
        "ix_telegram_staff_confirmation_tokens_staff_user_id",
        table_name="telegram_staff_confirmation_tokens",
    )
    op.drop_index(
        "ix_telegram_staff_confirmation_tokens_token_hash",
        table_name="telegram_staff_confirmation_tokens",
    )
    op.drop_index(
        op.f("ix_telegram_staff_confirmation_tokens_id"),
        table_name="telegram_staff_confirmation_tokens",
    )
    op.drop_table("telegram_staff_confirmation_tokens")
