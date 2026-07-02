"""add voice messages support - simplified for SQLite

Revision ID: voice_messages_002
Revises: 418b7eb4e51a
Create Date: 2025-12-08 23:35:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'voice_messages_002'
down_revision = '418b7eb4e51a'
branch_labels = None
depends_on = None


def upgrade():
    # Для SQLite просто добавляем новые колонки
    # content уже nullable в существующей таблице, поэтому не трогаем
    
    # Добавляем message_type
    try:
        op.add_column('messages', sa.Column('message_type', sa.String(20), nullable=False, server_default='text'))
    except:
        pass  # Колонка уже существует
    
    # Добавляем file_id
    try:
        op.add_column('messages', sa.Column('file_id', sa.Integer(), nullable=True))
    except:
        pass
    
    # Добавляем voice_duration
    try:
        op.add_column('messages', sa.Column('voice_duration', sa.Integer(), nullable=True))
    except:
        pass
    
    # Создаём индексы
    try:
        op.create_index('ix_messages_message_type', 'messages', ['message_type'])
    except:
        pass
    
    try:
        op.create_index('ix_messages_file_id', 'messages', ['file_id'])
    except:
        pass


def downgrade():
    # Откат
    try:
        op.drop_index('ix_messages_file_id', 'messages')
    except:
        pass
    
    try:
        op.drop_index('ix_messages_message_type', 'messages')
    except:
        pass
    
    try:
        op.drop_column('messages', 'voice_duration')
    except:
        pass
    
    try:
        op.drop_column('messages', 'file_id')
    except:
        pass
    
    try:
        op.drop_column('messages', 'message_type')
    except:
        pass
