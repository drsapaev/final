"""Add feature flags tables - simple version

Revision ID: 20250925_0002
Revises: 20250925_0001
Create Date: 2025-09-25 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import sqlite

# revision identifiers, used by Alembic.
revision = '20250925_0002'
down_revision = '20250925_0001'
branch_labels = None
depends_on = None


def upgrade():
    """Создание таблиц для фича-флагов"""
    
    # Создаем таблицу feature_flags
    try:
        op.create_table('feature_flags',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('key', sa.String(length=100), nullable=False),
            sa.Column('name', sa.String(length=200), nullable=False),
            sa.Column('description', sa.Text(), nullable=True),
            sa.Column('enabled', sa.Boolean(), nullable=False),
            sa.Column('config', sa.JSON(), nullable=True),
            sa.Column('category', sa.String(length=50), nullable=True),
            sa.Column('environment', sa.String(length=20), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=True),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('created_by', sa.String(length=100), nullable=True),
            sa.Column('updated_by', sa.String(length=100), nullable=True),
            sa.PrimaryKeyConstraint('id')
        )
        
        # Создаем индексы
        op.create_index(op.f('ix_feature_flags_id'), 'feature_flags', ['id'], unique=False)
        op.create_index(op.f('ix_feature_flags_key'), 'feature_flags', ['key'], unique=True)
        
    except Exception as e:
        print(f"Warning: Could not create feature_flags table: {e}")
    
    # Создаем таблицу feature_flag_history
    try:
        op.create_table('feature_flag_history',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('flag_key', sa.String(length=100), nullable=False),
            sa.Column('action', sa.String(length=20), nullable=False),
            sa.Column('old_value', sa.JSON(), nullable=True),
            sa.Column('new_value', sa.JSON(), nullable=True),
            sa.Column('changed_by', sa.String(length=100), nullable=True),
            sa.Column('changed_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=True),
            sa.Column('ip_address', sa.String(length=45), nullable=True),
            sa.Column('user_agent', sa.String(length=500), nullable=True),
            sa.Column('reason', sa.Text(), nullable=True),
            sa.PrimaryKeyConstraint('id')
        )
        
        # Создаем индексы
        op.create_index(op.f('ix_feature_flag_history_id'), 'feature_flag_history', ['id'], unique=False)
        op.create_index(op.f('ix_feature_flag_history_flag_key'), 'feature_flag_history', ['flag_key'], unique=False)
        
    except Exception as e:
        print(f"Warning: Could not create feature_flag_history table: {e}")


def downgrade():
    """Удаление таблиц фича-флагов"""
    
    try:
        op.drop_index(op.f('ix_feature_flag_history_flag_key'), table_name='feature_flag_history')
        op.drop_index(op.f('ix_feature_flag_history_id'), table_name='feature_flag_history')
        op.drop_table('feature_flag_history')
    except Exception as e:
        print(f"Warning: Could not drop feature_flag_history table: {e}")
    
    try:
        op.drop_index(op.f('ix_feature_flags_key'), table_name='feature_flags')
        op.drop_index(op.f('ix_feature_flags_id'), table_name='feature_flags')
        op.drop_table('feature_flags')
    except Exception as e:
        print(f"Warning: Could not drop feature_flags table: {e}")
