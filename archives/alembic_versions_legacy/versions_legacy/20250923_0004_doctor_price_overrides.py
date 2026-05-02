"""Добавляем таблицу doctor_price_overrides для изменения цен врачами

Revision ID: 20250923_0004
Revises: 20250923_0003
Create Date: 2025-09-23 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20250923_0004'
down_revision = '20250923_0003'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Создаём таблицу doctor_price_overrides
    op.create_table(
        'doctor_price_overrides',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('visit_id', sa.Integer(), nullable=False),
        sa.Column('doctor_id', sa.Integer(), nullable=False),
        sa.Column('service_id', sa.Integer(), nullable=False),
        sa.Column('original_price', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('new_price', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('reason', sa.String(length=255), nullable=False),
        sa.Column('details', sa.Text(), nullable=True),
        sa.Column('status', sa.String(length=32), nullable=False, server_default='pending'),
        sa.Column('approved_by', sa.Integer(), nullable=True),
        sa.Column('approved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('rejection_reason', sa.String(length=255), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP'), onupdate=sa.text('CURRENT_TIMESTAMP')),
        sa.ForeignKeyConstraint(['approved_by'], ['users.id'], ),
        sa.ForeignKeyConstraint(['doctor_id'], ['doctors.id'], ),
        sa.ForeignKeyConstraint(['service_id'], ['services.id'], ),
        sa.ForeignKeyConstraint(['visit_id'], ['visits.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Создаём индексы
    op.create_index(op.f('ix_doctor_price_overrides_visit_id'), 'doctor_price_overrides', ['visit_id'], unique=False)
    op.create_index(op.f('ix_doctor_price_overrides_doctor_id'), 'doctor_price_overrides', ['doctor_id'], unique=False)
    op.create_index(op.f('ix_doctor_price_overrides_service_id'), 'doctor_price_overrides', ['service_id'], unique=False)
    op.create_index(op.f('ix_doctor_price_overrides_status'), 'doctor_price_overrides', ['status'], unique=False)


def downgrade() -> None:
    # Удаляем индексы
    op.drop_index(op.f('ix_doctor_price_overrides_status'), table_name='doctor_price_overrides')
    op.drop_index(op.f('ix_doctor_price_overrides_service_id'), table_name='doctor_price_overrides')
    op.drop_index(op.f('ix_doctor_price_overrides_doctor_id'), table_name='doctor_price_overrides')
    op.drop_index(op.f('ix_doctor_price_overrides_visit_id'), table_name='doctor_price_overrides')
    
    # Удаляем таблицу
    op.drop_table('doctor_price_overrides')
