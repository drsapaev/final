"""Require a physician to review each version of a reusable section template."""

import sqlalchemy as sa

from alembic import op

revision = "0106_emr_template_review"
down_revision = "0105_emr_rx_lab_reviews"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "doctor_section_templates",
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "doctor_section_templates",
        sa.Column(
            "template_revision", sa.Integer(), nullable=False, server_default="1"
        ),
    )


def downgrade() -> None:
    op.drop_column("doctor_section_templates", "template_revision")
    op.drop_column("doctor_section_templates", "reviewed_at")
