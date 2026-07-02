"""lab_report_templates

Revision ID: 0005_lab_report_templates
Revises: 0004_widen_visit_status
Create Date: 2026-03-19 18:40:00.000000

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0005_lab_report_templates"
down_revision = "0004_widen_visit_status"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "lab_report_templates",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("family", sa.String(length=64), nullable=False),
        sa.Column("description", sa.String(length=1000), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_lab_report_templates_code", "lab_report_templates", ["code"], unique=True)
    op.create_index("ix_lab_report_templates_family", "lab_report_templates", ["family"], unique=False)

    op.create_table(
        "lab_report_template_versions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("template_id", sa.Integer(), nullable=False),
        sa.Column("version_no", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("layout_preset", sa.String(length=64), nullable=False),
        sa.Column("page_settings", sa.JSON(), nullable=False),
        sa.Column("branding_overrides", sa.JSON(), nullable=False),
        sa.Column("signer_defaults", sa.JSON(), nullable=False),
        sa.Column("footer_notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["template_id"], ["lab_report_templates.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("template_id", "version_no", name="uq_lab_template_version"),
    )
    op.create_index(
        "ix_lab_report_template_versions_template_id",
        "lab_report_template_versions",
        ["template_id"],
        unique=False,
    )
    op.create_index(
        "ix_lab_report_template_versions_status",
        "lab_report_template_versions",
        ["status"],
        unique=False,
    )

    op.create_table(
        "lab_report_sections",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("template_version_id", sa.Integer(), nullable=False),
        sa.Column("key", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("section_style", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(
            ["template_version_id"],
            ["lab_report_template_versions.id"],
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("template_version_id", "key", name="uq_lab_report_section_key"),
    )
    op.create_index(
        "ix_lab_report_sections_template_version_id",
        "lab_report_sections",
        ["template_version_id"],
        unique=False,
    )

    op.create_table(
        "lab_report_field_defs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("section_id", sa.Integer(), nullable=False),
        sa.Column("field_key", sa.String(length=64), nullable=False),
        sa.Column("label", sa.String(length=255), nullable=False),
        sa.Column("value_type", sa.String(length=16), nullable=False),
        sa.Column("unit", sa.String(length=64), nullable=True),
        sa.Column("reference_mode", sa.String(length=16), nullable=False),
        sa.Column("reference_text", sa.String(length=255), nullable=True),
        sa.Column("reference_rule", sa.JSON(), nullable=True),
        sa.Column("visibility_rule", sa.JSON(), nullable=True),
        sa.Column("highlight_rule", sa.JSON(), nullable=True),
        sa.Column("choice_options", sa.JSON(), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("required", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.ForeignKeyConstraint(["section_id"], ["lab_report_sections.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("section_id", "field_key", name="uq_lab_report_field_key"),
    )
    op.create_index("ix_lab_report_field_defs_section_id", "lab_report_field_defs", ["section_id"], unique=False)

    op.create_table(
        "lab_report_instances",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("order_id", sa.Integer(), nullable=True),
        sa.Column("visit_id", sa.Integer(), nullable=True),
        sa.Column("patient_id", sa.Integer(), nullable=False),
        sa.Column("template_id", sa.Integer(), nullable=False),
        sa.Column("template_version_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("patient_snapshot", sa.JSON(), nullable=False),
        sa.Column("branding_snapshot", sa.JSON(), nullable=False),
        sa.Column("signer_snapshot", sa.JSON(), nullable=False),
        sa.Column("supersedes_instance_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finalized_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("printed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["order_id"], ["lab_orders.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["visit_id"], ["visits.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["patient_id"], ["patients.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["template_id"], ["lab_report_templates.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["template_version_id"],
            ["lab_report_template_versions.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["supersedes_instance_id"],
            ["lab_report_instances.id"],
            ondelete="SET NULL",
        ),
    )
    for column_name in (
        "order_id",
        "visit_id",
        "patient_id",
        "template_id",
        "template_version_id",
        "status",
        "supersedes_instance_id",
    ):
        op.create_index(
            f"ix_lab_report_instances_{column_name}",
            "lab_report_instances",
            [column_name],
            unique=False,
        )

    op.create_table(
        "lab_report_values",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("instance_id", sa.Integer(), nullable=False),
        sa.Column("field_key", sa.String(length=64), nullable=False),
        sa.Column("value_text", sa.Text(), nullable=True),
        sa.Column("value_numeric", sa.Numeric(18, 4), nullable=True),
        sa.Column("resolved_reference_text", sa.Text(), nullable=True),
        sa.Column("resolved_flag", sa.String(length=32), nullable=True),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["instance_id"], ["lab_report_instances.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("instance_id", "field_key", name="uq_lab_report_value_field"),
    )
    op.create_index("ix_lab_report_values_instance_id", "lab_report_values", ["instance_id"], unique=False)
    op.create_index("ix_lab_report_values_field_key", "lab_report_values", ["field_key"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_lab_report_values_field_key", table_name="lab_report_values")
    op.drop_index("ix_lab_report_values_instance_id", table_name="lab_report_values")
    op.drop_table("lab_report_values")

    for column_name in (
        "supersedes_instance_id",
        "status",
        "template_version_id",
        "template_id",
        "patient_id",
        "visit_id",
        "order_id",
    ):
        op.drop_index(f"ix_lab_report_instances_{column_name}", table_name="lab_report_instances")
    op.drop_table("lab_report_instances")

    op.drop_index("ix_lab_report_field_defs_section_id", table_name="lab_report_field_defs")
    op.drop_table("lab_report_field_defs")

    op.drop_index("ix_lab_report_sections_template_version_id", table_name="lab_report_sections")
    op.drop_table("lab_report_sections")

    op.drop_index(
        "ix_lab_report_template_versions_status",
        table_name="lab_report_template_versions",
    )
    op.drop_index(
        "ix_lab_report_template_versions_template_id",
        table_name="lab_report_template_versions",
    )
    op.drop_table("lab_report_template_versions")

    op.drop_index("ix_lab_report_templates_family", table_name="lab_report_templates")
    op.drop_index("ix_lab_report_templates_code", table_name="lab_report_templates")
    op.drop_table("lab_report_templates")
