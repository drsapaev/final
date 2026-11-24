"""Fail closed on a pending 0107 all-free request before new payment work.

This is not the complete all-free workflow: unconverted issuers, clinical
transitions, grouped payments, invoice settlement and provider callbacks must
still be fenced or reconciled separately. No external provider is contacted.
"""
from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.capability_namespace import capability_schema_name
from app.db.financial_capability_contract import financial_all_free_lock_role
from app.models.all_free_request import AllFreeRequest
from app.models.visit import Visit


class AllFreeGuardError(HTTPException):
    """The pending-request boundary cannot safely allow this action."""


class PendingAllFreeError(AllFreeGuardError):
    """The checked Visit has a pending all-free request."""


def _pg_role_profile_is_safe(db: Session, schema: str, private_schema: str) -> bool:
    """Prove either capability-only or owner-templated stage privileges.

    Policy expressions are deparsed against the same relation by this server,
    so comparison does not depend on a hardcoded PostgreSQL deparser version.
    Owners/DBAs are trusted and must coordinate their DDL while traffic drains.
    """
    quoted_schema = db.get_bind().dialect.identifier_preparer.quote_schema(schema)
    financial_role = financial_all_free_lock_role(
        db, schema=schema, private=private_schema, quoted_schema=quoted_schema,
    )
    return db.execute(text("""
        WITH actor AS (
          SELECT oid, rolsuper, rolbypassrls, rolcreaterole, rolcreatedb, rolreplication, rolname
          FROM pg_catalog.pg_roles WHERE rolname=CURRENT_USER
        ), capability AS (
          SELECT p.proowner AS oid FROM pg_catalog.pg_proc p JOIN pg_catalog.pg_namespace n ON n.oid=p.pronamespace
          WHERE n.nspname=:private_schema AND p.proname='all_free_pending_exists' AND p.proargtypes='23'::oidvector
        ), tabs AS (
          SELECT c.oid, c.relname, c.relowner, c.relrowsecurity
          FROM pg_catalog.pg_class c JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace
          WHERE n.nspname=:schema AND c.relname IN
            ('all_free_requests','all_free_request_lines','all_free_request_events')
        ), checks AS (
          SELECT t.*,
            NOT pg_catalog.has_table_privilege(CURRENT_USER,t.oid,'UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER')
              AND NOT pg_catalog.has_any_column_privilege(CURRENT_USER,t.oid,'UPDATE,REFERENCES') AS no_mutation,
            NOT pg_catalog.has_table_privilege(CURRENT_USER,t.oid,'SELECT,INSERT')
              AND NOT pg_catalog.has_any_column_privilege(CURRENT_USER,t.oid,'SELECT,INSERT') AS capability_only,
            pg_catalog.has_table_privilege(CURRENT_USER,t.oid,'SELECT')
              AND pg_catalog.has_table_privilege(CURRENT_USER,t.oid,'INSERT') AS stage_grants,
            NOT EXISTS (
              SELECT 1 FROM pg_catalog.aclexplode(COALESCE(tacl.relacl,pg_catalog.acldefault('r',t.relowner))) x
              WHERE x.privilege_type IN ('SELECT','INSERT','UPDATE','DELETE','TRUNCATE','REFERENCES','TRIGGER')
                AND NOT (x.grantee IN (t.relowner,a.oid) OR
                  (x.grantee IS NOT DISTINCT FROM (SELECT oid FROM capability)
                    AND x.privilege_type='SELECT' AND NOT x.is_grantable) OR
                  (t.relname='all_free_requests' AND x.grantee IS NOT DISTINCT FROM CAST(:financial AS oid)
                    AND x.privilege_type='SELECT' AND NOT x.is_grantable))
            ) AND NOT EXISTS (
              SELECT 1 FROM pg_catalog.pg_attribute att,
                   LATERAL pg_catalog.aclexplode(att.attacl) x
              WHERE att.attrelid=t.oid AND att.attnum>0 AND NOT att.attisdropped
                AND x.privilege_type IN ('SELECT','INSERT','UPDATE','REFERENCES')
                AND NOT (x.grantee IN (t.relowner,a.oid) OR
                  (x.grantee IS NOT DISTINCT FROM (SELECT oid FROM capability) AND NOT x.is_grantable AND (
                    (t.relname='all_free_requests' AND x.privilege_type='UPDATE' AND att.attname IN
                      ('status','decision_kind','decision_context_epoch','decided_by_user_id',
                       'decided_by_user_id_snapshot','decided_by_role_snapshot','decided_at')) OR
                    (t.relname='all_free_request_events' AND x.privilege_type='INSERT' AND att.attname IN
                      ('request_id','event_type','actor_user_id','actor_user_id_snapshot','actor_role_snapshot')))) OR
                  (t.relname='all_free_requests' AND x.grantee IS NOT DISTINCT FROM CAST(:financial AS oid)
                    AND x.privilege_type='UPDATE' AND att.attname='id' AND NOT x.is_grantable))
            ) AS no_other_grants,
            own_select.polpermissive AND own_select.polcmd='r'
              AND own_select.polroles=ARRAY[t.relowner]::oid[]
              AND own_insert.polpermissive AND own_insert.polcmd='a'
              AND own_insert.polroles=ARRAY[t.relowner]::oid[]
              AND run_select.polpermissive AND run_select.polcmd='r'
              AND run_select.polroles=ARRAY[a.oid]::oid[]
              AND run_insert.polpermissive AND run_insert.polcmd='a'
              AND run_insert.polroles=ARRAY[a.oid]::oid[]
              AND pg_catalog.pg_get_expr(run_select.polqual,t.oid)
                    IS NOT DISTINCT FROM pg_catalog.pg_get_expr(own_select.polqual,t.oid)
              AND pg_catalog.pg_get_expr(run_select.polwithcheck,t.oid)
                    IS NOT DISTINCT FROM pg_catalog.pg_get_expr(own_select.polwithcheck,t.oid)
              AND pg_catalog.pg_get_expr(run_insert.polqual,t.oid)
                    IS NOT DISTINCT FROM pg_catalog.pg_get_expr(own_insert.polqual,t.oid)
              AND pg_catalog.pg_get_expr(run_insert.polwithcheck,t.oid)
                    IS NOT DISTINCT FROM pg_catalog.pg_get_expr(own_insert.polwithcheck,t.oid)
              AND NOT EXISTS (
                SELECT 1 FROM pg_catalog.pg_policy extra WHERE extra.polrelid=t.oid
                  AND extra.polname NOT IN ('allfree_template_select','allfree_template_insert',
                                             'allfree_backend_select','allfree_backend_insert')
                  AND EXISTS (SELECT 1 FROM pg_catalog.unnest(extra.polroles) rid
                    WHERE CASE WHEN rid=0 THEN true
                               ELSE pg_catalog.pg_has_role(CURRENT_USER,rid,'MEMBER') END)
              ) AS stage_policies
          FROM tabs t CROSS JOIN actor a
          JOIN pg_catalog.pg_class tacl ON tacl.oid=t.oid
          LEFT JOIN pg_catalog.pg_policy own_select ON own_select.polrelid=t.oid AND own_select.polname='allfree_template_select'
          LEFT JOIN pg_catalog.pg_policy own_insert ON own_insert.polrelid=t.oid AND own_insert.polname='allfree_template_insert'
          LEFT JOIN pg_catalog.pg_policy run_select ON run_select.polrelid=t.oid AND run_select.polname='allfree_backend_select'
          LEFT JOIN pg_catalog.pg_policy run_insert ON run_insert.polrelid=t.oid AND run_insert.polname='allfree_backend_insert'
        )
        SELECT count(*)=3 AND COALESCE(bool_and(c.relrowsecurity AND c.no_mutation AND c.no_other_grants),false)
          AND (COALESCE(bool_and(c.capability_only),false)
            OR (COALESCE(bool_and(COALESCE(c.stage_grants AND c.stage_policies,false)),false)
              AND NOT EXISTS (
                SELECT 1 FROM pg_catalog.pg_roles candidate CROSS JOIN actor a
                WHERE NOT candidate.rolsuper AND candidate.oid<>a.oid
                  AND pg_catalog.pg_has_role(candidate.oid,a.oid,'MEMBER')
              )))
          AND NOT a.rolsuper AND NOT a.rolbypassrls
          AND NOT a.rolcreaterole AND NOT a.rolcreatedb AND NOT a.rolreplication
          AND CURRENT_USER=SESSION_USER
          AND pg_catalog.lower(a.rolname) NOT IN ('anon','authenticated','public')
          AND NOT EXISTS (
            SELECT 1 FROM pg_catalog.pg_roles elevated
            WHERE (elevated.rolsuper OR elevated.rolbypassrls OR elevated.rolcreaterole
                   OR elevated.rolcreatedb OR elevated.rolreplication)
              AND pg_catalog.pg_has_role(a.oid,elevated.oid,'MEMBER')
          )
        FROM checks c CROSS JOIN actor a GROUP BY a.oid,a.rolsuper,a.rolbypassrls,
          a.rolcreaterole,a.rolcreatedb,a.rolreplication,a.rolname
    """), {"schema": schema, "private_schema": private_schema,
            "financial": financial_role}).scalar_one_or_none() is True


def lock_visit_without_pending(db: Session, visit_id: int) -> None:
    """Lock the Visit, then read 0107 pending state in a new statement.

    Stage writers must lock the same Visit first. PostgreSQL requires READ
    COMMITTED, a trusted engine-default schema and a narrowly granted 0114
    capability whose owner can see all 0107 rows. SQLite reserves its database writer before reads;
    a failed upgrade from a stale snapshot is an error rather than permission.
    The caller owns the transaction and must roll it back on every exception.
    """
    if type(visit_id) is not int or visit_id <= 0:
        raise AllFreeGuardError(status_code=404, detail="Визит не найден")
    with db.no_autoflush:
        # A refresh or SQL predicate cannot safely interpret local unflushed
        # changes to the target or evidence; never discard caller-owned state.
        loaded = db.identity_map.get(db.identity_key(Visit, visit_id))
        if loaded is not None and db.is_modified(loaded, include_collections=False):
            raise AllFreeGuardError(status_code=409, detail="Сначала сохраните изменения визита")
        if any(isinstance(item, AllFreeRequest) for item in (*db.new, *db.dirty, *db.deleted)):
            raise AllFreeGuardError(status_code=409, detail="Сначала сохраните изменения заявки")
        try:
            dialect = db.get_bind().dialect.name
            if dialect == "postgresql":
                isolation = db.execute(text("SHOW transaction_isolation")).scalar_one()
                if isolation not in {"read committed", "read uncommitted"}:
                    raise AllFreeGuardError(status_code=503, detail="Проверка заявки временно недоступна")
                schema = db.get_bind().dialect.default_schema_name
                if not schema or schema == "pg_catalog":
                    raise AllFreeGuardError(status_code=503, detail="Проверка заявки временно недоступна")
                members = settings.TRUSTED_DB_OWNER_MEMBERS
                if (not isinstance(members, (tuple, list))
                    or any(not isinstance(value, str) or not value or "\0" in value for value in members)
                    or len(set(members)) != len(members)
                    or (settings.TRUSTED_DB_SCHEMA is not None and settings.TRUSTED_DB_SCHEMA != schema)):
                    raise AllFreeGuardError(status_code=503, detail="Проверка заявки временно недоступна")
                # Run only this pg_catalog-qualified function before checking
                # the path; no attacker-controlled operators are resolved.
                path_state = db.execute(text("""SELECT pg_catalog.current_schemas(true) AS paths,
                  CASE WHEN pg_catalog.pg_my_temp_schema()=0 THEN NULL ELSE
                    (SELECT nspname FROM pg_catalog.pg_namespace WHERE oid=pg_catalog.pg_my_temp_schema()) END AS temp""")).mappings().one()
                expected_path = ["pg_catalog", schema] + ([path_state["temp"]] if path_state["temp"] else [])
                if list(path_state["paths"]) != expected_path:
                    raise AllFreeGuardError(status_code=503, detail="Проверка заявки временно недоступна")
                private_schema = capability_schema_name(schema)
                quoted_private = db.get_bind().dialect.identifier_preparer.quote_schema(private_schema)
                qualified_function = f'{quoted_private}.all_free_pending_exists(integer)'
                integrity = db.execute(text("""
                    SELECT p.prosecdef
                       AND (p.proowner = r.relowner OR EXISTS (
                         SELECT 1 FROM pg_catalog.pg_proc decision JOIN pg_catalog.pg_roles cap ON cap.oid=decision.proowner
                         WHERE decision.oid=pg_catalog.to_regprocedure(:decision_function)
                           AND decision.proowner=p.proowner AND decision.prosecdef
                           AND decision.prokind='f' AND decision.provolatile='v'
                           AND pg_catalog.cardinality(decision.proconfig)=2
                           AND 'search_path=pg_catalog'=ANY(decision.proconfig)
                           AND 'row_security=on'=ANY(decision.proconfig)
                           AND NOT cap.rolcanlogin AND NOT cap.rolsuper AND NOT cap.rolbypassrls
                           AND NOT cap.rolcreaterole AND NOT cap.rolcreatedb AND NOT cap.rolreplication
                           AND NOT pg_catalog.pg_has_role(CURRENT_USER,cap.oid,'MEMBER')
                           AND NOT EXISTS (SELECT 1 FROM pg_catalog.pg_roles inherited
                             WHERE inherited.oid<>cap.oid AND pg_catalog.pg_has_role(cap.oid,inherited.oid,'MEMBER'))
                           AND pg_catalog.has_function_privilege(CURRENT_USER,decision.oid,'EXECUTE')
                           AND NOT EXISTS (SELECT 1 FROM pg_catalog.aclexplode(COALESCE(decision.proacl,pg_catalog.acldefault('f',decision.proowner))) x
                             WHERE x.grantee NOT IN (decision.proowner,(SELECT oid FROM pg_catalog.pg_roles WHERE rolname=CURRENT_USER))
                               OR (x.grantee<>decision.proowner AND (x.privilege_type<>'EXECUTE' OR x.is_grantable)))
                       ))
                       AND p.prokind = 'f' AND p.provolatile = 'v'
                       AND r.relkind IN ('r', 'p') AND v.relkind IN ('r', 'p')
                       AND r.relrowsecurity
                       AND p.prorettype = 'pg_catalog.bool'::pg_catalog.regtype
                       AND pg_catalog.cardinality(p.proconfig) = 2
                       AND 'search_path=pg_catalog' = ANY(COALESCE(p.proconfig, ARRAY[]::text[]))
                       AND 'row_security=on' = ANY(COALESCE(p.proconfig, ARRAY[]::text[]))
                       AND pg_catalog.to_regclass('visits')::oid = v.oid
                       AND pg_catalog.to_regclass('all_free_requests')::oid = r.oid
                       AND pg_catalog.to_regprocedure(:qualified_function)::oid = p.oid
                       AND NOT pg_catalog.has_schema_privilege(CURRENT_USER, n.oid, 'CREATE')
                       AND private_ns.nspowner=n.nspowner
                       AND pg_catalog.has_schema_privilege(CURRENT_USER,private_ns.oid,'USAGE')
                       AND NOT pg_catalog.has_schema_privilege(CURRENT_USER,private_ns.oid,'CREATE')
                       AND pg_catalog.has_function_privilege(CURRENT_USER, p.oid, 'EXECUTE')
                       AND NOT EXISTS (
                           SELECT 1 FROM pg_catalog.aclexplode(
                             COALESCE(p.proacl, pg_catalog.acldefault('f', p.proowner))) a
                           WHERE a.grantee NOT IN (p.proowner,(SELECT oid FROM pg_catalog.pg_roles WHERE rolname=CURRENT_USER))
                              OR (a.grantee<>p.proowner AND (a.privilege_type<>'EXECUTE' OR a.is_grantable))
                       )
                       AND NOT EXISTS (
                           SELECT 1 FROM pg_catalog.aclexplode(
                             COALESCE(private_ns.nspacl, pg_catalog.acldefault('n', private_ns.nspowner))) a
                           WHERE a.privilege_type='CREATE' AND a.grantee<>private_ns.nspowner
                       )
                       AND NOT EXISTS (
                           SELECT 1 FROM pg_catalog.aclexplode(
                             COALESCE(n.nspacl, pg_catalog.acldefault('n', n.nspowner))) a
                           WHERE a.privilege_type = 'CREATE'
                             AND a.grantee NOT IN (n.nspowner, p.proowner)
                       )
                       AND NOT EXISTS (
                           SELECT 1 FROM pg_catalog.pg_roles candidate
                           WHERE NOT candidate.rolsuper
                             AND candidate.oid NOT IN (n.nspowner, p.proowner)
                             AND ((pg_catalog.pg_has_role(candidate.oid, n.nspowner, 'MEMBER')
                                   AND NOT (candidate.rolname=ANY(:trusted_members)))
                               OR (pg_catalog.pg_has_role(candidate.oid, p.proowner, 'MEMBER')
                                   AND (p.proowner<>n.nspowner OR NOT (candidate.rolname=ANY(:trusted_members)))))
                       )
                       AND NOT EXISTS (SELECT 1 FROM pg_catalog.unnest(CAST(:trusted_members AS text[])) expected(name)
                         WHERE NOT EXISTS (SELECT 1 FROM pg_catalog.pg_roles candidate
                           WHERE candidate.rolname=expected.name AND NOT candidate.rolsuper
                             AND NOT candidate.rolbypassrls AND NOT candidate.rolcreaterole
                             AND NOT candidate.rolcreatedb AND NOT candidate.rolreplication
                             AND candidate.oid<>n.nspowner
                             AND pg_catalog.pg_has_role(candidate.oid,n.nspowner,'MEMBER')))
                       AND (CAST(:expected_owner AS text) IS NULL OR schema_owner.rolname=:expected_owner)
                       AND (CAST(:expected_runtime AS text) IS NULL OR CURRENT_USER=:expected_runtime)
                       AND (schema_owner.rolsuper OR NOT schema_owner.rolcanlogin)
                       AND (function_owner.rolsuper OR NOT function_owner.rolcanlogin)
                    FROM pg_catalog.pg_namespace n
                    JOIN pg_catalog.pg_class v ON v.relnamespace=n.oid AND v.relname='visits'
                    JOIN pg_catalog.pg_class r ON r.relnamespace=n.oid AND r.relname='all_free_requests'
                    JOIN pg_catalog.pg_namespace private_ns ON private_ns.nspname=:private_schema
                    JOIN pg_catalog.pg_proc p ON p.pronamespace=private_ns.oid
                       AND p.proname='all_free_pending_exists' AND p.proargtypes='23'::oidvector
                    JOIN pg_catalog.pg_roles schema_owner ON schema_owner.oid=n.nspowner
                    JOIN pg_catalog.pg_roles function_owner ON function_owner.oid=p.proowner
                    WHERE n.nspname=:schema
                """), {"schema": schema, "private_schema": private_schema, "qualified_function": qualified_function,
                       "decision_function": f"{quoted_private}.decide_all_free(integer,text,text,integer,bigint,integer,integer,integer,bigint,bigint,bigint)",
                       "trusted_members": list(members), "expected_owner": settings.TRUSTED_DB_SCHEMA_OWNER,
                       "expected_runtime": settings.TRUSTED_DB_RUNTIME_ROLE}).scalar_one_or_none()
                if integrity is not True:
                    raise AllFreeGuardError(status_code=503, detail="Проверка заявки временно недоступна")
                if not _pg_role_profile_is_safe(db, schema, private_schema):
                    raise AllFreeGuardError(status_code=503, detail="Проверка заявки временно недоступна")
            elif dialect == "sqlite":
                # A zero-row UPDATE starts/reserves a writer even if no row
                # exists. SQLITE_BUSY[_SNAPSHOT] must propagate as denial.
                db.execute(text("UPDATE visits SET id=id WHERE 0"))
                exists = db.execute(text("""
                    SELECT 1 FROM sqlite_master
                    WHERE type='table' AND name='all_free_requests'
                """)).first()
                if exists is None:
                    raise AllFreeGuardError(status_code=503, detail="Проверка заявки временно недоступна")
            else:
                raise AllFreeGuardError(status_code=503, detail="Проверка заявки временно недоступна")

            locked = (db.query(Visit.id).filter(Visit.id == visit_id)
                      .with_for_update().first())
            if locked is None:
                raise AllFreeGuardError(status_code=404, detail="Визит не найден")
            # This must remain a distinct statement AFTER the Visit lock.
            if dialect == "postgresql":
                pending = db.execute(
                    text(f"SELECT {quoted_private}.all_free_pending_exists(CAST(:visit_id AS integer))"),
                    {"visit_id": visit_id},
                ).scalar_one()
                if type(pending) is not bool:
                    raise AllFreeGuardError(status_code=503, detail="Проверка заявки временно недоступна")
                # The capability now holds ACCESS SHARE on all three tables;
                # recheck role policies after those locks so a concurrent
                # ALTER POLICY cannot slip between validation and use.
                if not _pg_role_profile_is_safe(db, schema, private_schema):
                    raise AllFreeGuardError(status_code=503, detail="Проверка заявки временно недоступна")
            else:
                pending = (db.query(AllFreeRequest.id)
                           .filter(AllFreeRequest.visit_id == visit_id,
                                   AllFreeRequest.status == "pending")
                           .first()) is not None
            if pending:
                raise PendingAllFreeError(status_code=409, detail="Заявка All Free ожидает решения")
        except SQLAlchemyError as exc:
            raise AllFreeGuardError(status_code=503, detail="Проверка заявки временно недоступна") from exc


def require_all_free_decision_capability(db: Session, visit_id: int) -> str | None:
    """Check the pending decision primitive inside the caller's locked group.

    The caller must already hold the full sorted financial closure and receipt
    mutex, and call this before changing ORM state. This is a capability check,
    not an authorization, baseline check, re-quote or transaction boundary.
    PostgreSQL returns a quoted private schema; SQLite uses its local service
    implementation and returns None. The caller must roll back on failure.
    """
    try:
        lock_visit_without_pending(db, visit_id)
    except PendingAllFreeError:
        pass
    else:
        raise AllFreeGuardError(status_code=409, detail="Ожидающая заявка не найдена")
    dialect = db.get_bind().dialect
    if dialect.name == "sqlite":
        return None
    if dialect.name != "postgresql":
        raise AllFreeGuardError(status_code=503, detail="Проверка заявки временно недоступна")
    schema = dialect.default_schema_name
    private = dialect.identifier_preparer.quote_identifier(capability_schema_name(schema))
    visibility = f"{private}.all_free_pending_exists(integer)"
    decision = f"{private}.decide_all_free(integer,text,text,integer,bigint,integer,integer,integer,bigint,bigint,bigint)"
    try:
        # lock_visit_without_pending already checked the complete decision
        # configuration whenever these functions share a non-table owner.
        # Refuse the migration's unprovisioned table-owner configuration.
        valid = db.execute(text("""SELECT p.proowner=d.proowner AND p.proowner<>r.relowner
          FROM pg_catalog.pg_proc p JOIN pg_catalog.pg_proc d ON d.oid=pg_catalog.to_regprocedure(:decision)
          JOIN pg_catalog.pg_class r ON r.oid=pg_catalog.to_regclass(:requests)
          WHERE p.oid=pg_catalog.to_regprocedure(:visibility)"""),
          {"decision": decision, "visibility": visibility,
           "requests": f"{dialect.identifier_preparer.quote_schema(schema)}.all_free_requests"}).scalar_one_or_none()
        if valid is not True:
            raise AllFreeGuardError(status_code=503, detail="Решение временно недоступно")
    except SQLAlchemyError as exc:
        raise AllFreeGuardError(status_code=503, detail="Решение временно недоступно") from exc
    return private
