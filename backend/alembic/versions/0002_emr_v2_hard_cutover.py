"""emr_v2_hard_cutover

Revision ID: 0002_emr_v2_hard_cutover
Revises: 0001_baseline
Create Date: 2026-03-17 12:00:00.000000

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0002_emr_v2_hard_cutover"
down_revision = "0001_baseline"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("prescriptions", sa.Column("visit_id", sa.Integer(), nullable=True))
    op.add_column("prescriptions", sa.Column("emr_record_id", sa.Integer(), nullable=True))
    op.create_index(op.f("ix_prescriptions_visit_id"), "prescriptions", ["visit_id"], unique=False)
    op.create_index(
        op.f("ix_prescriptions_emr_record_id"),
        "prescriptions",
        ["emr_record_id"],
        unique=False,
    )
    op.create_foreign_key(
        "fk_prescriptions_visit_id_visits",
        "prescriptions",
        "visits",
        ["visit_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_prescriptions_emr_record_id_emr_records",
        "prescriptions",
        "emr_records",
        ["emr_record_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.add_column("files", sa.Column("visit_id", sa.Integer(), nullable=True))
    op.add_column("files", sa.Column("emr_record_id", sa.Integer(), nullable=True))
    op.create_index(op.f("ix_files_visit_id"), "files", ["visit_id"], unique=False)
    op.create_index(op.f("ix_files_emr_record_id"), "files", ["emr_record_id"], unique=False)
    op.create_foreign_key(
        "fk_files_visit_id_visits",
        "files",
        "visits",
        ["visit_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_files_emr_record_id_emr_records",
        "files",
        "emr_records",
        ["emr_record_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.create_table(
        "emr_migration_ledger",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("legacy_emr_id", sa.Integer(), nullable=False),
        sa.Column("legacy_appointment_id", sa.Integer(), nullable=True),
        sa.Column("patient_id", sa.Integer(), nullable=True),
        sa.Column("visit_id", sa.Integer(), nullable=True),
        sa.Column("canonical_emr_id", sa.Integer(), nullable=True),
        sa.Column("migrated_revision_id", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("source_checksum", sa.String(length=128), nullable=True),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("migrated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_payload", sa.JSON(), nullable=True),
        sa.ForeignKeyConstraint(["visit_id"], ["visits.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["canonical_emr_id"], ["emr_records.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["migrated_revision_id"], ["emr_revisions.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("legacy_emr_id"),
    )
    op.create_index(
        op.f("ix_emr_migration_ledger_legacy_appointment_id"),
        "emr_migration_ledger",
        ["legacy_appointment_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_emr_migration_ledger_patient_id"),
        "emr_migration_ledger",
        ["patient_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_emr_migration_ledger_visit_id"),
        "emr_migration_ledger",
        ["visit_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_emr_migration_ledger_canonical_emr_id"),
        "emr_migration_ledger",
        ["canonical_emr_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_emr_migration_ledger_migrated_revision_id"),
        "emr_migration_ledger",
        ["migrated_revision_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_emr_migration_ledger_status"),
        "emr_migration_ledger",
        ["status"],
        unique=False,
    )
    op.create_index(
        "ix_emr_migration_ledger_status_visit",
        "emr_migration_ledger",
        ["status", "visit_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_emr_migration_ledger_status_visit", table_name="emr_migration_ledger")
    op.drop_index(op.f("ix_emr_migration_ledger_status"), table_name="emr_migration_ledger")
    op.drop_index(op.f("ix_emr_migration_ledger_migrated_revision_id"), table_name="emr_migration_ledger")
    op.drop_index(op.f("ix_emr_migration_ledger_canonical_emr_id"), table_name="emr_migration_ledger")
    op.drop_index(op.f("ix_emr_migration_ledger_visit_id"), table_name="emr_migration_ledger")
    op.drop_index(op.f("ix_emr_migration_ledger_patient_id"), table_name="emr_migration_ledger")
    op.drop_index(op.f("ix_emr_migration_ledger_legacy_appointment_id"), table_name="emr_migration_ledger")
    op.drop_table("emr_migration_ledger")

    op.drop_constraint("fk_files_emr_record_id_emr_records", "files", type_="foreignkey")
    op.drop_constraint("fk_files_visit_id_visits", "files", type_="foreignkey")
    op.drop_index(op.f("ix_files_emr_record_id"), table_name="files")
    op.drop_index(op.f("ix_files_visit_id"), table_name="files")
    op.drop_column("files", "emr_record_id")
    op.drop_column("files", "visit_id")

    op.drop_constraint("fk_prescriptions_emr_record_id_emr_records", "prescriptions", type_="foreignkey")
    op.drop_constraint("fk_prescriptions_visit_id_visits", "prescriptions", type_="foreignkey")
    op.drop_index(op.f("ix_prescriptions_emr_record_id"), table_name="prescriptions")
    op.drop_index(op.f("ix_prescriptions_visit_id"), table_name="prescriptions")
    op.drop_column("prescriptions", "emr_record_id")
    op.drop_column("prescriptions", "visit_id")
