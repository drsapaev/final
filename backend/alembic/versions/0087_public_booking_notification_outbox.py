"""Persist retryable Registrar inbox notifications for public booking requests."""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0087_public_booking_notification_outbox"
down_revision = "0086_public_booking_confirm"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "public_booking_request_notification_outbox",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("request_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("request_version", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(length=60), nullable=False),
        sa.Column(
            "attempt_count",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column(
            "next_attempt_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error_code", sa.String(length=80), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "request_version > 0",
            name="ck_public_booking_notification_outbox_version",
        ),
        sa.CheckConstraint(
            "attempt_count >= 0",
            name="ck_public_booking_notification_outbox_attempts",
        ),
        sa.CheckConstraint(
            "event_type IN ('public_booking_request_submitted', "
            "'public_booking_request_resubmitted')",
            name="ck_public_booking_notification_outbox_type",
        ),
        sa.ForeignKeyConstraint(
            ["request_id"],
            ["public_booking_requests.id"],
            name="fk_public_booking_notification_outbox_request_id",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_public_booking_notification_outbox"),
        sa.UniqueConstraint(
            "request_id",
            "request_version",
            name="uq_public_booking_notification_outbox_request_version",
        ),
    )
    op.create_index(
        "ix_public_booking_notification_outbox_due",
        "public_booking_request_notification_outbox",
        ["next_attempt_at", "id"],
        postgresql_where=sa.text("completed_at IS NULL"),
        sqlite_where=sa.text("completed_at IS NULL"),
    )

    if op.get_bind().dialect.name == "postgresql":
        op.execute(
            sa.text(
                "ALTER TABLE public.public_booking_request_notification_outbox "
                "ENABLE ROW LEVEL SECURITY"
            )
        )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        bind.execute(
            sa.text(
                "LOCK TABLE public.public_booking_request_notification_outbox "
                "IN ACCESS EXCLUSIVE MODE"
            )
        )

    has_outbox_rows = bind.execute(
        sa.text(
            "SELECT EXISTS (SELECT 1 "
            "FROM public_booking_request_notification_outbox)"
        )
    ).scalar_one()
    if has_outbox_rows:
        raise RuntimeError(
            "Refusing to remove persisted public booking notification outbox rows."
        )

    op.drop_index(
        "ix_public_booking_notification_outbox_due",
        table_name="public_booking_request_notification_outbox",
    )
    op.drop_table("public_booking_request_notification_outbox")
