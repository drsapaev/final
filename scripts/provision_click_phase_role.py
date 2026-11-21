"""Provision explicit least-privilege Click issuance access; traffic drained.

This never configures provider credentials, issues URLs or contacts a provider.
It is an operator action, not an application startup or migration step.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from sqlalchemy import create_engine, text

sys.path.insert(0, str(Path(__file__).resolve().parent))
from provision_capability_namespace import _validate_owner_members


class ProvisionError(RuntimeError):
    pass


def require(ok: object, reason: str) -> None:
    if not ok:
        raise ProvisionError(reason)


def provision(engine, *, schema: str, owner: str, backend_role: str,
              trusted_owner_members: tuple[str, ...] = ()) -> None:
    require(engine.dialect.name == "postgresql", "PostgreSQL required")
    require(all(isinstance(x, str) and x and "\x00" not in x for x in (schema, owner, backend_role)), "Explicit names required")
    require(backend_role.lower() not in {"public", "anon", "authenticated"} and backend_role != owner, "Restricted backend role required")
    quote = engine.dialect.identifier_preparer.quote_identifier
    qs, qb = quote(schema), quote(backend_role)
    tables = ("provider_attempts", "provider_attempt_visits", "provider_active_visit_reservations", "click_issued_attempts", "click_prepares")
    with engine.begin() as db:
        db.execute(text("SET LOCAL search_path=pg_catalog"))
        identity = db.execute(text("""
          SELECT CURRENT_USER AS caller,n.oid AS ns,n.nspowner,o.oid AS owner_oid,a.oid AS actor_oid,
            o.rolsuper AS owner_super,o.rolcanlogin AS owner_login,a.rolcanlogin,
            pg_catalog.pg_has_role(CURRENT_USER,o.oid,'USAGE') AS owner_access,
            a.rolsuper OR a.rolbypassrls OR a.rolcreaterole OR a.rolcreatedb OR a.rolreplication AS elevated,
            pg_catalog.has_schema_privilege(a.oid,n.oid,'CREATE') AS actor_create,
            EXISTS (SELECT 1 FROM pg_catalog.aclexplode(COALESCE(n.nspacl,pg_catalog.acldefault('n',n.nspowner))) acl
              WHERE acl.privilege_type='CREATE' AND acl.grantee<>n.nspowner) AS other_create
          FROM pg_catalog.pg_namespace n,pg_catalog.pg_roles o,pg_catalog.pg_roles a
          WHERE n.nspname=:schema AND o.rolname=:owner AND a.rolname=:actor
        """), {"schema": schema, "owner": owner, "actor": backend_role}).mappings().one_or_none()
        require(identity is not None and identity["owner_access"] and identity["owner_oid"] == identity["nspowner"], "Trusted schema owner required")
        require(identity["owner_super"] or not identity["owner_login"], "Trusted schema owner required")
        _validate_owner_members(db, identity["owner_oid"], trusted_owner_members)
        require(identity["rolcanlogin"] and not identity["elevated"] and not identity["actor_create"] and not identity["other_create"], "Unsafe backend or schema")
        unsafe = db.execute(text("""
          SELECT EXISTS (SELECT 1 FROM pg_catalog.pg_roles r WHERE r.oid<>:actor AND
            (pg_catalog.pg_has_role(:actor,r.oid,'MEMBER') OR
             (NOT r.rolsuper AND pg_catalog.pg_has_role(r.oid,:actor,'MEMBER'))))
        """), {"actor": identity["actor_oid"]}).scalar_one()
        require(not unsafe, "Unsafe role membership")
        db.exec_driver_sql("LOCK TABLE " + ", ".join(f"{qs}.{quote(t)}" for t in tables) + " IN ACCESS EXCLUSIVE MODE")
        found = db.execute(text("""
          SELECT c.oid,c.relname,c.relowner,c.relrowsecurity,c.relforcerowsecurity
          FROM pg_catalog.pg_class c WHERE c.relnamespace=:ns AND c.relname=ANY(:names) AND c.relkind='r'
        """), {"ns": identity["ns"], "names": list(tables)}).mappings().all()
        require(len(found) == len(tables) and all(r["relowner"] == identity["owner_oid"] and r["relrowsecurity"] for r in found), "Trusted RLS tables required")
        require(all(r["relforcerowsecurity"] for r in found if r["relname"].startswith("click_")), "Forced RLS required")
        for row in found:
            table, oid = row["relname"], row["oid"]
            exposed = db.execute(text("""
              SELECT EXISTS (SELECT 1 FROM pg_catalog.pg_class c,
                LATERAL pg_catalog.aclexplode(COALESCE(c.relacl,pg_catalog.acldefault('r',c.relowner))) a
                WHERE c.oid=:oid AND a.grantee=0)
                OR EXISTS (SELECT 1 FROM pg_catalog.pg_attribute col,
                  LATERAL pg_catalog.aclexplode(col.attacl) a
                  WHERE col.attrelid=:oid AND col.attnum>0 AND NOT col.attisdropped AND a.grantee=0)
                OR EXISTS (SELECT 1 FROM pg_catalog.pg_roles r WHERE r.rolname IN ('anon','authenticated') AND
                  (pg_catalog.has_table_privilege(r.oid,:oid,'SELECT,INSERT,UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER')
                   OR pg_catalog.has_any_column_privilege(r.oid,:oid,'SELECT,INSERT,UPDATE,REFERENCES')))
            """), {"oid": oid}).scalar_one()
            require(not exposed, "Public or client role has Click phase privileges")
            restrictive = db.execute(text("""
              SELECT EXISTS (SELECT 1 FROM pg_catalog.pg_policy p WHERE p.polrelid=:oid AND NOT p.polpermissive
                AND p.polcmd IN ('r','a','w','*') AND EXISTS (SELECT 1 FROM pg_catalog.unnest(p.polroles) r
                  WHERE CASE WHEN r=0 THEN true ELSE pg_catalog.pg_has_role(:actor,r,'MEMBER') END))
            """), {"oid": oid, "actor": identity["actor_oid"]}).scalar_one()
            require(not restrictive, "Restrictive backend policy must be reconciled")
            for command, suffix in (("SELECT", "select"), ("INSERT", "insert")):
                name = f"click_phase_backend_{suffix}"
                existing = db.execute(text("""
                  SELECT p.polcmd,p.polpermissive,p.polroles,pg_catalog.pg_get_expr(p.polqual,p.polrelid) AS qual,
                    pg_catalog.pg_get_expr(p.polwithcheck,p.polrelid) AS checked
                  FROM pg_catalog.pg_policy p WHERE p.polrelid=:oid AND p.polname=:name
                """), {"oid": oid, "name": name}).mappings().one_or_none()
                if existing:
                    expected = ("r", "true", None) if command == "SELECT" else ("a", None, "true")
                    require(existing["polpermissive"] and list(existing["polroles"]) == [identity["actor_oid"]]
                            and (existing["polcmd"], existing["qual"], existing["checked"]) == expected, "Existing policy differs")
                else:
                    expression = "USING (true)" if command == "SELECT" else "WITH CHECK (true)"
                    db.exec_driver_sql(f"CREATE POLICY {name} ON {qs}.{quote(table)} FOR {command} TO {qb} {expression}")
            db.exec_driver_sql(f"GRANT SELECT, INSERT ON {qs}.{quote(table)} TO {qb}")
            require(not db.execute(text("SELECT pg_catalog.has_table_privilege(:actor,:oid,'UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER')"),
                                   {"actor": backend_role, "oid": oid}).scalar_one(), "Unsafe backend table grant")
            bad_columns = db.execute(text("""
              SELECT EXISTS (SELECT 1 FROM pg_catalog.pg_attribute a WHERE a.attrelid=:oid AND a.attnum>0 AND NOT a.attisdropped
                AND (pg_catalog.has_column_privilege(:actor,:oid,a.attnum,'REFERENCES')
                     OR (pg_catalog.has_column_privilege(:actor,:oid,a.attnum,'UPDATE')
                         AND NOT (:table='provider_attempts' AND a.attname IN ('status','updated_at')))))
            """), {"oid": oid, "actor": backend_role, "table": table}).scalar_one()
            require(not bad_columns, "Unsafe backend column grant")
        attempts = f"{qs}.provider_attempts"
        existing = db.execute(text("""
          SELECT p.polcmd,p.polpermissive,p.polroles,pg_catalog.pg_get_expr(p.polqual,p.polrelid) AS qual,
                 pg_catalog.pg_get_expr(p.polwithcheck,p.polrelid) AS checked
          FROM pg_catalog.pg_policy p WHERE p.polrelid=pg_catalog.to_regclass(:table) AND p.polname='click_phase_backend_update'
        """), {"table": attempts}).mappings().one_or_none()
        if existing:
            require(existing["polcmd"] == "w" and existing["polpermissive"] and list(existing["polroles"]) == [identity["actor_oid"]]
                    and existing["qual"] == "true" and existing["checked"] == "true", "Existing update policy differs")
        else:
            db.exec_driver_sql(f"CREATE POLICY click_phase_backend_update ON {attempts} FOR UPDATE TO {qb} USING (true) WITH CHECK (true)")
        db.exec_driver_sql(f"GRANT UPDATE (status,updated_at) ON {attempts} TO {qb}")
        db.exec_driver_sql(f"GRANT USAGE ON SCHEMA {qs} TO {qb}")
        for table in ("provider_attempts", "provider_attempt_visits", "click_issued_attempts", "click_prepares"):
            seq = f"{qs}.{quote(table + '_id_seq')}"
            require(not db.execute(text("SELECT pg_catalog.has_sequence_privilege(:actor,pg_catalog.to_regclass(:seq),'UPDATE')"),
                                   {"actor": backend_role, "seq": seq}).scalar_one(), "Unsafe sequence grant")
            db.exec_driver_sql(f"GRANT USAGE ON SEQUENCE {seq} TO {qb}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--schema", required=True)
    parser.add_argument("--owner", required=True)
    parser.add_argument("--backend-role", required=True)
    parser.add_argument("--trusted-owner-member", action="append", default=[])
    args = parser.parse_args()
    engine = None
    try:
        engine = create_engine(os.environ["DATABASE_URL"])
        provision(engine, schema=args.schema, owner=args.owner, backend_role=args.backend_role,
                  trusted_owner_members=tuple(args.trusted_owner_member))
    except Exception as exc:  # noqa: BLE001 - never log connection credentials
        print(f"Click phase provisioning failed ({type(exc).__name__})")
        return 1
    finally:
        if engine is not None:
            engine.dispose()
    print("Click phase backend role provisioned")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
