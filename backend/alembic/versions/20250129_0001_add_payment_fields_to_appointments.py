"""add payment fields to appointments

Revision ID: 20250129_0001
Revises: 20250829_0002
Create Date: 2025-01-29 12:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "20250129_0001"
down_revision = "add_emr_prescription"
branch_labels = None
depends_on = None


def _resolve_target_table() -> str | None:
    inspector = sa.inspect(op.get_bind())
    table_names = set(inspector.get_table_names())
    if "appointments" in table_names:
        return "appointments"
    if "visits" in table_names:
        return "visits"
    return None


def _has_column(table_name: str, column_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return any(col["name"] == column_name for col in inspector.get_columns(table_name))


def upgrade() -> None:
    target = _resolve_target_table()
    if target is None:
        return

    columns = [
        sa.Column("payment_amount", sa.Float(), nullable=True),
        sa.Column("payment_currency", sa.String(length=3), nullable=True, default="UZS"),
        sa.Column("payment_provider", sa.String(length=32), nullable=True),
        sa.Column("payment_transaction_id", sa.String(length=128), nullable=True),
        sa.Column("payment_webhook_id", sa.Integer(), nullable=True),
        sa.Column("payment_processed_at", sa.DateTime(timezone=True), nullable=True),
    ]
    for column in columns:
        if not _has_column(target, column.name):
            op.add_column(target, column)


def downgrade() -> None:
    target = _resolve_target_table()
    if target is None:
        return

    for column_name in (
        "payment_processed_at",
        "payment_webhook_id",
        "payment_transaction_id",
        "payment_provider",
        "payment_currency",
        "payment_amount",
    ):
        if _has_column(target, column_name):
            op.drop_column(target, column_name)
