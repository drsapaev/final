"""Keep EMR attribution correct when old application code writes to the new schema."""

from alembic import op

revision = "0108_emr_rollback_compat"
down_revision = "0107_emr_template_shortcut"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if op.get_context().dialect.name != "postgresql":
        return

    op.execute("""
        CREATE FUNCTION invalidate_emr_template_review() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            IF NEW.template_text IS DISTINCT FROM OLD.template_text THEN
                NEW.reviewed_at := NULL;
                NEW.template_revision := GREATEST(
                    NEW.template_revision, OLD.template_revision + 1
                );
            END IF;
            RETURN NEW;
        END;
        $$
    """)
    op.execute("""
        CREATE TRIGGER trg_emr_template_review_invalidate
        BEFORE UPDATE OF template_text ON doctor_section_templates FOR EACH ROW
        EXECUTE FUNCTION invalidate_emr_template_review()
    """)

    # A canonical issuance assigns the source revision with the prescription.
    # Legacy writers leave that column untouched even when replacing its contents.
    op.execute("""
        CREATE FUNCTION invalidate_emr_prescription_attribution() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            IF OLD.emr_revision_id IS NOT NULL
               AND NEW.emr_revision_id = OLD.emr_revision_id
               AND (
                   NEW.medications::jsonb IS DISTINCT FROM OLD.medications::jsonb
                   OR NEW.instructions IS DISTINCT FROM OLD.instructions
                   OR NEW.doctor_notes IS DISTINCT FROM OLD.doctor_notes
                   OR NEW.visit_id IS DISTINCT FROM OLD.visit_id
                   OR NEW.emr_record_id IS DISTINCT FROM OLD.emr_record_id
               ) THEN
                NEW.emr_revision_id := NULL;
            END IF;
            RETURN NEW;
        END;
        $$
    """)
    op.execute("""
        CREATE TRIGGER trg_emr_prescription_attribution_invalidate
        BEFORE UPDATE OF medications, instructions, doctor_notes, visit_id, emr_record_id
        ON prescriptions FOR EACH ROW
        EXECUTE FUNCTION invalidate_emr_prescription_attribution()
    """)


def downgrade() -> None:
    if op.get_context().dialect.name != "postgresql":
        return

    op.execute("DROP TRIGGER trg_emr_prescription_attribution_invalidate ON prescriptions")
    op.execute("DROP FUNCTION invalidate_emr_prescription_attribution()")
    op.execute("DROP TRIGGER trg_emr_template_review_invalidate ON doctor_section_templates")
    op.execute("DROP FUNCTION invalidate_emr_template_review()")
