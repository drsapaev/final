"""Add patient email persistence.

Revision ID: 0016_patient_email
Revises: 0015_derma_records
Create Date: 2026-03-26 23:59:00.000000

"""

from alembic import op
import sqlalchemy as sa


revision = "0016_patient_email"
down_revision = "0015_derma_records"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "patients",
        sa.Column("email", sa.String(length=255), nullable=True),
    )
    op.create_index(
        op.f("ix_patients_email"),
        "patients",
        ["email"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_patients_email"), table_name="patients")
    op.drop_column("patients", "email")
