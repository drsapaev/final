"""add clinic_id to messages for tenant isolation (F-002)

Revision ID: 0032_messages_clinic_id
Revises: 0031_cardio_ecg_records
Create Date: 2026-07-06

Security audit Wave 1 fix F-002: Tenant isolation for messages table.
Adds nullable clinic_id column with FK to clinics, backfilled from sender's clinic.
"""
from alembic import op
import sqlalchemy as sa


revision = "0032_messages_clinic_id"
down_revision = "0031_cardio_ecg_records"
branch_labels = None
depends_on = None


def upgrade():
    # Шаг 1: добавляем колонку как nullable (для backward compat и backfill)
    op.add_column(
        "messages",
        sa.Column("clinic_id", sa.Integer(), nullable=True),
    )

    # Шаг 2: backfill — заполняем clinic_id из sender's clinic (если users.clinic_id существует)
    # Используем raw SQL с проверкой существования колонки (single-clinic deployments могут не иметь users.clinic_id)
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'users' AND column_name = 'clinic_id'
            ) THEN
                UPDATE messages m
                SET clinic_id = u.clinic_id
                FROM users u
                WHERE m.sender_id = u.id
                  AND u.clinic_id IS NOT NULL
                  AND m.clinic_id IS NULL;
            END IF;
        END $$;
    """)

    # Шаг 3: добавляем FK + индекс (колонка остаётся nullable для backward compat)
    op.create_foreign_key(
        "fk_messages_clinic_id",
        "messages",
        "clinics",
        ["clinic_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index(
        "ix_messages_clinic_id",
        "messages",
        ["clinic_id"],
    )


def downgrade():
    op.drop_index("ix_messages_clinic_id", table_name="messages")
    op.drop_constraint("fk_messages_clinic_id", "messages", type_="foreignkey")
    op.drop_column("messages", "clinic_id")
