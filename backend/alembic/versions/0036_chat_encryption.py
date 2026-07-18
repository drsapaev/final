"""P1-4: Widen chat message columns for Fernet-encrypted content.

Revision ID: 0036_chat_encryption
Revises: 0035_fk_indexes
Create Date: 2026-07-07

Fernet-encrypted text is ~200+ chars for short messages. Widen Text columns
to accommodate encrypted values. Text type in PostgreSQL has no length limit,
so this migration is a no-op on PostgreSQL but documents the intent.
"""
from alembic import op

revision = "0036_chat_encryption"
down_revision = "0035_fk_indexes"
branch_labels = None
depends_on = None


def upgrade():
    # PostgreSQL Text type has no length limit — no change needed.
    # This migration exists for documentation and SQLite compatibility.
    pass


def downgrade():
    pass
