"""add_audit_log_fields_request_id_diff_hash

Revision ID: 2dab0720131b
Revises: e74e2b0a152d
Create Date: 2025-12-04 11:23:47.344972

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '2dab0720131b'
down_revision = 'a47243be82f0'  # Используем mergepoint как базовую версию
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ✅ FIX: Проверяем существование колонок перед добавлением
    from sqlalchemy import inspect
    bind = op.get_bind()
    inspector = inspect(bind)
    
    # Проверяем, существует ли таблица user_audit_logs
    if 'user_audit_logs' in inspector.get_table_names():
        columns = [col['name'] for col in inspector.get_columns('user_audit_logs')]
        
        # Добавляем поля request_id и diff_hash в user_audit_logs (только если их еще нет)
        if 'request_id' not in columns:
            op.add_column('user_audit_logs', sa.Column('request_id', sa.String(length=64), nullable=True))
        if 'diff_hash' not in columns:
            op.add_column('user_audit_logs', sa.Column('diff_hash', sa.String(length=32), nullable=True))
    
    # Создаем индексы для оптимизации запросов (если их еще нет)
    try:
        op.create_index(op.f('ix_user_audit_logs_request_id'), 'user_audit_logs', ['request_id'], unique=False)
    except:
        pass  # Индекс уже существует
    
    try:
        op.create_index(op.f('ix_user_audit_logs_user_id'), 'user_audit_logs', ['user_id'], unique=False)
    except:
        pass
    
    try:
        op.create_index(op.f('ix_user_audit_logs_action'), 'user_audit_logs', ['action'], unique=False)
    except:
        pass
    
    try:
        op.create_index(op.f('ix_user_audit_logs_resource_type'), 'user_audit_logs', ['resource_type'], unique=False)
    except:
        pass
    
    try:
        op.create_index(op.f('ix_user_audit_logs_resource_id'), 'user_audit_logs', ['resource_id'], unique=False)
    except:
        pass
    
    try:
        op.create_index(op.f('ix_user_audit_logs_ip_address'), 'user_audit_logs', ['ip_address'], unique=False)
    except:
        pass
    
    try:
        op.create_index(op.f('ix_user_audit_logs_session_id'), 'user_audit_logs', ['session_id'], unique=False)
    except:
        pass
    
    try:
        op.create_index(op.f('ix_user_audit_logs_created_at'), 'user_audit_logs', ['created_at'], unique=False)
    except:
        pass


def downgrade() -> None:
    # Удаляем индексы
    try:
        op.drop_index(op.f('ix_user_audit_logs_created_at'), table_name='user_audit_logs')
        op.drop_index(op.f('ix_user_audit_logs_session_id'), table_name='user_audit_logs')
        op.drop_index(op.f('ix_user_audit_logs_ip_address'), table_name='user_audit_logs')
        op.drop_index(op.f('ix_user_audit_logs_resource_id'), table_name='user_audit_logs')
        op.drop_index(op.f('ix_user_audit_logs_resource_type'), table_name='user_audit_logs')
        op.drop_index(op.f('ix_user_audit_logs_action'), table_name='user_audit_logs')
        op.drop_index(op.f('ix_user_audit_logs_user_id'), table_name='user_audit_logs')
        op.drop_index(op.f('ix_user_audit_logs_request_id'), table_name='user_audit_logs')
    except:
        pass
    
    # Удаляем поля
    op.drop_column('user_audit_logs', 'diff_hash')
    op.drop_column('user_audit_logs', 'request_id')

