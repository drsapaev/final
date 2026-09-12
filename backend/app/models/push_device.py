"""PR-6: canonical multi-device push registry.

The legacy single-device column ``users.device_token`` (String(255)) can
only remember ONE credential per user: the second registered device
silently overwrites the first, and there is nowhere to record that a
provider reported a credential dead. This table is the canonical
replacement:

- one user -> many devices (phone + tablet + PWA simultaneously);
- ``token`` is TEXT, not VARCHAR: neither FCM registration tokens nor
  Web Push subscription descriptors have a safe portable length bound;
  uniqueness is enforced through the fixed-length ``token_hash``
  (full SHA-256 hex) instead of the raw TEXT, because a B-tree over an
  incompressible 64 KiB credential would hit PostgreSQL's index-row-size
  limit and fail registration;
- ``token_fingerprint`` is a non-secret SHA-256 prefix of the credential
  so logs/support/ops can identify a device without ever storing or
  displaying the credential itself;
- a credential has at most ONE active owner across all users: the
  partial unique index ``uq_push_devices_active_credential`` is enforced
  at the DB level, and ``register`` atomically retires a previous owner
  when a shared installation switches accounts;
- ``enabled`` is the device-level switch, INDEPENDENT of the user-level
  master opt-out ``users.push_notifications_enabled``;
- ``invalidated_at`` marks a credential known to be dead (provider
  UNREGISTERED feedback, or superseded via an explicit
  ``previous_token`` rotation) so it is never used again, while the row
  is kept for audit.

Activation status: this PR does NOT activate FCM/Web Push sending. No
sender consumes this table yet; the first consumer is the Android FCM
pilot that follows this PR. The legacy column is frozen as deprecated:
new code paths never read it and never write it.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.db.base_class import Base

PROVIDERS = ("fcm", "webpush")
PLATFORMS = ("android", "web")


class PushDevice(Base):
    __tablename__ = "push_devices"
    __table_args__ = (
        CheckConstraint(
            "provider IN ('fcm', 'webpush')", name="ck_push_devices_provider"
        ),
        CheckConstraint(
            "platform IN ('android', 'web')", name="ck_push_devices_platform"
        ),
        # Same active credential may never appear twice for one user.
        # Uniqueness is keyed on the fixed-length token_hash (full
        # SHA-256 hex), NOT on the raw TEXT credential: a B-tree index
        # over an incompressible 64 KiB token would exceed PostgreSQL's
        # index-row-size limit and fail the very registration the
        # contract promises to accept. The service re-activates an
        # invalidated row instead of inserting a duplicate, so
        # invalidated history and a live row can never collide on the
        # same key.
        UniqueConstraint(
            "user_id", "token_hash", name="uq_push_devices_user_token_hash"
        ),
        Index("ix_push_devices_user_device", "user_id", "device_id"),
        # A credential has at most ONE active owner across ALL users.
        # When a shared installation switches accounts, register()
        # retires the previous owner atomically; this index makes the
        # "one active owner" invariant hold even under a concurrent
        # race, where the loser retries after the winner's retirement.
        # Partial on both PostgreSQL and SQLite (test world).
        Index(
            "uq_push_devices_active_credential",
            "token_hash",
            unique=True,
            postgresql_where=text("enabled AND invalidated_at IS NULL"),
            sqlite_where=text("enabled AND invalidated_at IS NULL"),
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    provider: Mapped[str] = mapped_column(String(20), nullable=False)
    platform: Mapped[str] = mapped_column(String(20), nullable=False)
    # App-generated stable per-install identifier. Nullable: a web/PWA
    # client may register before it has a persisted stable id.
    device_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    # Provider credential: FCM registration token, or a Web Push
    # subscription descriptor (endpoint / p256dh / auth JSON).
    # NEVER logged, NEVER reported to Sentry, NEVER echoed in responses.
    token: Mapped[str] = mapped_column(Text, nullable=False)
    # Full SHA-256 hex of the credential — the bounded uniqueness key.
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    # SHA-256 prefix of the credential — the only device-identifying
    # value that may appear in logs and API responses.
    token_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    # Device-level switch, independent of users.push_notifications_enabled.
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    # Set when the exact credential is known dead (provider feedback or
    # explicit rotation). Rows keep the timestamp for audit; they are
    # never selected for sending again.
    invalidated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
