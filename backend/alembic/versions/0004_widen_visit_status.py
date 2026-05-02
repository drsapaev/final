"""widen_visit_status

Revision ID: 0004_widen_visit_status
Revises: 0003_schema_parity_tables
Create Date: 2026-03-19 14:20:00.000000

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0004_widen_visit_status"
down_revision = "0003_schema_parity_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "visits",
        "status",
        existing_type=sa.String(length=16),
        type_=sa.String(length=32),
        existing_nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        "visits",
        "status",
        existing_type=sa.String(length=32),
        type_=sa.String(length=16),
        existing_nullable=False,
    )
