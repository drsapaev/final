"""Fence completed-consultation evidence against later visit changes.

Existing completed visits are not backfilled as evidence: historical service
classification at completion cannot be reconstructed reliably. The workflow
records an explicit snapshot in a later transaction, tied to the current
generation. This migration only fences that snapshot; it does not manufacture
one from the present catalog.

PostgreSQL accepts explicitly reviewed owner members and dedicated runtime
sequence users via REPEAT_ALLOCATOR_TRUSTED_OWNER_MEMBERS and
REPEAT_ALLOCATOR_TRUSTED_SEQUENCE_USERS JSON arrays. Only USAGE is granted to
configured sequence users; their role and complete ACL are verified again
before allocating. SQLite assumes the database file and arbitrary SQL writers
are trusted; its assignment trigger is defense in depth, not SQL isolation.
"""

import json
import os
import re

import sqlalchemy as sa

from alembic import op

revision = "0103_visit_repeat_evidence"
down_revision = "0102_visit_confirm_context"
branch_labels = None
depends_on = None

_FLOOR = 1 << 52
_BIGINT_MAX = (1 << 63) - 1
_CLOCK_TABLE = "CREATE TABLE IF NOT EXISTS repeat_evidence_generation_clock (id INTEGER PRIMARY KEY CHECK (id=1), value INTEGER NOT NULL CHECK (typeof(value)='integer' AND value >= 4503599627370496))"
_CLOCK_TRIGGERS = {
    "trg_repeat_clock_no_insert": "CREATE TRIGGER IF NOT EXISTS trg_repeat_clock_no_insert BEFORE INSERT ON repeat_evidence_generation_clock WHEN EXISTS (SELECT 1 FROM repeat_evidence_generation_clock) BEGIN SELECT RAISE(ABORT,'repeat clock already exists'); END",
    "trg_repeat_clock_no_delete": "CREATE TRIGGER IF NOT EXISTS trg_repeat_clock_no_delete BEFORE DELETE ON repeat_evidence_generation_clock BEGIN SELECT RAISE(ABORT,'repeat clock is persistent'); END",
    "trg_repeat_clock_monotonic": "CREATE TRIGGER IF NOT EXISTS trg_repeat_clock_monotonic BEFORE UPDATE ON repeat_evidence_generation_clock WHEN NEW.id != 1 OR OLD.value >= 9223372036854775807 OR NEW.value != OLD.value + 1 BEGIN SELECT RAISE(ABORT,'repeat clock must advance by one'); END",
}


def _sql_shape(sql: str) -> str:
    return re.sub(r"\s+|;", "", sql).lower().replace("ifnotexists", "")


def _sqlite_allocator_preflight(*, require_existing: bool = False) -> None:
    """Refuse unsafe persisted clocks before making any schema changes."""
    db = op.get_bind()
    # Reserve the main database before inspecting a potentially persistent
    # clock. Reject temp objects that could shadow unqualified migration SQL.
    shadow = db.execute(sa.text("""
        SELECT name FROM sqlite_temp_master WHERE name IN
          ('users','doctors','visits','visit_services','repeat_evidence_generation_clock')
    """)).first()
    if shadow is not None:
        raise RuntimeError("repeat allocator temporary shadow is unsafe")
    db.execute(sa.text("UPDATE main.doctors SET id=id WHERE 0"))
    row = db.execute(sa.text("SELECT type,sql FROM main.sqlite_master WHERE name='repeat_evidence_generation_clock'")).first()
    if row is None:
        if require_existing:
            raise RuntimeError("repeat allocator clock is missing")
        return
    if row.type != "table" or not row.sql or _sql_shape(row.sql) != _sql_shape(_CLOCK_TABLE):
        raise RuntimeError("repeat allocator clock schema is unsafe")
    clocks = db.execute(sa.text("SELECT id,value,typeof(value) FROM main.repeat_evidence_generation_clock")).all()
    if len(clocks) != 1 or clocks[0][0] != 1 or clocks[0][2] != "integer" or not _FLOOR <= clocks[0][1] < _BIGINT_MAX - 1:
        raise RuntimeError("repeat allocator clock value is unsafe")
    triggers = db.execute(sa.text("SELECT name,sql FROM main.sqlite_master WHERE type='trigger' AND tbl_name='repeat_evidence_generation_clock'")).all()
    if ({row.name for row in triggers} != set(_CLOCK_TRIGGERS)
            or any(not row.sql or _sql_shape(row.sql) != _sql_shape(_CLOCK_TRIGGERS[row.name]) for row in triggers)):
        raise RuntimeError("repeat allocator clock guards are unsafe")


def _pg_allocator_preflight(*, require_complete: bool = False) -> tuple[str, str, list[str]]:
    """Pin the trusted app schema and validate a retained sequence, if any."""
    db = op.get_bind()
    schema = op.get_context().opts.get("version_table_schema") or db.dialect.default_schema_name
    if (not isinstance(schema, str) or not schema or "\x00" in schema
            or len(schema.encode("utf-8")) > 63 or schema.startswith("pg_") or schema == "information_schema"):
        raise RuntimeError("repeat allocator schema is unsafe")
    owner = db.execute(sa.text("""
        SELECT r.rolname, n.nspowner, CURRENT_USER AS operator,
          (SELECT rolsuper FROM pg_catalog.pg_roles WHERE rolname=CURRENT_USER) AS operator_super,
          pg_catalog.pg_has_role(CURRENT_USER,n.nspowner,'MEMBER') AS trusted_operator,
          NOT EXISTS (SELECT 1 FROM pg_catalog.aclexplode(
            COALESCE(n.nspacl,pg_catalog.acldefault('n',n.nspowner))) a
            WHERE a.privilege_type='CREATE' AND a.grantee<>n.nspowner) AS safe_acl
        FROM pg_catalog.pg_namespace n JOIN pg_catalog.pg_roles r ON r.oid=n.nspowner
        WHERE n.nspname=:schema
    """), {"schema": schema}).mappings().first()
    if owner is None or not owner["trusted_operator"] or not owner["safe_acl"]:
        raise RuntimeError("repeat allocator schema ownership is unsafe")
    try:
        configured = json.loads(os.environ.get("REPEAT_ALLOCATOR_TRUSTED_OWNER_MEMBERS", "[]"))
    except (TypeError, ValueError):
        raise RuntimeError("repeat allocator owner members are unsafe") from None
    if (not isinstance(configured, list) or any(not isinstance(name, str) or not name for name in configured)
            or len(configured) != len(set(configured))
            or any(name.lower() in {"public", "anon", "authenticated"} for name in configured)):
        raise RuntimeError("repeat allocator owner members are unsafe")
    members = db.execute(sa.text("""
        SELECT r.rolname,r.rolbypassrls,r.rolcreaterole,r.rolcreatedb,r.rolreplication
        FROM pg_catalog.pg_roles r
        WHERE r.oid<>:owner AND NOT r.rolsuper AND pg_catalog.pg_has_role(r.oid,:owner,'MEMBER')
    """), {"owner": owner["nspowner"]}).mappings().all()
    allowed = set(configured)
    if not owner["operator_super"] and owner["operator"] != owner["rolname"]:
        # The authenticated operator performing this migration is trusted for
        # its own transaction; all additional members require explicit review.
        allowed.add(owner["operator"])
    if ({row["rolname"] for row in members} != allowed
            or any(any(row[key] for key in ("rolbypassrls", "rolcreaterole", "rolcreatedb", "rolreplication")) for row in members)):
        raise RuntimeError("repeat allocator owner members are unsafe")
    try:
        sequence_users = json.loads(os.environ.get("REPEAT_ALLOCATOR_TRUSTED_SEQUENCE_USERS", "[]"))
    except (TypeError, ValueError):
        raise RuntimeError("repeat allocator sequence users are unsafe") from None
    if (not isinstance(sequence_users, list)
            or any(not isinstance(name, str) or not name for name in sequence_users)
            or len(sequence_users) != len(set(sequence_users))
            or any(name.lower() in {"public", "anon", "authenticated"} for name in sequence_users)):
        raise RuntimeError("repeat allocator sequence users are unsafe")
    for name in sequence_users:
        valid = db.execute(sa.text("""
          SELECT r.rolcanlogin AND NOT r.rolsuper AND NOT r.rolbypassrls
            AND NOT r.rolcreaterole AND NOT r.rolcreatedb AND NOT r.rolreplication
            AND NOT pg_catalog.pg_has_role(r.oid,:owner,'MEMBER')
            AND NOT EXISTS (SELECT 1 FROM pg_catalog.pg_roles x WHERE x.oid<>r.oid
              AND pg_catalog.pg_has_role(r.oid,x.oid,'MEMBER'))
            AND NOT EXISTS (SELECT 1 FROM pg_catalog.pg_roles x WHERE x.oid<>r.oid AND NOT x.rolsuper
              AND pg_catalog.pg_has_role(x.oid,r.oid,'MEMBER'))
          FROM pg_catalog.pg_roles r WHERE r.rolname=:name
        """), {"owner": owner["nspowner"], "name": name}).scalar_one_or_none()
        if valid is not True:
            raise RuntimeError("repeat allocator sequence users are unsafe")
    quote = db.dialect.identifier_preparer.quote_identifier
    qualified = f"{quote(schema)}.{quote('repeat_evidence_generation_seq')}"
    # pg_temp is explicitly last, and the app namespace has no non-owner
    # CREATE grants. Trigger function names and unqualified DDL stay pinned.
    db.execute(sa.text("SELECT pg_catalog.set_config('search_path',:path,true)"),
               {"path": f"{quote(schema)}, pg_catalog, pg_temp"})
    db.execute(sa.text("SET LOCAL row_security=off"))
    entry = db.execute(sa.text("""
        SELECT c.oid,c.relkind,c.relowner,c.relpersistence,
          s.seqstart,s.seqincrement,s.seqmax,s.seqmin,s.seqcache,s.seqcycle,
          NOT EXISTS (SELECT 1 FROM pg_catalog.pg_depend d
            WHERE d.classid='pg_catalog.pg_class'::pg_catalog.regclass AND d.objid=c.oid
              AND d.deptype IN ('a','i')) AS independent
        FROM pg_catalog.pg_class c JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace
        LEFT JOIN pg_catalog.pg_sequence s ON s.seqrelid=c.oid
        WHERE n.nspname=:schema AND c.relname='repeat_evidence_generation_seq'
    """), {"schema": schema}).mappings().first()
    if entry is not None:
        if (entry["relkind"] != "S" or entry["relowner"] != owner["nspowner"]
                or entry["relpersistence"] != "p" or entry["seqstart"] != _FLOOR + 1
                or entry["seqincrement"] != 1 or entry["seqmax"] != _BIGINT_MAX
                or entry["seqmin"] != 1 or entry["seqcache"] != 1 or entry["seqcycle"]
                or not entry["independent"]):
            raise RuntimeError("repeat allocator sequence configuration is unsafe")
        grants = db.execute(sa.text("""
          SELECT a.grantee,a.privilege_type,a.is_grantable,r.rolname
          FROM pg_catalog.pg_class c,
            LATERAL pg_catalog.aclexplode(COALESCE(c.relacl,pg_catalog.acldefault('S',c.relowner))) a
          LEFT JOIN pg_catalog.pg_roles r ON r.oid=a.grantee
          WHERE c.oid=:sequence_oid AND a.grantee<>c.relowner
        """), {"sequence_oid": entry["oid"]}).mappings().all()
        if any(row["grantee"] == 0 or row["rolname"] not in sequence_users
               or row["privilege_type"] != "USAGE" or row["is_grantable"] for row in grants):
            raise RuntimeError("repeat allocator sequence configuration is unsafe")
        if require_complete and {row["rolname"] for row in grants} != set(sequence_users):
            raise RuntimeError("repeat allocator sequence grants are incomplete")
        last = db.execute(sa.text(f"SELECT last_value FROM {qualified}")).scalar_one()
        counts = db.execute(sa.text("SELECT (SELECT count(*) FROM doctors)+(SELECT count(*) FROM visits)")).scalar_one()
        if not _FLOOR < last < _BIGINT_MAX or counts >= _BIGINT_MAX - last:
            raise RuntimeError("repeat allocator sequence value is unsafe")
    elif require_complete:
        raise RuntimeError("repeat allocator sequence is missing")
    return qualified, owner["rolname"], sequence_users


def _upgrade() -> None:
    dialect = op.get_context().dialect.name
    if dialect == "postgresql":
        sequence, schema_owner, sequence_users = _pg_allocator_preflight()
    elif dialect == "sqlite":
        _sqlite_allocator_preflight()
    else:
        raise RuntimeError("Unsupported repeat allocator database")
    op.add_column(
        "doctors", sa.Column("repeat_owner_generation", sa.BigInteger(), nullable=False, server_default="0")
    )
    op.add_column(
        "visits",
        sa.Column("repeat_evidence_generation", sa.BigInteger(), nullable=False, server_default="0"),
    )
    op.add_column("visits", sa.Column("repeat_proof_generation", sa.BigInteger(), nullable=True))
    op.add_column("visits", sa.Column("repeat_proof_consultation", sa.Boolean(), nullable=True))
    op.add_column("visits", sa.Column("repeat_assigned_owner_generation", sa.BigInteger(), nullable=True))
    if dialect == "sqlite":
        # SQLite permits an inline nullable REFERENCES in ADD COLUMN, but
        # Alembic cannot add a foreign-key constraint in a later statement.
        # Rebuilding visits would destroy its existing 0102 triggers.
        op.execute("ALTER TABLE visits ADD COLUMN repeat_proof_doctor_user_id INTEGER REFERENCES users(id) ON DELETE SET NULL")
        op.execute("ALTER TABLE visits ADD COLUMN repeat_assigned_doctor_user_id INTEGER REFERENCES users(id) ON DELETE SET NULL")
    else:
        op.add_column(
            "visits",
            sa.Column(
                "repeat_proof_doctor_user_id", sa.Integer(),
                sa.ForeignKey("users.id", name="fk_visits_repeat_proof_doctor_user", ondelete="SET NULL"),
                nullable=True,
            ),
        )
        op.add_column(
            "visits",
            sa.Column(
                "repeat_assigned_doctor_user_id", sa.Integer(),
                sa.ForeignKey("users.id", name="fk_visits_repeat_assigned_doctor_user", ondelete="SET NULL"),
                nullable=True,
            ),
        )

    if dialect == "postgresql":
        # This allocator survives downgrade. Start above the complete range
        # used by the former random generations, including stale tokens.
        op.execute(f"CREATE SEQUENCE IF NOT EXISTS {sequence} AS bigint START WITH 4503599627370497 NO CYCLE")
        quoted_owner = op.get_bind().dialect.identifier_preparer.quote_identifier(schema_owner)
        op.execute(f"ALTER SEQUENCE {sequence} OWNER TO {quoted_owner}")
        for user in sequence_users:
            quoted_user = op.get_bind().dialect.identifier_preparer.quote_identifier(user)
            op.execute(f"GRANT USAGE ON SEQUENCE {sequence} TO {quoted_user}")
        # CREATE can inherit unsafe default ACLs from the migration operator.
        # Validate again before allocating any generation; never silently
        # revoke an unknown grantee to make a hostile deployment pass.
        _pg_allocator_preflight(require_complete=True)
        db = op.get_bind()
        db.execute(sa.text("UPDATE doctors SET repeat_owner_generation = pg_catalog.nextval(pg_catalog.to_regclass(:sequence))"), {"sequence": sequence})
        db.execute(sa.text("UPDATE visits SET repeat_evidence_generation = pg_catalog.nextval(pg_catalog.to_regclass(:sequence))"), {"sequence": sequence})
        op.execute("""
        CREATE FUNCTION maintain_repeat_doctor_owner_generation() RETURNS trigger AS $$
        BEGIN
          IF TG_OP = 'INSERT' OR NEW.user_id IS DISTINCT FROM OLD.user_id THEN
            NEW.repeat_owner_generation := pg_catalog.nextval(pg_catalog.format('%I.%I', TG_TABLE_SCHEMA, 'repeat_evidence_generation_seq')::pg_catalog.regclass);
          ELSE
            NEW.repeat_owner_generation := OLD.repeat_owner_generation;
          END IF;
          RETURN NEW;
        END;
        $$ LANGUAGE plpgsql SET search_path = pg_catalog
        """)
        op.execute("""
        CREATE TRIGGER trg_repeat_doctor_owner_generation
        BEFORE INSERT OR UPDATE ON doctors
        FOR EACH ROW EXECUTE FUNCTION maintain_repeat_doctor_owner_generation()
        """)
        op.execute("""
        CREATE FUNCTION invalidate_visit_repeat_evidence() RETURNS trigger AS $$
        BEGIN
          IF TG_OP = 'INSERT' THEN
            NEW.repeat_evidence_generation := pg_catalog.nextval(pg_catalog.format('%I.%I', TG_TABLE_SCHEMA, 'repeat_evidence_generation_seq')::pg_catalog.regclass);
            NEW.repeat_proof_generation := NULL;
            NEW.repeat_proof_consultation := NULL;
            NEW.repeat_proof_doctor_user_id := NULL;
            -- Only a newly assigned, preclinical visit gets an owner snapshot.
            -- Historical/in-progress inserts cannot manufacture provenance.
            NEW.repeat_assigned_doctor_user_id := NULL;
            NEW.repeat_assigned_owner_generation := NULL;
            IF NEW.status IN ('open', 'confirmed', 'pending_confirmation', 'confirmation_processing', 'waiting', 'scheduled')
               AND NEW.doctor_id IS NOT NULL THEN
              EXECUTE pg_catalog.format('SELECT user_id, repeat_owner_generation FROM %I.doctors WHERE id = $1', TG_TABLE_SCHEMA)
                INTO NEW.repeat_assigned_doctor_user_id, NEW.repeat_assigned_owner_generation USING NEW.doctor_id;
            END IF;
          ELSIF ROW(NEW.patient_id, NEW.doctor_id, NEW.visit_date)
               IS DISTINCT FROM ROW(OLD.patient_id, OLD.doctor_id, OLD.visit_date)
             OR (OLD.status IN ('completed', 'closed') AND NEW.status NOT IN ('completed', 'closed')) THEN
            NEW.repeat_evidence_generation := pg_catalog.nextval(pg_catalog.format('%I.%I', TG_TABLE_SCHEMA, 'repeat_evidence_generation_seq')::pg_catalog.regclass);
            NEW.repeat_proof_generation := NULL;
            NEW.repeat_proof_consultation := NULL;
            NEW.repeat_proof_doctor_user_id := NULL;
            IF NEW.doctor_id IS DISTINCT FROM OLD.doctor_id THEN
              NEW.repeat_assigned_doctor_user_id := NULL;
              NEW.repeat_assigned_owner_generation := NULL;
              IF NEW.status IN ('open', 'confirmed', 'pending_confirmation', 'confirmation_processing', 'waiting', 'scheduled')
                 AND NEW.doctor_id IS NOT NULL THEN
                EXECUTE pg_catalog.format('SELECT user_id, repeat_owner_generation FROM %I.doctors WHERE id = $1', TG_TABLE_SCHEMA)
                  INTO NEW.repeat_assigned_doctor_user_id, NEW.repeat_assigned_owner_generation USING NEW.doctor_id;
              END IF;
            ELSE
              NEW.repeat_assigned_doctor_user_id := OLD.repeat_assigned_doctor_user_id;
              NEW.repeat_assigned_owner_generation := OLD.repeat_assigned_owner_generation;
            END IF;
          ELSIF pg_catalog.pg_trigger_depth() <= 1 THEN
            -- Direct/bulk generation changes cannot restore stale evidence.
            NEW.repeat_evidence_generation := OLD.repeat_evidence_generation;
            NEW.repeat_assigned_doctor_user_id := OLD.repeat_assigned_doctor_user_id;
            NEW.repeat_assigned_owner_generation := OLD.repeat_assigned_owner_generation;
          END IF;
          RETURN NEW;
        END;
        $$ LANGUAGE plpgsql SET search_path = pg_catalog
        """)
        op.execute("""
        CREATE TRIGGER trg_visit_repeat_evidence
        BEFORE INSERT OR UPDATE ON visits
        FOR EACH ROW EXECUTE FUNCTION invalidate_visit_repeat_evidence()
        """)
        op.execute("""
        CREATE FUNCTION invalidate_repeat_doctor_rebinding() RETURNS trigger AS $$
        BEGIN
          IF NEW.user_id IS NOT DISTINCT FROM OLD.user_id THEN RETURN NEW; END IF;
          -- Doctor row is already locked by the caller; lock in-flight visits
          -- in id order before invalidating their assignment snapshots. A
          -- completed proof remains tied to the original human physician.
          EXECUTE pg_catalog.format('SELECT 1 FROM %I.visits WHERE doctor_id = $1 AND status NOT IN (''completed'', ''closed'') ORDER BY id FOR UPDATE', TG_TABLE_SCHEMA) USING NEW.id;
          EXECUTE pg_catalog.format('UPDATE %I.visits SET
            repeat_evidence_generation = pg_catalog.nextval(pg_catalog.format(''%%I.%%I'', $2, ''repeat_evidence_generation_seq'')::pg_catalog.regclass),
            repeat_proof_generation = NULL, repeat_proof_consultation = NULL,
            repeat_proof_doctor_user_id = NULL, repeat_assigned_doctor_user_id = NULL,
            repeat_assigned_owner_generation = NULL
          WHERE doctor_id = $1 AND status NOT IN (''completed'', ''closed'')', TG_TABLE_SCHEMA) USING NEW.id, TG_TABLE_SCHEMA;
          RETURN NEW;
        END;
        $$ LANGUAGE plpgsql SET search_path = pg_catalog
        """)
        op.execute("""
        CREATE TRIGGER trg_repeat_doctor_rebinding
        AFTER UPDATE OF user_id ON doctors
        FOR EACH ROW EXECUTE FUNCTION invalidate_repeat_doctor_rebinding()
        """)
        op.execute("""
        CREATE FUNCTION invalidate_visit_service_repeat_evidence() RETURNS trigger AS $$
        DECLARE old_visit integer; new_visit integer;
        BEGIN
          IF TG_OP = 'UPDATE' AND ROW(NEW.visit_id, NEW.service_id, NEW.qty)
             IS NOT DISTINCT FROM ROW(OLD.visit_id, OLD.service_id, OLD.qty) THEN
            RETURN NEW;
          END IF;
          IF TG_OP <> 'INSERT' THEN old_visit := OLD.visit_id; END IF;
          IF TG_OP <> 'DELETE' THEN new_visit := NEW.visit_id; END IF;
          EXECUTE pg_catalog.format('SELECT 1 FROM %I.visits WHERE id IN ($1, $2) ORDER BY id FOR UPDATE', TG_TABLE_SCHEMA) USING old_visit, new_visit;
          EXECUTE pg_catalog.format('UPDATE %I.visits SET
            repeat_evidence_generation = pg_catalog.nextval(pg_catalog.format(''%%I.%%I'', $3, ''repeat_evidence_generation_seq'')::pg_catalog.regclass),
            repeat_proof_generation = NULL,
            repeat_proof_consultation = NULL,
            repeat_proof_doctor_user_id = NULL
          WHERE id IN ($1, $2)', TG_TABLE_SCHEMA) USING old_visit, new_visit, TG_TABLE_SCHEMA;
          IF TG_OP = 'DELETE' THEN RETURN OLD; ELSE RETURN NEW; END IF;
        END;
        $$ LANGUAGE plpgsql SET search_path = pg_catalog
        """)
        op.execute("""
        CREATE TRIGGER trg_visit_service_repeat_evidence
        AFTER INSERT OR UPDATE OR DELETE ON visit_services
        FOR EACH ROW EXECUTE FUNCTION invalidate_visit_service_repeat_evidence()
        """)
    elif dialect == "sqlite":
        # The singleton is intentionally retained during downgrade; resetting
        # it could make a previously issued review capability valid again.
        op.execute(_CLOCK_TABLE)
        op.execute("INSERT INTO repeat_evidence_generation_clock (id,value) SELECT 1,4503599627370496 WHERE NOT EXISTS (SELECT 1 FROM repeat_evidence_generation_clock)")
        for statement in _CLOCK_TRIGGERS.values():
            op.execute(statement)
        op.execute("UPDATE repeat_evidence_generation_clock SET value=value+1")
        op.execute("UPDATE doctors SET repeat_owner_generation = (SELECT value FROM repeat_evidence_generation_clock)")
        op.execute("UPDATE repeat_evidence_generation_clock SET value=value+1")
        op.execute("UPDATE visits SET repeat_evidence_generation = (SELECT value FROM repeat_evidence_generation_clock)")
        for table, column in (("doctors", "repeat_owner_generation"), ("visits", "repeat_evidence_generation")):
            op.execute(f"""
            CREATE TRIGGER trg_{table}_repeat_generation_guard
            BEFORE UPDATE OF {column} ON {table} FOR EACH ROW
            WHEN NEW.{column} IS NOT OLD.{column} AND
              (NEW.{column} <= OLD.{column} OR NEW.{column} != (SELECT value FROM repeat_evidence_generation_clock WHERE id=1))
            BEGIN SELECT RAISE(ABORT,'invalid repeat generation'); END
            """)
        # SQLite has no trigger-depth/NEW assignment primitive. Protect
        # ordinary direct field updates while allowing the nested, freshly
        # generated assignment written by the insert/doctor-change triggers.
        # The database file and arbitrary SQL remain a trusted boundary.
        op.execute("""
        CREATE TRIGGER trg_visit_repeat_assignment_guard
        BEFORE UPDATE OF repeat_assigned_doctor_user_id, repeat_assigned_owner_generation ON visits
        FOR EACH ROW
        WHEN (NEW.repeat_assigned_doctor_user_id IS NOT OLD.repeat_assigned_doctor_user_id
              OR NEW.repeat_assigned_owner_generation IS NOT OLD.repeat_assigned_owner_generation)
          AND (NEW.repeat_assigned_doctor_user_id IS NOT NULL OR NEW.repeat_assigned_owner_generation IS NOT NULL)
          -- ON DELETE SET NULL may clear the actor before the doctor rebind.
          AND NOT (NEW.repeat_assigned_doctor_user_id IS NULL
                   AND NEW.repeat_assigned_owner_generation IS OLD.repeat_assigned_owner_generation)
          AND (NEW.repeat_evidence_generation IS OLD.repeat_evidence_generation
               OR NEW.repeat_evidence_generation IS NOT (SELECT value FROM repeat_evidence_generation_clock WHERE id=1)
               OR NEW.status IS NULL OR NEW.status NOT IN ('open', 'confirmed', 'pending_confirmation', 'confirmation_processing', 'waiting', 'scheduled')
               OR NEW.repeat_assigned_doctor_user_id IS NOT (SELECT user_id FROM doctors WHERE id=NEW.doctor_id)
               OR NEW.repeat_assigned_owner_generation IS NOT (SELECT repeat_owner_generation FROM doctors WHERE id=NEW.doctor_id))
        BEGIN SELECT RAISE(ABORT, 'invalid repeat assignment provenance'); END
        """)
        op.execute("""
        CREATE TRIGGER trg_repeat_doctor_owner_insert
        AFTER INSERT ON doctors FOR EACH ROW
        BEGIN
          UPDATE repeat_evidence_generation_clock SET value=value+1;
          UPDATE doctors SET repeat_owner_generation = (SELECT value FROM repeat_evidence_generation_clock) WHERE id=NEW.id;
        END
        """)
        op.execute("""
        CREATE TRIGGER trg_repeat_doctor_owner_change
        AFTER UPDATE OF user_id ON doctors FOR EACH ROW
        WHEN OLD.user_id IS NOT NEW.user_id
        BEGIN
          UPDATE repeat_evidence_generation_clock SET value=value+1;
          UPDATE doctors SET repeat_owner_generation = (SELECT value FROM repeat_evidence_generation_clock) WHERE id=NEW.id;
        END
        """)
        op.execute("""
        CREATE TRIGGER trg_repeat_doctor_owner_generation
        AFTER UPDATE OF repeat_owner_generation ON doctors FOR EACH ROW
        WHEN OLD.repeat_owner_generation IS NOT NEW.repeat_owner_generation
        BEGIN
          UPDATE repeat_evidence_generation_clock SET value=value+1;
          UPDATE visits SET repeat_evidence_generation = (SELECT value FROM repeat_evidence_generation_clock),
            repeat_proof_generation = NULL, repeat_proof_consultation = NULL,
            repeat_proof_doctor_user_id = NULL, repeat_assigned_doctor_user_id = NULL,
            repeat_assigned_owner_generation = NULL
          WHERE doctor_id=NEW.id AND status NOT IN ('completed', 'closed');
        END
        """)
        op.execute("""
        CREATE TRIGGER trg_visit_repeat_evidence_insert
        AFTER INSERT ON visits FOR EACH ROW
        BEGIN
          UPDATE repeat_evidence_generation_clock SET value=value+1;
          UPDATE visits SET repeat_evidence_generation = (SELECT value FROM repeat_evidence_generation_clock),
            repeat_proof_generation = NULL, repeat_proof_consultation = NULL,
            repeat_proof_doctor_user_id = NULL,
            repeat_assigned_doctor_user_id = CASE
              WHEN NEW.status IN ('open', 'confirmed', 'pending_confirmation', 'confirmation_processing', 'waiting', 'scheduled')
              THEN (SELECT user_id FROM doctors WHERE id=NEW.doctor_id) ELSE NULL END,
            repeat_assigned_owner_generation = CASE
              WHEN NEW.status IN ('open', 'confirmed', 'pending_confirmation', 'confirmation_processing', 'waiting', 'scheduled')
              THEN (SELECT repeat_owner_generation FROM doctors WHERE id=NEW.doctor_id) ELSE NULL END
          WHERE id = NEW.id;
        END
        """)
        op.execute("""
        CREATE TRIGGER trg_visit_repeat_evidence_context
        AFTER UPDATE OF patient_id, doctor_id, visit_date, status ON visits FOR EACH ROW
        WHEN OLD.patient_id IS NOT NEW.patient_id OR OLD.doctor_id IS NOT NEW.doctor_id
          OR OLD.visit_date IS NOT NEW.visit_date
          OR (OLD.status IN ('completed', 'closed') AND NEW.status NOT IN ('completed', 'closed'))
        BEGIN
          UPDATE repeat_evidence_generation_clock SET value=value+1;
          UPDATE visits SET repeat_evidence_generation = (SELECT value FROM repeat_evidence_generation_clock),
            repeat_proof_generation = NULL, repeat_proof_consultation = NULL,
            repeat_proof_doctor_user_id = NULL,
            repeat_assigned_doctor_user_id = CASE
              WHEN OLD.doctor_id IS NOT NEW.doctor_id THEN CASE
                WHEN NEW.status IN ('open', 'confirmed', 'pending_confirmation', 'confirmation_processing', 'waiting', 'scheduled')
                THEN (SELECT user_id FROM doctors WHERE id=NEW.doctor_id) ELSE NULL END
              ELSE OLD.repeat_assigned_doctor_user_id END,
            repeat_assigned_owner_generation = CASE
              WHEN OLD.doctor_id IS NOT NEW.doctor_id THEN CASE
                WHEN NEW.status IN ('open', 'confirmed', 'pending_confirmation', 'confirmation_processing', 'waiting', 'scheduled')
                THEN (SELECT repeat_owner_generation FROM doctors WHERE id=NEW.doctor_id) ELSE NULL END
              ELSE OLD.repeat_assigned_owner_generation END
          WHERE id = NEW.id;
        END
        """)
        # SQLite cannot distinguish a user-supplied generation update from a
        # nested trigger UPDATE. Clearing the proof in both cases prevents a
        # restored generation from reactivating the old snapshot.
        op.execute("""
        CREATE TRIGGER trg_visit_repeat_evidence_generation
        AFTER UPDATE OF repeat_evidence_generation ON visits FOR EACH ROW
        WHEN OLD.repeat_evidence_generation IS NOT NEW.repeat_evidence_generation
        BEGIN
          UPDATE visits SET repeat_proof_generation = NULL, repeat_proof_consultation = NULL,
            repeat_proof_doctor_user_id = NULL WHERE id = NEW.id;
        END
        """)
        for event, ids, when in (
            ("insert", "NEW.visit_id", "1"),
            ("delete", "OLD.visit_id", "1"),
            ("update", "OLD.visit_id, NEW.visit_id", "OLD.visit_id IS NOT NEW.visit_id OR OLD.service_id IS NOT NEW.service_id OR OLD.qty IS NOT NEW.qty"),
        ):
            op.execute(f"""
            CREATE TRIGGER trg_visit_service_repeat_evidence_{event}
            AFTER {event.upper()} ON visit_services FOR EACH ROW WHEN {when}
            BEGIN
              UPDATE repeat_evidence_generation_clock SET value=value+1;
              UPDATE visits SET repeat_evidence_generation = (SELECT value FROM repeat_evidence_generation_clock),
                repeat_proof_generation = NULL, repeat_proof_consultation = NULL,
                repeat_proof_doctor_user_id = NULL WHERE id IN ({ids});
            END
            """)


def _downgrade() -> None:
    dialect = op.get_context().dialect.name
    if dialect == "postgresql":
        # Apply the same trusted namespace, owner, ACL and retained-allocator
        # checks before any unqualified relation lookup or destructive DDL.
        _pg_allocator_preflight(require_complete=True)
        # A downgrade would erase these clinical facts and could silently
        # reinterpret later work. Lock first, then fail before changing DDL.
        op.execute("SET LOCAL row_security = off")
        op.execute("LOCK TABLE doctors, visits IN ACCESS EXCLUSIVE MODE")
        op.execute("""
        DO $$ BEGIN
          IF EXISTS (SELECT 1 FROM visits WHERE repeat_proof_generation IS NOT NULL
              OR repeat_proof_consultation IS NOT NULL OR repeat_proof_doctor_user_id IS NOT NULL
              OR repeat_assigned_owner_generation IS NOT NULL OR repeat_assigned_doctor_user_id IS NOT NULL) THEN
            RAISE EXCEPTION 'repeat evidence or assignments prevent downgrade';
          END IF;
        END $$
        """)
        op.execute("DROP TRIGGER trg_visit_service_repeat_evidence ON visit_services")
        op.execute("DROP FUNCTION invalidate_visit_service_repeat_evidence()")
        op.execute("DROP TRIGGER trg_repeat_doctor_rebinding ON doctors")
        op.execute("DROP FUNCTION invalidate_repeat_doctor_rebinding()")
        op.execute("DROP TRIGGER trg_repeat_doctor_owner_generation ON doctors")
        op.execute("DROP FUNCTION maintain_repeat_doctor_owner_generation()")
        op.execute("DROP TRIGGER trg_visit_repeat_evidence ON visits")
        op.execute("DROP FUNCTION invalidate_visit_repeat_evidence()")
        op.drop_constraint("fk_visits_repeat_assigned_doctor_user", "visits", type_="foreignkey")
        op.drop_constraint("fk_visits_repeat_proof_doctor_user", "visits", type_="foreignkey")
    elif dialect == "sqlite":
        _sqlite_allocator_preflight(require_existing=True)
        # Reserve SQLite's writer before inspecting evidence. The persistent
        # clock and its guards remain installed after this revision is removed.
        op.execute("UPDATE repeat_evidence_generation_clock SET value=value+1")
        op.execute("CREATE TEMP TABLE repeat_downgrade_guard (ok INTEGER CHECK(ok=1))")
        op.execute("""
        INSERT INTO repeat_downgrade_guard (ok)
        SELECT CASE WHEN EXISTS (SELECT 1 FROM visits WHERE repeat_proof_generation IS NOT NULL
          OR repeat_proof_consultation IS NOT NULL OR repeat_proof_doctor_user_id IS NOT NULL
          OR repeat_assigned_owner_generation IS NOT NULL OR repeat_assigned_doctor_user_id IS NOT NULL)
          THEN 0 ELSE 1 END
        """)
        op.execute("DROP TABLE repeat_downgrade_guard")
        for event in ("insert", "update", "delete"):
            op.execute(f"DROP TRIGGER trg_visit_service_repeat_evidence_{event}")
        op.execute("DROP TRIGGER trg_visit_repeat_evidence_generation")
        op.execute("DROP TRIGGER trg_visit_repeat_evidence_context")
        op.execute("DROP TRIGGER trg_visit_repeat_evidence_insert")
        op.execute("DROP TRIGGER trg_visit_repeat_assignment_guard")
        op.execute("DROP TRIGGER trg_repeat_doctor_owner_generation")
        op.execute("DROP TRIGGER trg_repeat_doctor_owner_change")
        op.execute("DROP TRIGGER trg_repeat_doctor_owner_insert")
        op.execute("DROP TRIGGER trg_visits_repeat_generation_guard")
        op.execute("DROP TRIGGER trg_doctors_repeat_generation_guard")
    op.drop_column("visits", "repeat_assigned_doctor_user_id")
    op.drop_column("visits", "repeat_assigned_owner_generation")
    op.drop_column("visits", "repeat_proof_doctor_user_id")
    op.drop_column("visits", "repeat_proof_consultation")
    op.drop_column("visits", "repeat_proof_generation")
    op.drop_column("visits", "repeat_evidence_generation")
    op.drop_column("doctors", "repeat_owner_generation")


def _run_with_restored_pg_settings(operation) -> None:
    """Keep the allocator's trusted settings inside this revision only.

    A PostgreSQL statement error aborts the transaction; in that case the
    required rollback also restores the settings and the original exception
    must remain visible to Alembic.
    """
    if op.get_context().dialect.name != "postgresql":
        operation()
        return
    db = op.get_bind()
    original = db.execute(sa.text("""
        SELECT pg_catalog.current_setting('search_path'),
               pg_catalog.current_setting('row_security')
    """)).one()

    def restore() -> None:
        db.execute(sa.text("""
            SELECT pg_catalog.set_config('search_path', :path, true),
                   pg_catalog.set_config('row_security', :rls, true)
        """), {"path": original[0], "rls": original[1]})

    try:
        operation()
    except BaseException:
        try:
            restore()
        except sa.exc.SQLAlchemyError:
            # A failed or closed transaction must be rolled back by Alembic.
            pass
        raise
    restore()


def upgrade() -> None:
    if op.get_context().as_sql:
        raise RuntimeError("Repeat evidence migration requires a live database preflight")
    _run_with_restored_pg_settings(_upgrade)


def downgrade() -> None:
    if op.get_context().as_sql:
        raise RuntimeError("Repeat evidence migration requires a live database preflight")
    _run_with_restored_pg_settings(_downgrade)
