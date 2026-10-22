"""Add a verified professional experience field to doctor profiles."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0081_doctor_experience_years"
down_revision = "0080_public_site_media"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "doctors",
        sa.Column("experience_years", sa.Integer(), nullable=True),
    )
    op.create_check_constraint(
        "ck_doctors_experience_years_nonnegative",
        "doctors",
        "experience_years IS NULL OR experience_years >= 0",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_doctors_experience_years_nonnegative",
        "doctors",
        type_="check",
    )
    op.drop_column("doctors", "experience_years")
