"""TWOFACTOR-BE-001 (audit #3892 group 33, issue #4063) — 2FA verify
brute-force defense, storage-backed.

``TwoFactorService.verify_two_factor`` accepted an unlimited number of wrong
TOTP/backup/recovery codes per user, forever: the only defenses were the
optional endpoint limiter (per-IP, bypassable from distributed sources) and
the 6-digit code space. This migration adds the persistent lockout state to
``two_factor_auth``:

* ``failed_attempts`` — consecutive failed verification counter
  (INT NOT NULL, server_default '0' so existing rows start clean);
* ``locked_until`` — nullable TIMESTAMPTZ; after 5 consecutive failures the
  service sets it to now + 15 minutes and rejects even correct codes until
  it passes (self-clearing on the next verify).

The columns are consumed by ``TwoFactorService.verify_two_factor`` (increment
on failure, reset on success, service-side lock check before any code
verification). No backfill is needed: NULL/0 means "never locked".
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

# alembic_version.version_num is VARCHAR(32) on PostgreSQL.
revision = "0093_two_factor_attempt_lockout"
down_revision = "0092_price_override_visit_price"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "two_factor_auth",
        sa.Column(
            "failed_attempts",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
            comment=(
                "TWOFACTOR-BE-001: счётчик подряд идущих неудачных "
                "верификаций 2FA; сбрасывается при успехе"
            ),
        ),
    )
    op.add_column(
        "two_factor_auth",
        sa.Column(
            "locked_until",
            sa.DateTime(timezone=True),
            nullable=True,
            comment=(
                "TWOFACTOR-BE-001: до какого момента верификация 2FA "
                "заблокирована после 5 неудачных попыток (NULL — не заблокирована)"
            ),
        ),
    )


def downgrade() -> None:
    op.drop_column("two_factor_auth", "locked_until")
    op.drop_column("two_factor_auth", "failed_attempts")
