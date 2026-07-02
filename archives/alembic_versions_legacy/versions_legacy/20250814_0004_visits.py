"""visits & visit_services

Revision ID: 20250814_0004
Revises: 20250814_0003
Create Date: 2025-08-14
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20250814_0004"
down_revision = "20250814_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # visits
    op.create_table(
        "visits",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "patient_id",
            sa.Integer(),
            sa.ForeignKey("patients.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "doctor_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "status", sa.String(length=16), nullable=False, server_default="open"
        ),  # open|in_progress|closed|canceled
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notes", sa.String(length=1000), nullable=True),
    )
    op.create_index("ix_visits_patient", "visits", ["patient_id"])
    op.create_index("ix_visits_doctor", "visits", ["doctor_id"])
    op.create_index("ix_visits_status", "visits", ["status"])

    # visit_services
    op.create_table(
        "visit_services",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "visit_id",
            sa.Integer(),
            sa.ForeignKey("visits.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("code", sa.String(length=32), nullable=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("price", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("qty", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_visit_services_visit", "visit_services", ["visit_id"])
    op.create_index("ix_visit_services_code", "visit_services", ["code"])


def downgrade() -> None:
    op.drop_index("ix_visit_services_code", table_name="visit_services")
    op.drop_index("ix_visit_services_visit", table_name="visit_services")
    op.drop_table("visit_services")

    op.drop_index("ix_visits_status", table_name="visits")
    op.drop_index("ix_visits_doctor", table_name="visits")
    op.drop_index("ix_visits_patient", table_name="visits")
    op.drop_table("visits")
