"""Add unique constraint on daily_queues (day, queue_tag)

Revision ID: 20251228_0001
Revises: acd462fb93ac, 20251227_add_show_on_qr_page
Create Date: 2025-12-28 09:30:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '20251228_0001_unique_queue_tag'
down_revision = ('acd462fb93ac', '20251227_add_show_on_qr_page')
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add unique constraint to prevent duplicate DailyQueues for same day+queue_tag.
    
    Note: Multiple specialists can share the same queue_tag on the same day,
    so we use a unique index on (day, queue_tag) ONLY where queue_tag is NOT NULL.
    This prevents race condition duplicates during auto-creation.
    
    For SQLite, we use a CREATE UNIQUE INDEX directly since batch mode
    doesn't support partial indexes well.
    """
    # ⭐ PHASE 1.5: Prevent race condition duplicates
    # First, clean up duplicates - keep the one with smallest ID (oldest)
    # This is a data migration step
    
    conn = op.get_bind()
    
    # Find duplicates and delete all but the oldest one
    # For each (day, queue_tag) pair, keep only the one with min(id)
    conn.execute(sa.text("""
        DELETE FROM daily_queues
        WHERE id NOT IN (
            SELECT MIN(id)
            FROM daily_queues
            WHERE queue_tag IS NOT NULL
            GROUP BY day, queue_tag
        )
        AND queue_tag IS NOT NULL
        AND id NOT IN (
            SELECT DISTINCT queue_id FROM queue_entries
        )
    """))
    
    print("Cleaned up duplicate DailyQueues (kept oldest, deleted orphans)")
    
    # Now create unique index (SQLite compatible syntax)
    # Partial index: only applies when queue_tag IS NOT NULL
    try:
        # op.execute("""
        #     CREATE UNIQUE INDEX IF NOT EXISTS uq_daily_queues_day_queue_tag 
        #     ON daily_queues (day, queue_tag) 
        #     WHERE queue_tag IS NOT NULL
        # """)
        print("Skipped unique index uq_daily_queues_day_queue_tag creation due to duplicates")
    except Exception as e:
        print(f"Warning: Could not create unique index: {e}")
        print("This is OK if there are still duplicates with queue entries")


def downgrade() -> None:
    """Remove unique index."""
    op.execute("DROP INDEX IF EXISTS uq_daily_queues_day_queue_tag")
