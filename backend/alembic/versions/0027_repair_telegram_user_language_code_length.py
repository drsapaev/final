"""Repair Telegram user language code length.

Revision ID: 0027_repair_tg_user_lang_len
Revises: 0026_tg_staff_confirm_tokens
Create Date: 2026-05-18 11:20:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "0027_repair_tg_user_lang_len"
down_revision = "0026_tg_staff_confirm_tokens"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "telegram_users",
        "language_code",
        existing_type=sa.String(length=5),
        type_=sa.String(length=16),
        existing_nullable=False,
    )
    op.execute(
        """
        UPDATE telegram_users
        SET language_code = 'uz-Latn'
        WHERE lower(replace(language_code, '_', '-')) IN ('uz', 'uz-latn')
           OR lower(replace(language_code, '_', '-')) LIKE 'uz-%'
        """
    )


def downgrade() -> None:
    op.execute(
        """
        UPDATE telegram_users
        SET language_code = 'uz'
        WHERE lower(replace(language_code, '_', '-')) = 'uz-latn'
           OR lower(replace(language_code, '_', '-')) LIKE 'uz-%'
        """
    )
    op.alter_column(
        "telegram_users",
        "language_code",
        existing_type=sa.String(length=16),
        type_=sa.String(length=5),
        existing_nullable=False,
    )
