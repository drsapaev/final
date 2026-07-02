"""Create cardio blood tests table.

Revision ID: 0014_cardio_blood_tests
Revises: 0013_lab_bind_actual_codes
Create Date: 2026-03-21 15:20:00.000000

"""

from alembic import op
import sqlalchemy as sa


revision = "0014_cardio_blood_tests"
down_revision = "0013_lab_bind_actual_codes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "cardio_blood_tests",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("patient_id", sa.Integer(), nullable=False),
        sa.Column("visit_id", sa.Integer(), nullable=True),
        sa.Column("doctor_id", sa.Integer(), nullable=True),
        sa.Column("test_date", sa.Date(), nullable=False),
        sa.Column("cholesterol_total", sa.Float(), nullable=True),
        sa.Column("cholesterol_hdl", sa.Float(), nullable=True),
        sa.Column("cholesterol_ldl", sa.Float(), nullable=True),
        sa.Column("triglycerides", sa.Float(), nullable=True),
        sa.Column("glucose", sa.Float(), nullable=True),
        sa.Column("crp", sa.Float(), nullable=True),
        sa.Column("troponin", sa.Float(), nullable=True),
        sa.Column("interpretation", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["doctor_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["patient_id"], ["patients.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["visit_id"], ["visits.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_cardio_blood_tests_id"), "cardio_blood_tests", ["id"], unique=False
    )
    op.create_index(
        op.f("ix_cardio_blood_tests_patient_id"),
        "cardio_blood_tests",
        ["patient_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_cardio_blood_tests_visit_id"),
        "cardio_blood_tests",
        ["visit_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_cardio_blood_tests_doctor_id"),
        "cardio_blood_tests",
        ["doctor_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_cardio_blood_tests_test_date"),
        "cardio_blood_tests",
        ["test_date"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_cardio_blood_tests_test_date"), table_name="cardio_blood_tests")
    op.drop_index(op.f("ix_cardio_blood_tests_doctor_id"), table_name="cardio_blood_tests")
    op.drop_index(op.f("ix_cardio_blood_tests_visit_id"), table_name="cardio_blood_tests")
    op.drop_index(op.f("ix_cardio_blood_tests_patient_id"), table_name="cardio_blood_tests")
    op.drop_index(op.f("ix_cardio_blood_tests_id"), table_name="cardio_blood_tests")
    op.drop_table("cardio_blood_tests")
