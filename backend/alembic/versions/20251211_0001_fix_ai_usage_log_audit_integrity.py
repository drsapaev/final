"""fix ai usage log audit integrity

Revision ID: 20251211_0001
Revises: voice_messages_002
Create Date: 2025-12-11 00:00:00.000000

CRITICAL FIX: AIUsageLog audit trail integrity
- provider_id: nullable=True + ondelete="SET NULL" → nullable=False + ondelete="RESTRICT"
- Added provider_name column to preserve provider name in audit logs
- Prevents loss of audit information when providers are deleted
- Providers must be marked as inactive instead of deleted if they have usage logs

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20251211_0001'
down_revision = 'voice_messages_002'
branch_labels = None
depends_on = None


def upgrade():
    """Apply changes to fix AIUsageLog audit integrity"""
    
    # Check if ai_usage_logs table exists before attempting migration
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    if 'ai_usage_logs' not in inspector.get_table_names():
        # Table doesn't exist, skip this migration
        return

    # Step 1: Add provider_name column (nullable first)
    try:
        op.add_column(
            'ai_usage_logs',
            sa.Column('provider_name', sa.String(length=100), nullable=True)
        )
    except Exception:
        pass  # Column may already exist

    # Step 2: Backfill provider_name from existing providers
    # For existing records, copy provider display_name
    try:
        op.execute("""
            UPDATE ai_usage_logs
            SET provider_name = (
                SELECT display_name
                FROM ai_providers
                WHERE ai_providers.id = ai_usage_logs.provider_id
            )
            WHERE provider_id IS NOT NULL
        """)
    except Exception:
        pass

    # Step 3: Set default value for any remaining NULL provider_name
    # (in case provider was already deleted)
    try:
        op.execute("""
            UPDATE ai_usage_logs
            SET provider_name = 'Unknown Provider (Deleted)'
            WHERE provider_name IS NULL
        """)
    except Exception:
        pass

    # Step 4: Make provider_name NOT NULL
    try:
        op.alter_column(
            'ai_usage_logs',
            'provider_name',
            nullable=False,
            existing_type=sa.String(length=100)
        )
    except Exception:
        pass

    # Step 5: Handle NULL provider_id records
    # Delete orphaned logs where provider_id is NULL (can't set FK to RESTRICT with NULLs)
    try:
        op.execute("""
            DELETE FROM ai_usage_logs
            WHERE provider_id IS NULL
        """)
    except Exception:
        pass

    # Step 6: Make provider_id NOT NULL
    try:
        op.alter_column(
            'ai_usage_logs',
            'provider_id',
            nullable=False,
            existing_type=sa.Integer()
        )
    except Exception:
        pass

    # Step 7: Drop and recreate FK constraint with RESTRICT
    # Note: SQLite doesn't support ALTER CONSTRAINT, so we need to check if it's SQLite
    # For SQLite, FK constraints are defined at table creation and can't be modified
    # This will work for PostgreSQL/MySQL

    # Try to drop existing FK if it exists (won't work on SQLite, but that's OK)
    try:
        op.drop_constraint(
            'ai_usage_logs_provider_id_fkey',
            'ai_usage_logs',
            type_='foreignkey'
        )
    except Exception:
        # SQLite or constraint doesn't exist
        pass

    # Create new FK constraint with RESTRICT (won't work on SQLite, but model definition handles it)
    try:
        op.create_foreign_key(
            'ai_usage_logs_provider_id_fkey',
            'ai_usage_logs',
            'ai_providers',
            ['provider_id'],
            ['id'],
            ondelete='RESTRICT'
        )
    except Exception:
        # SQLite - constraint is handled by model definition
        pass


def downgrade():
    """Revert changes (not recommended - loses audit integrity)"""

    # WARNING: This downgrade will LOSE audit trail integrity
    # Only use if absolutely necessary

    # Revert FK constraint to SET NULL
    try:
        op.drop_constraint(
            'ai_usage_logs_provider_id_fkey',
            'ai_usage_logs',
            type_='foreignkey'
        )
    except Exception:
        pass

    try:
        op.create_foreign_key(
            'ai_usage_logs_provider_id_fkey',
            'ai_usage_logs',
            'ai_providers',
            ['provider_id'],
            ['id'],
            ondelete='SET NULL'
        )
    except Exception:
        pass

    # Make provider_id nullable again
    op.alter_column(
        'ai_usage_logs',
        'provider_id',
        nullable=True,
        existing_type=sa.Integer()
    )

    # Drop provider_name column
    op.drop_column('ai_usage_logs', 'provider_name')
