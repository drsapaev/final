"""Add department to queue_tokens

Revision ID: 20250925_0004
Revises: 20250925_0003
Create Date: 2025-09-25 15:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '20250925_0004'
down_revision = '20250925_0003'
branch_labels = None
depends_on = None


def upgrade():
    """Добавление поля department в queue_tokens"""
    
    try:
        # Добавляем поле department
        op.add_column('queue_tokens', sa.Column('department', sa.String(length=50), nullable=True))
        
        # Создаем индекс
        op.create_index(op.f('ix_queue_tokens_department'), 'queue_tokens', ['department'], unique=False)
        
    except Exception as e:
        print(f"Warning: Could not add department column: {e}")


def downgrade():
    """Удаление поля department из queue_tokens"""
    
    try:
        op.drop_index(op.f('ix_queue_tokens_department'), table_name='queue_tokens')
        op.drop_column('queue_tokens', 'department')
    except Exception as e:
        print(f"Warning: Could not drop department column: {e}")
