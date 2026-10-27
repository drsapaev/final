"""Link confirmed public booking requests to regular appointments."""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

# alembic_version.version_num is VARCHAR(32) on PostgreSQL.
revision = "0086_public_booking_confirm"
down_revision = "0085_visit_service_duration"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "public_booking_requests",
        sa.Column("appointment_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_public_booking_requests_appointment_id",
        "public_booking_requests",
        "appointments",
        ["appointment_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index(
        "uq_public_booking_requests_appointment_id",
        "public_booking_requests",
        ["appointment_id"],
        unique=True,
        postgresql_where=sa.text("appointment_id IS NOT NULL"),
        sqlite_where=sa.text("appointment_id IS NOT NULL"),
    )
    op.drop_constraint(
        "ck_public_booking_requests_status",
        "public_booking_requests",
        type_="check",
    )
    op.create_check_constraint(
        "ck_public_booking_requests_status",
        "public_booking_requests",
        "status IN ('pending', 'needs_new_time', 'confirmed', 'rejected', 'withdrawn')",
    )
    op.drop_constraint(
        "ck_public_booking_request_events_type",
        "public_booking_request_events",
        type_="check",
    )
    op.create_check_constraint(
        "ck_public_booking_request_events_type",
        "public_booking_request_events",
        "event_type IN ('submitted', 'resubmitted', 'staff_requested_new_time', "
        "'confirmation_slot_unavailable', 'confirmed', 'rejected', 'withdrawn')",
    )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        bind.execute(
            sa.text(
                "LOCK TABLE public.public_booking_request_events, "
                "public.public_booking_requests IN ACCESS EXCLUSIVE MODE"
            )
        )

    has_confirmations = bind.execute(
        sa.text(
            "SELECT EXISTS (SELECT 1 FROM public_booking_requests "
            "WHERE appointment_id IS NOT NULL OR status = 'confirmed') "
            "OR EXISTS (SELECT 1 FROM public_booking_request_events "
            "WHERE event_type IN ('confirmed', 'confirmation_slot_unavailable'))"
        )
    ).scalar_one()
    if has_confirmations:
        raise RuntimeError(
            "Refusing to remove public booking confirmation history or appointment links."
        )

    op.drop_constraint(
        "ck_public_booking_request_events_type",
        "public_booking_request_events",
        type_="check",
    )
    op.create_check_constraint(
        "ck_public_booking_request_events_type",
        "public_booking_request_events",
        "event_type IN ('submitted', 'resubmitted', 'staff_requested_new_time', "
        "'rejected', 'withdrawn')",
    )
    op.drop_constraint(
        "ck_public_booking_requests_status",
        "public_booking_requests",
        type_="check",
    )
    op.create_check_constraint(
        "ck_public_booking_requests_status",
        "public_booking_requests",
        "status IN ('pending', 'needs_new_time', 'rejected', 'withdrawn')",
    )
    op.drop_index(
        "uq_public_booking_requests_appointment_id",
        table_name="public_booking_requests",
    )
    op.drop_constraint(
        "fk_public_booking_requests_appointment_id",
        "public_booking_requests",
        type_="foreignkey",
    )
    op.drop_column("public_booking_requests", "appointment_id")
