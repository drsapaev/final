"""Fence birth-date reviews against subsequent patient date changes.

No legacy date is presumed exact. Precision is only a provenance claim;
eligibility needs an independently authorized review of the current
generation. The schema does not implement that review or protect its API.
"""

import sqlalchemy as sa

from alembic import op

revision = "0110_patient_birth_precision"
down_revision = "0109_provider_reconciliation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    dialect = op.get_context().dialect.name
    if dialect not in {"postgresql", "sqlite"}:
        raise RuntimeError(f"Unsupported birth evidence dialect: {dialect}")
    op.add_column("patients", sa.Column("birth_date_generation", sa.BigInteger(), nullable=False, server_default="0"))
    op.add_column("patients", sa.Column("birth_date_precision", sa.String(24), nullable=False, server_default="unknown"))
    if dialect == "postgresql":
        op.create_check_constraint("ck_patient_birth_date_precision", "patients", "birth_date_precision IN ('unknown','year_only','reported_exact')")
        # Keep this allocator across downgrades: a previously issued, still
        # live review must never match a reused patient id after re-upgrade.
        op.execute("CREATE SEQUENCE IF NOT EXISTS patient_birth_generation_seq AS BIGINT MINVALUE 1 NO CYCLE")
        op.execute("UPDATE patients SET birth_date_generation = nextval('patient_birth_generation_seq'::regclass)")
        op.execute("""
        CREATE FUNCTION patient_birth_date_invalidate() RETURNS trigger AS $$
        BEGIN
          IF TG_OP = 'INSERT' THEN
            NEW.birth_date_generation := pg_catalog.nextval(pg_catalog.format('%I.%I', TG_TABLE_SCHEMA, 'patient_birth_generation_seq')::regclass);
            NEW.birth_date_precision := 'unknown';
          ELSIF NEW.birth_date IS DISTINCT FROM OLD.birth_date THEN
            NEW.birth_date_generation := pg_catalog.nextval(pg_catalog.format('%I.%I', TG_TABLE_SCHEMA, 'patient_birth_generation_seq')::regclass);
            NEW.birth_date_precision := 'unknown';
          ELSIF NEW.birth_date_precision IS DISTINCT FROM OLD.birth_date_precision OR NEW.user_id IS DISTINCT FROM OLD.user_id THEN
            NEW.birth_date_generation := pg_catalog.nextval(pg_catalog.format('%I.%I', TG_TABLE_SCHEMA, 'patient_birth_generation_seq')::regclass);
          ELSE
            NEW.birth_date_generation := OLD.birth_date_generation;
          END IF;
          RETURN NEW;
        END;
        $$ LANGUAGE plpgsql SET search_path = pg_catalog
        """)
        op.execute("CREATE TRIGGER trg_patient_birth_date_invalidate BEFORE INSERT OR UPDATE ON patients FOR EACH ROW EXECUTE FUNCTION patient_birth_date_invalidate()")
    else:
        # Triggers preserve pre-existing 0102 patient/visit triggers without a
        # table rebuild. A RETURNING caller must refresh after an AFTER trigger.
        op.execute("CREATE TABLE IF NOT EXISTS patient_birth_generation_clock (id INTEGER PRIMARY KEY CHECK(id=1), value INTEGER NOT NULL CHECK(typeof(value)='integer' AND value>=1))")
        op.execute("CREATE TRIGGER IF NOT EXISTS trg_birth_clock_no_delete BEFORE DELETE ON patient_birth_generation_clock BEGIN SELECT RAISE(ABORT, 'birth generation clock is persistent'); END")
        op.execute("CREATE TRIGGER IF NOT EXISTS trg_birth_clock_no_insert BEFORE INSERT ON patient_birth_generation_clock WHEN EXISTS (SELECT 1 FROM patient_birth_generation_clock) BEGIN SELECT RAISE(ABORT, 'birth generation clock is persistent'); END")
        op.execute("CREATE TRIGGER IF NOT EXISTS trg_birth_clock_monotonic BEFORE UPDATE ON patient_birth_generation_clock WHEN NEW.id IS NOT OLD.id OR typeof(NEW.value)<>'integer' OR OLD.value>=9223372036854775807 OR NEW.value<>OLD.value+1 BEGIN SELECT RAISE(ABORT, 'invalid birth generation clock'); END")
        op.execute("INSERT INTO patient_birth_generation_clock (id,value) SELECT 1,1 WHERE NOT EXISTS (SELECT 1 FROM patient_birth_generation_clock)")
        op.execute("UPDATE patient_birth_generation_clock SET value=value+1 WHERE id=1")
        op.execute("UPDATE patients SET birth_date_generation=(SELECT value FROM patient_birth_generation_clock WHERE id=1)")
        for event in ("insert", "update"):
            trigger_event = "INSERT" if event == "insert" else "UPDATE OF birth_date, birth_date_precision, user_id"
            condition = "" if event == "insert" else "WHEN OLD.birth_date IS NOT NEW.birth_date OR OLD.birth_date_precision IS NOT NEW.birth_date_precision OR OLD.user_id IS NOT NEW.user_id"
            next_precision = "'unknown'" if event == "insert" else "CASE WHEN OLD.birth_date IS NOT NEW.birth_date THEN 'unknown' ELSE NEW.birth_date_precision END"
            op.execute(f"""
            CREATE TRIGGER trg_patient_birth_date_{event}
            AFTER {trigger_event} ON patients FOR EACH ROW {condition}
            BEGIN
              UPDATE patient_birth_generation_clock SET value=value+1 WHERE id=1;
              UPDATE patients SET birth_date_generation=(SELECT value FROM patient_birth_generation_clock WHERE id=1),
                  birth_date_precision={next_precision} WHERE id=NEW.id;
            END
            """)
        # SQLite otherwise silently promotes a signed integer overflow to REAL.
        op.execute("""
        CREATE TRIGGER trg_patient_birth_generation_overflow
        BEFORE UPDATE OF birth_date, birth_date_precision, user_id ON patients FOR EACH ROW
        WHEN (OLD.birth_date IS NOT NEW.birth_date OR OLD.birth_date_precision IS NOT NEW.birth_date_precision OR OLD.user_id IS NOT NEW.user_id)
          AND (SELECT value FROM patient_birth_generation_clock WHERE id=1) >= 9223372036854775807
        BEGIN SELECT RAISE(ABORT, 'birth date generation exhausted'); END
        """)
        op.execute("""
        CREATE TRIGGER trg_patient_birth_generation_monotonic
        BEFORE UPDATE OF birth_date_generation ON patients FOR EACH ROW
        WHEN typeof(NEW.birth_date_generation) <> 'integer' OR NEW.birth_date_generation < 1
          OR (NEW.birth_date_generation <> OLD.birth_date_generation
              AND (NEW.birth_date_generation <= OLD.birth_date_generation
                   OR NEW.birth_date_generation <> (SELECT value FROM patient_birth_generation_clock WHERE id=1)))
        BEGIN SELECT RAISE(ABORT, 'invalid birth date generation'); END
        """)
        for event in ("insert", "update"):
            op.execute(f"""
            CREATE TRIGGER trg_patient_birth_precision_{event}
            BEFORE {event.upper()} ON patients FOR EACH ROW
            WHEN NEW.birth_date_precision NOT IN ('unknown','year_only','reported_exact')
            BEGIN SELECT RAISE(ABORT, 'invalid birth date precision'); END
            """)

    op.create_table(
        "patient_birth_date_evidence",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("patient_id", sa.Integer(), sa.ForeignKey("patients.id", ondelete="SET NULL")),
        sa.Column("patient_id_snapshot", sa.Integer(), nullable=False),
        sa.Column("birth_date_generation", sa.BigInteger(), nullable=False),
        sa.Column("actor_user_id_snapshot", sa.Integer(), nullable=False),
        sa.Column("actor_role", sa.String(64), nullable=False),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("patient_id", "birth_date_generation", name="uq_patient_birth_evidence_generation"),
        sa.CheckConstraint("patient_id_snapshot > 0 AND birth_date_generation > 0 AND actor_user_id_snapshot > 0", name="ck_patient_birth_evidence_identity"),
        sa.CheckConstraint("patient_id IS NULL OR patient_id = patient_id_snapshot", name="ck_patient_birth_evidence_patient"),
    )
    if dialect == "postgresql":
        op.execute("ALTER TABLE patient_birth_date_evidence ENABLE ROW LEVEL SECURITY")
        op.execute("""
        CREATE FUNCTION protect_patient_birth_evidence() RETURNS trigger AS $$
        BEGIN
          IF TG_OP = 'DELETE' THEN
            RAISE EXCEPTION 'birth evidence is append-only';
          END IF;
          IF OLD.patient_id IS NOT NULL AND NEW.patient_id IS NULL AND
             ROW(NEW.id, NEW.patient_id_snapshot, NEW.birth_date_generation,
                 NEW.actor_user_id_snapshot, NEW.actor_role, NEW.verified_at)
             IS NOT DISTINCT FROM
             ROW(OLD.id, OLD.patient_id_snapshot, OLD.birth_date_generation,
                 OLD.actor_user_id_snapshot, OLD.actor_role, OLD.verified_at) THEN
            RETURN NEW;
          END IF;
          RAISE EXCEPTION 'birth evidence is append-only';
        END;
        $$ LANGUAGE plpgsql SET search_path = pg_catalog
        """)
        op.execute("CREATE TRIGGER trg_patient_birth_evidence_protect BEFORE UPDATE OR DELETE ON patient_birth_date_evidence FOR EACH ROW EXECUTE FUNCTION protect_patient_birth_evidence()")
    else:
        op.execute("""
        CREATE TRIGGER trg_patient_birth_evidence_delete BEFORE DELETE ON patient_birth_date_evidence
        BEGIN SELECT RAISE(ABORT, 'birth evidence is append-only'); END
        """)
        op.execute("""
        CREATE TRIGGER trg_patient_birth_evidence_update BEFORE UPDATE ON patient_birth_date_evidence
        WHEN NOT (OLD.patient_id IS NOT NULL AND NEW.patient_id IS NULL
          AND NEW.id IS OLD.id AND NEW.patient_id_snapshot IS OLD.patient_id_snapshot
          AND NEW.birth_date_generation IS OLD.birth_date_generation
          AND NEW.actor_user_id_snapshot IS OLD.actor_user_id_snapshot
          AND NEW.actor_role IS OLD.actor_role AND NEW.verified_at IS OLD.verified_at)
        BEGIN SELECT RAISE(ABORT, 'birth evidence is append-only'); END
        """)


def downgrade() -> None:
    dialect = op.get_context().dialect.name
    unsafe = "EXISTS (SELECT 1 FROM patient_birth_date_evidence) OR EXISTS (SELECT 1 FROM patients WHERE birth_date_precision <> 'unknown')"
    if dialect == "postgresql":
        op.execute("SET LOCAL row_security = off")
        op.execute("LOCK TABLE patients, patient_birth_date_evidence IN ACCESS EXCLUSIVE MODE")
        op.execute(f"DO $$ BEGIN IF {unsafe} THEN RAISE EXCEPTION 'birth precision downgrade would discard evidence'; END IF; END $$")
        op.execute("DROP TRIGGER trg_patient_birth_evidence_protect ON patient_birth_date_evidence")
        op.execute("DROP FUNCTION protect_patient_birth_evidence()")
        op.execute("DROP TRIGGER trg_patient_birth_date_invalidate ON patients")
        op.execute("DROP FUNCTION patient_birth_date_invalidate()")
        op.drop_constraint("ck_patient_birth_date_precision", "patients", type_="check")
    elif dialect == "sqlite":
        op.execute("UPDATE patients SET id=id WHERE 0")
        op.execute("CREATE TEMP TABLE birth_precision_downgrade_guard (value INTEGER NOT NULL CHECK(value=0))")
        op.execute(f"INSERT INTO birth_precision_downgrade_guard SELECT CASE WHEN {unsafe} THEN 1 ELSE 0 END")
        op.execute("DROP TABLE birth_precision_downgrade_guard")
        op.execute("DROP TRIGGER trg_patient_birth_evidence_delete")
        op.execute("DROP TRIGGER trg_patient_birth_evidence_update")
        op.execute("DROP TRIGGER trg_patient_birth_generation_overflow")
        op.execute("DROP TRIGGER trg_patient_birth_generation_monotonic")
        for event in ("insert", "update"):
            op.execute(f"DROP TRIGGER trg_patient_birth_date_{event}")
            op.execute(f"DROP TRIGGER trg_patient_birth_precision_{event}")
    else:
        raise RuntimeError(f"Unsupported birth evidence dialect: {dialect}")
    op.drop_table("patient_birth_date_evidence")
    op.drop_column("patients", "birth_date_precision")
    op.drop_column("patients", "birth_date_generation")
