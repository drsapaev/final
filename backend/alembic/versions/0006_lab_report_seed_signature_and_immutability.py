"""lab_report_seed_immut

Revision ID: 0006_lab_report_seed_immut
Revises: 0005_lab_report_templates
Create Date: 2026-03-20 09:30:00.000000

"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "0006_lab_report_seed_immut"
down_revision = "0005_lab_report_templates"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "lab_report_template_versions",
        sa.Column("seed_signature", sa.String(length=64), nullable=True),
    )
    op.create_index(
        "ix_lab_report_template_versions_seed_signature",
        "lab_report_template_versions",
        ["seed_signature"],
        unique=False,
    )

    if op.get_context().dialect.name != "postgresql":
        return

    op.execute(
        """
        DROP TRIGGER IF EXISTS trg_lab_report_instances_guard ON lab_report_instances;
        """
    )
    op.execute(
        """
        DROP FUNCTION IF EXISTS prevent_finalized_lab_report_instance_update();
        """
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION prevent_finalized_lab_report_instance_update()
        RETURNS trigger AS $$
        BEGIN
            IF TG_OP = 'DELETE' THEN
                IF OLD.status IN ('FINALIZED', 'PRINTED') THEN
                    RAISE EXCEPTION 'Cannot delete finalized lab report instances';
                END IF;
                RETURN OLD;
            END IF;

            IF NEW.status = 'PRINTED' THEN
                IF OLD.status = 'FINALIZED'
                   AND NEW.order_id IS NOT DISTINCT FROM OLD.order_id
                   AND NEW.visit_id IS NOT DISTINCT FROM OLD.visit_id
                   AND NEW.patient_id IS NOT DISTINCT FROM OLD.patient_id
                   AND NEW.template_id IS NOT DISTINCT FROM OLD.template_id
                   AND NEW.template_version_id IS NOT DISTINCT FROM OLD.template_version_id
                   AND to_jsonb(NEW.patient_snapshot) IS NOT DISTINCT FROM to_jsonb(OLD.patient_snapshot)
                   AND to_jsonb(NEW.branding_snapshot) IS NOT DISTINCT FROM to_jsonb(OLD.branding_snapshot)
                   AND to_jsonb(NEW.signer_snapshot) IS NOT DISTINCT FROM to_jsonb(OLD.signer_snapshot)
                   AND NEW.supersedes_instance_id IS NOT DISTINCT FROM OLD.supersedes_instance_id
                   AND NEW.finalized_at IS NOT DISTINCT FROM OLD.finalized_at
                THEN
                    RETURN NEW;
                END IF;
                IF OLD.status = 'PRINTED'
                   AND NEW.order_id IS NOT DISTINCT FROM OLD.order_id
                   AND NEW.visit_id IS NOT DISTINCT FROM OLD.visit_id
                   AND NEW.patient_id IS NOT DISTINCT FROM OLD.patient_id
                   AND NEW.template_id IS NOT DISTINCT FROM OLD.template_id
                   AND NEW.template_version_id IS NOT DISTINCT FROM OLD.template_version_id
                   AND to_jsonb(NEW.patient_snapshot) IS NOT DISTINCT FROM to_jsonb(OLD.patient_snapshot)
                   AND to_jsonb(NEW.branding_snapshot) IS NOT DISTINCT FROM to_jsonb(OLD.branding_snapshot)
                   AND to_jsonb(NEW.signer_snapshot) IS NOT DISTINCT FROM to_jsonb(OLD.signer_snapshot)
                   AND NEW.supersedes_instance_id IS NOT DISTINCT FROM OLD.supersedes_instance_id
                   AND NEW.finalized_at IS NOT DISTINCT FROM OLD.finalized_at
                THEN
                    RETURN NEW;
                END IF;
                RAISE EXCEPTION 'Only finalized lab report instances can be marked printed';
            END IF;

            IF OLD.status = 'FINALIZED' THEN
                RAISE EXCEPTION 'Finalized lab report instances are immutable';
            END IF;

            IF OLD.status = 'PRINTED' THEN
                RAISE EXCEPTION 'Printed lab report instances are immutable';
            END IF;

            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_lab_report_instances_guard
        BEFORE UPDATE OR DELETE ON lab_report_instances
        FOR EACH ROW
        EXECUTE FUNCTION prevent_finalized_lab_report_instance_update();
        """
    )

    op.execute(
        """
        DROP TRIGGER IF EXISTS trg_lab_report_values_guard ON lab_report_values;
        """
    )
    op.execute(
        """
        DROP FUNCTION IF EXISTS prevent_finalized_lab_report_value_mutation();
        """
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION prevent_finalized_lab_report_value_mutation()
        RETURNS trigger AS $$
        DECLARE
            parent_status text;
            instance_id_value integer;
        BEGIN
            instance_id_value := COALESCE(NEW.instance_id, OLD.instance_id);
            SELECT status
            INTO parent_status
            FROM lab_report_instances
            WHERE id = instance_id_value;

            IF parent_status IN ('FINALIZED', 'PRINTED') THEN
                RAISE EXCEPTION 'Cannot mutate values for finalized lab report instances';
            END IF;

            IF TG_OP = 'DELETE' THEN
                RETURN OLD;
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_lab_report_values_guard
        BEFORE INSERT OR UPDATE OR DELETE ON lab_report_values
        FOR EACH ROW
        EXECUTE FUNCTION prevent_finalized_lab_report_value_mutation();
        """
    )


def downgrade() -> None:
    if op.get_context().dialect.name == "postgresql":
        op.execute(
            """
            DROP TRIGGER IF EXISTS trg_lab_report_values_guard ON lab_report_values;
            """
        )
        op.execute(
            """
            DROP FUNCTION IF EXISTS prevent_finalized_lab_report_value_mutation();
            """
        )
        op.execute(
            """
            DROP TRIGGER IF EXISTS trg_lab_report_instances_guard ON lab_report_instances;
            """
        )
        op.execute(
            """
            DROP FUNCTION IF EXISTS prevent_finalized_lab_report_instance_update();
            """
        )

    op.drop_index(
        "ix_lab_report_template_versions_seed_signature",
        table_name="lab_report_template_versions",
    )
    op.drop_column("lab_report_template_versions", "seed_signature")
