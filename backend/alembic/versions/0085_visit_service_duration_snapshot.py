"""Capture visit-service duration at visit creation."""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0085_visit_service_duration"
down_revision = "0084_public_booking_requests"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "visit_services",
        sa.Column("duration_minutes_snapshot", sa.Integer(), nullable=True),
    )
    op.execute(
        sa.text(
            "ALTER TABLE visit_services ADD CONSTRAINT "
            "ck_visit_services_duration_snapshot_positive CHECK ("
            "duration_minutes_snapshot IS NULL OR duration_minutes_snapshot > 0"
            ") NOT VALID"
        )
    )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        # Prevent a writer from storing a snapshot between the safety check
        # and removal of the column.
        bind.execute(sa.text("LOCK TABLE visit_services IN ACCESS EXCLUSIVE MODE"))

    has_snapshots = bind.execute(
        sa.text(
            "SELECT EXISTS ("
            "SELECT 1 FROM visit_services "
            "WHERE duration_minutes_snapshot IS NOT NULL"
            ")"
        )
    ).scalar_one()
    if has_snapshots:
        raise RuntimeError(
            "Refusing to remove visit-service duration snapshots after they "
            "have been recorded."
        )

    op.drop_constraint(
        "ck_visit_services_duration_snapshot_positive",
        "visit_services",
        type_="check",
    )
    op.drop_column("visit_services", "duration_minutes_snapshot")
