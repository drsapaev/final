"""visit payment integration

Revision ID: 20250829_0002
Revises: 20250829_0001
Create Date: 2025-08-29
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20250829_0002"
down_revision = "20250829_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Добавляем поля для интеграции с платежами в таблицу visits
    op.add_column(
        "visits",
        sa.Column(
            "payment_status",
            sa.String(length=32),
            nullable=True,
            server_default="unpaid",
        ),
    )
    op.add_column(
        "visits", sa.Column("payment_amount", sa.Numeric(12, 2), nullable=True)
    )
    op.add_column(
        "visits",
        sa.Column(
            "payment_currency", sa.String(length=3), nullable=True, server_default="UZS"
        ),
    )
    op.add_column(
        "visits", sa.Column("payment_provider", sa.String(length=32), nullable=True)
    )
    op.add_column(
        "visits",
        sa.Column("payment_transaction_id", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "visits", sa.Column("payment_webhook_id", sa.Integer(), nullable=True)
    )
    op.add_column(
        "visits",
        sa.Column("payment_processed_at", sa.DateTime(timezone=True), nullable=True),
    )

    # Создаём индексы для быстрого поиска
    op.create_index("ix_visits_payment_status", "visits", ["payment_status"])
    op.create_index("ix_visits_payment_provider", "visits", ["payment_provider"])
    op.create_index(
        "ix_visits_payment_transaction", "visits", ["payment_transaction_id"]
    )

    # Добавляем внешний ключ на payment_webhooks (если таблица существует)
    # SQLite не поддерживает внешние ключи через ALTER, поэтому не создаём их


def downgrade() -> None:
    # Удаляем индексы
    op.drop_index("ix_visits_payment_transaction", table_name="visits")
    op.drop_index("ix_visits_payment_provider", table_name="visits")
    op.drop_index("ix_visits_payment_status", table_name="visits")

    # Удаляем колонки
    op.drop_column("visits", "payment_processed_at")
    op.drop_column("visits", "payment_webhook_id")
    op.drop_column("visits", "payment_transaction_id")
    op.drop_column("visits", "payment_provider")
    op.drop_column("visits", "payment_currency")
    op.drop_column("visits", "payment_amount")
    op.drop_column("visits", "payment_status")
