"""Exact repeat-policy snapshots; PostgreSQL capability integration is pending.

This isolated helper is not yet wired into repeat eligibility. PostgreSQL
needs the separately reviewed and provisioned 0132 capability before that
integration can safely replace the current reader.
"""
from __future__ import annotations

import json
from decimal import Decimal, DecimalException

from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.capability_namespace import capability_schema_name
from app.db.trusted_schema import (
    TrustedSchemaUnavailable,
    _approved_roles,
    _check_owner_members,
    _identifier,
    _names,
    pin_application_schema,
)
from app.models.clinic import ClinicSettings
from app.services.doctor_repeat_discount import RepeatPolicyError, _setting_int


class RepeatPolicyUnavailable(RuntimeError):
    """The configured repeat policy cannot safely be interpreted."""


class RepeatPolicyBusy(RepeatPolicyUnavailable):
    """Retry the entire transaction after a policy snapshot conflict."""


_POLICY_LIMITS = {"repeat_visit_days": (1, 365), "repeat_visit_discount": (0, 100)}
_POLICY_DEFAULTS = {"repeat_visit_days": 21, "repeat_visit_discount": 0}
_MAX_POLICY_JSON_CHARS = 128


def repeat_policy_lock_function_body(schema: str) -> str:
    """Frozen body that takes a lock without evaluating table rows or RLS."""
    schema = _identifier(schema)
    quoted = '"' + schema.replace('"', '""') + '"'
    return f"""
BEGIN
  LOCK TABLE {quoted}.clinic_settings IN SHARE MODE NOWAIT;
  RETURN true;
END
"""


def repeat_policy_read_function_body(schema: str) -> str:
    """Frozen SQL body for the future 0132 read-only capability.

    The migration must carry an immutable copy and a parity test. A trusted
    operator provisions the separate owner and EXECUTE grant after migration.
    """
    schema = _identifier(schema)
    quoted = '"' + schema.replace('"', '""') + '"'
    return f"""
BEGIN
  RETURN QUERY SELECT s.key::pg_catalog.text, s.value::pg_catalog.text
    FROM {quoted}.clinic_settings AS s
    WHERE s.key IN ('repeat_visit_days', 'repeat_visit_discount')
    ORDER BY s.key LIMIT 3;
END
"""


def parse_repeat_policy_value(key: str, raw_json: str) -> int:
    """Interpret persisted JSON without binary-float rounding or fake defaults."""
    limits = _POLICY_LIMITS.get(key)
    if limits is None or not isinstance(raw_json, str) or len(raw_json) > _MAX_POLICY_JSON_CHARS:
        raise RepeatPolicyUnavailable("Настройки повторного визита недоступны")
    try:
        value = json.loads(raw_json, parse_float=Decimal, parse_int=Decimal, parse_constant=Decimal)
        return _setting_int(value, lower=limits[0], upper=limits[1])
    except (ValueError, TypeError, OverflowError, RecursionError, DecimalException, RepeatPolicyError):
        raise RepeatPolicyUnavailable("Настройки повторного визита недоступны") from None


def _pg_preflight_capability(
    db: Session, *, schema: str, owner: str, runtime: str, capability: str,
    lock_body: str, read_body: str,
) -> tuple[int, int]:
    """Check the callable before executing any of its code."""
    private = capability_schema_name(schema)
    state = db.execute(text("""
      WITH trusted_language AS (
        SELECT l.oid FROM pg_catalog.pg_language l
        JOIN pg_catalog.pg_roles lang_owner ON lang_owner.oid=l.lanowner
        JOIN pg_catalog.pg_depend d ON d.classid='pg_catalog.pg_language'::pg_catalog.regclass
          AND d.objid=l.oid AND d.deptype='e' AND d.refclassid='pg_catalog.pg_extension'::pg_catalog.regclass
        JOIN pg_catalog.pg_extension e ON e.oid=d.refobjid AND e.extname='plpgsql' AND e.extowner=l.lanowner
        JOIN pg_catalog.pg_proc handler ON handler.oid=l.lanplcallfoid AND handler.proowner=l.lanowner
        JOIN pg_catalog.pg_namespace handler_ns ON handler_ns.oid=handler.pronamespace
        JOIN pg_catalog.pg_language handler_lang ON handler_lang.oid=handler.prolang
        WHERE l.lanname='plpgsql' AND l.lanispl AND l.lanpltrusted
          AND (lang_owner.rolsuper OR lang_owner.rolname=:owner)
          AND handler_ns.nspname='pg_catalog' AND handler.proname='plpgsql_call_handler'
          AND handler.prosrc='plpgsql_call_handler' AND handler.probin='$libdir/plpgsql'
          AND handler_lang.lanname='c'
      )
      SELECT cap.oid AS cap_oid, actor.oid AS runtime_oid,
        read_fn.prosrc=:read_body AND lock_fn.prosrc=:lock_body
          AND read_fn.prosecdef AND read_fn.prokind='f' AND read_fn.provolatile='v'
          AND read_fn.probin IS NULL AND read_fn.prolang=(SELECT oid FROM trusted_language)
          AND read_fn.prosupport=0 AND NOT read_fn.proleakproof AND read_fn.proparallel='u'
          AND read_fn.provariadic=0 AND NOT read_fn.proisstrict
          AND read_fn.pronargs=0 AND read_fn.prorettype='pg_catalog.record'::pg_catalog.regtype
          AND read_fn.proargmodes=ARRAY['t','t']::"char"[]
          AND read_fn.proargnames=ARRAY['key','value_text']::text[]
          AND read_fn.proallargtypes=ARRAY['pg_catalog.text'::pg_catalog.regtype::oid,
                                           'pg_catalog.text'::pg_catalog.regtype::oid]
          AND lock_fn.prosecdef AND lock_fn.prokind='f' AND lock_fn.provolatile='v'
          AND lock_fn.probin IS NULL AND lock_fn.prolang=(SELECT oid FROM trusted_language)
          AND lock_fn.prosupport=0 AND NOT lock_fn.proleakproof AND lock_fn.proparallel='u'
          AND lock_fn.provariadic=0 AND NOT lock_fn.proisstrict
          AND lock_fn.pronargs=0 AND lock_fn.prorettype='pg_catalog.bool'::pg_catalog.regtype
          AND lock_fn.proargmodes IS NULL AND lock_fn.proallargtypes IS NULL
          AND pg_catalog.cardinality(read_fn.proconfig)=3
          AND 'search_path=pg_catalog'=ANY(read_fn.proconfig)
          AND 'row_security=on'=ANY(read_fn.proconfig)
          AND 'standard_conforming_strings=on'=ANY(read_fn.proconfig)
          AND pg_catalog.cardinality(lock_fn.proconfig)=3
          AND 'search_path=pg_catalog'=ANY(lock_fn.proconfig)
          AND 'row_security=on'=ANY(lock_fn.proconfig)
          AND 'standard_conforming_strings=on'=ANY(lock_fn.proconfig)
          AND NOT cap.rolcanlogin AND NOT cap.rolsuper AND NOT cap.rolbypassrls
          AND NOT cap.rolcreaterole AND NOT cap.rolcreatedb AND NOT cap.rolreplication
          AND actor.rolname=:runtime AND CURRENT_USER=SESSION_USER
          AND cap.oid<>actor.oid AND cap.oid<>app_ns.nspowner
          AND app_owner.rolname=:owner AND private_ns.nspowner=app_ns.nspowner
          AND pg_catalog.has_schema_privilege(actor.oid,private_ns.oid,'USAGE')
          AND NOT pg_catalog.has_schema_privilege(actor.oid,private_ns.oid,'CREATE')
          AND pg_catalog.has_schema_privilege(cap.oid,private_ns.oid,'USAGE')
          AND NOT pg_catalog.has_schema_privilege(cap.oid,private_ns.oid,'CREATE')
          AND pg_catalog.has_schema_privilege(cap.oid,app_ns.oid,'USAGE')
          AND NOT pg_catalog.has_schema_privilege(cap.oid,app_ns.oid,'CREATE')
          AND pg_catalog.has_function_privilege(actor.oid,read_fn.oid,'EXECUTE')
          AND pg_catalog.has_function_privilege(actor.oid,lock_fn.oid,'EXECUTE')
          AND NOT EXISTS (SELECT 1 FROM pg_catalog.pg_proc checked,
            LATERAL pg_catalog.aclexplode(COALESCE(checked.proacl,
              pg_catalog.acldefault('f',checked.proowner))) a
            WHERE checked.oid IN (read_fn.oid,lock_fn.oid)
              AND (a.grantee NOT IN (cap.oid,actor.oid)
                OR (a.grantee<>cap.oid AND (a.privilege_type<>'EXECUTE' OR a.is_grantable))))
          AND NOT EXISTS (SELECT 1 FROM pg_catalog.aclexplode(COALESCE(private_ns.nspacl,
            pg_catalog.acldefault('n',private_ns.nspowner))) a
            WHERE a.grantee=0 OR (a.privilege_type='CREATE' AND a.grantee<>private_ns.nspowner))
          AND NOT EXISTS (SELECT 1 FROM pg_catalog.pg_roles r
            WHERE r.oid<>cap.oid AND pg_catalog.pg_has_role(cap.oid,r.oid,'MEMBER'))
          AND NOT EXISTS (SELECT 1 FROM pg_catalog.pg_roles r
            WHERE r.oid<>cap.oid AND NOT r.rolsuper AND pg_catalog.pg_has_role(r.oid,cap.oid,'MEMBER'))
          AND NOT EXISTS (SELECT 1 FROM pg_catalog.pg_proc other
            WHERE other.proowner=cap.oid AND other.prosecdef AND other.oid NOT IN (read_fn.oid,lock_fn.oid))
          AND NOT EXISTS (SELECT 1 FROM pg_catalog.pg_class owned WHERE owned.relowner=cap.oid)
          AND NOT EXISTS (SELECT 1 FROM pg_catalog.pg_namespace n,
            LATERAL pg_catalog.aclexplode(COALESCE(n.nspacl,pg_catalog.acldefault('n',n.nspowner))) a
            WHERE a.grantee=cap.oid AND (n.oid NOT IN (app_ns.oid,private_ns.oid)
              OR a.privilege_type<>'USAGE' OR a.is_grantable)) AS safe
      FROM pg_catalog.pg_roles cap
      JOIN pg_catalog.pg_proc read_fn ON read_fn.proowner=cap.oid AND read_fn.proname='repeat_policy_read'
      JOIN pg_catalog.pg_namespace private_ns ON private_ns.oid=read_fn.pronamespace AND private_ns.nspname=:private
      JOIN pg_catalog.pg_proc lock_fn ON lock_fn.proowner=cap.oid AND lock_fn.pronamespace=private_ns.oid
        AND lock_fn.proname='repeat_policy_lock'
      JOIN pg_catalog.pg_namespace app_ns ON app_ns.nspname=:schema
      JOIN pg_catalog.pg_roles app_owner ON app_owner.oid=app_ns.nspowner
      JOIN pg_catalog.pg_roles actor ON actor.rolname=CURRENT_USER
      WHERE cap.rolname=:capability
    """), {"schema": schema, "private": private, "capability": capability,
           "owner": owner, "runtime": runtime, "lock_body": lock_body, "read_body": read_body}).mappings().all()
    if len(state) != 1 or state[0]["safe"] is not True:
        raise RepeatPolicyUnavailable("Настройки повторного визита недоступны")
    return state[0]["cap_oid"], state[0]["runtime_oid"]


def _pg_verify_settings_access(
    db: Session, *, schema: str, table_owner: str, table_owner_members: tuple[str, ...],
    runtime: str, runtime_oid: int, capability_oid: int, writers: tuple[str, ...],
) -> None:
    """Validate relation, role grants and effective RLS while SHARE is held."""
    relation = db.execute(text("""
      SELECT c.oid,c.relowner,c.relkind,c.relrowsecurity,r.rolname AS owner_name,
        EXISTS(SELECT 1 FROM pg_catalog.pg_inherits i WHERE i.inhrelid=c.oid OR i.inhparent=c.oid) AS inherited,
        pg_catalog.has_table_privilege(:cap,c.oid,'UPDATE') AS cap_update,
        pg_catalog.has_table_privilege(:cap,c.oid,'SELECT,INSERT,DELETE,TRUNCATE,REFERENCES,TRIGGER') AS cap_excess,
        pg_catalog.has_column_privilege(:cap,c.oid,'key','SELECT') AS cap_key,
        pg_catalog.has_column_privilege(:cap,c.oid,'value','SELECT') AS cap_value,
        (SELECT count(*)=2 AND COALESCE(bool_and(
           (a.attname='key' AND a.atttypid='pg_catalog.varchar'::pg_catalog.regtype
             AND a.atttypmod=104 AND a.attnotnull AND a.attgenerated='')
           OR (a.attname='value' AND a.atttypid='pg_catalog.json'::pg_catalog.regtype
             AND a.attgenerated='')),false)
         FROM pg_catalog.pg_attribute a WHERE a.attrelid=c.oid AND a.attnum>0
           AND NOT a.attisdropped AND a.attname IN ('key','value')) AS safe_types,
        EXISTS(SELECT 1 FROM pg_catalog.pg_attribute a WHERE a.attrelid=c.oid AND a.attnum>0
          AND NOT a.attisdropped AND a.attname NOT IN ('key','value')
          AND pg_catalog.has_column_privilege(:cap,c.oid,a.attname,'SELECT')) AS cap_other_read
      FROM pg_catalog.pg_class c JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace
      JOIN pg_catalog.pg_roles r ON r.oid=c.relowner
      WHERE n.nspname=:schema AND c.relname='clinic_settings'
    """), {"schema": schema, "cap": capability_oid}).mappings().first()
    if (relation is None or relation["relkind"] != "r" or relation["inherited"]
        or relation["owner_name"] != table_owner or relation["relowner"] in {runtime_oid, capability_oid}
        or not relation["cap_update"] or relation["cap_excess"] or not relation["cap_key"]
        or not relation["cap_value"] or relation["cap_other_read"] or not relation["safe_types"]):
        raise RepeatPolicyUnavailable("Настройки повторного визита недоступны")
    _check_owner_members(db, relation["relowner"], table_owner_members)
    approved = _approved_roles(db, owner_oid=relation["relowner"], owner_name=table_owner,
        owner_members=table_owner_members, runtime_oid=runtime_oid, runtime_name=runtime,
        role_groups=(writers,))
    allowed_writers = {relation["relowner"], runtime_oid, *(approved[name] for name in writers)}
    grants = db.execute(text("""
      SELECT a.grantee,a.privilege_type,a.is_grantable,NULL::text AS column_name FROM pg_catalog.pg_class c,
        LATERAL pg_catalog.aclexplode(COALESCE(c.relacl,pg_catalog.acldefault('r',c.relowner))) a WHERE c.oid=:oid
      UNION ALL
      SELECT a.grantee,a.privilege_type,a.is_grantable,col.attname::text FROM pg_catalog.pg_attribute col,
        LATERAL pg_catalog.aclexplode(col.attacl) a WHERE col.attrelid=:oid AND col.attnum>0 AND NOT col.attisdropped
    """), {"oid": relation["oid"]}).mappings().all()
    untrusted_readers = {0, *db.execute(text("""
      SELECT oid FROM pg_catalog.pg_roles WHERE pg_catalog.lower(rolname) IN ('anon','authenticated')
    """)).scalars().all()}
    for grant in grants:
        if grant["grantee"] == relation["relowner"]:
            continue
        if grant["grantee"] in untrusted_readers or grant["is_grantable"]:
            raise RepeatPolicyUnavailable("Настройки повторного визита недоступны")
        if grant["grantee"] == capability_oid:
            permitted = ((grant["privilege_type"] == "UPDATE" and grant["column_name"] is None)
                         or (grant["privilege_type"] == "SELECT" and grant["column_name"] in {"key", "value"}))
            if not permitted:
                raise RepeatPolicyUnavailable("Настройки повторного визита недоступны")
        elif grant["privilege_type"] != "SELECT" and grant["grantee"] not in allowed_writers:
            raise RepeatPolicyUnavailable("Настройки повторного визита недоступны")
    # Direct privileges on unrelated relations would give the no-login
    # capability role authority beyond this single reviewed operation.
    excess = db.execute(text("""
      SELECT EXISTS(SELECT 1 FROM pg_catalog.pg_class c,
          LATERAL pg_catalog.aclexplode(c.relacl) a WHERE c.oid<>:oid AND a.grantee=:cap)
        OR EXISTS(SELECT 1 FROM pg_catalog.pg_attribute col,
          LATERAL pg_catalog.aclexplode(col.attacl) a WHERE col.attrelid<>:oid AND a.grantee=:cap)
    """), {"oid": relation["oid"], "cap": capability_oid}).scalar_one()
    if excess:
        raise RepeatPolicyUnavailable("Настройки повторного визита недоступны")
    if relation["relrowsecurity"]:
        policies = db.execute(text("""
          SELECT p.polcmd::text AS command,p.polpermissive,
            pg_catalog.pg_get_expr(p.polqual,p.polrelid) AS predicate,
            pg_catalog.pg_get_expr(p.polwithcheck,p.polrelid) AS check_expr
          FROM pg_catalog.pg_policy p WHERE p.polrelid=:oid
            AND (0=ANY(p.polroles) OR :cap=ANY(p.polroles))
        """), {"oid": relation["oid"], "cap": capability_oid}).mappings().all()
        selectors = [row for row in policies if row["command"] in {"r", "*"}]
        if (any(not row["polpermissive"] or row["predicate"] not in {None, "true", "false"}
                for row in selectors)
            or not any(row["polpermissive"] and row["predicate"] in {None, "true"} for row in selectors)):
            raise RepeatPolicyUnavailable("Настройки повторного визита недоступны")
        updates = [row for row in policies if row["command"] in {"w", "*"} and row["polpermissive"]]
        if any(row["predicate"] != "false" or row["check_expr"] != "false" for row in updates):
            raise RepeatPolicyUnavailable("Настройки повторного визита недоступны")


def read_postgresql_repeat_policy(
    db: Session, *, schema: str, schema_owner: str, runtime_role: str,
    trusted_schema_owner_members: tuple[str, ...], capability_role: str,
    settings_owner: str, trusted_settings_owner_members: tuple[str, ...],
    trusted_settings_writers: tuple[str, ...],
) -> dict[str, int]:
    """Preflight, lock, verify relation/ACL/RLS, then read the policy.

    All identifiers come from trusted deployment configuration, never request
    data. Owners must drain traffic for GRANT/REVOKE/role or function DDL: a
    SHARE table lock does not serialize every ACL change. The caller must not
    use untracked SQL savepoints and must discard the snapshot after rollback.
    This is not connected to consumers until 0132 and its provisioning exist.
    """
    if db.get_bind().dialect.name != "postgresql" or db.in_nested_transaction():
        raise RepeatPolicyUnavailable("Настройки повторного визита недоступны")
    if any(isinstance(row, ClinicSettings) for row in (*db.new, *db.dirty, *db.deleted)):
        raise RepeatPolicyUnavailable("Настройки повторного визита недоступны")
    # A Session bound to an externally managed Connection can report no
    # nested transaction even though that Connection is inside a savepoint.
    # Rolling such a savepoint back would release the policy lock while the
    # outer transaction and the returned snapshot remain live.
    if db.connection().in_nested_transaction():
        raise RepeatPolicyUnavailable("Настройки повторного визита недоступны")
    try:
        schema = _identifier(schema)
        schema_owner = _identifier(schema_owner)
        runtime_role = _identifier(runtime_role)
        capability_role = _identifier(capability_role)
        settings_owner = _identifier(settings_owner)
        schema_members = _names(trusted_schema_owner_members)
        table_members = _names(trusted_settings_owner_members)
        writers = _names(trusted_settings_writers)
        if (capability_role.lower() in {"public", "anon", "authenticated"}
            or settings_owner.lower() in {"public", "anon", "authenticated"}
            or capability_role in {schema_owner, settings_owner, runtime_role, *writers}):
            raise RepeatPolicyUnavailable("Настройки повторного визита недоступны")
        if (schema != settings.TRUSTED_DB_SCHEMA or schema_owner != settings.TRUSTED_DB_SCHEMA_OWNER
            or runtime_role != settings.TRUSTED_DB_RUNTIME_ROLE
            or schema_members != tuple(settings.TRUSTED_DB_OWNER_MEMBERS)):
            raise RepeatPolicyUnavailable("Настройки повторного визита недоступны")
        with db.no_autoflush:
            pin_application_schema(
                db, schema=schema, expected_owner=schema_owner, expected_runtime_role=runtime_role,
                trusted_owner_members=schema_members, expected_auth_owner=settings.TRUSTED_AUTH_TABLE_OWNER,
                trusted_auth_owner_members=settings.TRUSTED_AUTH_OWNER_MEMBERS,
                trusted_auth_read_roles=settings.TRUSTED_AUTH_READ_ROLES,
                trusted_auth_write_roles=settings.TRUSTED_AUTH_WRITE_ROLES,
                expected_users_owner=settings.TRUSTED_AUTH_USERS_OWNER,
                trusted_users_owner_members=settings.TRUSTED_AUTH_USERS_OWNER_MEMBERS,
                trusted_users_write_roles=settings.TRUSTED_AUTH_USERS_WRITE_ROLES,
            )
            if db.execute(text("SHOW transaction_isolation")).scalar_one() != "read committed":
                raise RepeatPolicyUnavailable("Настройки повторного визита недоступны")
            lock_body = repeat_policy_lock_function_body(schema)
            read_body = repeat_policy_read_function_body(schema)
            cap_oid, runtime_oid = _pg_preflight_capability(
                db, schema=schema, owner=schema_owner, runtime=runtime_role,
                capability=capability_role, lock_body=lock_body, read_body=read_body,
            )
            # Before calling even the lock-only function, exclude a view or
            # other object whose LOCK could traverse unexpected relations.
            preliminary = db.execute(text("""
              SELECT c.relkind='r' AND r.rolname=:owner AND NOT EXISTS (
                SELECT 1 FROM pg_catalog.pg_inherits i WHERE i.inhrelid=c.oid OR i.inhparent=c.oid)
              FROM pg_catalog.pg_class c JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace
              JOIN pg_catalog.pg_roles r ON r.oid=c.relowner
              WHERE n.nspname=:schema AND c.relname='clinic_settings'
            """), {"schema": schema, "owner": settings_owner}).scalar_one_or_none()
            if preliminary is not True:
                raise RepeatPolicyUnavailable("Настройки повторного визита недоступны")
            private = db.get_bind().dialect.identifier_preparer.quote_identifier(capability_schema_name(schema))
            locked = db.execute(text(f"SELECT {private}.repeat_policy_lock()" )).scalar_one()
            if locked is not True:
                raise RepeatPolicyUnavailable("Настройки повторного визита недоступны")
            _pg_verify_settings_access(
                db, schema=schema, table_owner=settings_owner, table_owner_members=table_members,
                runtime=runtime_role, runtime_oid=runtime_oid, capability_oid=cap_oid, writers=writers,
            )
            rows = db.execute(text(f"SELECT key,value_text FROM {private}.repeat_policy_read()" )).all()
            result = dict(_POLICY_DEFAULTS)
            seen: set[str] = set()
            for key, value in rows:
                if key not in _POLICY_LIMITS or key in seen:
                    raise RepeatPolicyUnavailable("Настройки повторного визита недоступны")
                seen.add(key)
                result[key] = parse_repeat_policy_value(key, value)
            return result
    except (TrustedSchemaUnavailable, ValueError, TypeError):
        db.rollback()
        raise RepeatPolicyUnavailable("Настройки повторного визита недоступны") from None
    except RepeatPolicyUnavailable:
        db.rollback()
        raise
    except DBAPIError as exc:
        code = getattr(exc.orig, "sqlstate", None) or getattr(exc.orig, "pgcode", None)
        db.rollback()
        if code in {"55P03", "40P01"}:
            raise RepeatPolicyBusy("Настройки повторного визита изменяются") from None
        raise


def read_sqlite_repeat_policy(db: Session) -> dict[str, int]:
    """Reserve SQLite's writer before reading; caller retains the root txn.

    SQLite's JSON ORM decoder may already round a fractional number. Read raw
    JSON text after the reservation and reject unknown/null/malformed values.
    The caller must discard the snapshot after any rollback. SQLAlchemy-managed
    savepoints are rejected; callers must also avoid raw SQL savepoints that
    SQLAlchemy cannot track, since rollback to one may release the lock.
    """
    if db.get_bind().dialect.name != "sqlite" or db.in_nested_transaction():
        raise RepeatPolicyUnavailable("Настройки повторного визита недоступны")
    if any(isinstance(row, ClinicSettings) for row in (*db.new, *db.dirty, *db.deleted)):
        raise RepeatPolicyUnavailable("Настройки повторного визита недоступны")
    if db.connection().in_nested_transaction():
        raise RepeatPolicyUnavailable("Настройки повторного визита недоступны")
    try:
        with db.no_autoflush:
            if db.execute(text("PRAGMA read_uncommitted")).scalar_one() != 0:
                raise RepeatPolicyUnavailable("Настройки повторного визита недоступны")
            db.execute(text("UPDATE clinic_settings SET id=id WHERE 0"))
            rows = db.execute(text("""
                SELECT key, CAST(value AS TEXT) AS value_text FROM clinic_settings
                WHERE key IN ('repeat_visit_days','repeat_visit_discount') ORDER BY key
            """)).all()
    except DBAPIError as exc:
        code = getattr(exc.orig, "sqlite_errorcode", None)
        if code is not None and code & 0xff in {5, 6}:
            db.rollback()
            raise RepeatPolicyBusy("Настройки повторного визита изменяются") from None
        raise
    result = dict(_POLICY_DEFAULTS)
    seen: set[str] = set()
    try:
        for key, value in rows:
            if key not in _POLICY_LIMITS or key in seen:
                raise RepeatPolicyUnavailable("Настройки повторного визита недоступны")
            seen.add(key)
            result[key] = parse_repeat_policy_value(key, value)
    except RepeatPolicyUnavailable:
        # A bad persisted policy invalidates the caller's complete command;
        # never leave the writer reservation held after the refusal.
        db.rollback()
        raise
    return result
