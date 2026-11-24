"""Replace the deployed 0101 random link epoch with a monotonic allocator.

Upgrade preserves existing epochs and signed links. The allocator survives a
rollback so a previously issued capability cannot revive after re-upgrade.
"""
from alembic import op

revision = "0122_telegram_link_epoch"
down_revision = "0121_doctor_price_access"
branch_labels = None
depends_on = None


def upgrade() -> None:
    context = op.get_context()
    dialect = context.dialect.name
    if dialect == "postgresql":
        schema = context.opts.get("version_table_schema") or context.dialect.default_schema_name
        if not schema:
            raise RuntimeError("Trusted migration schema required")
        qualified = context.dialect.identifier_preparer.quote_schema(schema)
        sequence = f"{qualified}.telegram_patient_link_generation_seq".replace("'", "''")
        op.execute("SET LOCAL row_security=off")
        op.execute(f"LOCK TABLE {qualified}.telegram_users IN ACCESS EXCLUSIVE MODE")
        op.execute(f"CREATE SEQUENCE IF NOT EXISTS {qualified}.telegram_patient_link_generation_seq AS bigint NO CYCLE")
        op.execute(f"""
          SELECT 1 / CASE WHEN GREATEST(4503599627370496::bigint,
            COALESCE((SELECT MAX(patient_link_epoch) FROM {qualified}.telegram_users),0),
            (SELECT last_value FROM {qualified}.telegram_patient_link_generation_seq))
            < 9223372036854775807 THEN 1 ELSE 0 END
        """)
        op.execute(f"""
          SELECT pg_catalog.setval('{sequence}'::pg_catalog.regclass,
            GREATEST(4503599627370496::bigint,
              COALESCE((SELECT MAX(patient_link_epoch) FROM {qualified}.telegram_users),0),
              (SELECT last_value FROM {qualified}.telegram_patient_link_generation_seq)),true)
        """)
        op.execute(f"""
        CREATE OR REPLACE FUNCTION {qualified}.bump_telegram_patient_link_epoch()
        RETURNS trigger LANGUAGE plpgsql SET search_path=pg_catalog AS $$
        BEGIN
          IF TG_OP='INSERT' THEN
            NEW.patient_link_epoch := pg_catalog.nextval(pg_catalog.format('%I.telegram_patient_link_generation_seq',TG_TABLE_SCHEMA)::pg_catalog.regclass);
          ELSIF ROW(NEW.patient_id,NEW.chat_id,NEW.active,NEW.blocked,NEW.notifications_enabled,NEW.appointment_reminders)
            IS DISTINCT FROM ROW(OLD.patient_id,OLD.chat_id,OLD.active,OLD.blocked,OLD.notifications_enabled,OLD.appointment_reminders) THEN
            NEW.patient_link_epoch := pg_catalog.nextval(pg_catalog.format('%I.telegram_patient_link_generation_seq',TG_TABLE_SCHEMA)::pg_catalog.regclass);
          ELSE
            NEW.patient_link_epoch := OLD.patient_link_epoch;
          END IF;
          RETURN NEW;
        END $$
        """)
    elif dialect == "sqlite":
        _upgrade_sqlite()
    else:
        raise RuntimeError(f"Unsupported Telegram link dialect: {dialect}")


def _upgrade_sqlite() -> None:
    op.execute("CREATE TABLE IF NOT EXISTS telegram_patient_link_generation_clock (id INTEGER PRIMARY KEY CHECK(id=1), value INTEGER NOT NULL CHECK(typeof(value)='integer' AND value>=4503599627370496))")
    op.execute("INSERT INTO telegram_patient_link_generation_clock(id,value) SELECT 1,MAX(4503599627370496,COALESCE((SELECT MAX(patient_link_epoch) FROM telegram_users),0)) WHERE NOT EXISTS (SELECT 1 FROM telegram_patient_link_generation_clock)")
    op.execute("CREATE TEMP TABLE telegram_link_clock_upgrade_guard (valid INTEGER NOT NULL CHECK(valid=1))")
    op.execute("INSERT INTO telegram_link_clock_upgrade_guard SELECT CASE WHEN value<9223372036854775807 AND value>=COALESCE((SELECT MAX(patient_link_epoch) FROM telegram_users),0) THEN 1 ELSE 0 END FROM telegram_patient_link_generation_clock WHERE id=1")
    op.execute("DROP TABLE telegram_link_clock_upgrade_guard")
    op.execute("CREATE TRIGGER IF NOT EXISTS trg_tg_link_clock_no_delete BEFORE DELETE ON telegram_patient_link_generation_clock BEGIN SELECT RAISE(ABORT, 'link clock is persistent'); END")
    op.execute("CREATE TRIGGER IF NOT EXISTS trg_tg_link_clock_no_insert BEFORE INSERT ON telegram_patient_link_generation_clock WHEN EXISTS (SELECT 1 FROM telegram_patient_link_generation_clock) BEGIN SELECT RAISE(ABORT, 'link clock is persistent'); END")
    op.execute("CREATE TRIGGER IF NOT EXISTS trg_tg_link_clock_monotonic BEFORE UPDATE ON telegram_patient_link_generation_clock WHEN NEW.id IS NOT OLD.id OR typeof(NEW.value)<>'integer' OR OLD.value>=9223372036854775807 OR NEW.value<>OLD.value+1 BEGIN SELECT RAISE(ABORT, 'invalid link clock'); END")
    for name in ("trg_telegram_patient_link_epoch", "trg_telegram_patient_link_epoch_insert", "trg_tg_link_epoch_monotonic"):
        op.execute(f"DROP TRIGGER IF EXISTS {name}")
    op.execute("""
    CREATE TRIGGER trg_tg_link_epoch_monotonic BEFORE UPDATE OF patient_link_epoch ON telegram_users
    WHEN typeof(NEW.patient_link_epoch)<>'integer' OR
      (NEW.patient_link_epoch<>OLD.patient_link_epoch AND
       (NEW.patient_link_epoch<=OLD.patient_link_epoch OR
        NEW.patient_link_epoch<>(SELECT value FROM telegram_patient_link_generation_clock WHERE id=1)))
    BEGIN SELECT RAISE(ABORT, 'invalid Telegram link generation'); END
    """)
    op.execute("""
    CREATE TRIGGER trg_telegram_patient_link_epoch_insert AFTER INSERT ON telegram_users BEGIN
      UPDATE telegram_patient_link_generation_clock SET value=value+1 WHERE id=1;
      UPDATE telegram_users SET patient_link_epoch=(SELECT value FROM telegram_patient_link_generation_clock WHERE id=1) WHERE id=NEW.id;
    END
    """)
    op.execute("""
    CREATE TRIGGER trg_telegram_patient_link_epoch AFTER UPDATE OF patient_id,chat_id,active,blocked,notifications_enabled,appointment_reminders ON telegram_users
    WHEN OLD.patient_id IS NOT NEW.patient_id OR OLD.chat_id IS NOT NEW.chat_id
      OR OLD.active IS NOT NEW.active OR OLD.blocked IS NOT NEW.blocked
      OR OLD.notifications_enabled IS NOT NEW.notifications_enabled OR OLD.appointment_reminders IS NOT NEW.appointment_reminders
    BEGIN
      UPDATE telegram_patient_link_generation_clock SET value=value+1 WHERE id=1;
      UPDATE telegram_users SET patient_link_epoch=(SELECT value FROM telegram_patient_link_generation_clock WHERE id=1) WHERE id=NEW.id;
    END
    """)


def downgrade() -> None:
    # Preserve the safe allocator and trigger across ordinary 0122 rollback.
    pass
