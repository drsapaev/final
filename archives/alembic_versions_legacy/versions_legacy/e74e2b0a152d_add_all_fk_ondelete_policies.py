"""add_all_fk_ondelete_policies

Revision ID: e74e2b0a152d
Revises: 0e315951c2f5
Create Date: 2025-12-03 23:00:54.656004

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'e74e2b0a152d'
down_revision = '0e315951c2f5'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    This migration marks the addition of explicit ondelete policies to all FK constraints.
    
    NOTE: SQLite does not support ALTER TABLE to modify FK constraints.
    The FK policies are defined in SQLAlchemy models and will be applied when:
    1. Database is reset (all tables dropped and recreated)
    2. Fresh database is created with alembic upgrade head
    
    To apply these changes:
    - Run: backend/reset_database.ps1 (Windows PowerShell)
    - Or manually: Delete clinic.db, then run: alembic upgrade head
    
    All FK constraints now have explicit ondelete policies:
    - CASCADE: Authentication data, user profiles, 2FA data
    - SET NULL: Medical records, files, payments (audit trail), queue history
    - RESTRICT: Critical parent-child relationships (visits.patient_id, payment.visit_id)
    """
    # No-op migration: FK constraints are defined in models
    # They will be applied on next database creation/reset
    pass


def downgrade() -> None:
    # No-op: Cannot remove FK constraints in SQLite without recreating tables
    pass

