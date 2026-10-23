"""Add a nullable appointment duration snapshot for future interval booking."""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0083_appt_duration_snapshot"
down_revision = "0082_doctor_prof_category"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Historical appointments intentionally remain NULL. Their duration must
    # not be inferred from the current service catalog.
    op.add_column(
        "appointments",
        sa.Column("duration_minutes_snapshot", sa.Integer(), nullable=True),
    )
    op.create_check_constraint(
        "ck_appointments_duration_snapshot_positive",
        "appointments",
        "duration_minutes_snapshot IS NULL OR duration_minutes_snapshot > 0",
    )


def downgrade() -> None:
    has_duration_snapshots = (
        op.get_bind()
        .execute(
            sa.text(
                "SELECT EXISTS ("
                "SELECT 1 FROM appointments "
                "WHERE duration_minutes_snapshot IS NOT NULL"
                ")"
            )
        )
        .scalar_one()
    )
    if has_duration_snapshots:
        raise RuntimeError(
            "Refusing to remove appointment duration snapshots after they "
            "have been recorded."
        )

    op.drop_constraint(
        "ck_appointments_duration_snapshot_positive",
        "appointments",
        type_="check",
    )
    op.drop_column("appointments", "duration_minutes_snapshot")
