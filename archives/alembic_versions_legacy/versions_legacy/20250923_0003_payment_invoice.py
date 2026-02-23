"""add payment invoice for cart

Revision ID: 20250923_0003
Revises: 20250923_0002
Create Date: 2025-09-23

"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20250923_0003"
down_revision = "20250923_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Создаём таблицу payment_invoices для корзины (единый платёж за несколько визитов)
    op.create_table(
        "payment_invoices",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("patient_id", sa.Integer(), nullable=False),
        sa.Column("total_amount", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("currency", sa.String(length=8), nullable=False, server_default="UZS"),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="pending"),
        sa.Column("payment_method", sa.String(length=32), nullable=False, server_default="cash"),
        sa.Column("provider", sa.String(length=32), nullable=True),
        sa.Column("provider_payment_id", sa.String(length=128), nullable=True),
        sa.Column("provider_transaction_id", sa.String(length=128), nullable=True),
        sa.Column("payment_url", sa.String(length=512), nullable=True),
        sa.Column("provider_data", sa.JSON(), nullable=True),
        sa.Column("commission", sa.Numeric(precision=10, scale=2), nullable=True, server_default="0"),
        sa.Column("notes", sa.String(length=512), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    
    # Создаём таблицу связи invoice с визитами (many-to-many)
    op.create_table(
        "payment_invoice_visits",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("invoice_id", sa.Integer(), nullable=False),
        sa.Column("visit_id", sa.Integer(), nullable=False),
        sa.Column("visit_amount", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["invoice_id"], ["payment_invoices.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["visit_id"], ["visits.id"], ondelete="CASCADE"),
    )

    # Создаём индексы
    op.create_index("ix_payment_invoices_patient_id", "payment_invoices", ["patient_id"])
    op.create_index("ix_payment_invoices_status", "payment_invoices", ["status"])
    op.create_index("ix_payment_invoices_provider", "payment_invoices", ["provider"])
    op.create_index("ix_payment_invoices_provider_payment_id", "payment_invoices", ["provider_payment_id"])
    op.create_index("ix_payment_invoices_created_at", "payment_invoices", ["created_at"])
    
    op.create_index("ix_payment_invoice_visits_invoice_id", "payment_invoice_visits", ["invoice_id"])
    op.create_index("ix_payment_invoice_visits_visit_id", "payment_invoice_visits", ["visit_id"])
    
    # Уникальный индекс для предотвращения дублирования visit в одном invoice
    op.create_index("uq_payment_invoice_visits_invoice_visit", "payment_invoice_visits", ["invoice_id", "visit_id"], unique=True)


def downgrade() -> None:
    # Удаляем индексы
    op.drop_index("uq_payment_invoice_visits_invoice_visit", table_name="payment_invoice_visits")
    op.drop_index("ix_payment_invoice_visits_visit_id", table_name="payment_invoice_visits")
    op.drop_index("ix_payment_invoice_visits_invoice_id", table_name="payment_invoice_visits")
    op.drop_index("ix_payment_invoices_created_at", table_name="payment_invoices")
    op.drop_index("ix_payment_invoices_provider_payment_id", table_name="payment_invoices")
    op.drop_index("ix_payment_invoices_provider", table_name="payment_invoices")
    op.drop_index("ix_payment_invoices_status", table_name="payment_invoices")
    op.drop_index("ix_payment_invoices_patient_id", table_name="payment_invoices")
    
    # Удаляем таблицы
    op.drop_table("payment_invoice_visits")
    op.drop_table("payment_invoices")
