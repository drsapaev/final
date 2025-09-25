"""Add time restrictions to daily_queues

Revision ID: 20250925_0005
Revises: 20250925_0004
Create Date: 2025-09-25 16:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '20250925_0005'
down_revision = '20250925_0004'
branch_labels = None
depends_on = None


def upgrade():
    """Добавление временных ограничений в daily_queues"""
    
    try:
        # Добавляем поля временных ограничений
        op.add_column('daily_queues', sa.Column('online_start_time', sa.String(length=5), nullable=False, server_default='07:00'))
        op.add_column('daily_queues', sa.Column('online_end_time', sa.String(length=5), nullable=False, server_default='09:00'))
        op.add_column('daily_queues', sa.Column('max_online_entries', sa.Integer(), nullable=False, server_default='15'))
        
    except Exception as e:
        print(f"Warning: Could not add time restriction columns: {e}")


def downgrade():
    """Удаление временных ограничений из daily_queues"""
    
    try:
        op.drop_column('daily_queues', 'max_online_entries')
        op.drop_column('daily_queues', 'online_end_time')
        op.drop_column('daily_queues', 'online_start_time')
    except Exception as e:
        print(f"Warning: Could not drop time restriction columns: {e}")
