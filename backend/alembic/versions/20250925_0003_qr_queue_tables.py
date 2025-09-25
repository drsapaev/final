"""Add QR queue tables

Revision ID: 20250925_0003
Revises: 20250925_0002
Create Date: 2025-09-25 14:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import sqlite

# revision identifiers, used by Alembic.
revision = '20250925_0003'
down_revision = '20250925_0002'
branch_labels = None
depends_on = None


def upgrade():
    """Создание таблиц для QR очередей"""
    
    # Создаем таблицу queue_join_sessions
    try:
        op.create_table('queue_join_sessions',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('session_token', sa.String(length=64), nullable=False),
            sa.Column('qr_token', sa.String(length=64), nullable=False),
            sa.Column('patient_name', sa.String(length=200), nullable=False),
            sa.Column('phone', sa.String(length=20), nullable=False),
            sa.Column('telegram_id', sa.BigInteger(), nullable=True),
            sa.Column('status', sa.String(length=20), nullable=False),
            sa.Column('queue_entry_id', sa.Integer(), nullable=True),
            sa.Column('queue_number', sa.Integer(), nullable=True),
            sa.Column('user_agent', sa.String(length=500), nullable=True),
            sa.Column('ip_address', sa.String(length=45), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=True),
            sa.Column('joined_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(['qr_token'], ['queue_tokens.token'], ),
            sa.ForeignKeyConstraint(['queue_entry_id'], ['queue_entries.id'], ),
            sa.PrimaryKeyConstraint('id')
        )
        
        # Создаем индексы для queue_join_sessions
        op.create_index(op.f('ix_queue_join_sessions_id'), 'queue_join_sessions', ['id'], unique=False)
        op.create_index(op.f('ix_queue_join_sessions_session_token'), 'queue_join_sessions', ['session_token'], unique=True)
        op.create_index(op.f('ix_queue_join_sessions_qr_token'), 'queue_join_sessions', ['qr_token'], unique=False)
        op.create_index(op.f('ix_queue_join_sessions_phone'), 'queue_join_sessions', ['phone'], unique=False)
        op.create_index(op.f('ix_queue_join_sessions_telegram_id'), 'queue_join_sessions', ['telegram_id'], unique=False)
        
    except Exception as e:
        print(f"Warning: Could not create queue_join_sessions table: {e}")
    
    # Создаем таблицу queue_statistics
    try:
        op.create_table('queue_statistics',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('queue_id', sa.Integer(), nullable=False),
            sa.Column('date', sa.Date(), nullable=False),
            sa.Column('online_joins', sa.Integer(), nullable=False),
            sa.Column('desk_registrations', sa.Integer(), nullable=False),
            sa.Column('telegram_joins', sa.Integer(), nullable=False),
            sa.Column('confirmation_joins', sa.Integer(), nullable=False),
            sa.Column('total_served', sa.Integer(), nullable=False),
            sa.Column('total_no_show', sa.Integer(), nullable=False),
            sa.Column('average_wait_time', sa.Integer(), nullable=True),
            sa.Column('peak_hour', sa.Integer(), nullable=True),
            sa.Column('max_queue_length', sa.Integer(), nullable=False),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=True),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(['queue_id'], ['daily_queues.id'], ),
            sa.PrimaryKeyConstraint('id')
        )
        
        # Создаем индексы для queue_statistics
        op.create_index(op.f('ix_queue_statistics_id'), 'queue_statistics', ['id'], unique=False)
        op.create_index(op.f('ix_queue_statistics_queue_id'), 'queue_statistics', ['queue_id'], unique=False)
        op.create_index(op.f('ix_queue_statistics_date'), 'queue_statistics', ['date'], unique=False)
        
    except Exception as e:
        print(f"Warning: Could not create queue_statistics table: {e}")
    
    # Добавляем недостающие поля в queue_entries если их нет
    try:
        # Проверяем существование столбцов
        conn = op.get_bind()
        inspector = sa.inspect(conn)
        columns = [col['name'] for col in inspector.get_columns('queue_entries')]
        
        if 'called_at' not in columns:
            op.add_column('queue_entries', sa.Column('called_at', sa.DateTime(timezone=True), nullable=True))
        
        if 'called_by_user_id' not in columns:
            op.add_column('queue_entries', sa.Column('called_by_user_id', sa.Integer(), nullable=True))
            
    except Exception as e:
        print(f"Warning: Could not add columns to queue_entries: {e}")


def downgrade():
    """Удаление таблиц QR очередей"""
    
    try:
        # Удаляем дополнительные поля из queue_entries
        op.drop_column('queue_entries', 'called_by_user_id')
        op.drop_column('queue_entries', 'called_at')
    except Exception as e:
        print(f"Warning: Could not drop columns from queue_entries: {e}")
    
    try:
        op.drop_index(op.f('ix_queue_statistics_date'), table_name='queue_statistics')
        op.drop_index(op.f('ix_queue_statistics_queue_id'), table_name='queue_statistics')
        op.drop_index(op.f('ix_queue_statistics_id'), table_name='queue_statistics')
        op.drop_table('queue_statistics')
    except Exception as e:
        print(f"Warning: Could not drop queue_statistics table: {e}")
    
    try:
        op.drop_index(op.f('ix_queue_join_sessions_telegram_id'), table_name='queue_join_sessions')
        op.drop_index(op.f('ix_queue_join_sessions_phone'), table_name='queue_join_sessions')
        op.drop_index(op.f('ix_queue_join_sessions_qr_token'), table_name='queue_join_sessions')
        op.drop_index(op.f('ix_queue_join_sessions_session_token'), table_name='queue_join_sessions')
        op.drop_index(op.f('ix_queue_join_sessions_id'), table_name='queue_join_sessions')
        op.drop_table('queue_join_sessions')
    except Exception as e:
        print(f"Warning: Could not drop queue_join_sessions table: {e}")
