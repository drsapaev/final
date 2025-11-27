"""Department expansion Phase 1: ForeignKeys and Settings

Revision ID: 20251127_0001
Revises: 20250925_0005
Create Date: 2025-11-27

Description:
    Фаза 1 расширения системы управления отделениями:
    1. Создание таблиц: department_services, department_queue_settings, department_registration_settings
    2. Конвертация String полей department → ForeignKey department_id в:
       - Doctor.department_id
       - Service.department_id (с data migration)
       - Appointment.department_id (с data migration)
       - Visit.department_id (с data migration)
       - ScheduleTemplate.department_id (с data migration)
    3. Создание настроек по умолчанию для существующих отделений
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision = '20251127_0001'
down_revision = '20250925_0005'
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()

    # ============================================================
    # 1. СОЗДАНИЕ НОВЫХ ТАБЛИЦ
    # ============================================================

    # 1.1 DepartmentService (M:M с атрибутами)
    op.create_table('department_services',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('department_id', sa.Integer(), nullable=False),
        sa.Column('service_id', sa.Integer(), nullable=False),
        sa.Column('is_default', sa.Boolean(), nullable=False, server_default='0'),
        sa.Column('display_order', sa.Integer(), nullable=False, server_default='999'),
        sa.Column('price_override', sa.Numeric(10, 2), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True),
            server_default=sa.text("(datetime('now'))"), nullable=False),
        sa.ForeignKeyConstraint(['department_id'], ['departments.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['service_id'], ['services.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('department_id', 'service_id', name='uq_department_service')
    )
    op.create_index('ix_department_services_department_id',
        'department_services', ['department_id'])
    op.create_index('ix_department_services_service_id',
        'department_services', ['service_id'])

    # 1.2 DepartmentQueueSettings (1:1)
    op.create_table('department_queue_settings',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('department_id', sa.Integer(), nullable=False),
        sa.Column('enabled', sa.Boolean(), nullable=False, server_default='1'),
        sa.Column('queue_type', sa.String(20), nullable=False, server_default='mixed'),
        sa.Column('queue_prefix', sa.String(10), nullable=True),
        sa.Column('max_daily_queue', sa.Integer(), nullable=False, server_default='50'),
        sa.Column('max_concurrent_queue', sa.Integer(), nullable=False, server_default='15'),
        sa.Column('avg_wait_time', sa.Integer(), nullable=False, server_default='20'),
        sa.Column('show_on_display', sa.Boolean(), nullable=False, server_default='1'),
        sa.Column('auto_close_time', sa.String(5), nullable=False, server_default='09:00'),
        sa.Column('created_at', sa.DateTime(timezone=True),
            server_default=sa.text("(datetime('now'))"), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True),
            server_default=sa.text("(datetime('now'))"), nullable=False),
        sa.ForeignKeyConstraint(['department_id'], ['departments.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_department_queue_settings_department_id',
        'department_queue_settings', ['department_id'], unique=True)

    # 1.3 DepartmentRegistrationSettings (1:1)
    op.create_table('department_registration_settings',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('department_id', sa.Integer(), nullable=False),
        sa.Column('online_booking_enabled', sa.Boolean(), nullable=False, server_default='1'),
        sa.Column('requires_confirmation', sa.Boolean(), nullable=False, server_default='0'),
        sa.Column('min_booking_hours', sa.Integer(), nullable=False, server_default='2'),
        sa.Column('max_booking_days', sa.Integer(), nullable=False, server_default='30'),
        sa.Column('auto_assign_doctor', sa.Boolean(), nullable=False, server_default='0'),
        sa.Column('allow_walkin', sa.Boolean(), nullable=False, server_default='1'),
        sa.Column('created_at', sa.DateTime(timezone=True),
            server_default=sa.text("(datetime('now'))"), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True),
            server_default=sa.text("(datetime('now'))"), nullable=False),
        sa.ForeignKeyConstraint(['department_id'], ['departments.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_department_registration_settings_department_id',
        'department_registration_settings', ['department_id'], unique=True)

    # ============================================================
    # 2. ИЗМЕНЕНИЕ СУЩЕСТВУЮЩИХ ТАБЛИЦ (String → ForeignKey)
    # ============================================================

    # 2.1 Doctor: добавить department_id
    with op.batch_alter_table('doctors') as batch_op:
        batch_op.add_column(sa.Column('department_id', sa.Integer(), nullable=True))
        batch_op.create_index('ix_doctors_department_id', ['department_id'])
        batch_op.create_foreign_key('fk_doctors_department_id',
            'departments', ['department_id'], ['id'], ondelete='SET NULL')

    # 2.2 Service: добавить department_id (String → ForeignKey)
    with op.batch_alter_table('services') as batch_op:
        batch_op.add_column(sa.Column('department_id', sa.Integer(), nullable=True))
        batch_op.create_index('ix_services_department_id', ['department_id'])
        batch_op.create_foreign_key('fk_services_department_id',
            'departments', ['department_id'], ['id'], ondelete='SET NULL')

    # DATA MIGRATION: конвертируем String → ID для services
    conn.execute(text("""
        UPDATE services
        SET department_id = (
            SELECT d.id FROM departments d
            WHERE d.key = services.department
        )
        WHERE services.department IS NOT NULL
    """))

    # 2.3 Appointment: добавить department_id
    with op.batch_alter_table('appointments') as batch_op:
        batch_op.add_column(sa.Column('department_id', sa.Integer(), nullable=True))
        batch_op.create_index('ix_appointments_department_id', ['department_id'])
        batch_op.create_foreign_key('fk_appointments_department_id',
            'departments', ['department_id'], ['id'], ondelete='SET NULL')

    # DATA MIGRATION: конвертируем String → ID для appointments
    conn.execute(text("""
        UPDATE appointments
        SET department_id = (
            SELECT d.id FROM departments d
            WHERE d.key = appointments.department
        )
        WHERE appointments.department IS NOT NULL
    """))

    # 2.4 Visit: добавить department_id
    with op.batch_alter_table('visits') as batch_op:
        batch_op.add_column(sa.Column('department_id', sa.Integer(), nullable=True))
        batch_op.create_index('ix_visits_department_id', ['department_id'])
        batch_op.create_foreign_key('fk_visits_department_id',
            'departments', ['department_id'], ['id'], ondelete='SET NULL')

    # DATA MIGRATION: конвертируем String → ID для visits
    conn.execute(text("""
        UPDATE visits
        SET department_id = (
            SELECT d.id FROM departments d
            WHERE d.key = visits.department
        )
        WHERE visits.department IS NOT NULL
    """))

    # 2.5 ScheduleTemplate: добавить department_id
    with op.batch_alter_table('schedule_templates') as batch_op:
        batch_op.add_column(sa.Column('department_id', sa.Integer(), nullable=True))
        batch_op.create_index('ix_schedule_templates_department_id', ['department_id'])
        batch_op.create_foreign_key('fk_schedule_templates_department_id',
            'departments', ['department_id'], ['id'], ondelete='SET NULL')

    # DATA MIGRATION: конвертируем String → ID для schedule_templates
    conn.execute(text("""
        UPDATE schedule_templates
        SET department_id = (
            SELECT d.id FROM departments d
            WHERE d.key = schedule_templates.department
        )
        WHERE schedule_templates.department IS NOT NULL
    """))

    # ============================================================
    # 3. СОЗДАНИЕ НАСТРОЕК ПО УМОЛЧАНИЮ для существующих отделений
    # ============================================================

    # 3.1 Создать queue_settings для всех отделений
    conn.execute(text("""
        INSERT INTO department_queue_settings (department_id)
        SELECT id FROM departments WHERE id NOT IN (
            SELECT department_id FROM department_queue_settings
        )
    """))

    # 3.2 Создать registration_settings для всех отделений
    conn.execute(text("""
        INSERT INTO department_registration_settings (department_id)
        SELECT id FROM departments WHERE id NOT IN (
            SELECT department_id FROM department_registration_settings
        )
    """))


def downgrade() -> None:
    """Откат миграции"""

    # Удаляем department_id из schedule_templates
    with op.batch_alter_table('schedule_templates') as batch_op:
        batch_op.drop_constraint('fk_schedule_templates_department_id', type_='foreignkey')
        batch_op.drop_index('ix_schedule_templates_department_id')
        batch_op.drop_column('department_id')

    # Удаляем department_id из visits
    with op.batch_alter_table('visits') as batch_op:
        batch_op.drop_constraint('fk_visits_department_id', type_='foreignkey')
        batch_op.drop_index('ix_visits_department_id')
        batch_op.drop_column('department_id')

    # Удаляем department_id из appointments
    with op.batch_alter_table('appointments') as batch_op:
        batch_op.drop_constraint('fk_appointments_department_id', type_='foreignkey')
        batch_op.drop_index('ix_appointments_department_id')
        batch_op.drop_column('department_id')

    # Удаляем department_id из services
    with op.batch_alter_table('services') as batch_op:
        batch_op.drop_constraint('fk_services_department_id', type_='foreignkey')
        batch_op.drop_index('ix_services_department_id')
        batch_op.drop_column('department_id')

    # Удаляем department_id из doctors
    with op.batch_alter_table('doctors') as batch_op:
        batch_op.drop_constraint('fk_doctors_department_id', type_='foreignkey')
        batch_op.drop_index('ix_doctors_department_id')
        batch_op.drop_column('department_id')

    # Удаляем таблицы настроек
    op.drop_index('ix_department_registration_settings_department_id', 'department_registration_settings')
    op.drop_table('department_registration_settings')

    op.drop_index('ix_department_queue_settings_department_id', 'department_queue_settings')
    op.drop_table('department_queue_settings')

    op.drop_index('ix_department_services_service_id', 'department_services')
    op.drop_index('ix_department_services_department_id', 'department_services')
    op.drop_table('department_services')
