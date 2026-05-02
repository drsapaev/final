"""lab_value_flag_snapshot

Revision ID: 0009_lab_value_flag_snapshot
Revises: 0008_lab_catalog_normalization
Create Date: 2026-03-20 14:10:00.000000

"""

import sqlalchemy as sa

from alembic import op

revision = "0009_lab_value_flag_snapshot"
down_revision = "0008_lab_catalog_normalization"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "lab_report_values",
        sa.Column("resolved_flag_source", sa.String(length=32), nullable=True),
    )
    op.add_column(
        "lab_report_values",
        sa.Column("resolved_flag_severity", sa.Integer(), nullable=True),
    )
    op.add_column(
        "lab_report_values",
        sa.Column("resolved_flag_meta", sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("lab_report_values", "resolved_flag_meta")
    op.drop_column("lab_report_values", "resolved_flag_severity")
    op.drop_column("lab_report_values", "resolved_flag_source")
