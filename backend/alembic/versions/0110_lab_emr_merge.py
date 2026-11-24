"""Join the laboratory and EMR migration branches without changing the schema."""

revision = "0110_lab_emr_merge"
down_revision = ("0108_emr_rollback_compat", "0109_lab_create_receipt")
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Record the common head after both parent migrations have run."""


def downgrade() -> None:
    """Restore both branch heads without changing the schema."""
