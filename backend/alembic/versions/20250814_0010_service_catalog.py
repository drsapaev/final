"""service catalog

Revision ID: 20250814_0010
Revises: 20250814_0009
Create Date: 2025-08-14
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20250814_0010"
down_revision = "20250814_0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "service_catalog",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("code", sa.String(length=32), nullable=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("department", sa.String(length=64), nullable=True),
        sa.Column("unit", sa.String(length=32), nullable=True),  # шт., анализ, усл.
        sa.Column("price", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ux_service_catalog_code", "service_catalog", ["code"], unique=True)
    op.create_index("ix_service_catalog_dept", "service_catalog", ["department"])


def downgrade() -> None:
    op.drop_index("ix_service_catalog_dept", table_name="service_catalog")
    op.drop_index("ux_service_catalog_code", table_name="service_catalog")
    op.drop_table("service_catalog")