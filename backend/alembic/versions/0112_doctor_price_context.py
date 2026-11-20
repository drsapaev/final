"""Fence doctor price context and record exact command/result identity.

Schema only: issuers/approvers must enforce authorization, commit before
reply, verify all financial state and serialize monetary changes. Historical
overrides are deliberately unbound. SQLite uses a transactional clock, so an
uncommitted generation must never be published. Direct DBA changes to schema,
clock/sequence ownership or user fields outside the revocation protocol are
outside this guarantee.
"""
import hashlib
import json

import sqlalchemy as sa

from alembic import context as alembic_context
from alembic import op

revision = "0112_doctor_price_context"
down_revision = "0111_provider_attempts"
branch_labels = None
depends_on = None

_TARGETS = (
    ("visits", "price_context_generation", ("patient_id", "doctor_id", "visit_date", "visit_time", "department", "department_id", "encounter_id", "discount_mode")),
    ("visit_services", "price_line_generation", ("visit_id", "service_id", "code", "name", "duration_minutes_snapshot", "qty", "price", "currency")),
    ("doctors", "price_owner_generation", ("user_id", "active", "specialty", "department_id")),
)
_SNAPSHOTS = ("price_context_generation", "price_line_generation", "price_owner_generation", "doctor_user_auth_epoch")
_REQUESTER_FIELDS = ("requester_type", "requester_user_id", "requester_user_id_snapshot", "requester_auth_epoch")
_REQUESTER_BINDING = (
    "(requester_type IS NULL AND requester_user_id IS NULL AND requester_user_id_snapshot IS NULL AND requester_auth_epoch IS NULL) OR "
    "(requester_type IS NOT NULL AND requester_type IN ('doctor','admin') AND requester_user_id_snapshot IS NOT NULL AND requester_user_id_snapshot > 0 AND "
    "requester_auth_epoch IS NOT NULL AND requester_auth_epoch >= 0 AND (requester_user_id IS NULL OR requester_user_id = requester_user_id_snapshot))"
)
_DOCTOR_BINDING = (
    "(doctor_id_snapshot IS NULL AND doctor_id IS NULL AND price_owner_generation IS NULL "
    "AND doctor_owner_user_id_snapshot IS NULL AND doctor_owner_user_id IS NULL AND doctor_user_auth_epoch IS NULL) OR "
    "(doctor_id_snapshot IS NOT NULL AND doctor_id_snapshot > 0 AND price_owner_generation IS NOT NULL AND price_owner_generation > 0 "
    "AND (doctor_id IS NULL OR doctor_id = doctor_id_snapshot) AND ("
    "(doctor_owner_user_id_snapshot IS NULL AND doctor_owner_user_id IS NULL AND doctor_user_auth_epoch IS NULL) OR "
    "(doctor_owner_user_id_snapshot IS NOT NULL AND doctor_owner_user_id_snapshot > 0 AND "
    "(doctor_owner_user_id IS NULL OR doctor_owner_user_id = doctor_owner_user_id_snapshot) AND "
    "doctor_user_auth_epoch IS NOT NULL AND doctor_user_auth_epoch >= 0)))"
)
_CONFIRMATION_BINDING = (
    "(issued_confirmation_epoch IS NULL AND issued_confirmation_digest IS NULL AND issued_confirmation_digest_version IS NULL AND issued_confirmation_expires_at IS NULL) OR "
    "(operation = 'schedule_next' AND issued_confirmation_epoch IS NOT NULL AND issued_confirmation_epoch > 0 AND issued_confirmation_digest IS NOT NULL AND length(issued_confirmation_digest) = 64 AND issued_confirmation_digest_version IS NOT NULL AND issued_confirmation_digest_version > 0 AND issued_confirmation_expires_at IS NOT NULL)"
)
_SQLITE_INTEGERS = (
    "typeof(actor_user_id_snapshot)='integer' AND typeof(actor_user_auth_epoch)='integer' AND typeof(patient_id_snapshot)='integer' AND typeof(visit_id_snapshot)='integer' AND typeof(fingerprint_version)='integer' AND "
    "(doctor_id_snapshot IS NULL OR typeof(doctor_id_snapshot)='integer') AND (price_owner_generation IS NULL OR typeof(price_owner_generation)='integer') AND "
    "(doctor_owner_user_id_snapshot IS NULL OR typeof(doctor_owner_user_id_snapshot)='integer') AND (doctor_user_auth_epoch IS NULL OR typeof(doctor_user_auth_epoch)='integer') AND "
    "(issued_confirmation_epoch IS NULL OR typeof(issued_confirmation_epoch)='integer') AND (issued_confirmation_digest_version IS NULL OR typeof(issued_confirmation_digest_version)='integer')"
)



def _trusted_owner_members():
    """Read only an explicit migration-operator allowlist; never infer it."""
    value = op.get_context().opts.get("trusted_capability_owner_members")
    if value is None:
        try:
            arguments = alembic_context.get_x_argument()
            matches = [argument.partition("=")[2] for argument in arguments
                       if argument.partition("=")[0] == "capability_owner_members"]
            if len(matches) > 1:
                raise RuntimeError("Invalid capability owner-member allowlist")
            value = matches[0] if matches else None
        except (AttributeError, NameError):
            value = None
    if value is None:
        return ()
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except (ValueError, TypeError):
            raise RuntimeError("Invalid capability owner-member allowlist") from None
    if not isinstance(value, (list, tuple)):
        raise RuntimeError("Invalid capability owner-member allowlist")
    names = []
    for name in value:
        if not isinstance(name, str) or not name or "\0" in name or name.lower() in {"public", "anon", "authenticated"}:
            raise RuntimeError("Invalid capability owner-member allowlist")
        try:
            if len(name.encode("utf-8")) > 63:
                raise RuntimeError("Invalid capability owner-member allowlist")
        except UnicodeError:
            raise RuntimeError("Invalid capability owner-member allowlist") from None
        names.append(name)
    if len(set(names)) != len(names):
        raise RuntimeError("Invalid capability owner-member allowlist")
    return tuple(names)


def _pin_trusted_schema():
    """Pin DDL and definer dependencies to a trusted migration schema.

    The engine's initialized default or explicit Alembic version schema is
    the anchor; never trust a later caller-controlled search_path. No non-owner
    role (including PUBLIC) may be granted CREATE in that schema. Offline SQL
    requires an explicit version schema and emits the same runtime guard.
    """
    context = op.get_context()
    schema = context.version_table_schema
    if not schema and not context.as_sql:
        schema = op.get_bind().dialect.default_schema_name
    if not isinstance(schema, str) or not schema:
        raise RuntimeError("doctor price migration requires an explicit trusted schema")
    if schema == "information_schema" or schema.startswith("pg_"):
        raise RuntimeError("doctor price migration requires a non-system schema")
    # Identifiers are quoted separately and string literals use SQL-standard
    # quote doubling. Enforce that interpretation even on legacy sessions
    # configured with standard_conforming_strings=off.
    op.execute("SELECT pg_catalog.set_config('doctor_price.saved_standard_strings', pg_catalog.current_setting('standard_conforming_strings'), true)")
    op.execute("SET LOCAL standard_conforming_strings = on")
    quote = context.dialect.identifier_preparer.quote_identifier
    schema_q = quote(schema)
    schema_literal = schema.replace("'", "''")
    members = _trusted_owner_members()
    member_literals = [name.replace("'", "''") for name in members]
    member_array = "ARRAY[" + ",".join("'" + name + "'" for name in member_literals) + "]::text[]"
    guard_tag = "$doctor_price_guard$"
    while guard_tag in schema_literal or any(guard_tag in name for name in member_literals):
        guard_tag = guard_tag[:-1] + "_x$"
    op.execute(f"""DO {guard_tag} BEGIN
      IF NOT EXISTS (
        SELECT 1 FROM pg_catalog.pg_namespace n
        WHERE n.nspname = '{schema_literal}'
          AND pg_catalog.pg_has_role(current_user, n.nspowner, 'USAGE')
          AND NOT EXISTS (
            SELECT 1 FROM pg_catalog.aclexplode(
              COALESCE(n.nspacl, pg_catalog.acldefault('n', n.nspowner))
            ) a WHERE a.privilege_type = 'CREATE' AND a.grantee <> n.nspowner
          )
          AND NOT EXISTS (
            SELECT 1 FROM pg_catalog.pg_roles r
            WHERE r.oid<>n.nspowner AND NOT r.rolsuper
              AND pg_catalog.pg_has_role(r.oid,n.nspowner,'MEMBER')
              AND (NOT EXISTS (SELECT 1 FROM pg_catalog.unnest({member_array}) expected(name)
                    WHERE pg_catalog.convert_to(r.rolname::text,'UTF8')=pg_catalog.convert_to(expected.name,'UTF8'))
                   OR r.rolbypassrls
                   OR r.rolcreaterole OR r.rolcreatedb OR r.rolreplication)
          )
          AND NOT EXISTS (
            SELECT 1 FROM pg_catalog.unnest({member_array}) expected(name)
            WHERE NOT EXISTS (SELECT 1 FROM pg_catalog.pg_roles r
              WHERE pg_catalog.convert_to(r.rolname::text,'UTF8')=pg_catalog.convert_to(expected.name,'UTF8')
                AND r.oid<>n.nspowner AND NOT r.rolsuper
                AND pg_catalog.pg_has_role(r.oid,n.nspowner,'MEMBER'))
          )
      ) THEN RAISE EXCEPTION 'doctor price migration schema is not trusted'; END IF;
    END {guard_tag}""")
    op.execute("SELECT pg_catalog.set_config('doctor_price.saved_search_path', pg_catalog.current_setting('search_path'), true)")
    op.execute(f"SET LOCAL search_path TO {schema_q}, pg_catalog, pg_temp")
    return schema


def _restore_search_path():
    op.execute("SELECT pg_catalog.set_config('search_path', pg_catalog.current_setting('doctor_price.saved_search_path'), true)")
    op.execute("SELECT pg_catalog.set_config('standard_conforming_strings', pg_catalog.current_setting('doctor_price.saved_standard_strings'), true)")


def _capability_schema_name(schema):
    # Frozen migration-local v1; keep in parity with app.db.capability_namespace.
    if not isinstance(schema, str) or not schema or "\0" in schema:
        raise ValueError("Invalid application schema")
    raw = schema.encode("utf-8")
    if len(raw) > 63:
        raise ValueError("Application schema exceeds PostgreSQL identifier limit")
    return "clinic_internal_" + hashlib.sha256(b"clinic-capability-schema-v1\0" + raw).hexdigest()[:32]


def _bootstrap_capability_namespace(schema):
    """Create a new owner-only namespace; never adopt an existing one."""
    private = _capability_schema_name(schema)
    quote = op.get_context().dialect.identifier_preparer.quote_identifier
    qp = quote(private)
    app_literal = schema.replace("'", "''")
    private_literal = private.replace("'", "''")
    tag = "$capability_bootstrap$"
    while tag in app_literal:
        tag = tag[:-1] + "_x$"
    # CREATE SCHEMA (without IF NOT EXISTS) deliberately rejects collisions
    # and pre-created objects, even if their names look plausible.
    op.execute(f"""DO {tag}
    DECLARE trusted_owner name;
    BEGIN
      SELECT r.rolname INTO STRICT trusted_owner FROM pg_catalog.pg_namespace n
        JOIN pg_catalog.pg_roles r ON r.oid=n.nspowner WHERE n.nspname='{app_literal}';
      EXECUTE pg_catalog.format('CREATE SCHEMA %I AUTHORIZATION %I', '{private_literal}', trusted_owner);
    END {tag}""")
    op.execute(f"REVOKE ALL ON SCHEMA {qp} FROM PUBLIC")
    op.execute(f"""CREATE TABLE {qp}.clinic_capability_namespace (
      id SMALLINT PRIMARY KEY CHECK (id=1),
      format_version SMALLINT NOT NULL CHECK (format_version=1),
      application_schema TEXT NOT NULL CHECK (pg_catalog.octet_length(application_schema) BETWEEN 1 AND 63),
      private_schema TEXT NOT NULL CHECK (pg_catalog.octet_length(private_schema) BETWEEN 1 AND 63)
    )""")
    op.execute(f"""CREATE TABLE {qp}.clinic_capability_role_profile (
      role_name TEXT PRIMARY KEY CHECK (pg_catalog.octet_length(role_name) BETWEEN 1 AND 63),
      role_kind TEXT NOT NULL CHECK (role_kind IN ('backend', 'capability_owner'))
    )""")
    op.execute(f"INSERT INTO {qp}.clinic_capability_namespace (id,format_version,application_schema,private_schema) VALUES (1,1,'{app_literal}','{private_literal}')")
    for table in ("clinic_capability_namespace", "clinic_capability_role_profile"):
        op.execute(f"REVOKE ALL ON TABLE {qp}.{table} FROM PUBLIC")
        op.execute(f"""DO {tag} DECLARE trusted_owner name; BEGIN
          SELECT r.rolname INTO STRICT trusted_owner FROM pg_catalog.pg_namespace n
            JOIN pg_catalog.pg_roles r ON r.oid=n.nspowner WHERE n.nspname='{app_literal}';
          EXECUTE pg_catalog.format('ALTER TABLE %I.{table} OWNER TO %I', '{private_literal}', trusted_owner);
        END {tag}""")
    return private


def _assert_initial_capability_acl(schema):
    """Reject inherited default grants rather than adopting broader access."""
    private = _capability_schema_name(schema)
    app_literal, private_literal = schema.replace("'", "''"), private.replace("'", "''")
    tag = "$doctor_price_initial_acl$"
    while tag in app_literal:
        tag = tag[:-1] + "_x$"
    op.execute(f"""DO {tag} DECLARE app_owner oid; private_oid oid; BEGIN
      SELECT nspowner INTO STRICT app_owner FROM pg_catalog.pg_namespace WHERE nspname='{app_literal}';
      SELECT oid INTO STRICT private_oid FROM pg_catalog.pg_namespace
        WHERE nspname='{private_literal}' AND nspowner=app_owner;
      IF EXISTS (SELECT 1 FROM pg_catalog.pg_namespace n,
          LATERAL pg_catalog.aclexplode(COALESCE(n.nspacl,pg_catalog.acldefault('n',n.nspowner))) a
          WHERE n.oid=private_oid AND a.grantee<>app_owner)
        OR EXISTS (SELECT 1 FROM pg_catalog.pg_class c,
          LATERAL pg_catalog.aclexplode(COALESCE(c.relacl,pg_catalog.acldefault('r',c.relowner))) a
          WHERE c.relnamespace=private_oid AND c.relkind='r'
            AND (c.relowner<>app_owner OR a.grantee<>app_owner))
        OR EXISTS (SELECT 1 FROM pg_catalog.pg_attribute a JOIN pg_catalog.pg_class c ON c.oid=a.attrelid
          WHERE c.relnamespace=private_oid AND a.attacl IS NOT NULL)
        OR EXISTS (SELECT 1 FROM pg_catalog.pg_proc p,
          LATERAL pg_catalog.aclexplode(COALESCE(p.proacl,pg_catalog.acldefault('f',p.proowner))) a
          WHERE p.pronamespace=private_oid AND (p.proowner<>app_owner OR a.grantee<>app_owner))
        OR EXISTS (SELECT 1 FROM pg_catalog.pg_class c JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace,
          LATERAL pg_catalog.aclexplode(COALESCE(c.relacl,pg_catalog.acldefault('S',c.relowner))) a
          WHERE n.nspname='{app_literal}' AND c.relname='doctor_price_generation_seq'
            AND (c.relowner<>app_owner OR a.grantee<>app_owner))
      THEN RAISE EXCEPTION 'doctor price capability default grants are unsafe'; END IF;
    END {tag}""")


def _install_generations(dialect, schema=None):
    for table, generation, _ in _TARGETS:
        op.add_column(table, sa.Column(generation, sa.BigInteger(), nullable=False, server_default="1"))
    if dialect == "postgresql":
        # Pin object names to the migration schema: SECURITY DEFINER must not
        # resolve attacker-controlled search_path objects.
        if not schema:
            raise RuntimeError("doctor price context requires a trusted schema")
        quote = op.get_context().dialect.identifier_preparer.quote_identifier
        schema_q = quote(schema)
        private = _capability_schema_name(schema)
        private_q = quote(private)
        seq = f"{schema_q}.doctor_price_generation_seq"
        seq_literal = seq.replace("'", "''")
        function_tag = "$doctor_price_function$"
        while function_tag in seq_literal:
            function_tag = function_tag[:-1] + "_x$"
        op.execute(f"CREATE SEQUENCE {seq} AS bigint START WITH 2 NO CYCLE")
        app_literal = schema.replace("'", "''")
        sequence_owner_tag = "$doctor_price_sequence_owner$"
        while sequence_owner_tag in app_literal:
            sequence_owner_tag = sequence_owner_tag[:-1] + "_x$"
        op.execute(f"""DO {sequence_owner_tag} DECLARE trusted_owner name; BEGIN
          SELECT r.rolname INTO STRICT trusted_owner FROM pg_catalog.pg_namespace n
            JOIN pg_catalog.pg_roles r ON r.oid=n.nspowner WHERE n.nspname='{app_literal}';
          EXECUTE pg_catalog.format('ALTER SEQUENCE %I.doctor_price_generation_seq OWNER TO %I', '{app_literal}', trusted_owner);
        END {sequence_owner_tag}""")
        for table, generation, fields in _TARGETS:
            changed = " OR ".join(f"NEW.{f} IS DISTINCT FROM OLD.{f}" for f in fields)
            if table == "visits":
                changed += " OR ((OLD.status IN ('canceled', 'cancelled', 'expired')) IS DISTINCT FROM (NEW.status IN ('canceled', 'cancelled', 'expired')))"
            fn = f"{private_q}.doctor_price_gen_{table}"
            op.execute(f"""CREATE FUNCTION {fn}() RETURNS trigger
                LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog AS {function_tag}
                BEGIN
                  IF TG_OP = 'INSERT' THEN
                    NEW.{generation} := nextval('{seq_literal}'::regclass);
                  ELSE
                    IF NEW.id IS DISTINCT FROM OLD.id THEN
                      RAISE EXCEPTION 'doctor price context primary key is immutable';
                    END IF;
                    IF {changed} THEN
                      NEW.{generation} := nextval('{seq_literal}'::regclass);
                    ELSE
                      NEW.{generation} := OLD.{generation};
                    END IF;
                  END IF;
                  RETURN NEW;
                END {function_tag}""")
            op.execute(f"REVOKE ALL ON FUNCTION {fn}() FROM PUBLIC")
            app_literal = schema.replace("'", "''")
            private_literal = private.replace("'", "''")
            owner_tag = "$doctor_price_owner$"
            while owner_tag in app_literal:
                owner_tag = owner_tag[:-1] + "_x$"
            op.execute(f"""DO {owner_tag} DECLARE trusted_owner name; BEGIN
              SELECT r.rolname INTO STRICT trusted_owner FROM pg_catalog.pg_namespace n
                JOIN pg_catalog.pg_roles r ON r.oid=n.nspowner WHERE n.nspname='{app_literal}';
              EXECUTE pg_catalog.format('ALTER FUNCTION %I.doctor_price_gen_{table}() OWNER TO %I', '{private_literal}', trusted_owner);
            END {owner_tag}""")
            op.execute(f"CREATE TRIGGER doctor_price_gen_{table} BEFORE INSERT OR UPDATE ON {schema_q}.{table} FOR EACH ROW EXECUTE FUNCTION {fn}()")
    elif dialect == "sqlite":
        op.execute("CREATE TABLE doctor_price_generation_clock (id INTEGER PRIMARY KEY CHECK(id=1), value INTEGER NOT NULL CHECK(typeof(value)='integer' AND value>=1))")
        op.execute("INSERT INTO doctor_price_generation_clock (id,value) VALUES (1,1)")
        op.execute("""CREATE TRIGGER doctor_price_clock_no_delete BEFORE DELETE ON doctor_price_generation_clock
            BEGIN SELECT RAISE(ABORT, 'doctor price clock cannot be deleted'); END""")
        op.execute("""CREATE TRIGGER doctor_price_clock_no_replace BEFORE INSERT ON doctor_price_generation_clock
            WHEN EXISTS (SELECT 1 FROM doctor_price_generation_clock)
            BEGIN SELECT RAISE(ABORT, 'doctor price clock already exists'); END""")
        op.execute("""CREATE TRIGGER doctor_price_clock_advance BEFORE UPDATE ON doctor_price_generation_clock
            WHEN NEW.id IS NOT OLD.id OR typeof(NEW.value) <> 'integer' OR NEW.value != OLD.value + 1
            BEGIN SELECT RAISE(ABORT, 'doctor price clock must advance once'); END""")
        for table, generation, fields in _TARGETS:
            changed = " OR ".join(f"NEW.{f} IS NOT OLD.{f}" for f in fields)
            if table == "visits":
                changed += " OR ((OLD.status IN ('canceled', 'cancelled', 'expired')) IS NOT (NEW.status IN ('canceled', 'cancelled', 'expired')))"
            op.execute(f"""CREATE TRIGGER doctor_price_pk_{table} BEFORE UPDATE OF id ON {table}
                WHEN NEW.id IS NOT OLD.id BEGIN SELECT RAISE(ABORT, 'doctor price context primary key is immutable'); END""")
            op.execute(f"""CREATE TRIGGER doctor_price_guard_{table} BEFORE UPDATE OF {generation} ON {table}
                WHEN NEW.{generation} IS NOT OLD.{generation} AND NEW.{generation} IS NOT (SELECT value FROM doctor_price_generation_clock WHERE id=1)
                BEGIN SELECT RAISE(ABORT, 'doctor price generation cannot be restored'); END""")
            body = f"UPDATE doctor_price_generation_clock SET value=value+1 WHERE id=1; UPDATE {table} SET {generation}=(SELECT value FROM doctor_price_generation_clock WHERE id=1) WHERE id=NEW.id;"
            op.execute(f"CREATE TRIGGER doctor_price_insert_{table} AFTER INSERT ON {table} BEGIN {body} END")
            columns = ",".join(fields + (("status",) if table == "visits" else ()))
            op.execute(f"CREATE TRIGGER doctor_price_update_{table} AFTER UPDATE OF {columns} ON {table} WHEN {changed} BEGIN {body} END")
    else:
        raise RuntimeError(f"Unsupported doctor price context dialect: {dialect}")


def _create_intents(dialect):
    registry_check = ("key_check_digest ~ '^[0-9a-f]{64}$'" if dialect == "postgresql" else "typeof(version)='integer' AND key_check_digest NOT GLOB '*[^0-9a-f]*'")
    op.create_table(
        "doctor_price_hmac_key_versions",
        sa.Column("version", sa.Integer(), primary_key=True),
        sa.Column("key_check_digest", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("version > 0 AND length(key_check_digest) = 64", name="ck_doctor_price_hmac_key_value"),
        sa.CheckConstraint(registry_check, name=f"ck_doctor_price_hmac_key_{'pg' if dialect == 'postgresql' else 'sqlite'}"),
    )
    if dialect == "postgresql":
        op.execute("""CREATE FUNCTION doctor_price_hmac_key_immutable() RETURNS trigger
            LANGUAGE plpgsql SET search_path = pg_catalog AS $$
            BEGIN RAISE EXCEPTION 'doctor price HMAC version is immutable'; END $$""")
        op.execute("CREATE TRIGGER doctor_price_hmac_key_immutable BEFORE UPDATE OR DELETE ON doctor_price_hmac_key_versions FOR EACH ROW EXECUTE FUNCTION doctor_price_hmac_key_immutable()")
        op.execute("CREATE TRIGGER doctor_price_hmac_key_immutable_truncate BEFORE TRUNCATE ON doctor_price_hmac_key_versions FOR EACH STATEMENT EXECUTE FUNCTION doctor_price_hmac_key_immutable()")
    else:
        op.execute("""CREATE TRIGGER doctor_price_hmac_key_immutable_insert BEFORE INSERT ON doctor_price_hmac_key_versions
            WHEN EXISTS (SELECT 1 FROM doctor_price_hmac_key_versions WHERE version=NEW.version)
            BEGIN SELECT RAISE(ABORT, 'doctor price HMAC version already exists'); END""")
        for event in ("UPDATE", "DELETE"):
            op.execute(f"CREATE TRIGGER doctor_price_hmac_key_immutable_{event.lower()} BEFORE {event} ON doctor_price_hmac_key_versions BEGIN SELECT RAISE(ABORT, 'doctor price HMAC version is immutable'); END")
    hash_check = ("fingerprint ~ '^[0-9a-f]{64}$' AND (issued_confirmation_digest IS NULL OR issued_confirmation_digest ~ '^[0-9a-f]{64}$')" if dialect == "postgresql" else "fingerprint NOT GLOB '*[^0-9a-f]*' AND (issued_confirmation_digest IS NULL OR issued_confirmation_digest NOT GLOB '*[^0-9a-f]*')")
    op.create_table(
        "doctor_price_intents",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("operation", sa.String(16), nullable=False),
        sa.Column("requester_type", sa.String(16), nullable=False),
        sa.Column("actor_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("actor_user_id_snapshot", sa.Integer(), nullable=False),
        sa.Column("actor_user_auth_epoch", sa.BigInteger(), nullable=False),
        sa.Column("doctor_id", sa.Integer(), sa.ForeignKey("doctors.id", ondelete="SET NULL")),
        sa.Column("doctor_id_snapshot", sa.Integer()),
        sa.Column("doctor_owner_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("doctor_owner_user_id_snapshot", sa.Integer()),
        sa.Column("patient_id", sa.Integer(), sa.ForeignKey("patients.id", ondelete="SET NULL")),
        sa.Column("patient_id_snapshot", sa.Integer(), nullable=False),
        sa.Column("visit_id", sa.Integer(), sa.ForeignKey("visits.id", ondelete="SET NULL")),
        sa.Column("visit_id_snapshot", sa.Integer(), nullable=False),
        sa.Column("doctor_user_auth_epoch", sa.BigInteger()),
        sa.Column("price_owner_generation", sa.BigInteger()),
        sa.Column("fingerprint_version", sa.Integer(), sa.ForeignKey("doctor_price_hmac_key_versions.version", ondelete="RESTRICT"), nullable=False),
        sa.Column("fingerprint", sa.String(64), nullable=False),
        sa.Column("issued_confirmation_epoch", sa.BigInteger()),
        sa.Column("issued_confirmation_digest", sa.String(64)),
        sa.Column("issued_confirmation_digest_version", sa.Integer(), sa.ForeignKey("doctor_price_hmac_key_versions.version", ondelete="RESTRICT")),
        sa.Column("issued_confirmation_expires_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("id", "actor_user_id_snapshot", "operation", name="uq_doctor_price_intent_identity"),
        sa.CheckConstraint("operation IN ('schedule_next', 'add_service')", name="ck_doctor_price_intent_operation"),
        *(sa.CheckConstraint(f"{snapshot} > 0 AND ({live} IS NULL OR {live} = {snapshot})", name=f"ck_doctor_price_intent_{name}") for live, snapshot, name in (("actor_user_id", "actor_user_id_snapshot", "actor"), ("patient_id", "patient_id_snapshot", "patient"), ("visit_id", "visit_id_snapshot", "visit"))),
        sa.CheckConstraint("requester_type IN ('doctor', 'admin') AND actor_user_auth_epoch >= 0", name="ck_doctor_price_intent_requester"),
        sa.CheckConstraint(_DOCTOR_BINDING, name="ck_doctor_price_intent_doctor"),
        sa.CheckConstraint("requester_type <> 'doctor' OR (doctor_id_snapshot IS NOT NULL AND doctor_owner_user_id_snapshot IS NOT NULL AND doctor_owner_user_id_snapshot = actor_user_id_snapshot)", name="ck_doctor_price_intent_doctor_requester"),
        sa.CheckConstraint(_CONFIRMATION_BINDING, name="ck_doctor_price_intent_confirmation"),
        sa.CheckConstraint("fingerprint_version > 0 AND length(fingerprint) = 64", name="ck_doctor_price_intent_hash_length"),
        *([sa.CheckConstraint(_SQLITE_INTEGERS, name="ck_doctor_price_intent_integers_sqlite")] if dialect == "sqlite" else []),
        sa.CheckConstraint(hash_check, name=f"ck_doctor_price_intent_hash_{'pg' if dialect == 'postgresql' else 'sqlite'}"),
    )
    op.create_index("ix_doctor_price_intent_recent", "doctor_price_intents", ["actor_user_id_snapshot", "operation", "created_at"])
    op.create_index("ix_doctor_price_intent_fingerprint", "doctor_price_intents", ["actor_user_id_snapshot", "operation", "fingerprint_version", "fingerprint"])
    alias_check = ("key_hash ~ '^[0-9a-f]{64}$'" if dialect == "postgresql" else "typeof(actor_user_id_snapshot)='integer' AND typeof(intent_id)='integer' AND key_hash NOT GLOB '*[^0-9a-f]*'")
    op.create_table(
        "doctor_price_intent_keys",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("intent_id", sa.Integer(), nullable=False),
        sa.Column("actor_user_id_snapshot", sa.Integer(), nullable=False),
        sa.Column("operation", sa.String(16), nullable=False),
        sa.Column("key_hash", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("actor_user_id_snapshot", "operation", "key_hash", name="uq_doctor_price_intent_alias"),
        sa.ForeignKeyConstraint(["intent_id", "actor_user_id_snapshot", "operation"],
                                ["doctor_price_intents.id", "doctor_price_intents.actor_user_id_snapshot", "doctor_price_intents.operation"],
                                name="fk_doctor_price_intent_alias_identity", ondelete="RESTRICT"),
        sa.CheckConstraint("actor_user_id_snapshot > 0 AND operation IN ('schedule_next', 'add_service') AND length(key_hash) = 64", name="ck_doctor_price_intent_alias_value"),
        sa.CheckConstraint(alias_check, name=f"ck_doctor_price_intent_alias_{'pg' if dialect == 'postgresql' else 'sqlite'}"),
    )
    op.create_table(
        "doctor_price_intent_lines",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("intent_id", sa.Integer(), sa.ForeignKey("doctor_price_intents.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("service_id_snapshot", sa.Integer(), nullable=False),
        sa.Column("qty", sa.Integer(), nullable=False),
        sa.Column("raw_custom_minor", sa.BigInteger()),
        sa.Column("baseline_minor", sa.BigInteger(), nullable=False),
        sa.Column("proposed_minor", sa.BigInteger(), nullable=False),
        sa.Column("visit_service_id", sa.Integer(), sa.ForeignKey("visit_services.id", ondelete="SET NULL")),
        sa.Column("visit_service_id_snapshot", sa.Integer(), nullable=False),
        sa.Column("override_id", sa.Integer(), sa.ForeignKey("doctor_price_overrides.id", ondelete="SET NULL")),
        sa.Column("override_id_snapshot", sa.Integer()),
        sa.UniqueConstraint("intent_id", "ordinal", name="uq_doctor_price_intent_line_ordinal"),
        *([sa.CheckConstraint("typeof(ordinal) = 'integer' AND typeof(service_id_snapshot) = 'integer' AND typeof(qty) = 'integer' AND (raw_custom_minor IS NULL OR typeof(raw_custom_minor) = 'integer') AND typeof(baseline_minor) = 'integer' AND typeof(proposed_minor) = 'integer' AND typeof(visit_service_id_snapshot) = 'integer' AND (override_id_snapshot IS NULL OR typeof(override_id_snapshot) = 'integer')", name="ck_doctor_price_intent_line_integers_sqlite")] if dialect == "sqlite" else []),
        sa.CheckConstraint("ordinal >= 0 AND service_id_snapshot > 0 AND qty BETWEEN 1 AND 2147483647", name="ck_doctor_price_intent_line_identity"),
        sa.CheckConstraint("raw_custom_minor IS NULL OR raw_custom_minor BETWEEN 0 AND 999999999999", name="ck_doctor_price_intent_line_raw"),
        sa.CheckConstraint("baseline_minor BETWEEN 0 AND 999999999999 AND proposed_minor BETWEEN 0 AND 999999999999", name="ck_doctor_price_intent_line_amount"),
        sa.CheckConstraint("visit_service_id_snapshot > 0 AND (visit_service_id IS NULL OR visit_service_id = visit_service_id_snapshot)", name="ck_doctor_price_intent_line_target"),
        sa.CheckConstraint("(override_id_snapshot IS NULL AND override_id IS NULL) OR (override_id_snapshot IS NOT NULL AND override_id_snapshot > 0 AND (override_id IS NULL OR override_id = override_id_snapshot))", name="ck_doctor_price_intent_line_override"),
    )
    if dialect == "postgresql":
        op.execute("ALTER TABLE doctor_price_hmac_key_versions ENABLE ROW LEVEL SECURITY")
        op.execute("ALTER TABLE doctor_price_intents ENABLE ROW LEVEL SECURITY")
        op.execute("ALTER TABLE doctor_price_intent_keys ENABLE ROW LEVEL SECURITY")
        op.execute("ALTER TABLE doctor_price_intent_lines ENABLE ROW LEVEL SECURITY")


def upgrade():
    dialect = op.get_context().dialect.name
    if dialect not in ("postgresql", "sqlite"):
        raise RuntimeError(f"Unsupported doctor price context dialect: {dialect}")
    schema = _pin_trusted_schema() if dialect == "postgresql" else None
    if dialect == "postgresql":
        _bootstrap_capability_namespace(schema)
    _install_generations(dialect, schema)
    for name in _SNAPSHOTS:
        op.add_column("doctor_price_overrides", sa.Column(name, sa.BigInteger(), nullable=True))
    op.add_column("doctor_price_overrides", sa.Column("requester_type", sa.String(16)))
    op.add_column("doctor_price_overrides", sa.Column("requester_user_id_snapshot", sa.Integer()))
    op.add_column("doctor_price_overrides", sa.Column("requester_auth_epoch", sa.BigInteger()))
    if dialect == "postgresql":
        op.add_column("doctor_price_overrides", sa.Column("requester_user_id", sa.Integer()))
        op.create_foreign_key("fk_doctor_price_requester_user", "doctor_price_overrides", "users", ["requester_user_id"], ["id"], ondelete="SET NULL")
        op.create_check_constraint("ck_doctor_price_requester_binding", "doctor_price_overrides", _REQUESTER_BINDING)
    else:
        op.execute("ALTER TABLE doctor_price_overrides ADD COLUMN requester_user_id INTEGER REFERENCES users(id) ON DELETE SET NULL")
        # No SQLite table rebuild: that would silently discard existing triggers.
        valid = _REQUESTER_BINDING.replace("requester_type", "NEW.requester_type").replace("requester_user_id_snapshot", "NEW.requester_user_id_snapshot").replace("requester_auth_epoch", "NEW.requester_auth_epoch").replace("requester_user_id", "NEW.requester_user_id")
        # Replace order above can double-prefix user_id_snapshot; fix it.
        valid = valid.replace("NEW.NEW.", "NEW.")
        valid += " AND (NEW.requester_user_id_snapshot IS NULL OR typeof(NEW.requester_user_id_snapshot)='integer') AND (NEW.requester_auth_epoch IS NULL OR typeof(NEW.requester_auth_epoch)='integer')"
        for event in ("INSERT", "UPDATE"):
            op.execute(f"CREATE TRIGGER doctor_price_override_requester_{event.lower()} BEFORE {event} ON doctor_price_overrides WHEN NOT ({valid}) BEGIN SELECT RAISE(ABORT, 'invalid price requester binding'); END")
    _create_intents(dialect)
    if dialect == "postgresql":
        _assert_initial_capability_acl(schema)
        _restore_search_path()


def downgrade():
    dialect = op.get_context().dialect.name
    if dialect not in ("postgresql", "sqlite"):
        raise RuntimeError(f"Unsupported doctor price context dialect: {dialect}")
    if dialect == "postgresql":
        schema = _pin_trusted_schema()
        private = _capability_schema_name(schema)
        private_q = op.get_context().dialect.identifier_preparer.quote_identifier(private)
        _assert_initial_capability_acl(schema)
        app_literal, private_literal = schema.replace("'", "''"), private.replace("'", "''")
        tag = "$doctor_price_downgrade_marker$"
        while tag in app_literal:
            tag = tag[:-1] + "_x$"
        op.execute(f"""DO {tag} BEGIN
          IF (SELECT count(*) FROM {private_q}.clinic_capability_namespace)<>1 OR NOT EXISTS (
            SELECT 1 FROM {private_q}.clinic_capability_namespace
            WHERE id=1 AND format_version=1
              AND pg_catalog.convert_to(application_schema,'UTF8')=pg_catalog.convert_to('{app_literal}','UTF8')
              AND pg_catalog.convert_to(private_schema,'UTF8')=pg_catalog.convert_to('{private_literal}','UTF8')
          ) THEN RAISE EXCEPTION 'capability namespace marker mismatch'; END IF;
        END {tag}""")
    unsafe = "EXISTS (SELECT 1 FROM doctor_price_hmac_key_versions) OR EXISTS (SELECT 1 FROM doctor_price_intents) OR EXISTS (SELECT 1 FROM doctor_price_intent_keys) OR EXISTS (SELECT 1 FROM doctor_price_intent_lines) OR EXISTS (SELECT 1 FROM doctor_price_overrides WHERE " + " OR ".join(f"{n} IS NOT NULL" for n in _SNAPSHOTS + _REQUESTER_FIELDS) + ")"
    if dialect == "postgresql":
        op.execute("SET LOCAL row_security = off")
        op.execute(f"LOCK TABLE {private_q}.clinic_capability_namespace, {private_q}.clinic_capability_role_profile IN ACCESS EXCLUSIVE MODE")
        op.execute(f"DO $$ BEGIN IF EXISTS (SELECT 1 FROM {private_q}.clinic_capability_role_profile) THEN RAISE EXCEPTION 'capability namespace has provisioned roles'; END IF; END $$")
        op.execute("LOCK TABLE doctor_price_hmac_key_versions, doctor_price_intents, doctor_price_intent_keys, doctor_price_intent_lines, doctor_price_overrides IN ACCESS EXCLUSIVE MODE")
        op.execute(f"DO $$ BEGIN IF {unsafe} THEN RAISE EXCEPTION 'doctor price downgrade would discard evidence'; END IF; END $$")
    elif dialect == "sqlite":
        op.execute("UPDATE doctor_price_intents SET id=id WHERE 0")
        op.execute("CREATE TEMP TABLE doctor_price_downgrade_guard_0112 (value INTEGER NOT NULL CHECK(value=0))")
        op.execute(f"INSERT INTO doctor_price_downgrade_guard_0112 SELECT CASE WHEN {unsafe} THEN 1 ELSE 0 END")
        op.execute("DROP TABLE doctor_price_downgrade_guard_0112")
    else:
        raise RuntimeError(f"Unsupported doctor price context dialect: {dialect}")
    op.drop_table("doctor_price_intent_lines")
    op.drop_table("doctor_price_intent_keys")
    op.drop_index("ix_doctor_price_intent_fingerprint", table_name="doctor_price_intents")
    op.drop_index("ix_doctor_price_intent_recent", table_name="doctor_price_intents")
    op.drop_table("doctor_price_intents")
    if dialect == "postgresql":
        op.execute("DROP TRIGGER doctor_price_hmac_key_immutable_truncate ON doctor_price_hmac_key_versions")
        op.execute("DROP TRIGGER doctor_price_hmac_key_immutable ON doctor_price_hmac_key_versions")
        op.execute("DROP FUNCTION doctor_price_hmac_key_immutable()")
    else:
        op.execute("DROP TRIGGER doctor_price_hmac_key_immutable_insert")
        op.execute("DROP TRIGGER doctor_price_hmac_key_immutable_update")
        op.execute("DROP TRIGGER doctor_price_hmac_key_immutable_delete")
    op.drop_table("doctor_price_hmac_key_versions")
    if dialect == "postgresql":
        op.drop_constraint("ck_doctor_price_requester_binding", "doctor_price_overrides", type_="check")
        op.drop_constraint("fk_doctor_price_requester_user", "doctor_price_overrides", type_="foreignkey")
    else:
        op.execute("DROP TRIGGER doctor_price_override_requester_insert")
        op.execute("DROP TRIGGER doctor_price_override_requester_update")
    for name in _REQUESTER_FIELDS + _SNAPSHOTS:
        op.drop_column("doctor_price_overrides", name)
    if dialect == "postgresql":
        for table, _, _ in _TARGETS:
            op.execute(f"DROP TRIGGER doctor_price_gen_{table} ON {table}")
            op.execute(f"DROP FUNCTION {private_q}.doctor_price_gen_{table}()")
        op.execute("DROP SEQUENCE doctor_price_generation_seq")
        op.execute(f"DROP TABLE {private_q}.clinic_capability_role_profile")
        op.execute(f"DROP TABLE {private_q}.clinic_capability_namespace")
        # RESTRICT rejects later capability objects or unexpected dependencies.
        op.execute(f"DROP SCHEMA {private_q}")
    else:
        for table, _, _ in _TARGETS:
            for prefix in ("pk", "guard", "insert", "update"):
                op.execute(f"DROP TRIGGER doctor_price_{prefix}_{table}")
        for suffix in ("no_delete", "no_replace", "advance"):
            op.execute(f"DROP TRIGGER doctor_price_clock_{suffix}")
        op.drop_table("doctor_price_generation_clock")
    for table, generation, _ in _TARGETS:
        op.drop_column(table, generation)
    if dialect == "postgresql":
        _restore_search_path()
