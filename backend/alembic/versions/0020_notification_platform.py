"""create notification event and delivery tables

Revision ID: 0020_notification_platform
Revises: 0019_user_pref_security_settings
Create Date: 2026-03-30 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0020_notification_platform"
down_revision = "0019_user_pref_security_settings"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "notification_events",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("event_id", sa.String(length=36), nullable=False, unique=True, index=True),
        sa.Column("schema_version", sa.Integer(), nullable=False, server_default=sa.text("2")),
        sa.Column("event_type", sa.String(length=100), nullable=False, index=True),
        sa.Column("correlation_id", sa.String(length=36), nullable=True, index=True),
        sa.Column("dedup_key", sa.String(length=255), nullable=False),
        sa.UniqueConstraint("dedup_key", name="uq_notification_events_dedup_key"),
        sa.Column("source_module", sa.String(length=100), nullable=False, index=True),
        sa.Column("actor_id", sa.Integer(), nullable=True, index=True),
        sa.Column("actor_role", sa.String(length=50), nullable=True, index=True),
        sa.Column("entity_type", sa.String(length=100), nullable=True, index=True),
        sa.Column("entity_id", sa.String(length=100), nullable=True, index=True),
        sa.Column("severity", sa.String(length=20), nullable=False, server_default=sa.text("'info'")),
        sa.Column("priority", sa.String(length=20), nullable=False, server_default=sa.text("'normal'")),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("payload_snapshot", sa.JSON(), nullable=True),
        sa.Column("deep_link", sa.String(length=500), nullable=True),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index(
        "ix_notification_events_event_type_created_at",
        "notification_events",
        ["event_type", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_notification_events_severity_created_at",
        "notification_events",
        ["severity", "created_at"],
        unique=False,
    )

    op.create_table(
        "notification_deliveries",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("delivery_id", sa.String(length=36), nullable=False, unique=True, index=True),
        sa.Column(
            "event_id",
            sa.Integer(),
            sa.ForeignKey("notification_events.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("recipient_type", sa.String(length=20), nullable=False, index=True),
        sa.Column("recipient_id", sa.Integer(), nullable=False, index=True),
        sa.Column("role", sa.String(length=50), nullable=True, index=True),
        sa.Column("department_key", sa.String(length=100), nullable=True, index=True),
        sa.Column("channel", sa.String(length=20), nullable=False, index=True),
        sa.Column("dedup_key", sa.String(length=255), nullable=False),
        sa.UniqueConstraint(
            "recipient_id",
            "channel",
            "dedup_key",
            name="uq_notification_deliveries_recipient_channel_dedup",
        ),
        sa.Column("sequence_id", sa.Integer(), nullable=False, index=True),
        sa.Column(
            "delivery_status",
            sa.String(length=20),
            nullable=False,
            server_default=sa.text("'pending'"),
        ),
        sa.Column("dispatched_at", sa.DateTime(), nullable=True),
        sa.Column("first_delivered_at", sa.DateTime(), nullable=True),
        sa.Column("seen_at", sa.DateTime(), nullable=True),
        sa.Column("read_at", sa.DateTime(), nullable=True),
        sa.Column("archived_at", sa.DateTime(), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("payload_snapshot", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index(
        "ix_notification_deliveries_recipient_sequence",
        "notification_deliveries",
        ["recipient_id", "sequence_id"],
        unique=False,
    )
    op.create_index(
        "ix_notification_deliveries_recipient_status",
        "notification_deliveries",
        ["recipient_id", "delivery_status"],
        unique=False,
    )
    op.create_index(
        "ix_notification_deliveries_role_status",
        "notification_deliveries",
        ["role", "delivery_status"],
        unique=False,
    )
    op.create_index(
        "ix_notification_deliveries_department_status",
        "notification_deliveries",
        ["department_key", "delivery_status"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_notification_deliveries_department_status",
        table_name="notification_deliveries",
    )
    op.drop_index("ix_notification_deliveries_role_status", table_name="notification_deliveries")
    op.drop_index("ix_notification_deliveries_recipient_status", table_name="notification_deliveries")
    op.drop_index("ix_notification_deliveries_recipient_sequence", table_name="notification_deliveries")
    op.drop_table("notification_deliveries")

    op.drop_index("ix_notification_events_severity_created_at", table_name="notification_events")
    op.drop_index("ix_notification_events_event_type_created_at", table_name="notification_events")
    op.drop_table("notification_events")
