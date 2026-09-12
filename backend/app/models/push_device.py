"""PR-6: Push device credential registry — one row per (device, credential).

This is the canonical MULTI-DEVICE registry for push channels. It replaces
the single-device legacy column ``users.device_token`` as the source of
truth for "which credentials can receive a push" — WITHOUT activating any
channel: FCM_ENABLED stays off, no VAPID keys are introduced, Telegram/SMS
are untouched. Activation (Android FCM pilot) is a separate product
decision that comes AFTER this registry, per the owner's fixed queue:

    PR-6 device registry → Android FCM pilot → delivery metrics →
    Web Push/VAPID decision → legacy users.device_token removal.

Design decisions (owner requirements):

- ``token`` is TEXT (not VARCHAR(255)): FCM registration tokens fit in
  255 chars today, but Web Push endpoint URLs and future provider
  credentials must not be squeezed into a legacy width. Abuse is bounded
  at the API contract layer (Pydantic max_length), not in the DB.
- ``credential`` (JSON) carries the provider-specific payload. For
  ``provider="webpush"`` this holds the PushSubscription keys
  (``keys.p256dh`` / ``keys.auth``); the ``token`` column holds the
  subscription endpoint. A Web Push subscription is NEVER squeezed into
  the FCM-token format.
- ``enabled`` is the device-level switch (user can mute one device).
  ``users.push_notifications_enabled`` REMAINS the user-level master
  opt-out — device-level operations never write it.
- ``invalidated_at`` marks a credential known dead (canonical FCM
  UNREGISTERED verdict) or superseded (rotation / account move). Only the
  EXACT credential that actually failed is invalidated — a replacement
  token registered while a failing send was in flight is never touched.
- One user MAY have several devices; one physical device (stable
  app-generated ``device_id``) MAY be re-registered with a rotated token;
  one ACTIVE credential MUST NOT duplicate: enforced by the partial
  unique index ``uq_push_devices_active_credential`` (only rows with
  ``invalidated_at IS NULL`` participate).
- No token/endpoint value is ever logged, echoed in responses or sent to
  Sentry — responses carry a short SHA-256 fingerprint instead.
- The table is created ONLY by Alembic (0064), which also enables RLS in
  the same revision (0046 contract: deny-all, no policies, owner bypasses
  — verified ``relrowsecurity = true`` by a disposable-PostgreSQL test).
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
    JSON,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func, text

from app.db.base_class import Base

# Providers / platforms are closed enums guarded by CHECK constraints in
# the table (and mirrored here for API-contract validation).
PUSH_PROVIDERS: tuple[str, ...] = ("fcm", "webpush")
PUSH_PLATFORMS: tuple[str, ...] = ("android", "web")


class PushDevice(Base):
    __tablename__ = "push_devices"
    __table_args__ = (
        CheckConstraint(
            "provider IN ('fcm', 'webpush')", name="ck_push_devices_provider"
        ),
        CheckConstraint(
            "platform IN ('android', 'web')", name="ck_push_devices_platform"
        ),
        # One ACTIVE credential must not duplicate across users/devices.
        # Partial (invalidated_at IS NULL): dead/superseded rows keep their
        # history and free the slot for a fresh registration.
        Index(
            "uq_push_devices_active_credential",
            "provider",
            "token",
            unique=True,
            postgresql_where=text("invalidated_at IS NULL"),
            sqlite_where=text("invalidated_at IS NULL"),
        ),
        # Rotation / per-device lookups.
        Index("ix_push_devices_user_device", "user_id", "device_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    provider: Mapped[str] = mapped_column(String(16), nullable=False)
    platform: Mapped[str] = mapped_column(String(16), nullable=False)
    # App-generated stable identifier of the PHYSICAL device (client-side
    # UUID). Nullable: legacy clients may not send one.
    device_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    # Provider credential: FCM registration token or Web Push subscription
    # endpoint. TEXT — no legacy width.
    token: Mapped[str] = mapped_column(Text, nullable=False)
    # Provider-specific payload (webpush: {"keys": {"p256dh", "auth"}}).
    credential: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    # Device-level switch. The user-level master opt-out lives on
    # users.push_notifications_enabled and is NEVER written here.
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    # Set only when the EXACT credential is known dead/superseded.
    invalidated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
