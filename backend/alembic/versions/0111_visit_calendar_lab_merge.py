"""Join the visit-calendar and laboratory/EMR migration histories."""

revision = "0111_visit_calendar_lab_merge"
down_revision = ("0104_visit_calendar_intent", "0110_lab_emr_merge")
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Record the common application head without changing the schema."""


def downgrade() -> None:
    """Restore both independent parent heads without changing the schema."""
