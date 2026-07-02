"""Create derma examination and procedure tables.

Revision ID: 0015_derma_records
Revises: 0014_cardio_blood_tests
Create Date: 2026-03-21 18:20:00.000000

"""

from alembic import op
import sqlalchemy as sa


revision = "0015_derma_records"
down_revision = "0014_cardio_blood_tests"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "derma_examinations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("patient_id", sa.Integer(), nullable=False),
        sa.Column("visit_id", sa.Integer(), nullable=True),
        sa.Column("doctor_id", sa.Integer(), nullable=True),
        sa.Column("examination_date", sa.Date(), nullable=False),
        sa.Column("skin_type", sa.Text(), nullable=False),
        sa.Column("skin_condition", sa.Text(), nullable=True),
        sa.Column("lesions", sa.Text(), nullable=True),
        sa.Column("distribution", sa.Text(), nullable=True),
        sa.Column("symptoms", sa.Text(), nullable=True),
        sa.Column("diagnosis", sa.Text(), nullable=True),
        sa.Column("treatment_plan", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["doctor_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["patient_id"], ["patients.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["visit_id"], ["visits.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_derma_examinations_id"),
        "derma_examinations",
        ["id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_derma_examinations_patient_id"),
        "derma_examinations",
        ["patient_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_derma_examinations_visit_id"),
        "derma_examinations",
        ["visit_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_derma_examinations_doctor_id"),
        "derma_examinations",
        ["doctor_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_derma_examinations_examination_date"),
        "derma_examinations",
        ["examination_date"],
        unique=False,
    )

    op.create_table(
        "derma_procedures",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("patient_id", sa.Integer(), nullable=False),
        sa.Column("visit_id", sa.Integer(), nullable=True),
        sa.Column("doctor_id", sa.Integer(), nullable=True),
        sa.Column("procedure_date", sa.Date(), nullable=False),
        sa.Column("procedure_type", sa.Text(), nullable=False),
        sa.Column("area_treated", sa.Text(), nullable=True),
        sa.Column("products_used", sa.Text(), nullable=True),
        sa.Column("results", sa.Text(), nullable=True),
        sa.Column("follow_up", sa.Text(), nullable=True),
        sa.Column("total_cost", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["doctor_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["patient_id"], ["patients.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["visit_id"], ["visits.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_derma_procedures_id"),
        "derma_procedures",
        ["id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_derma_procedures_patient_id"),
        "derma_procedures",
        ["patient_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_derma_procedures_visit_id"),
        "derma_procedures",
        ["visit_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_derma_procedures_doctor_id"),
        "derma_procedures",
        ["doctor_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_derma_procedures_procedure_date"),
        "derma_procedures",
        ["procedure_date"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_derma_procedures_procedure_date"),
        table_name="derma_procedures",
    )
    op.drop_index(op.f("ix_derma_procedures_doctor_id"), table_name="derma_procedures")
    op.drop_index(op.f("ix_derma_procedures_visit_id"), table_name="derma_procedures")
    op.drop_index(
        op.f("ix_derma_procedures_patient_id"),
        table_name="derma_procedures",
    )
    op.drop_index(op.f("ix_derma_procedures_id"), table_name="derma_procedures")
    op.drop_table("derma_procedures")

    op.drop_index(
        op.f("ix_derma_examinations_examination_date"),
        table_name="derma_examinations",
    )
    op.drop_index(
        op.f("ix_derma_examinations_doctor_id"),
        table_name="derma_examinations",
    )
    op.drop_index(
        op.f("ix_derma_examinations_visit_id"),
        table_name="derma_examinations",
    )
    op.drop_index(
        op.f("ix_derma_examinations_patient_id"),
        table_name="derma_examinations",
    )
    op.drop_index(op.f("ix_derma_examinations_id"), table_name="derma_examinations")
    op.drop_table("derma_examinations")
