"""Join the booking notification and payment refund migration branches."""

from __future__ import annotations

revision = "0089_merge_booking_refund_heads"
down_revision = (
    "0087_booking_notification_outbox",
    "0088_fm_refund_claim",
)
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Merge the independent schema branches without changing the schema."""


def downgrade() -> None:
    """Return to the two branch heads; no schema change is required."""
