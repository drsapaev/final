"""Provision the 0123 conservative guard for explicit trusted roles only.

Run by a database operator with traffic drained. No provider I/O occurs here.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from sqlalchemy import create_engine, text

sys.path.insert(0, str(Path(__file__).resolve().parent))
from provision_capability_namespace import (
    capability_schema_name,
    merge_namespace_roles,
    validate_namespace,
)


class ProvisionError(RuntimeError):
    pass


def require(value, message):
    if not value:
        raise ProvisionError(message)


def provision(engine, *, schema: str, expected_owner: str, backend_role: str, capability_role: str,
              trusted_owner_members: tuple[str, ...] = ()) -> None:
    require(engine.dialect.name == "postgresql", "PostgreSQL required")
    require(all(isinstance(x, str) and x and "\x00" not in x for x in (schema, expected_owner, backend_role, capability_role)), "Explicit names required")
    require(backend_role != capability_role and backend_role.lower() not in {"anon", "authenticated", "public"}, "Distinct trusted roles required")
    quote = engine.dialect.identifier_preparer.quote_identifier
    qs, qb, qc = map(quote, (schema, backend_role, capability_role))
    qp = quote(capability_schema_name(schema))
    with engine.begin() as db:
        db.execute(text("SET LOCAL search_path=pg_catalog"))
        role_rows = db.execute(text("""
          SELECT oid,rolname,rolcanlogin,rolsuper,rolbypassrls,rolcreaterole,rolcreatedb,rolreplication
          FROM pg_catalog.pg_roles WHERE rolname IN (:backend,:cap)
        """), {"backend": backend_role, "cap": capability_role}).mappings().all()
        roles = {r["rolname"]: r for r in role_rows}
        require(set(roles) == {backend_role, capability_role}, "Roles unavailable")
        backend, cap = roles[backend_role], roles[capability_role]
        require(backend["rolcanlogin"] and not cap["rolcanlogin"], "Expected LOGIN backend and NOLOGIN capability")
        require(all(not r[k] for r in role_rows for k in ("rolsuper", "rolbypassrls", "rolcreaterole", "rolcreatedb", "rolreplication")), "Elevated role forbidden")
        unsafe = db.execute(text("""
          SELECT EXISTS (SELECT 1 FROM pg_catalog.pg_roles x WHERE x.oid NOT IN (:backend,:cap)
            AND (pg_catalog.pg_has_role(:backend,x.oid,'MEMBER') OR pg_catalog.pg_has_role(:cap,x.oid,'MEMBER')
              OR (NOT x.rolsuper AND (pg_catalog.pg_has_role(x.oid,:backend,'MEMBER') OR pg_catalog.pg_has_role(x.oid,:cap,'MEMBER')))))
            OR pg_catalog.pg_has_role(:backend,:cap,'MEMBER') OR pg_catalog.pg_has_role(:cap,:backend,'MEMBER')
        """), {"backend": backend["oid"], "cap": cap["oid"]}).scalar_one()
        require(not unsafe, "Unsafe role memberships")
        ns = db.execute(text("""
          SELECT n.oid,n.nspowner,o.rolname AS owner_name,o.rolsuper,o.rolcanlogin,
            pg_catalog.has_schema_privilege(:backend,n.oid,'CREATE') AS backend_create,
            pg_catalog.has_schema_privilege(:cap,n.oid,'CREATE') AS cap_create,
            EXISTS (SELECT 1 FROM pg_catalog.aclexplode(COALESCE(n.nspacl,pg_catalog.acldefault('n',n.nspowner))) a
              WHERE a.privilege_type='CREATE' AND a.grantee<>n.nspowner) AS other_create
          FROM pg_catalog.pg_namespace n JOIN pg_catalog.pg_roles o ON o.oid=n.nspowner WHERE n.nspname=:schema
        """), {"schema": schema, "backend": backend_role, "cap": capability_role}).mappings().one_or_none()
        require(ns is not None and ns["owner_name"] == expected_owner
                and (ns["rolsuper"] or not ns["rolcanlogin"]), "Trusted schema owner required")
        require(not ns["backend_create"] and not ns["cap_create"] and not ns["other_create"], "Untrusted schema CREATE")
        merge_namespace_roles(db, schema, expected_owner=ns["owner_name"], backend_roles=(backend_role,),
                              capability_owner_roles=(capability_role,), trusted_owner_members=trusted_owner_members)
        tables = ("provider_reconciliation_events", "click_callback_receipts", "provider_reconciliation_mutex")
        db.exec_driver_sql("LOCK TABLE " + ", ".join(f"{qs}.{quote(x)}" for x in tables) + " IN ACCESS EXCLUSIVE MODE")
        details = db.execute(text("""
          SELECT c.relname,c.relowner,c.relrowsecurity,c.relforcerowsecurity FROM pg_catalog.pg_class c
          WHERE c.relnamespace=:namespace AND c.relname=ANY(:names) AND c.relkind='r'
        """), {"namespace": ns["oid"], "names": list(tables)}).mappings().all()
        require(len(details) == 3 and all(x["relowner"] == ns["nspowner"] and x["relrowsecurity"] for x in details), "Expected trusted RLS tables")
        require(all(x["relforcerowsecurity"] for x in details if x["relname"] != "provider_reconciliation_events"), "Expected forced RLS")
        caller = db.execute(text("SELECT oid,rolsuper FROM pg_catalog.pg_roles WHERE rolname=CURRENT_USER")).mappings().one()
        require(caller["rolsuper"] or caller["oid"] == ns["nspowner"], "Trusted owner required")
        db.exec_driver_sql(f"GRANT USAGE ON SCHEMA {qs} TO {qc}, {qb}")
        for table, col in (("provider_reconciliation_events", "id"), ("click_callback_receipts", "phase"), ("provider_reconciliation_mutex", "id")):
            db.exec_driver_sql(f"GRANT SELECT ({quote(col)}) ON {qs}.{quote(table)} TO {qc}")
            ensure_policy(db, schema, table, "reconciliation_cap_select", "SELECT", qc, cap["oid"], "true", None)
        db.exec_driver_sql(f"GRANT UPDATE (id) ON {qs}.provider_reconciliation_mutex TO {qc}")
        ensure_policy(db, schema, "provider_reconciliation_mutex", "reconciliation_cap_update", "UPDATE", qc, cap["oid"], "true", "false")
        db.exec_driver_sql(f"GRANT CREATE ON SCHEMA {qp} TO {qc}")
        for function in ("reconciliation_mutex_lock()", "reconciliation_pending_guard()"):
            db.exec_driver_sql(f"ALTER FUNCTION {qp}.{function} OWNER TO {qc}")
        db.exec_driver_sql(f"REVOKE CREATE ON SCHEMA {qp} FROM {qc}")
        db.exec_driver_sql(f"GRANT EXECUTE ON FUNCTION {qp}.reconciliation_pending_guard() TO {qb}")
        validate_namespace(db, schema, expected_owner=ns["owner_name"], trusted_owner_members=trusted_owner_members)


def ensure_policy(db, schema, table, name, command, quoted_role, role_oid, qual, checked):
    row = db.execute(text("""
      SELECT p.polcmd,p.polpermissive,p.polroles,pg_catalog.pg_get_expr(p.polqual,p.polrelid) AS qual,
        pg_catalog.pg_get_expr(p.polwithcheck,p.polrelid) AS checked
      FROM pg_catalog.pg_policy p JOIN pg_catalog.pg_class c ON c.oid=p.polrelid
      JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace
      WHERE n.nspname=:schema AND c.relname=:table AND p.polname=:name
    """), {"schema": schema, "table": table, "name": name}).mappings().one_or_none()
    if row:
        require(row["polcmd"] == {"SELECT": "r", "UPDATE": "w"}[command] and row["polpermissive"]
                and list(row["polroles"]) == [role_oid] and row["qual"] == qual and row["checked"] == checked,
                "Existing policy differs")
        return
    q = db.dialect.identifier_preparer.quote_identifier
    check = f" WITH CHECK ({checked})" if checked is not None else ""
    db.exec_driver_sql(f"CREATE POLICY {q(name)} ON {q(schema)}.{q(table)} FOR {command} TO {quoted_role} USING ({qual}){check}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--schema", required=True)
    parser.add_argument("--owner", required=True)
    parser.add_argument("--backend-role", required=True)
    parser.add_argument("--capability-role", required=True)
    parser.add_argument("--trusted-owner-member", action="append", default=[])
    args = parser.parse_args()
    engine = None
    try:
        engine = create_engine(os.environ["DATABASE_URL"])
        provision(engine, schema=args.schema, expected_owner=args.owner, backend_role=args.backend_role, capability_role=args.capability_role,
                  trusted_owner_members=tuple(args.trusted_owner_member))
    except Exception as exc:  # noqa: BLE001 - connection details must not enter logs
        print(f"Reconciliation provisioning failed ({type(exc).__name__})")
        return 1
    finally:
        if engine:
            engine.dispose()
    print("Reconciliation capability provisioned")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
