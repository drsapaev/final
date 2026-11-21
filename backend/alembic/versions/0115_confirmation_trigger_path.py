"""Repair already-installed 0102 PG trigger resolution without changing ACLs.

The target schema comes from the trusted Alembic engine configuration, never
from a request's search_path. Offline generation must provide an explicit
version_table_schema. The replacement keeps function owners and privileges.
"""

from alembic import op

revision = "0115_confirmation_trigger_path"
down_revision = "0114_all_free_visibility"
branch_labels = None
depends_on = None


def upgrade() -> None:
    context = op.get_context()
    if context.dialect.name == "sqlite":
        _upgrade_sqlite()
        return
    if context.dialect.name != "postgresql":
        raise RuntimeError("Unsupported confirmation-trigger dialect")
    # SQLAlchemy obtains default_schema_name at engine initialization, before
    # request-level SET search_path. Migration startup must use a trusted path.
    schema = context.opts.get("version_table_schema") or context.dialect.default_schema_name
    if not schema:
        raise RuntimeError("Trusted migration schema required for confirmation trigger repair")
    qualified = context.dialect.identifier_preparer.quote_schema(schema)
    sequence_literal = f"{qualified}.visit_confirmation_generation_seq".replace("'", "''")
    # Lock out old trigger writers while selecting the actual high-water mark.
    # The original random allocator used at most 2**52, but installations can
    # contain larger values. Never rewrite an existing epoch or issued token.
    op.execute(f"LOCK TABLE {qualified}.visits IN ACCESS EXCLUSIVE MODE")
    op.execute(f"CREATE SEQUENCE IF NOT EXISTS {qualified}.visit_confirmation_generation_seq AS bigint")
    op.execute(f"""
    SELECT 1 / CASE WHEN GREATEST(4503599627370496::bigint,
        COALESCE((SELECT MAX(confirmation_context_epoch) FROM {qualified}.visits), 0),
        (SELECT last_value FROM {qualified}.visit_confirmation_generation_seq))
      < 9223372036854775807 THEN 1 ELSE 0 END
    """)
    op.execute(f"""
    SELECT pg_catalog.setval('{sequence_literal}'::pg_catalog.regclass,
      GREATEST(4503599627370496::bigint,
        COALESCE((SELECT MAX(confirmation_context_epoch) FROM {qualified}.visits), 0),
        (SELECT last_value FROM {qualified}.visit_confirmation_generation_seq)), true)
    """)
    op.execute(f"""
    CREATE OR REPLACE FUNCTION {qualified}.invalidate_visit_confirmation_context() RETURNS trigger
    LANGUAGE plpgsql SET search_path = pg_catalog AS $$
    BEGIN
      IF TG_OP = 'INSERT' THEN
        NEW.confirmation_context_epoch := pg_catalog.nextval(pg_catalog.format('%I.visit_confirmation_generation_seq', TG_TABLE_SCHEMA)::pg_catalog.regclass);
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
        NEW.confirmation_context_epoch := pg_catalog.nextval(pg_catalog.format('%I.visit_confirmation_generation_seq', TG_TABLE_SCHEMA)::pg_catalog.regclass);
        NEW.confirmation_token := NULL;
        NEW.confirmation_expires_at := NULL;
        IF NEW.status = 'pending_confirmation' THEN
          NEW.reminder_sent_at := NULL;
          NEW.reminder_generation := GREATEST(COALESCE(NEW.reminder_generation, 0), COALESCE(OLD.reminder_generation, 0) + 1);
        END IF;
      ELSIF pg_trigger_depth() <= 1 THEN
        NEW.confirmation_context_epoch := OLD.confirmation_context_epoch;
      END IF;
      RETURN NEW;
    END $$
    """)
    op.execute(f"""
    CREATE OR REPLACE FUNCTION {qualified}.invalidate_visit_service_confirmation() RETURNS trigger
    LANGUAGE plpgsql SET search_path = pg_catalog AS $$
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
      EXECUTE pg_catalog.format('SELECT 1 FROM %I.visits WHERE id IN ($1, $2) ORDER BY id FOR UPDATE', TG_TABLE_SCHEMA) USING old_visit, new_visit;
      EXECUTE pg_catalog.format('UPDATE %I.visits SET
        confirmation_context_epoch = pg_catalog.nextval(pg_catalog.format(''%%I.visit_confirmation_generation_seq'', $3)::pg_catalog.regclass),
        confirmation_token = NULL, confirmation_expires_at = NULL,
        reminder_sent_at = CASE WHEN status = ''pending_confirmation'' THEN NULL ELSE reminder_sent_at END,
        reminder_generation = CASE WHEN status = ''pending_confirmation''
          AND (confirmation_token IS NOT NULL OR reminder_sent_at IS NOT NULL OR reminder_claimed_at IS NOT NULL)
          THEN COALESCE(reminder_generation, 0) + 1 ELSE reminder_generation END
        WHERE id IN ($1, $2)', TG_TABLE_SCHEMA) USING old_visit, new_visit, TG_TABLE_SCHEMA;
      IF TG_OP = 'DELETE' THEN RETURN OLD; ELSE RETURN NEW; END IF;
    END $$
    """)
    op.execute(f"""
    CREATE OR REPLACE FUNCTION {qualified}.invalidate_patient_phone_confirmations() RETURNS trigger
    LANGUAGE plpgsql SET search_path = pg_catalog AS $$
    BEGIN
      IF NEW.phone IS NOT DISTINCT FROM OLD.phone THEN RETURN NEW; END IF;
      EXECUTE pg_catalog.format('SELECT 1 FROM %I.visits WHERE patient_id = $1 AND status IN (''pending_confirmation'', ''confirmation_processing'') ORDER BY id FOR UPDATE', TG_TABLE_SCHEMA) USING NEW.id;
      EXECUTE pg_catalog.format('UPDATE %I.visits SET
        confirmation_context_epoch = pg_catalog.nextval(pg_catalog.format(''%%I.visit_confirmation_generation_seq'', $2)::pg_catalog.regclass),
        confirmation_token = NULL, confirmation_expires_at = NULL,
        reminder_sent_at = NULL, reminder_generation = COALESCE(reminder_generation, 0) + 1
        WHERE patient_id = $1 AND status IN (''pending_confirmation'', ''confirmation_processing'')', TG_TABLE_SCHEMA) USING NEW.id, TG_TABLE_SCHEMA;
      RETURN NEW;
    END $$
    """)


def _upgrade_sqlite() -> None:
    # One persistent counter survives rollback/re-upgrade. The existing
    # epochs and tokens are left intact; every later invalidation advances it.
    op.execute("CREATE TABLE IF NOT EXISTS visit_confirmation_generation_clock (id INTEGER PRIMARY KEY CHECK(id=1), value INTEGER NOT NULL CHECK(typeof(value)='integer' AND value>=4503599627370496))")
    op.execute("INSERT INTO visit_confirmation_generation_clock (id,value) SELECT 1, MAX(4503599627370496, COALESCE((SELECT MAX(confirmation_context_epoch) FROM visits), 0)) WHERE NOT EXISTS (SELECT 1 FROM visit_confirmation_generation_clock)")
    op.execute("CREATE TEMP TABLE confirmation_clock_upgrade_guard (valid INTEGER NOT NULL CHECK(valid=1))")
    op.execute("INSERT INTO confirmation_clock_upgrade_guard SELECT CASE WHEN value < 9223372036854775807 AND value >= COALESCE((SELECT MAX(confirmation_context_epoch) FROM visits),0) THEN 1 ELSE 0 END FROM visit_confirmation_generation_clock WHERE id=1")
    op.execute("DROP TABLE confirmation_clock_upgrade_guard")
    op.execute("CREATE TRIGGER IF NOT EXISTS trg_confirmation_clock_no_delete BEFORE DELETE ON visit_confirmation_generation_clock BEGIN SELECT RAISE(ABORT, 'confirmation clock is persistent'); END")
    op.execute("CREATE TRIGGER IF NOT EXISTS trg_confirmation_clock_no_insert BEFORE INSERT ON visit_confirmation_generation_clock WHEN EXISTS (SELECT 1 FROM visit_confirmation_generation_clock) BEGIN SELECT RAISE(ABORT, 'confirmation clock is persistent'); END")
    op.execute("CREATE TRIGGER IF NOT EXISTS trg_confirmation_clock_monotonic BEFORE UPDATE ON visit_confirmation_generation_clock WHEN NEW.id IS NOT OLD.id OR typeof(NEW.value)<>'integer' OR OLD.value>=9223372036854775807 OR NEW.value<>OLD.value+1 BEGIN SELECT RAISE(ABORT, 'invalid confirmation clock'); END")
    for name in ("trg_visit_confirmation_context_insert", "trg_visit_confirmation_context", "trg_visit_service_confirmation_insert", "trg_visit_service_confirmation_update", "trg_visit_service_confirmation_delete", "trg_patient_phone_confirmation_context", "trg_confirmation_epoch_monotonic"):
        op.execute(f"DROP TRIGGER IF EXISTS {name}")
    op.execute("""
    CREATE TRIGGER trg_confirmation_epoch_monotonic BEFORE UPDATE OF confirmation_context_epoch ON visits
    WHEN typeof(NEW.confirmation_context_epoch)<>'integer' OR
      (NEW.confirmation_context_epoch<>OLD.confirmation_context_epoch AND
       (NEW.confirmation_context_epoch<=OLD.confirmation_context_epoch OR
        NEW.confirmation_context_epoch<>(SELECT value FROM visit_confirmation_generation_clock WHERE id=1)))
    BEGIN SELECT RAISE(ABORT, 'invalid confirmation epoch'); END
    """)
    op.execute("""
    CREATE TRIGGER trg_visit_confirmation_context_insert AFTER INSERT ON visits BEGIN
      UPDATE visit_confirmation_generation_clock SET value=value+1 WHERE id=1;
      UPDATE visits SET confirmation_context_epoch=(SELECT value FROM visit_confirmation_generation_clock WHERE id=1) WHERE id=NEW.id;
    END
    """)
    op.execute("""
    CREATE TRIGGER trg_visit_confirmation_context AFTER UPDATE OF patient_id, doctor_id, visit_date, visit_time, department, department_id, discount_mode, confirmation_channel, status ON visits
    WHEN OLD.patient_id IS NOT NEW.patient_id OR OLD.doctor_id IS NOT NEW.doctor_id
      OR OLD.visit_date IS NOT NEW.visit_date OR OLD.visit_time IS NOT NEW.visit_time
      OR OLD.department IS NOT NEW.department OR OLD.department_id IS NOT NEW.department_id
      OR OLD.discount_mode IS NOT NEW.discount_mode
      OR COALESCE(NULLIF(lower(trim(OLD.confirmation_channel)), ''), 'auto') IS NOT COALESCE(NULLIF(lower(trim(NEW.confirmation_channel)), ''), 'auto')
      OR (OLD.status='pending_confirmation' AND NEW.status NOT IN ('pending_confirmation','confirmation_processing'))
      OR (OLD.status NOT IN ('pending_confirmation','confirmation_processing') AND NEW.status='pending_confirmation')
    BEGIN
      UPDATE visit_confirmation_generation_clock SET value=value+1 WHERE id=1;
      UPDATE visits SET confirmation_context_epoch=(SELECT value FROM visit_confirmation_generation_clock WHERE id=1),
        confirmation_token=NULL, confirmation_expires_at=NULL,
        reminder_sent_at=CASE WHEN NEW.status='pending_confirmation' THEN NULL ELSE NEW.reminder_sent_at END,
        reminder_generation=CASE WHEN NEW.status='pending_confirmation' THEN MAX(COALESCE(NEW.reminder_generation,0),COALESCE(OLD.reminder_generation,0)+1) ELSE NEW.reminder_generation END
      WHERE id=NEW.id;
    END
    """)
    for event, ids, condition in (
        ("insert", "NEW.visit_id", "1"),
        ("delete", "OLD.visit_id", "1"),
        ("update", "OLD.visit_id, NEW.visit_id", "OLD.visit_id IS NOT NEW.visit_id OR OLD.service_id IS NOT NEW.service_id OR OLD.code IS NOT NEW.code OR OLD.name IS NOT NEW.name OR OLD.duration_minutes_snapshot IS NOT NEW.duration_minutes_snapshot OR OLD.qty IS NOT NEW.qty OR OLD.price IS NOT NEW.price OR OLD.currency IS NOT NEW.currency"),
    ):
        op.execute(f"""
        CREATE TRIGGER trg_visit_service_confirmation_{event} AFTER {event.upper()} ON visit_services WHEN {condition} BEGIN
          UPDATE visit_confirmation_generation_clock SET value=value+1 WHERE id=1;
          UPDATE visits SET confirmation_context_epoch=(SELECT value FROM visit_confirmation_generation_clock WHERE id=1),
            confirmation_token=NULL, confirmation_expires_at=NULL,
            reminder_sent_at=CASE WHEN status='pending_confirmation' THEN NULL ELSE reminder_sent_at END,
            reminder_generation=CASE WHEN status='pending_confirmation' AND (confirmation_token IS NOT NULL OR reminder_sent_at IS NOT NULL OR reminder_claimed_at IS NOT NULL) THEN COALESCE(reminder_generation,0)+1 ELSE reminder_generation END
          WHERE id IN ({ids});
        END
        """)
    op.execute("""
    CREATE TRIGGER trg_patient_phone_confirmation_context AFTER UPDATE OF phone ON patients WHEN OLD.phone IS NOT NEW.phone BEGIN
      UPDATE visit_confirmation_generation_clock SET value=value+1 WHERE id=1;
      UPDATE visits SET confirmation_context_epoch=(SELECT value FROM visit_confirmation_generation_clock WHERE id=1),
        confirmation_token=NULL, confirmation_expires_at=NULL, reminder_sent_at=NULL,
        reminder_generation=COALESCE(reminder_generation,0)+1
      WHERE patient_id=NEW.id AND status IN ('pending_confirmation','confirmation_processing');
    END
    """)


def downgrade() -> None:
    # Do not restore attacker-controlled name resolution during a rollback.
    pass
