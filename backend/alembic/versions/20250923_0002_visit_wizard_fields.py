"""add visit wizard fields

Revision ID: 20250923_0002
Revises: 20250923_0001
Create Date: 2025-09-23

"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20250923_0002"
down_revision = "20250923_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Добавляем новые поля в таблицу visits для мастера регистрации
    
    # Поле для режима скидки (none, repeat, benefit, all_free)
    op.add_column(
        "visits",
        sa.Column(
            "discount_mode",
            sa.String(length=16),
            nullable=False,
            server_default="none",
        ),
    )
    
    # Поле для статуса одобрения льгот (none, pending, approved, rejected)
    op.add_column(
        "visits",
        sa.Column(
            "approval_status",
            sa.String(length=16),
            nullable=False,
            server_default="none",
        ),
    )
    
    # Поле для переопределения цены врачом (JSON с историей изменений)
    op.add_column(
        "visits",
        sa.Column(
            "doctor_price_override",
            sa.JSON(),
            nullable=True,
        ),
    )
    
    # Поле для связи с врачом (если требуется)
    op.add_column(
        "visits",
        sa.Column(
            "doctor_id",
            sa.Integer(),
            nullable=True,
        ),
    )
    
    # Поле для даты визита
    op.add_column(
        "visits",
        sa.Column(
            "visit_date",
            sa.Date(),
            nullable=True,
        ),
    )
    
    # Поле для времени визита
    op.add_column(
        "visits",
        sa.Column(
            "visit_time",
            sa.String(length=8),
            nullable=True,
        ),
    )
    
    # Поле для отделения/специальности
    op.add_column(
        "visits",
        sa.Column(
            "department",
            sa.String(length=64),
            nullable=True,
        ),
    )

    # Создаём индексы для быстрого поиска
    op.create_index("ix_visits_discount_mode", "visits", ["discount_mode"])
    op.create_index("ix_visits_approval_status", "visits", ["approval_status"])
    op.create_index("ix_visits_doctor_id", "visits", ["doctor_id"])
    op.create_index("ix_visits_visit_date", "visits", ["visit_date"])
    op.create_index("ix_visits_department", "visits", ["department"])


def downgrade() -> None:
    # Удаляем индексы
    op.drop_index("ix_visits_department", table_name="visits")
    op.drop_index("ix_visits_visit_date", table_name="visits")
    op.drop_index("ix_visits_doctor_id", table_name="visits")
    op.drop_index("ix_visits_approval_status", table_name="visits")
    op.drop_index("ix_visits_discount_mode", table_name="visits")
    
    # Удаляем колонки
    op.drop_column("visits", "department")
    op.drop_column("visits", "visit_time")
    op.drop_column("visits", "visit_date")
    op.drop_column("visits", "doctor_id")
    op.drop_column("visits", "doctor_price_override")
    op.drop_column("visits", "approval_status")
    op.drop_column("visits", "discount_mode")
