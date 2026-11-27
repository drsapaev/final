"""Add universal lab equipment profiles and approved clinical settings history.

Revision ID: 0112_lab_universal_configuration
Revises: 0111_visit_calendar_lab_merge
"""

import sqlalchemy as sa

from alembic import op

revision = "0112_lab_universal_configuration"
down_revision = "0111_visit_calendar_lab_merge"
branch_labels = None
depends_on = None

NEW_TABLES = (
    "lab_equipment_integration_profiles",
    "lab_equipment_integration_profile_versions",
    "lab_clinical_configuration_versions",
)


def upgrade() -> None:
    op.create_table(
        "lab_equipment_integration_profiles",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "equipment_id",
            sa.Integer(),
            sa.ForeignKey("equipment.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("device_role", sa.String(length=24), nullable=False),
        sa.Column(
            "created_by_user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "equipment_id",
            "device_role",
            name="uq_lab_equipment_profile_equipment_role",
        ),
        sa.CheckConstraint(
            "device_role IN ('analyzer', 'printer', 'label_printer', 'scanner', 'local_agent')",
            name="ck_lab_equipment_profile_device_role",
        ),
    )
    op.create_index(
        "ix_lab_equipment_integration_profiles_equipment_id",
        "lab_equipment_integration_profiles",
        ["equipment_id"],
    )

    op.create_table(
        "lab_equipment_integration_profile_versions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "profile_id",
            sa.Integer(),
            sa.ForeignKey(
                "lab_equipment_integration_profiles.id", ondelete="RESTRICT"
            ),
            nullable=False,
        ),
        sa.Column("version_no", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("adapter_key", sa.String(length=100), nullable=False),
        sa.Column("protocol_code", sa.String(length=64), nullable=False),
        sa.Column("transport_code", sa.String(length=32), nullable=False),
        sa.Column("mapping_profile", sa.JSON(), nullable=False),
        sa.Column("transport_settings", sa.JSON(), nullable=False),
        sa.Column("device_settings", sa.JSON(), nullable=False),
        sa.Column(
            "simulator_validation_status", sa.String(length=16), nullable=False
        ),
        sa.Column("simulator_validated_at", sa.DateTime(timezone=True)),
        sa.Column("simulator_evidence_ref", sa.String(length=255)),
        sa.Column(
            "physical_validation_status", sa.String(length=16), nullable=False
        ),
        sa.Column("physical_validated_at", sa.DateTime(timezone=True)),
        sa.Column(
            "physical_validated_by_user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
        ),
        sa.Column("physical_evidence_ref", sa.String(length=255)),
        sa.Column(
            "clinical_approved_by_user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
        ),
        sa.Column("clinical_approved_at", sa.DateTime(timezone=True)),
        sa.Column(
            "clinical_approval_configuration_version_id",
            sa.Integer(),
        ),
        sa.Column("clinical_approval_authority_snapshot", sa.JSON()),
        sa.Column(
            "created_by_user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("activated_at", sa.DateTime(timezone=True)),
        sa.Column("retired_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint(
            "profile_id", "version_no", name="uq_lab_equipment_profile_version"
        ),
        sa.CheckConstraint(
            "version_no > 0", name="ck_lab_equipment_profile_version_positive"
        ),
        sa.CheckConstraint(
            "status IN ('DRAFT', 'ACTIVE', 'RETIRED')",
            name="ck_lab_equipment_profile_version_status",
        ),
        sa.CheckConstraint(
            "simulator_validation_status IN ('NOT_RUN', 'PASS', 'FAIL')",
            name="ck_lab_equipment_simulator_validation_status",
        ),
        sa.CheckConstraint(
            "physical_validation_status IN ('NOT_RUN', 'PASS', 'FAIL')",
            name="ck_lab_equipment_physical_validation_status",
        ),
        sa.CheckConstraint(
            "(simulator_validation_status = 'NOT_RUN' AND simulator_validated_at IS NULL "
            "AND simulator_evidence_ref IS NULL) OR "
            "(simulator_validation_status IN ('PASS', 'FAIL') AND simulator_validated_at IS NOT NULL "
            "AND simulator_evidence_ref IS NOT NULL)",
            name="ck_lab_equipment_simulator_evidence_state",
        ),
        sa.CheckConstraint(
            "(physical_validation_status = 'NOT_RUN' AND physical_validated_at IS NULL "
            "AND physical_validated_by_user_id IS NULL AND physical_evidence_ref IS NULL) OR "
            "(physical_validation_status IN ('PASS', 'FAIL') AND physical_validated_at IS NOT NULL "
            "AND physical_validated_by_user_id IS NOT NULL AND physical_evidence_ref IS NOT NULL)",
            name="ck_lab_equipment_physical_evidence_state",
        ),
        sa.CheckConstraint(
            "(clinical_approved_by_user_id IS NULL AND clinical_approved_at IS NULL "
            "AND clinical_approval_configuration_version_id IS NULL "
            "AND clinical_approval_authority_snapshot IS NULL) OR "
            "(clinical_approved_by_user_id IS NOT NULL AND clinical_approved_at IS NOT NULL "
            "AND clinical_approval_configuration_version_id IS NOT NULL "
            "AND clinical_approval_authority_snapshot IS NOT NULL)",
            name="ck_lab_equipment_clinical_approval_evidence_state",
        ),
        sa.CheckConstraint(
            "status != 'ACTIVE' OR (activated_at IS NOT NULL "
            "AND simulator_validation_status = 'PASS' "
            "AND physical_validation_status = 'PASS')",
            name="ck_lab_equipment_active_requires_both_validations",
        ),
    )
    op.create_index(
        "ix_lab_equipment_integration_profile_versions_profile_id",
        "lab_equipment_integration_profile_versions",
        ["profile_id"],
    )
    op.create_index(
        "ix_lab_equipment_integration_profile_versions_status",
        "lab_equipment_integration_profile_versions",
        ["status"],
    )
    op.create_index(
        "uq_lab_equipment_profile_active_version",
        "lab_equipment_integration_profile_versions",
        ["profile_id"],
        unique=True,
        postgresql_where=sa.text("status = 'ACTIVE'"),
        sqlite_where=sa.text("status = 'ACTIVE'"),
    )

    op.create_table(
        "lab_clinical_configuration_versions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("version_no", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("configuration_schema_version", sa.Integer(), nullable=False),
        sa.Column("configuration_snapshot", sa.JSON(), nullable=False),
        sa.Column(
            "primary_lab_physician_user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
        ),
        sa.Column(
            "substitute_lab_physician_user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
        ),
        sa.Column(
            "approved_by_user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
        ),
        sa.Column("approved_role_code", sa.String(length=64)),
        sa.Column("approval_authority_snapshot", sa.JSON()),
        sa.Column(
            "created_by_user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("approved_at", sa.DateTime(timezone=True)),
        sa.Column("archived_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint(
            "version_no", name="uq_lab_clinical_configuration_version"
        ),
        sa.CheckConstraint(
            "version_no > 0",
            name="ck_lab_clinical_configuration_version_positive",
        ),
        sa.CheckConstraint(
            "status IN ('DRAFT', 'PENDING_APPROVAL', 'APPROVED', 'ARCHIVED')",
            name="ck_lab_clinical_configuration_status",
        ),
        sa.CheckConstraint(
            "substitute_lab_physician_user_id IS NULL OR primary_lab_physician_user_id IS NULL "
            "OR substitute_lab_physician_user_id != primary_lab_physician_user_id",
            name="ck_lab_clinical_configuration_distinct_reviewers",
        ),
        sa.CheckConstraint(
            "status != 'APPROVED' OR (primary_lab_physician_user_id IS NOT NULL "
            "AND approved_by_user_id IS NOT NULL AND approved_at IS NOT NULL "
            "AND approved_role_code IS NOT NULL AND approval_authority_snapshot IS NOT NULL "
            "AND (approved_by_user_id = primary_lab_physician_user_id "
            "OR (substitute_lab_physician_user_id IS NOT NULL "
            "AND approved_by_user_id = substitute_lab_physician_user_id)))",
            name="ck_lab_clinical_configuration_approval_owner",
        ),
    )
    op.create_index(
        "ix_lab_clinical_configuration_versions_status",
        "lab_clinical_configuration_versions",
        ["status"],
    )
    op.create_index(
        "uq_lab_clinical_configuration_approved",
        "lab_clinical_configuration_versions",
        ["status"],
        unique=True,
        postgresql_where=sa.text("status = 'APPROVED'"),
        sqlite_where=sa.text("status = 'APPROVED'"),
    )

    op.add_column(
        "lab_report_instances",
        sa.Column(
            "clinical_configuration_version_id",
            sa.Integer(),
            sa.ForeignKey(
                "lab_clinical_configuration_versions.id", ondelete="RESTRICT"
            ),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_lab_report_instances_clinical_configuration_version_id",
        "lab_report_instances",
        ["clinical_configuration_version_id"],
    )
    op.add_column(
        "lab_report_values",
        sa.Column(
            "source_integration_profile_version_id",
            sa.Integer(),
            sa.ForeignKey(
                "lab_equipment_integration_profile_versions.id",
                ondelete="RESTRICT",
            ),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_lab_report_values_source_integration_profile_version_id",
        "lab_report_values",
        ["source_integration_profile_version_id"],
    )
    op.add_column(
        "lab_specimen_events",
        sa.Column(
            "integration_profile_version_id",
            sa.Integer(),
            sa.ForeignKey(
                "lab_equipment_integration_profile_versions.id",
                ondelete="RESTRICT",
            ),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_lab_specimen_events_integration_profile_version_id",
        "lab_specimen_events",
        ["integration_profile_version_id"],
    )

    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        for table_name in NEW_TABLES:
            op.execute(
                f"ALTER TABLE public.{table_name} ENABLE ROW LEVEL SECURITY"
            )
        op.execute(
            """
            CREATE FUNCTION public.guard_lab_equipment_profile_version() RETURNS trigger
            LANGUAGE plpgsql AS $$
            BEGIN
              IF TG_OP = 'DELETE' THEN
                IF OLD.status <> 'DRAFT' THEN
                  RAISE EXCEPTION 'Active or retired lab equipment profiles cannot be deleted';
                END IF;
                RETURN OLD;
              END IF;
              IF OLD.status IN ('ACTIVE', 'RETIRED') THEN
                IF OLD.status = 'ACTIVE'
                   AND NEW.status = 'RETIRED'
                   AND (to_jsonb(NEW) - ARRAY['status', 'retired_at']::text[])
                       = (to_jsonb(OLD) - ARRAY['status', 'retired_at']::text[]) THEN
                  RETURN NEW;
                END IF;
                RAISE EXCEPTION 'Active or retired lab equipment profile versions are immutable';
              END IF;
              RETURN NEW;
            END;
            $$
            """
        )
        op.execute(
            """
            CREATE TRIGGER trg_lab_equipment_profile_version_immutable
            BEFORE UPDATE OR DELETE ON public.lab_equipment_integration_profile_versions
            FOR EACH ROW EXECUTE FUNCTION public.guard_lab_equipment_profile_version()
            """
        )
        op.execute(
            """
            CREATE FUNCTION public.guard_lab_clinical_configuration_version() RETURNS trigger
            LANGUAGE plpgsql AS $$
            BEGIN
              IF TG_OP = 'DELETE' THEN
                IF OLD.status IN ('APPROVED', 'ARCHIVED') THEN
                  RAISE EXCEPTION 'Approved lab clinical configurations cannot be deleted';
                END IF;
                RETURN OLD;
              END IF;
              IF OLD.status IN ('APPROVED', 'ARCHIVED') THEN
                IF OLD.status = 'APPROVED'
                   AND NEW.status = 'ARCHIVED'
                   AND (to_jsonb(NEW) - ARRAY['status', 'updated_at', 'archived_at']::text[])
                       = (to_jsonb(OLD) - ARRAY['status', 'updated_at', 'archived_at']::text[]) THEN
                  RETURN NEW;
                END IF;
                RAISE EXCEPTION 'Approved lab clinical configuration versions are immutable';
              END IF;
              RETURN NEW;
            END;
            $$
            """
        )
        op.execute(
            """
            CREATE TRIGGER trg_lab_clinical_configuration_version_immutable
            BEFORE UPDATE OR DELETE ON public.lab_clinical_configuration_versions
            FOR EACH ROW EXECUTE FUNCTION public.guard_lab_clinical_configuration_version()
            """
        )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        bind.execute(
            sa.text(
                "LOCK TABLE public.lab_equipment_integration_profiles, "
                "public.lab_equipment_integration_profile_versions, "
                "public.lab_clinical_configuration_versions, "
                "public.lab_report_instances, public.lab_report_values, "
                "public.lab_specimen_events "
                "IN ACCESS EXCLUSIVE MODE"
            )
        )
    for table_name in NEW_TABLES:
        if bind.execute(
            sa.text(f"SELECT EXISTS (SELECT 1 FROM {table_name})")
        ).scalar_one():
            raise RuntimeError(
                f"Refusing to remove persisted laboratory configuration data from {table_name}."
            )
    if bind.execute(
        sa.text(
            "SELECT EXISTS (SELECT 1 FROM lab_report_instances "
            "WHERE clinical_configuration_version_id IS NOT NULL)"
        )
    ).scalar_one():
        raise RuntimeError(
            "Refusing to remove applied clinical-configuration provenance from lab reports."
        )
    if bind.execute(
        sa.text(
            "SELECT EXISTS (SELECT 1 FROM lab_report_values "
            "WHERE source_integration_profile_version_id IS NOT NULL)"
        )
    ).scalar_one():
        raise RuntimeError(
            "Refusing to remove applied equipment-profile provenance from lab results."
        )
    if bind.execute(
        sa.text(
            "SELECT EXISTS (SELECT 1 FROM lab_specimen_events "
            "WHERE integration_profile_version_id IS NOT NULL)"
        )
    ).scalar_one():
        raise RuntimeError(
            "Refusing to remove applied equipment-profile provenance from specimen labels."
        )

    if bind.dialect.name == "postgresql":
        op.execute(
            "DROP TRIGGER trg_lab_clinical_configuration_version_immutable "
            "ON public.lab_clinical_configuration_versions"
        )
        op.execute(
            "DROP FUNCTION public.guard_lab_clinical_configuration_version()"
        )
        op.execute(
            "DROP TRIGGER trg_lab_equipment_profile_version_immutable "
            "ON public.lab_equipment_integration_profile_versions"
        )
        op.execute("DROP FUNCTION public.guard_lab_equipment_profile_version()")

    op.drop_index(
        "ix_lab_specimen_events_integration_profile_version_id",
        table_name="lab_specimen_events",
    )
    op.drop_column("lab_specimen_events", "integration_profile_version_id")
    op.drop_index(
        "ix_lab_report_values_source_integration_profile_version_id",
        table_name="lab_report_values",
    )
    op.drop_column(
        "lab_report_values", "source_integration_profile_version_id"
    )
    op.drop_index(
        "ix_lab_report_instances_clinical_configuration_version_id",
        table_name="lab_report_instances",
    )
    op.drop_column(
        "lab_report_instances", "clinical_configuration_version_id"
    )
    op.drop_table("lab_clinical_configuration_versions")
    op.drop_table("lab_equipment_integration_profile_versions")
    op.drop_table("lab_equipment_integration_profiles")
