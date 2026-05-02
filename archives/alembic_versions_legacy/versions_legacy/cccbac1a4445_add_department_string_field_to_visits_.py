"""Add department string field to visits table

Revision ID: cccbac1a4445
Revises: a47243be82f0
Create Date: 2025-11-27 22:30:49.949819

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'cccbac1a4445'
down_revision = 'a47243be82f0'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add department string field to visits table
    # Check if column already exists (may be created by model definition)
    from sqlalchemy import inspect
    
    # ✅ FIX: Use Alembic's connection instead of creating a separate engine
    # This ensures we check the same connection that the migration runs on
    bind = op.get_bind()
    inspector = inspect(bind)
    
    try:
        # Check if visits table exists and has department column
        if 'visits' in inspector.get_table_names():
            columns = [col['name'] for col in inspector.get_columns('visits')]
            if 'department' not in columns:
                op.add_column('visits', sa.Column('department', sa.String(64), nullable=True))
            else:
                # Column already exists, skip
                pass
        else:
            # Table doesn't exist yet, will be created by model
            pass
    except Exception:
        # Fallback: try to add column, ignore if it fails
        try:
            op.add_column('visits', sa.Column('department', sa.String(64), nullable=True))
        except Exception:
            # Column already exists, ignore
            pass


def downgrade() -> None:
    # Remove department string field from visits table
    # ✅ FIX: Add error handling for symmetric migration behavior
    from sqlalchemy import inspect
    
    bind = op.get_bind()
    inspector = inspect(bind)
    
    try:
        # Check if visits table exists and has department column
        if 'visits' in inspector.get_table_names():
            columns = [col['name'] for col in inspector.get_columns('visits')]
            if 'department' in columns:
                op.drop_column('visits', 'department')
            else:
                # Column doesn't exist, skip
                pass
        else:
            # Table doesn't exist, skip
            pass
    except Exception:
        # Fallback: try to drop column, ignore if it fails
        try:
            op.drop_column('visits', 'department')
        except Exception:
            # Column doesn't exist, ignore
            pass

