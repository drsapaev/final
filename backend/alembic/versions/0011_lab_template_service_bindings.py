"""lab_template_service_bindings

Revision ID: 0011_lab_tpl_service_bind
Revises: 0010_lab_seed_sig_guard
Create Date: 2026-03-20 16:40:00.000000

"""

from alembic import op
import sqlalchemy as sa


revision = "0011_lab_tpl_service_bind"
down_revision = "0010_lab_seed_sig_guard"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "lab_template_service_bindings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("service_code", sa.String(length=32), nullable=False),
        sa.Column("template_code", sa.String(length=64), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["template_code"],
            ["lab_report_templates.code"],
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "service_code",
            "template_code",
            name="uq_lab_template_service_binding",
        ),
    )
    op.create_index(
        "ix_lab_template_service_bindings_service_code",
        "lab_template_service_bindings",
        ["service_code"],
        unique=False,
    )
    op.create_index(
        "ix_lab_template_service_bindings_template_code",
        "lab_template_service_bindings",
        ["template_code"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_lab_template_service_bindings_template_code",
        table_name="lab_template_service_bindings",
    )
    op.drop_index(
        "ix_lab_template_service_bindings_service_code",
        table_name="lab_template_service_bindings",
    )
    op.drop_table("lab_template_service_bindings")
