"""Add longitudinal clinical entries without modifying existing visit documents."""

import sqlalchemy as sa

from alembic import op

revision = "0104_patient_clinical_revisions"
down_revision = "0103_public_site_daily_counts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "patient_clinical_revisions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("entry_id", sa.Uuid(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("schema_version", sa.Integer(), nullable=False),
        sa.Column(
            "patient_id",
            sa.Integer(),
            sa.ForeignKey("patients.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "visit_id",
            sa.Integer(),
            sa.ForeignKey("visits.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("author_id", sa.Integer(), nullable=False),
        sa.Column("source", sa.String(24), nullable=False),
        sa.Column("clinical_details", sa.JSON(), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("confirmed_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint(
            "entry_id", "version", name="uq_patient_clinical_entry_version"
        ),
        sa.CheckConstraint("version > 0", name="ck_patient_clinical_positive_version"),
    )
    op.create_index(
        "ix_patient_clinical_patient_entry",
        "patient_clinical_revisions",
        ["patient_id", "entry_id", "version"],
    )
    if op.get_bind().dialect.name == "postgresql":
        op.execute("ALTER TABLE patient_clinical_revisions ENABLE ROW LEVEL SECURITY")


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        bind.execute(
            sa.text("LOCK TABLE patient_clinical_revisions IN ACCESS EXCLUSIVE MODE")
        )
    if bind.execute(
        sa.text("SELECT EXISTS (SELECT 1 FROM patient_clinical_revisions)")
    ).scalar_one():
        raise RuntimeError(
            "Patient clinical revisions must be retained. Roll back application code only."
        )
    op.drop_table("patient_clinical_revisions")
