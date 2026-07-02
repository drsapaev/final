"""lab_tpl_version_guard

Revision ID: 0007_lab_tpl_version_guard
Revises: 0006_lab_report_seed_immut
Create Date: 2026-03-20 10:35:00.000000

"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "0007_lab_tpl_version_guard"
down_revision = "0006_lab_report_seed_immut"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if op.get_context().dialect.name != "postgresql":
        return

    op.execute(
        """
        DROP TRIGGER IF EXISTS trg_lab_report_template_versions_guard
        ON lab_report_template_versions;
        """
    )
    op.execute(
        """
        DROP FUNCTION IF EXISTS prevent_non_draft_lab_report_template_version_mutation();
        """
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION prevent_non_draft_lab_report_template_version_mutation()
        RETURNS trigger AS $$
        BEGIN
            IF TG_OP = 'DELETE' THEN
                IF OLD.status IN ('PUBLISHED', 'ARCHIVED') THEN
                    RAISE EXCEPTION 'Published lab report template versions cannot be deleted';
                END IF;
                RETURN OLD;
            END IF;

            IF OLD.status = 'PUBLISHED' THEN
                IF NEW.status = 'ARCHIVED'
                   AND (to_jsonb(NEW) - 'updated_at' - 'status')
                       IS NOT DISTINCT FROM (to_jsonb(OLD) - 'updated_at' - 'status')
                THEN
                    RETURN NEW;
                END IF;
                RAISE EXCEPTION 'Published lab report template versions are immutable';
            END IF;

            IF OLD.status = 'ARCHIVED' THEN
                RAISE EXCEPTION 'Archived lab report template versions are immutable';
            END IF;

            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_lab_report_template_versions_guard
        BEFORE UPDATE OR DELETE ON lab_report_template_versions
        FOR EACH ROW
        EXECUTE FUNCTION prevent_non_draft_lab_report_template_version_mutation();
        """
    )

    op.execute(
        """
        DROP TRIGGER IF EXISTS trg_lab_report_sections_guard
        ON lab_report_sections;
        """
    )
    op.execute(
        """
        DROP TRIGGER IF EXISTS trg_lab_report_field_defs_guard
        ON lab_report_field_defs;
        """
    )
    op.execute(
        """
        DROP FUNCTION IF EXISTS prevent_non_draft_lab_report_template_structure_mutation();
        """
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION prevent_non_draft_lab_report_template_structure_mutation()
        RETURNS trigger AS $$
        DECLARE
            old_status text;
            new_status text;
        BEGIN
            IF TG_TABLE_NAME = 'lab_report_sections' THEN
                IF TG_OP IN ('UPDATE', 'DELETE') THEN
                    SELECT status
                    INTO old_status
                    FROM lab_report_template_versions
                    WHERE id = OLD.template_version_id;
                END IF;

                IF TG_OP IN ('UPDATE', 'INSERT') THEN
                    SELECT status
                    INTO new_status
                    FROM lab_report_template_versions
                    WHERE id = NEW.template_version_id;
                END IF;
            ELSIF TG_TABLE_NAME = 'lab_report_field_defs' THEN
                IF TG_OP IN ('UPDATE', 'DELETE') THEN
                    SELECT version.status
                    INTO old_status
                    FROM lab_report_sections section
                    JOIN lab_report_template_versions version
                      ON version.id = section.template_version_id
                    WHERE section.id = OLD.section_id;
                END IF;

                IF TG_OP IN ('UPDATE', 'INSERT') THEN
                    SELECT version.status
                    INTO new_status
                    FROM lab_report_sections section
                    JOIN lab_report_template_versions version
                      ON version.id = section.template_version_id
                    WHERE section.id = NEW.section_id;
                END IF;
            END IF;

            IF old_status IN ('PUBLISHED', 'ARCHIVED')
               OR new_status IN ('PUBLISHED', 'ARCHIVED')
            THEN
                RAISE EXCEPTION 'Only draft lab report template versions can change structure';
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
        CREATE TRIGGER trg_lab_report_sections_guard
        BEFORE INSERT OR UPDATE OR DELETE ON lab_report_sections
        FOR EACH ROW
        EXECUTE FUNCTION prevent_non_draft_lab_report_template_structure_mutation();
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_lab_report_field_defs_guard
        BEFORE INSERT OR UPDATE OR DELETE ON lab_report_field_defs
        FOR EACH ROW
        EXECUTE FUNCTION prevent_non_draft_lab_report_template_structure_mutation();
        """
    )


def downgrade() -> None:
    if op.get_context().dialect.name != "postgresql":
        return

    op.execute(
        """
        DROP TRIGGER IF EXISTS trg_lab_report_field_defs_guard
        ON lab_report_field_defs;
        """
    )
    op.execute(
        """
        DROP TRIGGER IF EXISTS trg_lab_report_sections_guard
        ON lab_report_sections;
        """
    )
    op.execute(
        """
        DROP FUNCTION IF EXISTS prevent_non_draft_lab_report_template_structure_mutation();
        """
    )
    op.execute(
        """
        DROP TRIGGER IF EXISTS trg_lab_report_template_versions_guard
        ON lab_report_template_versions;
        """
    )
    op.execute(
        """
        DROP FUNCTION IF EXISTS prevent_non_draft_lab_report_template_version_mutation();
        """
    )
