"""PR-6: push_devices — the canonical multi-device push registry.

The legacy single-device column ``users.device_token`` (String(255)) can
only remember ONE credential per user: a second registered device
silently overwrites the first, and there is nowhere to record that a
provider reported a credential dead. This revision creates the canonical
replacement table:

- one user -> many devices;
- ``token`` is TEXT: neither FCM registration tokens nor Web Push
  subscription descriptors have a safe portable length bound;
- uniqueness is keyed on the FIXED-LENGTH ``token_hash`` (full SHA-256
  hex), never on the raw TEXT credential: a B-tree over an
  incompressible 64 KiB token would exceed PostgreSQL's index-row-size
  limit and fail the very registration the contract promises to accept;
- ``uq_push_devices_active_credential`` (partial unique on token_hash
  WHERE enabled AND invalidated_at IS NULL) allows at most ONE active
  owner per credential across all users: a shared installation that
  switches accounts retires the previous owner atomically in register();
- ``token_fingerprint`` is a non-secret SHA-256 prefix of the credential,
  the only device-identifying value allowed in logs/responses;
- ``enabled`` is the device-level switch, independent of the user-level
  master opt-out ``users.push_notifications_enabled``;
- ``invalidated_at`` marks a credential known dead (provider UNREGISTERED
  feedback or explicit previous_token rotation) while keeping the row for
  audit;
- UNIQUE (user_id, token) enforces "the same credential never appears
  twice for one user" at the DB level, so a concurrent register race
  loses on the constraint instead of duplicating the device.

Deliberately OUT OF SCOPE for this revision (and the whole PR): no
backfill from ``users.device_token``, no sender reads/writes, no VAPID
keys, no topics. The registry is write-maintained only; activation is a
separate, census-gated decision.

Column notes:
- token_fingerprint is NOT NULL: it is derived from the token at every
  write in the service layer, so a missing fingerprint would mean the
  write bypassed the service. Same for token_hash.
- enabled is NOT NULL with a server-side default of TRUE, mirroring the
  ORM default.

Revision ID: 0064_push_devices_registry
Revises: 0063_queue_resource_contract
Create Date: 2026-09-12
"""

import sqlalchemy as sa

from alembic import op

revision = "0064_push_devices_registry"
down_revision = "0063_queue_resource_contract"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "push_devices",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("provider", sa.String(length=20), nullable=False),
        sa.Column("platform", sa.String(length=20), nullable=False),
        sa.Column("device_id", sa.String(length=128), nullable=True),
        sa.Column("token", sa.Text(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("token_fingerprint", sa.String(length=64), nullable=False),
        sa.Column(
            "enabled", sa.Boolean(), server_default=sa.true(), nullable=False
        ),
        sa.Column(
            "last_seen_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("invalidated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=True,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=True,
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "provider IN ('fcm', 'webpush')", name="ck_push_devices_provider"
        ),
        sa.CheckConstraint(
            "platform IN ('android', 'web')", name="ck_push_devices_platform"
        ),
        sa.UniqueConstraint(
            "user_id", "token_hash", name="uq_push_devices_user_token_hash"
        ),
    )
    op.create_index("ix_push_devices_user_id", "push_devices", ["user_id"])
    op.create_index("ix_push_devices_id", "push_devices", ["id"])
    op.create_index("ix_push_devices_token_hash", "push_devices", ["token_hash"])
    op.create_index(
        "ix_push_devices_user_device", "push_devices", ["user_id", "device_id"]
    )
    # At most ONE active owner per credential across all users (see the
    # service contract: register() retires a previous owner atomically;
    # the index makes the invariant hold even under a race).
    op.create_index(
        "uq_push_devices_active_credential",
        "push_devices",
        ["token_hash"],
        unique=True,
        postgresql_where=sa.text("enabled AND invalidated_at IS NULL"),
    )
    # RLS parity with the 0046/0050/0062 sweeps —
    # ops/scripts/check_public_rls.py (CI backend-tests job, right after
    # `alembic upgrade head`) fails the build on any public table with
    # relrowsecurity = false. This table holds provider credentials, so
    # the guardrail matters more than usual here.
    op.execute("ALTER TABLE public.push_devices ENABLE ROW LEVEL SECURITY")


def downgrade() -> None:
    op.drop_index(
        "uq_push_devices_active_credential", table_name="push_devices"
    )
    op.drop_index("ix_push_devices_user_device", table_name="push_devices")
    op.drop_index("ix_push_devices_token_hash", table_name="push_devices")
    op.drop_index("ix_push_devices_id", table_name="push_devices")
    op.drop_index("ix_push_devices_user_id", table_name="push_devices")
    op.drop_table("push_devices")
