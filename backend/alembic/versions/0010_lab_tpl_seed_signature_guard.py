"""lab_tpl_seed_signature_guard

Revision ID: 0010_lab_seed_sig_guard
Revises: 0009_lab_value_flag_snapshot
Create Date: 2026-03-20 11:25:00.000000

"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "0010_lab_seed_sig_guard"
down_revision = "0009_lab_value_flag_snapshot"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if op.get_context().dialect.name != "postgresql":
        return

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
                IF NEW.status = OLD.status
                   AND (to_jsonb(NEW) - 'updated_at' - 'seed_signature')
                       IS NOT DISTINCT FROM (to_jsonb(OLD) - 'updated_at' - 'seed_signature')
                THEN
                    RETURN NEW;
                END IF;

                IF NEW.status = 'ARCHIVED'
                   AND (to_jsonb(NEW) - 'updated_at' - 'status' - 'seed_signature')
                       IS NOT DISTINCT FROM (to_jsonb(OLD) - 'updated_at' - 'status' - 'seed_signature')
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


def downgrade() -> None:
    if op.get_context().dialect.name != "postgresql":
        return

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
