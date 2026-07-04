"""Create cardio_ecg_records table.

Revision ID: 0031_cardio_ecg_records
Revises: 0030_visit_queue_updated_at
Create Date: 2026-07-03 06:00:00.000000

R-11 / P-003 (UX audit): the GET /cardio/ecg endpoint previously returned
`[]` unconditionally and POST /cardio/ecg returned a fake `{id: 1}` with no
persistence. The cardiologist panel's "history" tab called GET /cardio/ecg
and never received any records, so the doctor could not see prior ECG
results alongside blood tests and file attachments — a direct clinical-
safety risk (dynamic ECG comparison is the basis of ischaemia diagnosis).

This migration introduces the cardio_ecg_records table to back those
endpoints. Each row links a File (already stored in the existing
`files` table — the frontend's ECGViewer uploads via /files/upload) to a
patient/visit and stores the parsed ECG parameters (heart_rate, PR, QRS,
QT, rhythm, ST-segment, T-wave) plus an interpretation note.

The parameters JSON column keeps the parsing result of ECGParser.jsx so
the frontend can re-render the ECG viewer without re-parsing the file.
"""

from alembic import op
import sqlalchemy as sa


revision = "0031_cardio_ecg_records"
down_revision = "0030_visit_queue_updated_at"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "cardio_ecg_records",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("patient_id", sa.Integer(), nullable=False),
        sa.Column("visit_id", sa.Integer(), nullable=True),
        sa.Column("doctor_id", sa.Integer(), nullable=True),
        # Link to the underlying file in the existing files table.
        # ON DELETE RESTRICT: a stored ECG record must never silently lose
        # its source file — deleting a file that has a linked ECG must be
        # an explicit two-step operation.
        sa.Column("file_id", sa.Integer(), nullable=True),
        sa.Column("ecg_date", sa.Date(), nullable=False),
        # Parsed parameters (mirrors ECGParser.jsx output).
        sa.Column("heart_rate", sa.Float(), nullable=True),
        sa.Column("pr_interval", sa.Float(), nullable=True),
        sa.Column("qrs_duration", sa.Float(), nullable=True),
        sa.Column("qt_interval", sa.Float(), nullable=True),
        sa.Column("qt_corrected", sa.Float(), nullable=True),
        sa.Column("rhythm", sa.String(length=120), nullable=True),
        sa.Column("st_segment", sa.String(length=120), nullable=True),
        sa.Column("t_wave", sa.String(length=120), nullable=True),
        sa.Column("axis", sa.String(length=60), nullable=True),
        # Free-form interpretation / conclusion by the doctor.
        sa.Column("interpretation", sa.Text(), nullable=True),
        # Provenance: 'device' (uploaded from ECG machine), 'manual' (typed),
        # 'ai' (AI-interpretation through /ai/ecg-interpret). Future-proof.
        sa.Column("source", sa.String(length=32), nullable=True),
        # Catch-all for any additional parsed parameters we may want to
        # persist later (e.g. lead-specific amplitudes) without a migration.
        sa.Column("parameters", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["doctor_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["patient_id"], ["patients.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["visit_id"], ["visits.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["file_id"], ["files.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_cardio_ecg_records_id"),
        "cardio_ecg_records",
        ["id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_cardio_ecg_records_patient_id"),
        "cardio_ecg_records",
        ["patient_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_cardio_ecg_records_visit_id"),
        "cardio_ecg_records",
        ["visit_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_cardio_ecg_records_doctor_id"),
        "cardio_ecg_records",
        ["doctor_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_cardio_ecg_records_ecg_date"),
        "cardio_ecg_records",
        ["ecg_date"],
        unique=False,
    )
    op.create_index(
        op.f("ix_cardio_ecg_records_file_id"),
        "cardio_ecg_records",
        ["file_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_cardio_ecg_records_file_id"), table_name="cardio_ecg_records")
    op.drop_index(op.f("ix_cardio_ecg_records_ecg_date"), table_name="cardio_ecg_records")
    op.drop_index(op.f("ix_cardio_ecg_records_doctor_id"), table_name="cardio_ecg_records")
    op.drop_index(op.f("ix_cardio_ecg_records_visit_id"), table_name="cardio_ecg_records")
    op.drop_index(op.f("ix_cardio_ecg_records_patient_id"), table_name="cardio_ecg_records")
    op.drop_index(op.f("ix_cardio_ecg_records_id"), table_name="cardio_ecg_records")
    op.drop_table("cardio_ecg_records")
