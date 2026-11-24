"""Require a physician to review each version of a reusable section template."""

import sqlalchemy as sa

from alembic import op

revision = "0106_emr_template_review"
down_revision = "0105_emr_rx_lab_reviews"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if op.get_context().as_sql:
        # Defer the schema checks until PostgreSQL applies the generated SQL.
        op.execute(
            "ALTER TABLE doctor_section_templates "
            "ADD COLUMN IF NOT EXISTS reviewed_at TIMESTAMP WITH TIME ZONE, "
            "ADD COLUMN IF NOT EXISTS template_revision INTEGER DEFAULT 1 NOT NULL"
        )
        op.execute(
            """
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM pg_catalog.pg_attribute
                    WHERE attrelid = 'doctor_section_templates'::regclass
                    AND attname = 'template_revision'
                    AND atthasdef
                ) THEN
                    ALTER TABLE doctor_section_templates
                        ALTER COLUMN template_revision SET DEFAULT 1;
                END IF;
            END;
            $$
            """
        )
        return

    # Revision 0003 can bootstrap the table from current model metadata.
    columns = {
        column["name"]: column
        for column in sa.inspect(op.get_bind()).get_columns("doctor_section_templates")
    }
    if "reviewed_at" not in columns:
        op.add_column(
            "doctor_section_templates",
            sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        )
    if "template_revision" not in columns:
        op.add_column(
            "doctor_section_templates",
            sa.Column(
                "template_revision", sa.Integer(), nullable=False, server_default="1"
            ),
        )
    elif columns["template_revision"]["default"] is None:
        op.alter_column(
            "doctor_section_templates", "template_revision", server_default="1"
        )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        bind.execute(
            sa.text("LOCK TABLE doctor_section_templates IN ACCESS EXCLUSIVE MODE")
        )
    has_review_history = bind.execute(
        sa.text(
            "SELECT EXISTS (SELECT 1 FROM doctor_section_templates "
            "WHERE reviewed_at IS NOT NULL OR template_revision > 1)"
        )
    ).scalar_one()
    if has_review_history:
        raise RuntimeError(
            "Template review history must be retained. Roll back application code only."
        )
    op.drop_column("doctor_section_templates", "template_revision")
    op.drop_column("doctor_section_templates", "reviewed_at")
