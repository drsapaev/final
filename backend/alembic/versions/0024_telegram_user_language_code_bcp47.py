"""Store Telegram user language codes as BCP 47 tags.

Revision ID: 0024_telegram_user_language_code_bcp47
Revises: 0023_ticket_print_qr_default
Create Date: 2026-05-16 10:55:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "0024_telegram_user_language_code_bcp47"
down_revision = "0023_ticket_print_qr_default"
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
