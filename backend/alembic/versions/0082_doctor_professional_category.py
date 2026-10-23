"""Add a structured professional qualification category to doctor profiles."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0082_doctor_prof_category"
down_revision = "0081_doctor_experience_years"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Existing records intentionally remain NULL. Website biography text is
    # not a verified source for this working-profile field.
    op.add_column(
        "doctors",
        sa.Column("professional_category", sa.String(length=12), nullable=True),
    )
    op.create_check_constraint(
        "ck_doctors_professional_category_allowed",
        "doctors",
        "professional_category IS NULL OR professional_category IN "
        "('third', 'second', 'first', 'highest')",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_doctors_professional_category_allowed",
        "doctors",
        type_="check",
    )
    op.drop_column("doctors", "professional_category")
