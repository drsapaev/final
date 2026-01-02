"""Add show_on_qr_page to queue_profiles

Revision ID: 20251227_add_show_on_qr_page
Revises: 
Create Date: 2025-12-27

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20251227_add_show_on_qr_page'
down_revision = None  # Will need to be updated based on existing migrations
branch_labels = None
depends_on = None


def upgrade():
    """Add show_on_qr_page column to queue_profiles table"""
    # Check if column exists first (in case migration was partially run)
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    
    # Check if table exists
    if 'queue_profiles' not in inspector.get_table_names():
        print("Table queue_profiles does not exist, skipping migration")
        return
    
    # Check if column already exists
    columns = [col['name'] for col in inspector.get_columns('queue_profiles')]
    if 'show_on_qr_page' not in columns:
        op.add_column(
            'queue_profiles',
            sa.Column('show_on_qr_page', sa.Boolean(), nullable=False, server_default='true')
        )
        print("Added show_on_qr_page column to queue_profiles")
    else:
        print("Column show_on_qr_page already exists, skipping")


def downgrade():
    """Remove show_on_qr_page column from queue_profiles table"""
    # Check if column exists
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    
    if 'queue_profiles' not in inspector.get_table_names():
        return
    
    columns = [col['name'] for col in inspector.get_columns('queue_profiles')]
    if 'show_on_qr_page' in columns:
        op.drop_column('queue_profiles', 'show_on_qr_page')
