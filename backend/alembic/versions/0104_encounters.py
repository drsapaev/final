"""Add durable, patient-consistent registration encounter identities.

Historical visits do not prove common registration, even if they share an
invoice or date. Each receives its own ``legacy_unresolved`` identity. A visit
whose patient is missing remains unlinked and cannot become eligible merely
because this migration ran. Generation is an initial identifier only; it is
not yet a fence for encounter membership, pricing, or entitlement changes.

Mixed deployments must stop old writers or keep encounter-dependent benefits
disabled until all writers are upgraded and missing links are reconciled.
Downgrade is refused once non-legacy, grouped, orphaned or changed identities
exist. Later financial-ledger migrations must protect their own downgrade.
An allowed downgrade discards the technical generation and encounter creation
timestamp of singleton legacy_unresolved rows. A later upgrade creates fresh
generations; any version-bound capability must be revoked rather than reused.
"""

import sqlalchemy as sa

from alembic import op

revision = "0104_encounters"
down_revision = "0103_visit_repeat_evidence"
branch_labels = None
depends_on = None


def upgrade() -> None:
    dialect = op.get_context().dialect.name
    random_default = (
        "(floor(random() * 4503599627370496)::bigint + 1)"
        if dialect == "postgresql"
        else "((random() & 4503599627370495) + 1)"
    )
    op.create_table(
        "encounters",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("patient_id", sa.Integer(), sa.ForeignKey("patients.id", ondelete="SET NULL"), nullable=True),
        sa.Column("provenance", sa.String(32), nullable=False),
        sa.Column("legacy_visit_id", sa.Integer(), nullable=True),
        sa.Column("generation", sa.BigInteger(), nullable=False, server_default=sa.text(random_default)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("id", "patient_id", name="uq_encounters_id_patient"),
        sa.UniqueConstraint("legacy_visit_id", name="uq_encounters_legacy_visit"),
        sa.CheckConstraint("length(trim(provenance)) > 0", name="ck_encounters_provenance_nonempty"),
        *([sa.CheckConstraint("patient_id IS NOT NULL OR provenance = 'legacy_unresolved'", name="ck_encounters_unresolved_patient")] if dialect == "postgresql" else []),
        sa.CheckConstraint("generation > 0", name="ck_encounters_generation_positive"),
    )
    op.create_index("ix_encounters_patient_id", "encounters", ["patient_id"])
    if dialect == "postgresql":
        # The new public table follows the repository's deny-by-default RLS
        # convention; the application database role must have its own access.
        op.execute("ALTER TABLE encounters ENABLE ROW LEVEL SECURITY")
        op.add_column("visits", sa.Column("encounter_id", sa.Integer(), nullable=True))
        op.create_foreign_key(
            "fk_visits_encounter", "visits", "encounters", ["encounter_id"], ["id"],
            ondelete="RESTRICT",
        )
        op.add_column("appointments", sa.Column("encounter_id", sa.Integer(), nullable=True))
        op.add_column("appointments", sa.Column("source_visit_id", sa.Integer(), nullable=True))
        op.add_column("queue_entries", sa.Column("encounter_id", sa.Integer(), nullable=True))
        op.create_foreign_key("fk_appointments_encounter", "appointments", "encounters", ["encounter_id"], ["id"], ondelete="SET NULL")
        op.create_foreign_key("fk_appointments_source_visit", "appointments", "visits", ["source_visit_id"], ["id"], ondelete="SET NULL")
        op.create_foreign_key("fk_queue_encounter", "queue_entries", "encounters", ["encounter_id"], ["id"], ondelete="SET NULL")
    elif dialect == "sqlite":
        # An inline FK is possible without a table rebuild, preserving the
        # 0102/0103 triggers. Composite consistency is enforced below.
        op.execute("ALTER TABLE visits ADD COLUMN encounter_id INTEGER REFERENCES encounters(id) ON DELETE RESTRICT")
        op.execute("ALTER TABLE appointments ADD COLUMN encounter_id INTEGER REFERENCES encounters(id) ON DELETE SET NULL")
        op.execute("ALTER TABLE appointments ADD COLUMN source_visit_id INTEGER REFERENCES visits(id) ON DELETE SET NULL")
        op.execute("ALTER TABLE queue_entries ADD COLUMN encounter_id INTEGER REFERENCES encounters(id) ON DELETE SET NULL")
    else:
        raise RuntimeError(f"Unsupported encounter migration dialect: {dialect}")
    op.create_index("ix_visits_encounter_id", "visits", ["encounter_id"])
    op.create_index("ix_appointments_encounter_id", "appointments", ["encounter_id"])
    op.create_index("ix_appointments_source_visit_id", "appointments", ["source_visit_id"])
    op.create_index("ix_queue_entries_encounter_id", "queue_entries", ["encounter_id"])

    op.execute("""
        INSERT INTO encounters (patient_id, provenance, legacy_visit_id, created_at)
        SELECT CASE WHEN p.id IS NULL THEN NULL ELSE v.patient_id END,
               'legacy_unresolved', v.id, COALESCE(v.created_at, CURRENT_TIMESTAMP)
        FROM visits v LEFT JOIN patients p ON p.id = v.patient_id
    """)
    op.execute("""
        UPDATE visits SET encounter_id = (
          SELECT e.id FROM encounters e
          WHERE e.legacy_visit_id = visits.id AND e.patient_id = visits.patient_id
        )
    """)

    if dialect == "postgresql":
        # DEFERRABLE allows an authorized group transfer to update parent and
        # child patient identities in either order in one transaction.
        # MATCH SIMPLE composite FKs do not check rows with NULL patient ids;
        # an unresolved legacy row must remain unlinked rather than exploiting
        # that SQL NULL behavior on a drifted, nullable schema.
        op.create_check_constraint(
            "ck_visits_encounter_patient_present", "visits", "encounter_id IS NULL OR patient_id IS NOT NULL"
        )
        op.create_foreign_key(
            "fk_visits_encounter_patient", "visits", "encounters",
            ["encounter_id", "patient_id"], ["id", "patient_id"],
            deferrable=True, initially="DEFERRED",
        )
        # These composite keys establish one patient/group identity even when
        # an appointment or queue row names both its visit and its encounter.
        # Old queue rows with no encounter remain explicitly unresolved.
        op.create_unique_constraint("uq_visits_id_patient", "visits", ["id", "patient_id"])
        op.create_unique_constraint("uq_visits_id_patient_encounter", "visits", ["id", "patient_id", "encounter_id"])
        op.create_check_constraint("ck_queue_encounter_patient_present", "queue_entries", "encounter_id IS NULL OR patient_id IS NOT NULL")
        op.create_foreign_key("fk_appointments_encounter_patient", "appointments", "encounters", ["encounter_id", "patient_id"], ["id", "patient_id"], deferrable=True, initially="DEFERRED")
        op.create_foreign_key("fk_appointments_source_patient", "appointments", "visits", ["source_visit_id", "patient_id"], ["id", "patient_id"], deferrable=True, initially="DEFERRED")
        op.create_foreign_key("fk_appointments_source_encounter", "appointments", "visits", ["source_visit_id", "patient_id", "encounter_id"], ["id", "patient_id", "encounter_id"], deferrable=True, initially="DEFERRED")
        op.create_foreign_key("fk_queue_encounter_patient", "queue_entries", "encounters", ["encounter_id", "patient_id"], ["id", "patient_id"], deferrable=True, initially="DEFERRED")
        op.create_foreign_key("fk_queue_visit_encounter", "queue_entries", "visits", ["visit_id", "patient_id", "encounter_id"], ["id", "patient_id", "encounter_id"], deferrable=True, initially="DEFERRED")
        op.execute("""
        CREATE FUNCTION normalize_encounter_anonymization() RETURNS trigger AS $$
        BEGIN
          IF NEW.patient_id IS NULL AND OLD.patient_id IS NOT NULL THEN
            NEW.provenance := 'legacy_unresolved';
          END IF;
          RETURN NEW;
        END;
        $$ LANGUAGE plpgsql SET search_path = pg_catalog
        """)
        op.execute("""
        CREATE TRIGGER trg_encounter_anonymization
        BEFORE UPDATE OF patient_id ON encounters
        FOR EACH ROW EXECUTE FUNCTION normalize_encounter_anonymization()
        """)
        op.execute("""
        CREATE FUNCTION detach_queue_from_anonymous_encounter() RETURNS trigger AS $$
        BEGIN
          IF NEW.patient_id IS NULL AND OLD.patient_id IS NOT NULL THEN
            EXECUTE pg_catalog.format('UPDATE %I.queue_entries SET encounter_id=NULL WHERE encounter_id=$1', TG_TABLE_SCHEMA) USING NEW.id;
          END IF;
          RETURN NEW;
        END;
        $$ LANGUAGE plpgsql SET search_path = pg_catalog
        """)
        op.execute("""
        CREATE TRIGGER trg_encounter_anonymous_queue_detach
        AFTER UPDATE OF patient_id ON encounters
        FOR EACH ROW EXECUTE FUNCTION detach_queue_from_anonymous_encounter()
        """)
        op.execute("""
        CREATE FUNCTION detach_queue_encounter_without_identity() RETURNS trigger AS $$
        BEGIN
          IF (OLD.patient_id IS NOT NULL AND NEW.patient_id IS NULL)
             OR (OLD.visit_id IS NOT NULL AND NEW.visit_id IS NULL) THEN
            NEW.encounter_id := NULL;
          END IF;
          RETURN NEW;
        END;
        $$ LANGUAGE plpgsql SET search_path = pg_catalog
        """)
        op.execute("""
        CREATE TRIGGER trg_queue_encounter_identity_detach
        BEFORE UPDATE OF patient_id, visit_id ON queue_entries
        FOR EACH ROW EXECUTE FUNCTION detach_queue_encounter_without_identity()
        """)
        op.execute("""
        CREATE FUNCTION detach_appointment_encounter_without_source() RETURNS trigger AS $$
        BEGIN
          IF OLD.source_visit_id IS NOT NULL AND NEW.source_visit_id IS NULL THEN
            NEW.encounter_id := NULL;
          END IF;
          RETURN NEW;
        END;
        $$ LANGUAGE plpgsql SET search_path = pg_catalog
        """)
        op.execute("""
        CREATE TRIGGER trg_appointment_encounter_source_detach
        BEFORE UPDATE OF source_visit_id ON appointments
        FOR EACH ROW EXECUTE FUNCTION detach_appointment_encounter_without_source()
        """)
    else:
        # SQLite cannot ALTER in a composite FK without rebuilding visits and
        # losing existing triggers. These checks are immediate; transfers must
        # detach, change both patient ids and reattach in ONE transaction.
        for event in ("insert", "update"):
            op.execute(f"""
            CREATE TRIGGER trg_visit_encounter_patient_{event}
            BEFORE {event.upper()} ON visits FOR EACH ROW
            WHEN NEW.encounter_id IS NOT NULL AND NOT EXISTS (
              SELECT 1 FROM encounters e WHERE e.id=NEW.encounter_id
                AND e.patient_id IS NOT NULL AND e.patient_id=NEW.patient_id
            )
            BEGIN SELECT RAISE(ABORT, 'encounter patient mismatch'); END
            """)
        op.execute("""
        CREATE TRIGGER trg_encounter_patient_consistency_update
        BEFORE UPDATE OF id, patient_id ON encounters FOR EACH ROW
        WHEN EXISTS (
          SELECT 1 FROM visits v WHERE v.encounter_id=OLD.id AND
            (NEW.id IS NOT OLD.id OR NEW.patient_id IS NULL OR v.patient_id IS NULL
             OR v.patient_id != NEW.patient_id)
        ) OR EXISTS (
          SELECT 1 FROM appointments a WHERE a.encounter_id=OLD.id AND
            (NEW.id IS NOT OLD.id OR NEW.patient_id IS NULL OR a.patient_id IS NULL
             OR a.patient_id != NEW.patient_id)
        ) OR EXISTS (
          SELECT 1 FROM queue_entries q WHERE q.encounter_id=OLD.id AND NEW.patient_id IS NOT NULL AND
            (NEW.id IS NOT OLD.id OR q.patient_id IS NULL OR q.patient_id != NEW.patient_id)
        )
        BEGIN SELECT RAISE(ABORT, 'encounter patient mismatch'); END
        """)
        op.execute("""
        CREATE TRIGGER trg_encounter_referenced_delete
        BEFORE DELETE ON encounters FOR EACH ROW
        WHEN EXISTS (SELECT 1 FROM visits v WHERE v.encounter_id=OLD.id)
        BEGIN SELECT RAISE(ABORT, 'encounter is referenced'); END
        """)
        op.execute("""
        CREATE TRIGGER trg_encounter_unresolved_insert
        BEFORE INSERT ON encounters FOR EACH ROW
        WHEN NEW.patient_id IS NULL AND NEW.provenance <> 'legacy_unresolved'
        BEGIN SELECT RAISE(ABORT, 'anonymous encounter must be unresolved'); END
        """)
        op.execute("""
        CREATE TRIGGER trg_encounter_unresolved_provenance
        BEFORE UPDATE OF provenance ON encounters FOR EACH ROW
        WHEN OLD.patient_id IS NULL AND NEW.patient_id IS NULL AND NEW.provenance <> 'legacy_unresolved'
        BEGIN SELECT RAISE(ABORT, 'anonymous encounter must be unresolved'); END
        """)
        op.execute("""
        CREATE TRIGGER trg_encounter_anonymization
        AFTER UPDATE OF patient_id ON encounters FOR EACH ROW
        WHEN OLD.patient_id IS NOT NULL AND NEW.patient_id IS NULL
        BEGIN
          UPDATE encounters SET provenance='legacy_unresolved' WHERE id=NEW.id;
          UPDATE queue_entries SET encounter_id=NULL WHERE encounter_id=NEW.id;
        END
        """)
        for event in ("insert", "update"):
            event_sql = "INSERT" if event == "insert" else "UPDATE OF patient_id, encounter_id, source_visit_id"
            op.execute(f"""
            CREATE TRIGGER trg_appointment_encounter_identity_{event}
            BEFORE {event_sql} ON appointments FOR EACH ROW
            WHEN (NEW.encounter_id IS NOT NULL AND NOT EXISTS (
                    SELECT 1 FROM encounters e WHERE e.id=NEW.encounter_id
                      AND e.patient_id IS NOT NULL AND e.patient_id=NEW.patient_id))
              OR (NEW.source_visit_id IS NOT NULL AND NOT EXISTS (
                    SELECT 1 FROM visits v WHERE v.id=NEW.source_visit_id AND v.patient_id=NEW.patient_id))
              OR (NEW.source_visit_id IS NOT NULL AND NEW.encounter_id IS NOT NULL AND NOT EXISTS (
                    SELECT 1 FROM visits v WHERE v.id=NEW.source_visit_id AND v.patient_id=NEW.patient_id
                      AND v.encounter_id=NEW.encounter_id))
            BEGIN SELECT RAISE(ABORT, 'appointment encounter identity mismatch'); END
            """)
        op.execute("""
        CREATE TRIGGER trg_appointment_encounter_source_detach
        AFTER UPDATE OF source_visit_id ON appointments FOR EACH ROW
        WHEN OLD.source_visit_id IS NOT NULL AND NEW.source_visit_id IS NULL AND NEW.encounter_id IS NOT NULL
        BEGIN UPDATE appointments SET encounter_id=NULL WHERE id=NEW.id; END
        """)
        op.execute("""
        CREATE TRIGGER trg_queue_encounter_identity_insert
        BEFORE INSERT ON queue_entries FOR EACH ROW
        WHEN NEW.encounter_id IS NOT NULL AND (
          NEW.patient_id IS NULL OR NOT EXISTS (
            SELECT 1 FROM encounters e WHERE e.id=NEW.encounter_id AND e.patient_id=NEW.patient_id)
          OR (NEW.visit_id IS NOT NULL AND NOT EXISTS (
            SELECT 1 FROM visits v WHERE v.id=NEW.visit_id AND v.patient_id=NEW.patient_id
              AND v.encounter_id=NEW.encounter_id))
        )
        BEGIN SELECT RAISE(ABORT, 'queue encounter identity mismatch'); END
        """)
        op.execute("""
        CREATE TRIGGER trg_queue_encounter_identity_update
        BEFORE UPDATE OF patient_id, visit_id, encounter_id ON queue_entries FOR EACH ROW
        WHEN NEW.encounter_id IS NOT NULL AND NOT (OLD.patient_id IS NOT NULL AND NEW.patient_id IS NULL)
          AND (NEW.patient_id IS NULL OR NOT EXISTS (
            SELECT 1 FROM encounters e WHERE e.id=NEW.encounter_id AND e.patient_id=NEW.patient_id)
            OR (NEW.visit_id IS NOT NULL AND NOT EXISTS (
              SELECT 1 FROM visits v WHERE v.id=NEW.visit_id AND v.patient_id=NEW.patient_id
                AND v.encounter_id=NEW.encounter_id)))
        BEGIN SELECT RAISE(ABORT, 'queue encounter identity mismatch'); END
        """)
        op.execute("""
        CREATE TRIGGER trg_queue_encounter_identity_detach
        AFTER UPDATE OF patient_id, visit_id ON queue_entries FOR EACH ROW
        WHEN NEW.encounter_id IS NOT NULL AND (
          (OLD.patient_id IS NOT NULL AND NEW.patient_id IS NULL)
          OR (OLD.visit_id IS NOT NULL AND NEW.visit_id IS NULL))
        BEGIN UPDATE queue_entries SET encounter_id=NULL WHERE id=NEW.id; END
        """)
        op.execute("""
        CREATE TRIGGER trg_visit_referenced_encounter_identity
        BEFORE UPDATE OF id, patient_id, encounter_id ON visits FOR EACH ROW
        WHEN EXISTS (
          SELECT 1 FROM appointments a WHERE a.source_visit_id=OLD.id AND
            (NEW.id IS NOT OLD.id OR NEW.patient_id IS NOT a.patient_id
             OR (a.encounter_id IS NOT NULL AND NEW.encounter_id IS NOT a.encounter_id))
        ) OR EXISTS (
          SELECT 1 FROM queue_entries q WHERE q.visit_id=OLD.id AND q.encounter_id IS NOT NULL AND
            (NEW.id IS NOT OLD.id OR NEW.patient_id IS NOT q.patient_id
             OR NEW.encounter_id IS NOT q.encounter_id)
        )
        BEGIN SELECT RAISE(ABORT, 'visit encounter identity mismatch'); END
        """)


_UNSAFE_DOWNGRADE = """
    EXISTS (
      SELECT 1 FROM encounters e LEFT JOIN visits v ON v.id=e.legacy_visit_id
      WHERE e.provenance <> 'legacy_unresolved' OR e.legacy_visit_id IS NULL OR v.id IS NULL
        OR (e.patient_id IS NULL AND (
              v.encounter_id IS NOT NULL OR EXISTS (SELECT 1 FROM patients p WHERE p.id=v.patient_id)
            ))
        OR (e.patient_id IS NOT NULL AND (
              v.patient_id IS NULL OR v.patient_id <> e.patient_id
              OR v.encounter_id IS NULL OR v.encounter_id <> e.id
            ))
        OR EXISTS (SELECT 1 FROM visits other WHERE other.encounter_id=e.id AND other.id<>e.legacy_visit_id)
    ) OR EXISTS (
      SELECT 1 FROM visits v WHERE NOT EXISTS (
        SELECT 1 FROM encounters e WHERE e.legacy_visit_id=v.id AND e.provenance='legacy_unresolved'
      )
    ) OR EXISTS (
      SELECT 1 FROM appointments a WHERE a.encounter_id IS NOT NULL OR a.source_visit_id IS NOT NULL
    ) OR EXISTS (
      SELECT 1 FROM queue_entries q WHERE q.encounter_id IS NOT NULL
    )
"""


def downgrade() -> None:
    dialect = op.get_context().dialect.name
    if dialect == "postgresql":
        # Prevent a concurrent writer from creating information after the
        # safety check but before DDL drops the encounter table.
        op.execute("LOCK TABLE visits, appointments, queue_entries, encounters IN ACCESS EXCLUSIVE MODE")
        op.execute(f"""
        DO $$ BEGIN
          IF {_UNSAFE_DOWNGRADE} OR EXISTS (
            SELECT 1 FROM pg_constraint c
            WHERE c.contype='f' AND c.confrelid='encounters'::regclass
              AND c.conrelid NOT IN ('visits'::regclass, 'appointments'::regclass, 'queue_entries'::regclass)
          ) THEN
            RAISE EXCEPTION 'encounter downgrade would destroy grouping history';
          END IF;
        END $$
        """)
        op.execute("DROP TRIGGER trg_appointment_encounter_source_detach ON appointments")
        op.execute("DROP FUNCTION detach_appointment_encounter_without_source()")
        op.execute("DROP TRIGGER trg_queue_encounter_identity_detach ON queue_entries")
        op.execute("DROP FUNCTION detach_queue_encounter_without_identity()")
        op.execute("DROP TRIGGER trg_encounter_anonymous_queue_detach ON encounters")
        op.execute("DROP FUNCTION detach_queue_from_anonymous_encounter()")
        op.execute("DROP TRIGGER trg_encounter_anonymization ON encounters")
        op.execute("DROP FUNCTION normalize_encounter_anonymization()")
        for constraint in ("fk_appointments_source_encounter", "fk_appointments_source_patient", "fk_appointments_encounter_patient", "fk_appointments_source_visit", "fk_appointments_encounter"):
            op.drop_constraint(constraint, "appointments", type_="foreignkey")
        for constraint in ("fk_queue_visit_encounter", "fk_queue_encounter_patient", "fk_queue_encounter"):
            op.drop_constraint(constraint, "queue_entries", type_="foreignkey")
        op.drop_constraint("ck_queue_encounter_patient_present", "queue_entries", type_="check")
        op.drop_constraint("fk_visits_encounter_patient", "visits", type_="foreignkey")
        op.drop_constraint("ck_visits_encounter_patient_present", "visits", type_="check")
        op.drop_constraint("fk_visits_encounter", "visits", type_="foreignkey")
        op.drop_constraint("uq_visits_id_patient_encounter", "visits", type_="unique")
        op.drop_constraint("uq_visits_id_patient", "visits", type_="unique")
    elif dialect == "sqlite":
        # An empty write obtains SQLite's writer lock before checking. CHECK
        # also renders in offline SQL; no changes occur before it succeeds.
        op.execute("UPDATE encounters SET generation=generation WHERE 0")
        op.execute("CREATE TEMP TABLE encounter_downgrade_guard_0104 (value INTEGER NOT NULL CHECK (value=0))")
        op.execute(f"""
        INSERT INTO encounter_downgrade_guard_0104 (value)
        SELECT CASE WHEN {_UNSAFE_DOWNGRADE} OR EXISTS (
          SELECT 1 FROM sqlite_master m JOIN pragma_foreign_key_list(m.name) f
          WHERE m.type='table' AND m.name NOT IN ('visits','appointments','queue_entries') AND f."table"='encounters'
        ) THEN 1 ELSE 0 END
        """)
        op.execute("DROP TABLE encounter_downgrade_guard_0104")
        op.execute("DROP TRIGGER trg_visit_referenced_encounter_identity")
        op.execute("DROP TRIGGER trg_queue_encounter_identity_detach")
        op.execute("DROP TRIGGER trg_queue_encounter_identity_update")
        op.execute("DROP TRIGGER trg_queue_encounter_identity_insert")
        op.execute("DROP TRIGGER trg_appointment_encounter_source_detach")
        for event in ("insert", "update"):
            op.execute(f"DROP TRIGGER trg_appointment_encounter_identity_{event}")
        op.execute("DROP TRIGGER trg_encounter_anonymization")
        op.execute("DROP TRIGGER trg_encounter_unresolved_provenance")
        op.execute("DROP TRIGGER trg_encounter_unresolved_insert")
        op.execute("DROP TRIGGER trg_encounter_referenced_delete")
        op.execute("DROP TRIGGER trg_encounter_patient_consistency_update")
        for event in ("insert", "update"):
            op.execute(f"DROP TRIGGER trg_visit_encounter_patient_{event}")
    else:
        raise RuntimeError(f"Unsupported encounter migration dialect: {dialect}")
    op.drop_index("ix_queue_entries_encounter_id", table_name="queue_entries")
    op.drop_index("ix_appointments_source_visit_id", table_name="appointments")
    op.drop_index("ix_appointments_encounter_id", table_name="appointments")
    op.drop_column("queue_entries", "encounter_id")
    op.drop_column("appointments", "source_visit_id")
    op.drop_column("appointments", "encounter_id")
    op.drop_index("ix_visits_encounter_id", table_name="visits")
    op.drop_column("visits", "encounter_id")
    op.drop_index("ix_encounters_patient_id", table_name="encounters")
    op.drop_table("encounters")
