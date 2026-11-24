"""Provision benefit quotes and opt-in registrar decisions for the 0118 backend."""
from __future__ import annotations

import argparse
import importlib.util
import os
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

TABLES = ("encounter_benefit_applications", "encounter_benefit_allocations",
          "encounter_benefit_events", "encounter_benefit_visit_snapshots")


class ProvisionError(RuntimeError):
    pass


def _require(condition: object, message: str) -> None:
    if not condition:
        raise ProvisionError(message)


def provision(engine: Engine, *, schema: str, backend_role: str, capability_role: str, expected_owner: str,
              trusted_owner_members: tuple[str, ...] = (), enable_registrar_decisions: bool = False) -> None:
    _require(engine.dialect.name == "postgresql", "PostgreSQL required")
    _require(all(isinstance(x, str) and x and "\x00" not in x for x in (schema, backend_role, capability_role, expected_owner)), "Explicit schema, owner and roles required")
    _require(backend_role != capability_role and schema not in {"pg_catalog", "information_schema"}, "Distinct roles and trusted schema required")
    quote = engine.dialect.identifier_preparer.quote_identifier
    qs, qb, qc = map(quote, (schema, backend_role, capability_role))
    helper_path = Path(__file__).resolve().parent / "provision_capability_namespace.py"
    spec = importlib.util.spec_from_file_location("benefit_capability_namespace", helper_path)
    _require(spec is not None and spec.loader is not None, "Capability namespace helper unavailable")
    namespace_helper = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(namespace_helper)
    qp = quote(namespace_helper.capability_schema_name(schema))
    with engine.begin() as db:
        db.execute(text("SET LOCAL search_path=pg_catalog"))
        namespace_helper.merge_namespace_roles(db, schema, expected_owner=expected_owner, trusted_owner_members=trusted_owner_members,
                                               backend_roles=(backend_role,), capability_owner_roles=(capability_role,))
        roles = db.execute(text("""
          SELECT oid,rolname,rolcanlogin,rolsuper,rolbypassrls,rolcreaterole,rolcreatedb,rolreplication
          FROM pg_catalog.pg_roles WHERE rolname IN (:backend,:capability)
        """), {"backend": backend_role, "capability": capability_role}).mappings().all()
        by_name = {row["rolname"]: row for row in roles}
        _require(set(by_name) == {backend_role, capability_role}, "Both roles must exist")
        backend, cap = by_name[backend_role], by_name[capability_role]
        _require(backend["rolcanlogin"] and not cap["rolcanlogin"] and backend_role.lower() not in {"public","anon","authenticated"}, "Invalid backend or capability role")
        _require(all(not role[key] for role in roles for key in ("rolsuper","rolbypassrls","rolcreaterole","rolcreatedb","rolreplication")), "Administrative roles are forbidden")
        memberships = db.execute(text("""
          SELECT EXISTS (SELECT 1 FROM pg_catalog.pg_roles r WHERE NOT r.rolsuper AND r.oid<>:cap AND pg_catalog.pg_has_role(r.oid,:cap,'MEMBER'))
            OR EXISTS (SELECT 1 FROM pg_catalog.pg_roles r WHERE r.oid<>:cap AND pg_catalog.pg_has_role(:cap,r.oid,'MEMBER'))
            OR EXISTS (SELECT 1 FROM pg_catalog.pg_roles r WHERE NOT r.rolsuper AND r.oid<>:backend AND pg_catalog.pg_has_role(r.oid,:backend,'MEMBER'))
            OR EXISTS (SELECT 1 FROM pg_catalog.pg_roles r WHERE r.oid<>:backend AND pg_catalog.pg_has_role(:backend,r.oid,'MEMBER'))
        """), {"backend": backend["oid"], "cap": cap["oid"]}).scalar_one()
        _require(not memberships, "Role memberships must be reconciled")
        namespace = db.execute(text("""
          SELECT n.oid,n.nspowner,r.rolsuper,r.rolcanlogin,
            pg_catalog.has_schema_privilege(:backend,n.oid,'CREATE') AS backend_create,
            pg_catalog.has_schema_privilege(:cap,n.oid,'CREATE') AS cap_create,
            EXISTS (SELECT 1 FROM pg_catalog.aclexplode(COALESCE(n.nspacl,pg_catalog.acldefault('n',n.nspowner))) a
              WHERE a.privilege_type='CREATE' AND a.grantee<>n.nspowner) AS unexpected_create
          FROM pg_catalog.pg_namespace n JOIN pg_catalog.pg_roles r ON r.oid=n.nspowner WHERE n.nspname=:schema
        """), {"schema": schema, "backend": backend_role, "cap": capability_role}).mappings().one_or_none()
        _require(namespace is not None and (namespace["rolsuper"] or not namespace["rolcanlogin"]), "Untrusted schema owner")
        _require(not namespace["backend_create"] and not namespace["cap_create"] and not namespace["unexpected_create"], "Schema CREATE must remain owner-only")
        base_name, quote_name = f"{qp}.financial_probe_group(integer)", f"{qp}.encounter_benefit_quote(integer)"
        functions = db.execute(text("""
          SELECT p.oid,p.proname,p.proowner,p.prosecdef,p.provolatile,p.proconfig,
                 p.prorettype='pg_catalog.jsonb'::pg_catalog.regtype AS returns_json
          FROM pg_catalog.pg_proc p WHERE p.oid IN (pg_catalog.to_regprocedure(:base),pg_catalog.to_regprocedure(:quote))
        """), {"base": base_name, "quote": quote_name}).mappings().all()
        by_function = {row["proname"]: row for row in functions}
        _require(set(by_function) == {"financial_probe_group", "encounter_benefit_quote"}, "0118 and 0125 capabilities required")
        base, benefit = by_function["financial_probe_group"], by_function["encounter_benefit_quote"]
        _require(base["proowner"] == cap["oid"] and base["prosecdef"] and sorted(base["proconfig"] or []) == ["row_security=on","search_path=pg_catalog"], "Provision 0118 capability first")
        _require(benefit["prosecdef"] and benefit["provolatile"] == "s" and benefit["returns_json"]
                 and sorted(benefit["proconfig"] or []) == ["row_security=on","search_path=pg_catalog"], "Unsafe benefit capability")
        _require(db.execute(text("SELECT pg_catalog.has_function_privilege(:role,pg_catalog.to_regprocedure(:name),'EXECUTE')"),
                            {"role": backend_role, "name": base_name}).scalar_one(), "0118 backend grant required")
        db.exec_driver_sql("LOCK TABLE " + ", ".join(f"{qs}.{quote(table)}" for table in TABLES) + " IN ACCESS EXCLUSIVE MODE")
        rows = db.execute(text("""
          SELECT c.relname,c.relowner,c.relrowsecurity FROM pg_catalog.pg_class c
          WHERE c.relnamespace=:schema AND c.relname=ANY(:tables) AND c.relkind IN ('r','p')
        """), {"schema": namespace["oid"], "tables": list(TABLES)}).mappings().all()
        tables = {row["relname"]: row for row in rows}
        _require(set(tables) == set(TABLES) and all(r["relrowsecurity"] for r in rows), "Benefit evidence tables require RLS")
        caller = db.execute(text("SELECT oid,rolsuper FROM pg_catalog.pg_roles WHERE rolname=CURRENT_USER")).mappings().one()
        _require(caller["rolsuper"] or all(r["relowner"] == caller["oid"] for r in rows), "Caller must control benefit evidence tables")
        for table in TABLES:
            qt = f"{qs}.{quote(table)}"
            db.exec_driver_sql(f"GRANT SELECT ON {qt} TO {qc}")
            policy = db.execute(text("""
              SELECT p.polcmd,p.polpermissive,p.polroles,pg_catalog.pg_get_expr(p.polqual,p.polrelid) AS qual
              FROM pg_catalog.pg_policy p WHERE p.polrelid=pg_catalog.to_regclass(:table) AND p.polname='benefit_cap_select'
            """), {"table": qt}).mappings().one_or_none()
            if policy:
                _require(policy["polcmd"] == "r" and policy["polpermissive"] and list(policy["polroles"]) == [cap["oid"]] and policy["qual"] == "true", "Existing benefit policy differs")
            else:
                db.exec_driver_sql(f"CREATE POLICY benefit_cap_select ON {qt} FOR SELECT TO {qc} USING (true)")
        db.exec_driver_sql(f"GRANT CREATE ON SCHEMA {qp} TO {qc}")
        db.exec_driver_sql(f"ALTER FUNCTION {quote_name} OWNER TO {qc}")
        db.exec_driver_sql(f"REVOKE CREATE ON SCHEMA {qp} FROM {qc}")
        db.exec_driver_sql(f"GRANT EXECUTE ON FUNCTION {quote_name} TO {qb}")
        if enable_registrar_decisions:
            decision = f"{qp}.approve_registrar_benefit(integer,integer,integer,bigint,text)"
            safe = db.execute(text("""
              SELECT p.proowner=:owner AND p.prosecdef AND p.prokind='f' AND p.provolatile='v'
                AND p.prorettype='pg_catalog.jsonb'::pg_catalog.regtype AND pg_catalog.cardinality(p.proconfig)=3
                AND 'search_path=pg_catalog'=ANY(p.proconfig) AND 'row_security=off'=ANY(p.proconfig)
                AND 'extra_float_digits=3'=ANY(p.proconfig)
                AND NOT r.rolcanlogin AND NOT r.rolsuper AND NOT r.rolbypassrls
                AND NOT r.rolcreaterole AND NOT r.rolcreatedb AND NOT r.rolreplication
                AND NOT EXISTS (SELECT 1 FROM pg_catalog.aclexplode(COALESCE(p.proacl,pg_catalog.acldefault('f',p.proowner))) acl
                  WHERE acl.grantee NOT IN (:owner,:backend) OR (acl.grantee=:backend AND acl.is_grantable))
                AND (SELECT count(*)=5 AND COALESCE(bool_and(c.relowner=:owner AND c.relrowsecurity AND NOT c.relforcerowsecurity
                  AND NOT pg_catalog.has_any_column_privilege(CAST(:backend AS oid),c.oid,'INSERT,UPDATE')
                  AND NOT pg_catalog.has_table_privilege(CAST(:backend AS oid),c.oid,'DELETE,TRUNCATE,TRIGGER')),false)
                  FROM pg_catalog.pg_class c WHERE c.relnamespace=:schema AND c.relname=ANY(:tables))
              FROM pg_catalog.pg_proc p JOIN pg_catalog.pg_roles r ON r.oid=p.proowner
              WHERE p.oid=pg_catalog.to_regprocedure(:decision)
            """), {"owner": namespace["nspowner"], "backend": backend["oid"], "schema": namespace["oid"],
                   "tables": [*TABLES, "encounter_benefit_quota_anchors"], "decision": decision}).scalar_one_or_none()
            _require(safe is True, "Unsafe registrar benefit decision capability")
            db.exec_driver_sql(f"GRANT EXECUTE ON FUNCTION {decision} TO {qb}")
        namespace_helper.validate_namespace(db, schema, expected_owner=expected_owner, trusted_owner_members=trusted_owner_members)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--schema", required=True)
    parser.add_argument("--backend-role", required=True)
    parser.add_argument("--capability-role", required=True)
    parser.add_argument("--schema-owner", required=True)
    parser.add_argument("--trusted-owner-member", action="append", default=[])
    parser.add_argument("--enable-registrar-decisions", action="store_true")
    args = parser.parse_args()
    url = os.environ.get("DATABASE_URL")
    _require(bool(url), "DATABASE_URL must be configured")
    engine = create_engine(url)
    try:
        provision(engine, schema=args.schema, backend_role=args.backend_role, capability_role=args.capability_role, expected_owner=args.schema_owner,
                  trusted_owner_members=tuple(args.trusted_owner_member), enable_registrar_decisions=args.enable_registrar_decisions)
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
