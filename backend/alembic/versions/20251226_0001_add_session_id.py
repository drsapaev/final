"""Add session_id to OnlineQueueEntry for service grouping

Revision ID: 20251226_0001
Revises: 20251220_0001_visit_source_ssot
Create Date: 2025-12-26
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20251226_0001_add_session_id'
down_revision = '418b7eb4e51a'  # Current DB version (merge_heads_for_user_profile)
branch_labels = None
depends_on = None


def upgrade():
    # 1. Add session_id column (with existence check)
    from sqlalchemy.engine.reflection import Inspector
    conn = op.get_bind()
    inspector = Inspector.from_engine(conn)
    columns = [col['name'] for col in inspector.get_columns('queue_entries')]
    
    if 'session_id' not in columns:
        op.add_column('queue_entries', 
            sa.Column('session_id', sa.String(100), nullable=True))
        print("Added session_id column")
    else:
        print("session_id column already exists, skipping")
    
    # 2. Create index for session_id (with existence check)
    indexes = [idx['name'] for idx in inspector.get_indexes('queue_entries')]
    if 'ix_queue_entries_session_id' not in indexes:
        op.create_index('ix_queue_entries_session_id', 'queue_entries', ['session_id'])
        print("Created index ix_queue_entries_session_id")
    else:
        print("Index ix_queue_entries_session_id already exists, skipping")
    
    # 3. Fill legacy data (SQLite compatible)
    # NOTE: Legacy data may be inconsistent - this is acceptable
    # Format: visit_123 OR patient_queue_date OR entry_id
    op.execute("""
        UPDATE queue_entries 
        SET session_id = COALESCE(
            -- If visit_id exists, use it as session key
            CASE WHEN visit_id IS NOT NULL 
                 THEN 'visit_' || CAST(visit_id AS TEXT)
                 ELSE NULL 
            END,
            -- Otherwise generate from patient + queue + day
            CASE WHEN patient_id IS NOT NULL 
                 THEN CAST(patient_id AS TEXT) || '_' || 
                      CAST(queue_id AS TEXT) || '_' ||
                      COALESCE(
                          (SELECT strftime('%Y-%m-%d', dq.day) 
                           FROM daily_queues dq WHERE dq.id = queue_entries.queue_id),
                          strftime('%Y-%m-%d', 'now')
                      )
                 -- Fallback for entries without patient
                 ELSE 'entry_' || CAST(id AS TEXT)
            END
        )
        WHERE session_id IS NULL
    """)
    
    # 4. Note: Partial unique index for race condition protection is optional
    # Skip for initial migration due to potential NULL/duplicate conflicts
    # Can be added manually later: 
    # CREATE UNIQUE INDEX ix_queue_session_unique 
    # ON queue_entries (patient_id, queue_id, session_id)
    # WHERE status IN ('waiting', 'called', 'in_service') AND session_id IS NOT NULL
    pass


def downgrade():
    # Drop unique index first
    op.execute("DROP INDEX IF EXISTS ix_queue_session_unique")
    
    # Drop regular index
    op.drop_index('ix_queue_entries_session_id', table_name='queue_entries')
    
    # Drop column
    op.drop_column('queue_entries', 'session_id')
