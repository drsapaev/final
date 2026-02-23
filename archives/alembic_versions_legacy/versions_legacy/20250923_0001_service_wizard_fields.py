"""add service wizard fields

Revision ID: 20250923_0001
Revises: 20250829_0002
Create Date: 2025-09-23

"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20250923_0001"
down_revision = "20250829_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Добавляем новые поля в таблицу services для мастера регистрации
    
    # Поле для обязательности врача (только ЭхоКГ и рентген зуба требуют врача)
    op.add_column(
        "services",
        sa.Column(
            "requires_doctor",
            sa.Boolean(),
            nullable=False,
            server_default="false",
        ),
    )
    
    # Поле для тега очереди (ecg, cardiology_common, stomatology, lab, etc.)
    op.add_column(
        "services",
        sa.Column(
            "queue_tag",
            sa.String(length=32),
            nullable=True,
        ),
    )
    
    # Поле для определения консультации (для льготных/повторных визитов)
    op.add_column(
        "services",
        sa.Column(
            "is_consultation",
            sa.Boolean(),
            nullable=False,
            server_default="false",
        ),
    )
    
    # Поле для разрешения врачу менять цену (дерматология, стоматология)
    op.add_column(
        "services",
        sa.Column(
            "allow_doctor_price_override",
            sa.Boolean(),
            nullable=False,
            server_default="false",
        ),
    )

    # Создаём индексы для быстрого поиска
    op.create_index("ix_services_requires_doctor", "services", ["requires_doctor"])
    op.create_index("ix_services_queue_tag", "services", ["queue_tag"])
    op.create_index("ix_services_is_consultation", "services", ["is_consultation"])


def downgrade() -> None:
    # Удаляем индексы
    op.drop_index("ix_services_is_consultation", table_name="services")
    op.drop_index("ix_services_queue_tag", table_name="services")
    op.drop_index("ix_services_requires_doctor", table_name="services")
    
    # Удаляем колонки
    op.drop_column("services", "allow_doctor_price_override")
    op.drop_column("services", "is_consultation")
    op.drop_column("services", "queue_tag")
    op.drop_column("services", "requires_doctor")
