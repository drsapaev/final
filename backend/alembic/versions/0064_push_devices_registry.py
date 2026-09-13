"""PR-6: push_devices — canonical multi-device push credential registry.

Revision ID: 0064_push_devices_registry
Revises: 0063_queue_resource_contract
Create Date: 2026-09-12

Creates the registry that replaces the single-device legacy column
``users.device_token`` as the source of truth for push credentials —
WITHOUT activating any channel (FCM_ENABLED stays off, no VAPID,
Telegram/SMS untouched, no topics). Activation (Android FCM pilot) is a
separate product decision that comes AFTER this registry:

    PR-6 device registry → Android FCM pilot → delivery metrics →
    Web Push/VAPID decision → legacy users.device_token removal.

Schema decisions:

- ``token`` is TEXT (FCM tokens fit 255 chars today; Web Push endpoint
  URLs and future provider credentials must not inherit a legacy width).
- ``credential`` (JSON) carries the provider-specific payload — for
  webpush the PushSubscription keys (p256dh/auth); the FCM-token format
  is never forced onto Web Push subscriptions.
- ``enabled`` is the device-level switch; the user-level master opt-out
  stays on ``users.push_notifications_enabled``.
- ``invalidated_at`` marks a credential known dead (canonical FCM
  UNREGISTERED verdict) or superseded (rotation / account move); only the
  EXACT failed credential is ever invalidated.
- One ACTIVE credential must not duplicate: partial UNIQUE index over
  (provider, token) restricted to ``invalidated_at IS NULL``. Dead rows
  keep their history and free the slot.

RLS contract (0046): the table is created and gets ``ENABLE ROW LEVEL
SECURITY`` in the SAME revision — deny-all posture (no policies; the
Supabase anon/authenticated roles see nothing, the owner-role backend
bypasses). A disposable-PostgreSQL gate_d test asserts
``pg_class.relrowsecurity = true`` after ``alembic upgrade head`` and the
down/upgrade cycle.

Downgrade drops the table (RLS state goes with it). The legacy
``users.device_token`` column is deliberately NOT touched here — its
destructive removal is a separate PR after the post-census decision.
"""
from alembic import op
import sqlalchemy as sa

revision = "0064_push_devices_registry"
down_revision = "0063_queue_resource_contract"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "push_devices",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("provider", sa.String(length=16), nullable=False),
        sa.Column("platform", sa.String(length=16), nullable=False),
        sa.Column("device_id", sa.String(length=128), nullable=True),
        sa.Column("token", sa.Text(), nullable=False),
        sa.Column("credential", sa.JSON(), nullable=True),
        sa.Column(
            "enabled", sa.Boolean(), nullable=False, server_default=sa.true()
        ),
        sa.Column(
            "last_seen_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("invalidated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=True,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=True,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "provider IN ('fcm', 'webpush')", name="ck_push_devices_provider"
        ),
        sa.CheckConstraint(
            "platform IN ('android', 'web')", name="ck_push_devices_platform"
        ),
    )
    op.create_index(
        op.f("ix_push_devices_user_id"), "push_devices", ["user_id"], unique=False
    )
    op.create_index(
        "ix_push_devices_user_device",
        "push_devices",
        ["user_id", "device_id"],
        unique=False,
    )
    op.create_index(
        "uq_push_devices_active_credential",
        "push_devices",
        ["provider", "token"],
        unique=True,
        postgresql_where=sa.text("invalidated_at IS NULL"),
    )

    # RLS in the SAME migration that creates the table (0046 contract):
    # deny-all for the Supabase API roles, owner-role backend unaffected.
    op.execute("ALTER TABLE public.push_devices ENABLE ROW LEVEL SECURITY")


def downgrade() -> None:
    op.drop_index(
        "uq_push_devices_active_credential", table_name="push_devices"
    )
    op.drop_index("ix_push_devices_user_device", table_name="push_devices")
    op.drop_index(op.f("ix_push_devices_user_id"), table_name="push_devices")
    op.drop_table("push_devices")
