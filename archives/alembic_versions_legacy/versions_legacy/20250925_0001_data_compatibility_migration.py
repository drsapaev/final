"""Миграция для обеспечения совместимости данных очередей и печати талонов

Revision ID: 20250925_0001
Revises: b3a7a4f9c515
Create Date: 2025-09-25 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import sqlite

# revision identifiers, used by Alembic.
revision = '20250925_0001'
down_revision = 'b3a7a4f9c515'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    Обеспечиваем совместимость данных очередей и печати талонов
    """
    
    # 1. Создаем индекс для быстрого поиска очередей по дате и тегу
    try:
        op.create_index(
            'ix_daily_queues_day_queue_tag', 
            'daily_queues', 
            ['day', 'queue_tag']
        )
    except Exception:
        # Индекс уже существует
        pass
    
    # 2. Создаем индекс для быстрого поиска записей очереди по визиту
    try:
        op.create_index(
            'ix_queue_entries_visit_id_status', 
            'queue_entries', 
            ['visit_id', 'status']
        )
    except Exception:
        # Индекс уже существует
        pass
    
    # 3. Создаем индекс для быстрого поиска по источнику записи
    try:
        op.create_index(
            'ix_queue_entries_source_created_at', 
            'queue_entries', 
            ['source', 'created_at']
        )
    except Exception:
        # Индекс уже существует
        pass
    
    # 4. Добавляем поле для хранения данных печати талонов
    try:
        op.add_column(
            'queue_entries',
            sa.Column(
                'print_data',
                sa.JSON(),
                nullable=True,
                comment='Данные для печати талона (номер, врач, услуги и т.д.)'
            )
        )
    except Exception:
        # Поле уже существует
        pass
    
    # 5. Добавляем поле для отслеживания печати
    try:
        op.add_column(
            'queue_entries',
            sa.Column(
                'printed_at',
                sa.DateTime(timezone=True),
                nullable=True,
                comment='Время печати талона'
            )
        )
    except Exception:
        # Поле уже существует
        pass
    
    # 6. Добавляем поле для версии данных (для совместимости)
    try:
        op.add_column(
            'queue_entries',
            sa.Column(
                'data_version',
                sa.String(16),
                nullable=False,
                server_default='v1.0',
                comment='Версия структуры данных для обратной совместимости'
            )
        )
    except Exception:
        # Поле уже существует
        pass
    
    # 7. Создаем таблицу для аудита изменений очередей
    try:
        op.create_table(
            'queue_audit_log',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('queue_entry_id', sa.Integer(), nullable=False),
            sa.Column('action', sa.String(32), nullable=False),  # created, updated, called, served, cancelled
            sa.Column('old_data', sa.JSON(), nullable=True),
            sa.Column('new_data', sa.JSON(), nullable=True),
            sa.Column('changed_by_user_id', sa.Integer(), nullable=True),
            sa.Column('changed_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
            sa.Column('ip_address', sa.String(45), nullable=True),
            sa.Column('user_agent', sa.String(255), nullable=True),
            sa.ForeignKeyConstraint(['queue_entry_id'], ['queue_entries.id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['changed_by_user_id'], ['users.id']),
            sa.PrimaryKeyConstraint('id')
        )
        
        # Индексы для аудита
        op.create_index('ix_queue_audit_log_queue_entry_id', 'queue_audit_log', ['queue_entry_id'])
        op.create_index('ix_queue_audit_log_action_changed_at', 'queue_audit_log', ['action', 'changed_at'])
        
    except Exception:
        # Таблица уже существует
        pass
    
    # 8. Создаем таблицу для настроек печати
    try:
        op.create_table(
            'print_settings',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('printer_name', sa.String(100), nullable=False),
            sa.Column('printer_type', sa.String(32), nullable=False),  # thermal, laser, pdf
            sa.Column('template_name', sa.String(64), nullable=False),  # ticket, prescription, memo
            sa.Column('settings', sa.JSON(), nullable=False),  # Настройки принтера
            sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
            sa.Column('department', sa.String(64), nullable=True),  # Привязка к отделению
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
            sa.PrimaryKeyConstraint('id')
        )
        
        # Индексы для настроек печати
        op.create_index('ix_print_settings_printer_type_active', 'print_settings', ['printer_type', 'is_active'])
        op.create_index('ix_print_settings_department', 'print_settings', ['department'])
        
    except Exception:
        # Таблица уже существует
        pass
    
    # 9. Создаем таблицу для истории печати
    try:
        op.create_table(
            'print_history',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('queue_entry_id', sa.Integer(), nullable=True),
            sa.Column('visit_id', sa.Integer(), nullable=True),
            sa.Column('print_type', sa.String(32), nullable=False),  # ticket, prescription, memo
            sa.Column('printer_name', sa.String(100), nullable=False),
            sa.Column('print_data', sa.JSON(), nullable=False),  # Данные что печатали
            sa.Column('status', sa.String(16), nullable=False),  # success, failed, pending
            sa.Column('error_message', sa.String(255), nullable=True),
            sa.Column('printed_by_user_id', sa.Integer(), nullable=True),
            sa.Column('printed_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
            sa.ForeignKeyConstraint(['queue_entry_id'], ['queue_entries.id'], ondelete='SET NULL'),
            sa.ForeignKeyConstraint(['visit_id'], ['visits.id'], ondelete='SET NULL'),
            sa.ForeignKeyConstraint(['printed_by_user_id'], ['users.id']),
            sa.PrimaryKeyConstraint('id')
        )
        
        # Индексы для истории печати
        op.create_index('ix_print_history_queue_entry_id', 'print_history', ['queue_entry_id'])
        op.create_index('ix_print_history_visit_id', 'print_history', ['visit_id'])
        op.create_index('ix_print_history_print_type_status', 'print_history', ['print_type', 'status'])
        op.create_index('ix_print_history_printed_at', 'print_history', ['printed_at'])
        
    except Exception:
        # Таблица уже существует
        pass


def downgrade() -> None:
    """
    Откат миграции (только для разработки)
    """
    
    # Удаляем таблицы в обратном порядке
    try:
        op.drop_table('print_history')
    except Exception:
        pass
    
    try:
        op.drop_table('print_settings')
    except Exception:
        pass
    
    try:
        op.drop_table('queue_audit_log')
    except Exception:
        pass
    
    # Удаляем добавленные поля
    try:
        op.drop_column('queue_entries', 'data_version')
    except Exception:
        pass
    
    try:
        op.drop_column('queue_entries', 'printed_at')
    except Exception:
        pass
    
    try:
        op.drop_column('queue_entries', 'print_data')
    except Exception:
        pass
    
    # Удаляем индексы
    try:
        op.drop_index('ix_queue_entries_source_created_at', table_name='queue_entries')
    except Exception:
        pass
    
    try:
        op.drop_index('ix_queue_entries_visit_id_status', table_name='queue_entries')
    except Exception:
        pass
    
    try:
        op.drop_index('ix_daily_queues_day_queue_tag', table_name='daily_queues')
    except Exception:
        pass
