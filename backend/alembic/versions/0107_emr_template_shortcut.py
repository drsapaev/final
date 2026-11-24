"""Store a physician's optional shortcut on a section template."""

import sqlalchemy as sa

from alembic import op

revision = "0107_emr_template_shortcut"
down_revision = "0106_emr_template_review"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if op.get_context().as_sql:
        op.execute(
            "ALTER TABLE doctor_section_templates "
            "ADD COLUMN IF NOT EXISTS shortcut VARCHAR(16)"
        )
        return

    # Revision 0003 can create this table from the current model on a fresh install.
    columns = sa.inspect(op.get_bind()).get_columns("doctor_section_templates")
    if not any(column["name"] == "shortcut" for column in columns):
        op.add_column(
            "doctor_section_templates",
            sa.Column("shortcut", sa.String(16), nullable=True),
        )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        bind.execute(
            sa.text("LOCK TABLE doctor_section_templates IN ACCESS EXCLUSIVE MODE")
        )
    has_shortcuts = bind.execute(
        sa.text("SELECT EXISTS (SELECT 1 FROM doctor_section_templates WHERE shortcut IS NOT NULL)")
    ).scalar_one()
    if has_shortcuts:
        raise RuntimeError("Physician template shortcuts must be retained. Roll back code only.")
    op.drop_column("doctor_section_templates", "shortcut")
