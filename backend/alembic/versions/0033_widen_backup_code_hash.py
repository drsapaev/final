"""widen two_factor_backup_codes.code to VARCHAR(64) for SHA-256 hashes (F-AUTH-001)

Revision ID: 0033_widen_backup_code_hash
Revises: 0032_messages_branch_id
Create Date: 2026-07-07

Re-audit AUTH-REAUDIT-28 P0 fix: PR #1941 hashed backup codes with SHA-256
(64-char hex), but the column stayed at VARCHAR(10). PostgreSQL raises
DataError on INSERT; SQLite silently truncates (masking the bug in dev/test).

This migration widens the column to VARCHAR(64). Existing rows (if any) are
already 64-char hashes from two_factor_service._hash_backup_code, so no
data backfill is needed.
"""
from alembic import op
import sqlalchemy as sa


revision = "0033_widen_backup_code_hash"
down_revision = "0032_messages_branch_id"
branch_labels = None
depends_on = None


def upgrade():
    # PostgreSQL: ALTER COLUMN ... TYPE VARCHAR(64) — safe (widening).
    # SQLite: alembic batch mode required (SQLite cannot ALTER COLUMN in-place).
    op.alter_column(
        "two_factor_backup_codes",
        "code",
        existing_type=sa.String(length=10),
        type_=sa.String(length=64),
        nullable=False,
        existing_nullable=False,
    )


def downgrade():
    # Narrowing back to VARCHAR(10) would truncate SHA-256 hashes — destructive.
    # Only allow if all rows have been migrated back to plaintext (not the case).
    op.alter_column(
        "two_factor_backup_codes",
        "code",
        existing_type=sa.String(length=64),
        type_=sa.String(length=10),
        nullable=False,
        existing_nullable=False,
    )
