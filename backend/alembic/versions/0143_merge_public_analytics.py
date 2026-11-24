"""Join the public site analytics and payment migration branches."""

from __future__ import annotations

revision = "0143_merge_public_analytics"
down_revision = (
    "0142_deposit_visit_payment",
    "0103_public_site_daily_counts",
)
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Join the independent version histories."""


def downgrade() -> None:
    """Return to the two branch heads."""
