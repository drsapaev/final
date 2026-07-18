"""Alembic migration: widen telegram_configs.bot_token for encrypted storage.

Revision ID: 0034_bot_token_encrypted
Revises: 0033_widen_backup_code_hash
Create Date: 2026-07-07

TG-AUDIT-28 P1: bot_token stored as plaintext String(200). Fernet-encrypted
tokens are ~200+ chars. Widen column to String(500) to accommodate encrypted
values. Existing plaintext tokens remain readable until re-encrypted.
"""
from alembic import op
import sqlalchemy as sa


revision = "0034_bot_token_encrypted"
down_revision = "0033_widen_backup_code_hash"
branch_labels = None
depends_on = None


def upgrade():
    # Widen bot_token column for Fernet-encrypted values
    op.alter_column(
        "telegram_configs",
        "bot_token",
        existing_type=sa.String(length=200),
        type_=sa.String(length=500),
        existing_nullable=True,
    )


def downgrade():
    op.alter_column(
        "telegram_configs",
        "bot_token",
        existing_type=sa.String(length=500),
        type_=sa.String(length=200),
        existing_nullable=True,
    )
