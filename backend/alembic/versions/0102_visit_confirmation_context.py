"""Fence visit confirmation credentials to the current clinical context.

The trigger covers ORM, Core and bulk writes. A context-changing statement
cannot simultaneously issue a replacement token: issue it in a subsequent
statement after all visit-service changes have been flushed. Existing PWA
tokens are preserved by upgrade itself. Telegram capability signatures include
the new random epoch, so old buttons do not revive after a downgrade/re-upgrade.
"""

import sqlalchemy as sa

from alembic import op

revision = "0102_visit_confirm_context"
down_revision = "0101_tg_patient_link_epoch"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("visits", sa.Column("confirmation_context_epoch", sa.BigInteger(), nullable=False, server_default="0"))
    dialect = op.get_context().dialect.name
    if dialect == "postgresql":
        op.execute("UPDATE visits SET confirmation_context_epoch = floor(random() * 4503599627370496)::bigint + 1")
        op.alter_column("visits", "confirmation_context_epoch", server_default=sa.text("(floor(random() * 4503599627370496)::bigint + 1)"))
        op.execute("""
        CREATE FUNCTION invalidate_visit_confirmation_context() RETURNS trigger AS $$
        BEGIN
          IF TG_OP = 'INSERT' THEN
            NEW.confirmation_context_epoch := floor(random() * 4503599627370496)::bigint + 1;
          ELSIF ROW(NEW.patient_id, NEW.doctor_id, NEW.visit_date, NEW.visit_time,
                 NEW.department, NEW.department_id, NEW.discount_mode,
                 COALESCE(NULLIF(LOWER(BTRIM(NEW.confirmation_channel)), ''), 'auto'))
             IS DISTINCT FROM
             ROW(OLD.patient_id, OLD.doctor_id, OLD.visit_date, OLD.visit_time,
                 OLD.department, OLD.department_id, OLD.discount_mode,
                 COALESCE(NULLIF(LOWER(BTRIM(OLD.confirmation_channel)), ''), 'auto'))
             OR (OLD.status = 'pending_confirmation' AND NEW.status NOT IN
                 ('pending_confirmation', 'confirmation_processing'))
             OR (OLD.status NOT IN ('pending_confirmation', 'confirmation_processing')
                 AND NEW.status = 'pending_confirmation') THEN
            NEW.confirmation_context_epoch := floor(random() * 4503599627370496)::bigint + 1;
            NEW.confirmation_token := NULL;
            NEW.confirmation_expires_at := NULL;
            IF NEW.status = 'pending_confirmation' THEN
              NEW.reminder_sent_at := NULL;
              NEW.reminder_generation := GREATEST(
                COALESCE(NEW.reminder_generation, 0),
                COALESCE(OLD.reminder_generation, 0) + 1
              );
            END IF;
          ELSIF pg_trigger_depth() <= 1 THEN
            -- Direct/bulk writes cannot reinstate an earlier generation.
            NEW.confirmation_context_epoch := OLD.confirmation_context_epoch;
          END IF;
          RETURN NEW;
        END;
        $$ LANGUAGE plpgsql
        """)
        op.execute("""
        CREATE TRIGGER trg_visit_confirmation_context
        BEFORE INSERT OR UPDATE ON visits
        FOR EACH ROW EXECUTE FUNCTION invalidate_visit_confirmation_context()
        """)
        op.execute("""
        CREATE FUNCTION invalidate_visit_service_confirmation() RETURNS trigger AS $$
        DECLARE old_visit integer; new_visit integer;
        BEGIN
          IF TG_OP = 'UPDATE' AND ROW(NEW.visit_id, NEW.service_id, NEW.code, NEW.name,
                 NEW.duration_minutes_snapshot, NEW.qty, NEW.price, NEW.currency)
             IS NOT DISTINCT FROM ROW(OLD.visit_id, OLD.service_id, OLD.code, OLD.name,
                 OLD.duration_minutes_snapshot, OLD.qty, OLD.price, OLD.currency) THEN
            RETURN NEW;
          END IF;
          IF TG_OP <> 'INSERT' THEN old_visit := OLD.visit_id; END IF;
          IF TG_OP <> 'DELETE' THEN new_visit := NEW.visit_id; END IF;
          -- A service can move between two visits. Lock owners in a stable
          -- order so opposite moves do not acquire parent locks in reverse.
          PERFORM 1 FROM visits WHERE id IN (old_visit, new_visit) ORDER BY id FOR UPDATE;
          UPDATE visits SET
            confirmation_context_epoch = floor(random() * 4503599627370496)::bigint + 1,
            confirmation_token = NULL, confirmation_expires_at = NULL,
            reminder_sent_at = CASE WHEN status = 'pending_confirmation' THEN NULL ELSE reminder_sent_at END,
            reminder_generation = CASE WHEN status = 'pending_confirmation'
              AND (confirmation_token IS NOT NULL OR reminder_sent_at IS NOT NULL OR reminder_claimed_at IS NOT NULL)
              THEN COALESCE(reminder_generation, 0) + 1 ELSE reminder_generation END
          WHERE id IN (old_visit, new_visit);
          IF TG_OP = 'DELETE' THEN RETURN OLD; ELSE RETURN NEW; END IF;
        END;
        $$ LANGUAGE plpgsql
        """)
        op.execute("""
        CREATE TRIGGER trg_visit_service_confirmation_context
        AFTER INSERT OR UPDATE OR DELETE ON visit_services
        FOR EACH ROW EXECUTE FUNCTION invalidate_visit_service_confirmation()
        """)
        op.execute("""
        CREATE FUNCTION invalidate_patient_phone_confirmations() RETURNS trigger AS $$
        BEGIN
          IF NEW.phone IS NOT DISTINCT FROM OLD.phone THEN RETURN NEW; END IF;
          -- Lock in a stable order when one patient has multiple pending visits.
          PERFORM 1 FROM visits WHERE patient_id = NEW.id
            AND status IN ('pending_confirmation', 'confirmation_processing')
            ORDER BY id FOR UPDATE;
          UPDATE visits SET
            confirmation_context_epoch = floor(random() * 4503599627370496)::bigint + 1,
            confirmation_token = NULL, confirmation_expires_at = NULL,
            reminder_sent_at = NULL,
            reminder_generation = COALESCE(reminder_generation, 0) + 1
          WHERE patient_id = NEW.id
            AND status IN ('pending_confirmation', 'confirmation_processing');
          RETURN NEW;
        END;
        $$ LANGUAGE plpgsql
        """)
        op.execute("""
        CREATE TRIGGER trg_patient_phone_confirmation_context
        AFTER UPDATE OF phone ON patients
        FOR EACH ROW EXECUTE FUNCTION invalidate_patient_phone_confirmations()
        """)
    elif dialect == "sqlite":
        op.execute("UPDATE visits SET confirmation_context_epoch = (random() & 4503599627370495) + 1")
        op.execute("""
        CREATE TRIGGER trg_visit_confirmation_context_insert
        AFTER INSERT ON visits FOR EACH ROW
        BEGIN
          UPDATE visits SET confirmation_context_epoch = (random() & 4503599627370495) + 1 WHERE id = NEW.id;
        END
        """)
        op.execute("""
        CREATE TRIGGER trg_visit_confirmation_context
        AFTER UPDATE OF patient_id, doctor_id, visit_date, visit_time, department,
                        department_id, discount_mode, confirmation_channel, status ON visits
        FOR EACH ROW
        WHEN OLD.patient_id IS NOT NEW.patient_id OR OLD.doctor_id IS NOT NEW.doctor_id
          OR OLD.visit_date IS NOT NEW.visit_date OR OLD.visit_time IS NOT NEW.visit_time
          OR OLD.department IS NOT NEW.department OR OLD.department_id IS NOT NEW.department_id
          OR OLD.discount_mode IS NOT NEW.discount_mode
          OR COALESCE(NULLIF(lower(trim(OLD.confirmation_channel)), ''), 'auto')
             IS NOT COALESCE(NULLIF(lower(trim(NEW.confirmation_channel)), ''), 'auto')
          OR (OLD.status = 'pending_confirmation' AND NEW.status NOT IN
              ('pending_confirmation', 'confirmation_processing'))
          OR (OLD.status NOT IN ('pending_confirmation', 'confirmation_processing')
              AND NEW.status = 'pending_confirmation')
        BEGIN
          UPDATE visits SET confirmation_context_epoch = (random() & 4503599627370495) + 1,
            confirmation_token = NULL, confirmation_expires_at = NULL,
            reminder_sent_at = CASE WHEN NEW.status = 'pending_confirmation'
              THEN NULL ELSE NEW.reminder_sent_at END,
            reminder_generation = CASE WHEN NEW.status = 'pending_confirmation'
              THEN MAX(COALESCE(NEW.reminder_generation, 0),
                       COALESCE(OLD.reminder_generation, 0) + 1)
              ELSE NEW.reminder_generation END
          WHERE id = NEW.id;
        END
        """)
        for event, ids, when in (
            ("insert", "NEW.visit_id", "1"),
            ("delete", "OLD.visit_id", "1"),
            ("update", "OLD.visit_id, NEW.visit_id", "OLD.visit_id IS NOT NEW.visit_id OR OLD.service_id IS NOT NEW.service_id OR OLD.code IS NOT NEW.code OR OLD.name IS NOT NEW.name OR OLD.duration_minutes_snapshot IS NOT NEW.duration_minutes_snapshot OR OLD.qty IS NOT NEW.qty OR OLD.price IS NOT NEW.price OR OLD.currency IS NOT NEW.currency"),
        ):
            op.execute(f"""
            CREATE TRIGGER trg_visit_service_confirmation_{event}
            AFTER {event.upper()} ON visit_services FOR EACH ROW WHEN {when}
            BEGIN
              UPDATE visits SET confirmation_context_epoch = (random() & 4503599627370495) + 1,
                confirmation_token = NULL, confirmation_expires_at = NULL,
                reminder_sent_at = CASE WHEN status = 'pending_confirmation' THEN NULL ELSE reminder_sent_at END,
                reminder_generation = CASE WHEN status = 'pending_confirmation'
                  AND (confirmation_token IS NOT NULL OR reminder_sent_at IS NOT NULL OR reminder_claimed_at IS NOT NULL)
                  THEN COALESCE(reminder_generation, 0) + 1 ELSE reminder_generation END
              WHERE id IN ({ids});
            END
            """)

        op.execute("""
        CREATE TRIGGER trg_patient_phone_confirmation_context
        AFTER UPDATE OF phone ON patients FOR EACH ROW
        WHEN OLD.phone IS NOT NEW.phone
        BEGIN
          UPDATE visits SET
            confirmation_context_epoch = (random() & 4503599627370495) + 1,
            confirmation_token = NULL, confirmation_expires_at = NULL,
            reminder_sent_at = NULL,
            reminder_generation = COALESCE(reminder_generation, 0) + 1
          WHERE patient_id = NEW.id
            AND status IN ('pending_confirmation', 'confirmation_processing');
        END
        """)


def downgrade() -> None:
    dialect = op.get_context().dialect.name
    if dialect == "postgresql":
        op.execute("DROP TRIGGER trg_patient_phone_confirmation_context ON patients")
        op.execute("DROP FUNCTION invalidate_patient_phone_confirmations()")
        op.execute("DROP TRIGGER trg_visit_service_confirmation_context ON visit_services")
        op.execute("DROP FUNCTION invalidate_visit_service_confirmation()")
        op.execute("DROP TRIGGER trg_visit_confirmation_context ON visits")
        op.execute("DROP FUNCTION invalidate_visit_confirmation_context()")
    elif dialect == "sqlite":
        op.execute("DROP TRIGGER trg_patient_phone_confirmation_context")
        for event in ("insert", "update", "delete"):
            op.execute(f"DROP TRIGGER trg_visit_service_confirmation_{event}")
        op.execute("DROP TRIGGER trg_visit_confirmation_context")
        op.execute("DROP TRIGGER trg_visit_confirmation_context_insert")
    op.drop_column("visits", "confirmation_context_epoch")
