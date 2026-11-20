"""Allocate distinct patient ownership epochs; no inbox authorization is implied."""

import sqlalchemy as sa

from alembic import op

revision = "0113_subject_ownership"
down_revision = "0112_doctor_price_context"
branch_labels = None
depends_on = None


def upgrade() -> None:
    dialect = op.get_context().dialect.name
    if dialect not in {"postgresql", "sqlite"}:
        raise RuntimeError(f"Unsupported subject ownership dialect: {dialect}")
    if dialect == "postgresql":
        # Avoid a silently incomplete backfill under row-level security.
        op.execute("SET LOCAL row_security = off")
        op.execute("LOCK TABLE patients IN ACCESS EXCLUSIVE MODE")
    op.add_column(
        "patients",
        sa.Column(
            "notification_owner_generation",
            sa.BigInteger(),
            nullable=False,
            server_default="0",
        ),
    )
    if dialect == "postgresql":
        # Non-transactional sequence gaps on rollback are intentional.
        op.execute(
            "CREATE SEQUENCE IF NOT EXISTS patient_notification_owner_clock AS BIGINT NO CYCLE"
        )
        op.execute(
            "UPDATE patients SET notification_owner_generation=nextval('patient_notification_owner_clock')"
        )
        op.execute("""
        CREATE FUNCTION patient_notification_owner_invalidate() RETURNS trigger AS $$
        BEGIN
          IF TG_OP = 'INSERT' THEN
            NEW.notification_owner_generation := pg_catalog.nextval(pg_catalog.format('%I.%I', TG_TABLE_SCHEMA, 'patient_notification_owner_clock')::pg_catalog.regclass);
          ELSIF NEW.user_id IS DISTINCT FROM OLD.user_id OR NEW.is_deleted IS DISTINCT FROM OLD.is_deleted THEN
            NEW.notification_owner_generation := pg_catalog.nextval(pg_catalog.format('%I.%I', TG_TABLE_SCHEMA, 'patient_notification_owner_clock')::pg_catalog.regclass);
          ELSE
            NEW.notification_owner_generation := OLD.notification_owner_generation;
          END IF;
          RETURN NEW;
        END;
        $$ LANGUAGE plpgsql SET search_path = pg_catalog
        """)
        op.execute(
            "CREATE TRIGGER trg_patient_notification_owner BEFORE INSERT OR UPDATE ON patients FOR EACH ROW EXECUTE FUNCTION patient_notification_owner_invalidate()"
        )
    else:
        # One transactional clock survives patient deletion and ID reuse.
        op.execute(
            "CREATE TABLE IF NOT EXISTS patient_notification_owner_clock (id INTEGER PRIMARY KEY CHECK(id=1), value INTEGER NOT NULL CHECK(typeof(value)='integer' AND value>=0))"
        )
        op.execute(
            "INSERT INTO patient_notification_owner_clock (id,value) SELECT 1, 0 WHERE NOT EXISTS (SELECT 1 FROM patient_notification_owner_clock)"
        )
        op.execute("""
        CREATE TRIGGER IF NOT EXISTS trg_patient_notification_clock_insert BEFORE INSERT ON patient_notification_owner_clock
        WHEN EXISTS (SELECT 1 FROM patient_notification_owner_clock)
        BEGIN SELECT RAISE(ABORT, 'patient owner clock already exists'); END
        """)
        op.execute("""
        CREATE TRIGGER IF NOT EXISTS trg_patient_notification_clock_delete BEFORE DELETE ON patient_notification_owner_clock
        BEGIN SELECT RAISE(ABORT, 'patient owner clock cannot be deleted'); END
        """)
        op.execute("""
        CREATE TRIGGER IF NOT EXISTS trg_patient_notification_clock_update BEFORE UPDATE ON patient_notification_owner_clock
        WHEN NEW.id <> OLD.id OR typeof(NEW.value) <> 'integer' OR OLD.value >= 9223372036854775807 OR NEW.value <> OLD.value+1
        BEGIN SELECT RAISE(ABORT, 'invalid or exhausted patient owner clock'); END
        """)
        # Keep the clock across downgrade: old issued capabilities can outlive
        # a deleted patient, so all legacy rows get fresh global epochs.
        op.execute("""
        CREATE TRIGGER trg_patient_notification_owner_backfill
        AFTER UPDATE OF notification_owner_generation ON patients FOR EACH ROW
        WHEN NEW.notification_owner_generation=0
        BEGIN
          UPDATE patient_notification_owner_clock SET value=value+1 WHERE id=1;
          UPDATE patients SET notification_owner_generation=(SELECT value FROM patient_notification_owner_clock WHERE id=1) WHERE id=NEW.id;
        END
        """)
        op.execute("UPDATE patients SET notification_owner_generation=0")
        op.execute("DROP TRIGGER trg_patient_notification_owner_backfill")
        # AFTER triggers require SQLite INSERT RETURNING consumers to refresh.
        op.execute("""
        CREATE TRIGGER trg_patient_notification_owner_insert AFTER INSERT ON patients FOR EACH ROW
        BEGIN
          UPDATE patient_notification_owner_clock SET value=value+1 WHERE id=1;
          UPDATE patients SET notification_owner_generation=(SELECT value FROM patient_notification_owner_clock WHERE id=1) WHERE id=NEW.id;
        END
        """)
        op.execute("""
        CREATE TRIGGER trg_patient_notification_owner_change AFTER UPDATE OF user_id, is_deleted ON patients FOR EACH ROW
        WHEN OLD.user_id IS NOT NEW.user_id OR OLD.is_deleted IS NOT NEW.is_deleted
        BEGIN
          UPDATE patient_notification_owner_clock SET value=value+1 WHERE id=1;
          UPDATE patients SET notification_owner_generation=(SELECT value FROM patient_notification_owner_clock WHERE id=1) WHERE id=NEW.id;
        END
        """)
        op.execute("""
        CREATE TRIGGER trg_patient_notification_owner_monotonic
        BEFORE UPDATE OF notification_owner_generation ON patients FOR EACH ROW
        WHEN typeof(NEW.notification_owner_generation) <> 'integer' OR NEW.notification_owner_generation < 1
          OR (NEW.notification_owner_generation <> OLD.notification_owner_generation
              AND (NEW.notification_owner_generation <= OLD.notification_owner_generation
                OR NEW.notification_owner_generation <> (SELECT value FROM patient_notification_owner_clock WHERE id=1)))
        BEGIN SELECT RAISE(ABORT, 'invalid patient notification owner generation'); END
        """)


def downgrade() -> None:
    dialect = op.get_context().dialect.name
    if dialect == "postgresql":
        op.execute("SET LOCAL row_security = off")
        op.execute("LOCK TABLE patients IN ACCESS EXCLUSIVE MODE")
        op.execute(
            "DO $$ BEGIN IF EXISTS (SELECT 1 FROM patients) THEN RAISE EXCEPTION 'patient ownership downgrade requires an empty patient table'; END IF; END $$"
        )
        op.execute("DROP TRIGGER trg_patient_notification_owner ON patients")
        op.execute("DROP FUNCTION patient_notification_owner_invalidate()")
    elif dialect == "sqlite":
        op.execute("UPDATE patients SET id=id WHERE 0")
        op.execute(
            "CREATE TEMP TABLE patient_owner_downgrade_guard (value INTEGER NOT NULL CHECK(value=0))"
        )
        op.execute(
            "INSERT INTO patient_owner_downgrade_guard SELECT CASE WHEN EXISTS (SELECT 1 FROM patients) THEN 1 ELSE 0 END"
        )
        op.execute("DROP TABLE patient_owner_downgrade_guard")
        for name in ("insert", "change", "monotonic"):
            op.execute(f"DROP TRIGGER trg_patient_notification_owner_{name}")
    else:
        raise RuntimeError(f"Unsupported subject ownership dialect: {dialect}")
    op.drop_column("patients", "notification_owner_generation")
