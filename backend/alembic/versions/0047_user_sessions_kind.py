"""Add session_kind to user_sessions for two-stage 2FA authentication.

Distinguishes server-side pending-session tokens:

- ``pending_2fa``   — issued at login for users with enrolled 2FA;
                      exchangeable only via ``/2fa/verify`` (challenge).
- ``2fa_enrollment`` — issued at login for critical roles (Admin/Cashier)
                      without enrolled 2FA; accepted ONLY by
                      ``/2fa/setup`` and ``/2fa/verify-setup``; single-use,
                      10-minute TTL, revoked on exchange.

NULL (legacy rows) is treated as ``pending_2fa`` by lookups, so sessions
created before this revision keep working. The enrollment token is a
random server-side session value, NOT a JWT: normal endpoints only
accept JWTs, so an enrollment token can never reach business APIs by
construction.
"""
from __future__ import annotations

import sqlalchemy as sa

from alembic import op

# Revision identifiers — chained after 0046_enable_rls.
revision = "0047_user_sessions_kind"
down_revision = "0046_enable_rls"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # IF NOT EXISTS keeps this idempotent on databases where the column
    # was already added manually.
    op.execute(
        sa.text(
            "ALTER TABLE user_sessions ADD COLUMN IF NOT EXISTS session_kind VARCHAR(32)"
        )
    )


def downgrade() -> None:
    op.execute(
        sa.text("ALTER TABLE user_sessions DROP COLUMN IF EXISTS session_kind")
    )
