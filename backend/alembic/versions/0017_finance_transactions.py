"""create finance transactions table

Revision ID: 0017_finance_transactions
Revises: 0016_patient_email
Create Date: 2026-03-27 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0017_finance_transactions"
down_revision = "0016_patient_email"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "finance_transactions",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("type", sa.String(length=16), nullable=False),
        sa.Column("category", sa.String(length=255), nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("patient_id", sa.Integer(), sa.ForeignKey("patients.id", ondelete="SET NULL"), nullable=True),
        sa.Column("doctor_id", sa.Integer(), sa.ForeignKey("doctors.id", ondelete="SET NULL"), nullable=True),
        sa.Column("payment_method", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("transaction_date", sa.Date(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("reference", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index(op.f("ix_finance_transactions_id"), "finance_transactions", ["id"], unique=False)
    op.create_index(op.f("ix_finance_transactions_type"), "finance_transactions", ["type"], unique=False)
    op.create_index(op.f("ix_finance_transactions_category"), "finance_transactions", ["category"], unique=False)
    op.create_index(op.f("ix_finance_transactions_patient_id"), "finance_transactions", ["patient_id"], unique=False)
    op.create_index(op.f("ix_finance_transactions_doctor_id"), "finance_transactions", ["doctor_id"], unique=False)
    op.create_index(op.f("ix_finance_transactions_payment_method"), "finance_transactions", ["payment_method"], unique=False)
    op.create_index(op.f("ix_finance_transactions_status"), "finance_transactions", ["status"], unique=False)
    op.create_index(op.f("ix_finance_transactions_transaction_date"), "finance_transactions", ["transaction_date"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_finance_transactions_transaction_date"), table_name="finance_transactions")
    op.drop_index(op.f("ix_finance_transactions_status"), table_name="finance_transactions")
    op.drop_index(op.f("ix_finance_transactions_payment_method"), table_name="finance_transactions")
    op.drop_index(op.f("ix_finance_transactions_doctor_id"), table_name="finance_transactions")
    op.drop_index(op.f("ix_finance_transactions_patient_id"), table_name="finance_transactions")
    op.drop_index(op.f("ix_finance_transactions_category"), table_name="finance_transactions")
    op.drop_index(op.f("ix_finance_transactions_type"), table_name="finance_transactions")
    op.drop_index(op.f("ix_finance_transactions_id"), table_name="finance_transactions")
    op.drop_table("finance_transactions")
