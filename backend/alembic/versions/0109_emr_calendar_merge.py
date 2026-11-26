"""Join the calendar intent and EMR workspace revision branches."""

revision = "0109_emr_calendar_merge"
down_revision = ("0104_visit_calendar_intent", "0108_emr_rollback_compat")
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Record both already-applied branches as a single head."""


def downgrade() -> None:
    """Return to the two branch heads without changing the schema."""
