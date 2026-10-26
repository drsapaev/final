"""Store non-reserving public booking requests and their state history."""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0084_public_booking_requests"
down_revision = "0083_appt_duration_snapshot"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "public_booking_requests",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("patient_id", sa.Integer(), nullable=False),
        sa.Column("service_id", sa.Integer(), nullable=False),
        sa.Column("doctor_id", sa.Integer(), nullable=False),
        sa.Column("appointment_date", sa.Date(), nullable=False),
        sa.Column("appointment_time", sa.Time(), nullable=False),
        sa.Column(
            "status",
            sa.String(length=32),
            server_default=sa.text("'pending'"),
            nullable=False,
        ),
        sa.Column("settings_version", sa.Integer(), nullable=False),
        sa.Column("version", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'needs_new_time', 'rejected', 'withdrawn')",
            name="ck_public_booking_requests_status",
        ),
        sa.CheckConstraint("version > 0", name="ck_public_booking_requests_version"),
        sa.CheckConstraint(
            "settings_version >= 0",
            name="ck_public_booking_requests_settings_version",
        ),
        sa.ForeignKeyConstraint(
            ["patient_id"],
            ["patients.id"],
            name="fk_public_booking_requests_patient_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["service_id"],
            ["services.id"],
            name="fk_public_booking_requests_service_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["doctor_id"],
            ["doctors.id"],
            name="fk_public_booking_requests_doctor_id",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_public_booking_requests"),
    )
    op.create_index(
        "ix_public_booking_requests_patient_created",
        "public_booking_requests",
        ["patient_id", "created_at"],
    )
    op.create_index(
        "ix_public_booking_requests_status_created",
        "public_booking_requests",
        ["status", "created_at"],
    )

    op.create_table(
        "public_booking_request_events",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("request_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("actor_user_id", sa.Integer(), nullable=True),
        sa.Column("event_type", sa.String(length=40), nullable=False),
        sa.Column("from_status", sa.String(length=32), nullable=True),
        sa.Column("to_status", sa.String(length=32), nullable=False),
        sa.Column("previous_appointment_date", sa.Date(), nullable=True),
        sa.Column("previous_appointment_time", sa.Time(), nullable=True),
        sa.Column("requested_appointment_date", sa.Date(), nullable=False),
        sa.Column("requested_appointment_time", sa.Time(), nullable=False),
        sa.Column("idempotency_key_hash", sa.String(length=64), nullable=True),
        sa.Column("payload_hash", sa.String(length=64), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "event_type IN ('submitted', 'resubmitted', 'staff_requested_new_time', "
            "'rejected', 'withdrawn')",
            name="ck_public_booking_request_events_type",
        ),
        sa.CheckConstraint(
            "(idempotency_key_hash IS NULL) = (payload_hash IS NULL)",
            name="ck_public_booking_request_events_idempotency_pair",
        ),
        sa.ForeignKeyConstraint(
            ["request_id"],
            ["public_booking_requests.id"],
            name="fk_public_booking_request_events_request_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["actor_user_id"],
            ["users.id"],
            name="fk_public_booking_request_events_actor_user_id",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_public_booking_request_events"),
        sa.UniqueConstraint(
            "idempotency_key_hash",
            name="uq_public_booking_request_events_idempotency_key_hash",
        ),
    )
    op.create_index(
        "ix_public_booking_request_events_request_id",
        "public_booking_request_events",
        ["request_id", "id"],
    )

    op.execute(
        sa.text("ALTER TABLE public.public_booking_requests ENABLE ROW LEVEL SECURITY")
    )
    op.execute(
        sa.text(
            "ALTER TABLE public.public_booking_request_events ENABLE ROW LEVEL SECURITY"
        )
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
    has_requests = bind.execute(
        sa.text("SELECT EXISTS (SELECT 1 FROM public_booking_requests)")
    ).scalar_one()
    if has_requests:
        raise RuntimeError(
            "Refusing to remove public booking requests and their history."
        )

    op.drop_index(
        "ix_public_booking_request_events_request_id",
        table_name="public_booking_request_events",
    )
    op.drop_table("public_booking_request_events")
    op.drop_index(
        "ix_public_booking_requests_status_created",
        table_name="public_booking_requests",
    )
    op.drop_index(
        "ix_public_booking_requests_patient_created",
        table_name="public_booking_requests",
    )
    op.drop_table("public_booking_requests")
