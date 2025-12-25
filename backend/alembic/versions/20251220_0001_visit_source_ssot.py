"""add source field to visits table

Revision ID: 20251220_0001
Revises: 20251214_0002_merge_heads
Create Date: 2025-12-20

SSOT Migration: Add source field to Visit model.
Source determines where the visit originated from:
- 'online' = QR/Telegram registration
- 'desk' = Registrar desk registration
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20251220_0001_visit_source_ssot'
down_revision = '20251214_0002_merge_heads'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add source column with default 'desk'
    op.add_column(
        'visits',
        sa.Column('source', sa.String(20), nullable=False, server_default='desk')
    )
    
    # Create index for filtering by source
    op.create_index('ix_visits_source', 'visits', ['source'])
    
    # Data migration: Set source='online' for visits linked to QR OnlineQueueEntry
    # This uses raw SQL to update existing records
    op.execute("""
        UPDATE visits 
        SET source = 'online' 
        WHERE id IN (
            SELECT DISTINCT visit_id 
            FROM queue_entries 
            WHERE visit_id IS NOT NULL 
              AND source IN ('online', 'confirmation', 'telegram')
        )
    """)


def downgrade() -> None:
    op.drop_index('ix_visits_source', table_name='visits')
    op.drop_column('visits', 'source')
