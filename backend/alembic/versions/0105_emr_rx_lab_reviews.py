"""Link prescriptions to EMR snapshots and record version-specific lab review."""

import sqlalchemy as sa

from alembic import op

revision = "0105_emr_rx_lab_reviews"
down_revision = "0104_patient_clinical_revisions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "prescriptions", sa.Column("emr_revision_id", sa.Integer(), nullable=True)
    )
    op.create_foreign_key(
        "fk_prescriptions_emr_revision_id",
        "prescriptions",
        "emr_revisions",
        ["emr_revision_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index(
        "ix_prescriptions_emr_revision_id", "prescriptions", ["emr_revision_id"]
    )
    op.create_table(
        "lab_result_reviews",
        sa.Column(
            "instance_id",
            sa.Integer(),
            sa.ForeignKey("lab_report_instances.id", ondelete="RESTRICT"),
            primary_key=True,
        ),
        sa.Column(
            "reviewer_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            primary_key=True,
        ),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("next_action", sa.String(500), nullable=True),
    )
    if op.get_bind().dialect.name == "postgresql":
        op.execute("ALTER TABLE lab_result_reviews ENABLE ROW LEVEL SECURITY")


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        bind.execute(
            sa.text(
                "LOCK TABLE prescriptions, lab_result_reviews IN ACCESS EXCLUSIVE MODE"
            )
        )
    has_links = bind.execute(
        sa.text(
            "SELECT EXISTS (SELECT 1 FROM prescriptions WHERE emr_revision_id IS NOT NULL)"
        )
    ).scalar_one()
    has_reviews = bind.execute(
        sa.text("SELECT EXISTS (SELECT 1 FROM lab_result_reviews)")
    ).scalar_one()
    if has_links or has_reviews:
        raise RuntimeError(
            "Prescription links and lab reviews must be retained. Roll back application code only."
        )
    op.drop_table("lab_result_reviews")
    op.drop_index("ix_prescriptions_emr_revision_id", table_name="prescriptions")
    op.drop_constraint(
        "fk_prescriptions_emr_revision_id", "prescriptions", type_="foreignkey"
    )
    op.drop_column("prescriptions", "emr_revision_id")
