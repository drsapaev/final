"""lab_catalog_normalization

Revision ID: 0008_lab_catalog_normalization
Revises: 0007_lab_tpl_version_guard
Create Date: 2026-03-20 12:30:00.000000

"""

from alembic import op
import sqlalchemy as sa


revision = "0008_lab_catalog_normalization"
down_revision = "0007_lab_tpl_version_guard"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "lab_catalog_units",
        sa.Column("code", sa.String(length=32), primary_key=True),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("symbol", sa.String(length=32), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
    )

    op.create_table(
        "lab_catalog_analytes",
        sa.Column("code", sa.String(length=64), primary_key=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("short_name", sa.String(length=64), nullable=True),
        sa.Column("category", sa.String(length=64), nullable=False),
        sa.Column("default_unit_code", sa.String(length=32), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.ForeignKeyConstraint(
            ["default_unit_code"],
            ["lab_catalog_units.code"],
            ondelete="SET NULL",
        ),
    )
    op.create_index(
        "ix_lab_catalog_analytes_category",
        "lab_catalog_analytes",
        ["category"],
        unique=False,
    )
    op.create_index(
        "ix_lab_catalog_analytes_default_unit_code",
        "lab_catalog_analytes",
        ["default_unit_code"],
        unique=False,
    )

    op.create_table(
        "lab_catalog_reference_ranges",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("analyte_code", sa.String(length=64), nullable=False),
        sa.Column("sex", sa.String(length=1), nullable=True),
        sa.Column("age_min_months", sa.Integer(), nullable=True),
        sa.Column("age_max_months", sa.Integer(), nullable=True),
        sa.Column("text", sa.String(length=255), nullable=True),
        sa.Column("low", sa.Numeric(18, 4), nullable=True),
        sa.Column("high", sa.Numeric(18, 4), nullable=True),
        sa.Column("warning_low", sa.Numeric(18, 4), nullable=True),
        sa.Column("warning_high", sa.Numeric(18, 4), nullable=True),
        sa.Column("critical_low", sa.Numeric(18, 4), nullable=True),
        sa.Column("critical_high", sa.Numeric(18, 4), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.ForeignKeyConstraint(
            ["analyte_code"],
            ["lab_catalog_analytes.code"],
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "analyte_code",
            "sex",
            "age_min_months",
            "age_max_months",
            "sort_order",
            name="uq_lab_catalog_reference_range_scope",
        ),
    )
    op.create_index(
        "ix_lab_catalog_reference_ranges_analyte_code",
        "lab_catalog_reference_ranges",
        ["analyte_code"],
        unique=False,
    )
    op.create_index(
        "ix_lab_catalog_reference_ranges_sex",
        "lab_catalog_reference_ranges",
        ["sex"],
        unique=False,
    )

    op.add_column(
        "lab_report_field_defs",
        sa.Column("analyte_code", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "lab_report_field_defs",
        sa.Column("unit_code", sa.String(length=32), nullable=True),
    )
    op.create_index(
        "ix_lab_report_field_defs_analyte_code",
        "lab_report_field_defs",
        ["analyte_code"],
        unique=False,
    )
    op.create_index(
        "ix_lab_report_field_defs_unit_code",
        "lab_report_field_defs",
        ["unit_code"],
        unique=False,
    )
    op.create_foreign_key(
        "fk_lab_report_field_defs_analyte_code",
        "lab_report_field_defs",
        "lab_catalog_analytes",
        ["analyte_code"],
        ["code"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_lab_report_field_defs_unit_code",
        "lab_report_field_defs",
        "lab_catalog_units",
        ["unit_code"],
        ["code"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_lab_report_field_defs_unit_code",
        "lab_report_field_defs",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_lab_report_field_defs_analyte_code",
        "lab_report_field_defs",
        type_="foreignkey",
    )
    op.drop_index("ix_lab_report_field_defs_unit_code", table_name="lab_report_field_defs")
    op.drop_index(
        "ix_lab_report_field_defs_analyte_code",
        table_name="lab_report_field_defs",
    )
    op.drop_column("lab_report_field_defs", "unit_code")
    op.drop_column("lab_report_field_defs", "analyte_code")

    op.drop_index(
        "ix_lab_catalog_reference_ranges_sex",
        table_name="lab_catalog_reference_ranges",
    )
    op.drop_index(
        "ix_lab_catalog_reference_ranges_analyte_code",
        table_name="lab_catalog_reference_ranges",
    )
    op.drop_table("lab_catalog_reference_ranges")

    op.drop_index("ix_lab_catalog_analytes_default_unit_code", table_name="lab_catalog_analytes")
    op.drop_index("ix_lab_catalog_analytes_category", table_name="lab_catalog_analytes")
    op.drop_table("lab_catalog_analytes")

    op.drop_table("lab_catalog_units")
