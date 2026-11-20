"""Provision the narrow 0116 trigger owner on a trusted PostgreSQL schema.

Traffic must be drained. The role names are explicit and never inferred from
production. This script does not configure public-token reads or reissue.
"""
from __future__ import annotations

import argparse
import importlib.util
import os
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine


class ProvisionError(RuntimeError):
    pass


def _require(condition: object, message: str) -> None:
    if not condition:
        raise ProvisionError(message)


def _reviewed_body(quoted_schema: str, private_schema: str, *, patient_lock: bool = False) -> str:
    path = Path(__file__).resolve().parents[1] / "backend/alembic/versions/0116_patient_owner_confirmation.py"
    spec = importlib.util.spec_from_file_location("confirmation_migration_0116", path)
    if spec is None or spec.loader is None:
        raise ProvisionError("Reviewed migration unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    factory = module.patient_lock_function_body if patient_lock else module.owner_function_body
    return factory(quoted_schema, private_schema)


def _namespace_helper():
    path = Path(__file__).resolve().parent / "provision_capability_namespace.py"
    spec = importlib.util.spec_from_file_location("confirmation_capability_namespace", path)
    if spec is None or spec.loader is None:
        raise ProvisionError("Reviewed capability namespace helper unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def provision(engine: Engine, schema: str, capability_role: str, runtime_role: str, *,
              expected_owner: str, trusted_owner_members: tuple[str, ...] = ()) -> None:
    _require(engine.dialect.name == "postgresql", "PostgreSQL is required")
    _require(bool(schema) and bool(capability_role) and bool(runtime_role) and bool(expected_owner), "Explicit schema, owner and both roles are required")
    _require("\0" not in schema + capability_role + runtime_role + expected_owner and capability_role != runtime_role,
             "Invalid schema or roles")
    quote = engine.dialect.identifier_preparer.quote_identifier
    qs, qc, qr = quote(schema), quote(capability_role), quote(runtime_role)
    patients, visits = f"{qs}.patients", f"{qs}.visits"
    namespace = _namespace_helper()
    private = namespace.capability_schema_name(schema)
    qp = quote(private)
    function = f"{qp}.invalidate_patient_owner_confirmations()"
    patient_lock = f"{qp}.lock_confirmation_patient(pg_catalog.int4)"
    with engine.begin() as db:
        db.execute(text("SET LOCAL search_path=pg_catalog"))
        namespace.merge_namespace_roles(
            db, schema, expected_owner=expected_owner,
            backend_roles=(runtime_role,), capability_owner_roles=(capability_role,),
            trusted_owner_members=trusted_owner_members,
        )
        roles = db.execute(text("""
          SELECT oid,rolname,rolcanlogin,rolsuper,rolbypassrls,rolcreaterole,rolcreatedb,rolreplication
          FROM pg_catalog.pg_roles WHERE rolname IN (:cap,:runtime)
        """), {"cap": capability_role, "runtime": runtime_role}).mappings().all()
        by_name = {r["rolname"]: r for r in roles}
        _require(set(by_name) == {capability_role, runtime_role}, "Both existing roles are required")
        cap, runtime = by_name[capability_role], by_name[runtime_role]
        _require(not cap["rolcanlogin"] and not any(cap[k] for k in ("rolsuper", "rolbypassrls", "rolcreaterole", "rolcreatedb", "rolreplication")),
                 "Capability owner must be a nonadministrative NOLOGIN role")
        _require(runtime["rolcanlogin"] and not any(runtime[k] for k in ("rolsuper", "rolbypassrls", "rolcreaterole", "rolcreatedb", "rolreplication")),
                 "Runtime must be a nonadministrative LOGIN role")
        _require(not db.execute(text("""
          SELECT EXISTS(SELECT 1 FROM pg_catalog.pg_roles r
            WHERE NOT r.rolsuper AND r.oid<>:cap AND
              (pg_catalog.pg_has_role(r.oid,:cap,'MEMBER') OR pg_catalog.pg_has_role(:cap,r.oid,'MEMBER')))
        """), {"cap": cap["oid"]}).scalar_one(), "Capability role has unsafe memberships")
        ns = db.execute(text("SELECT oid,nspowner,nspacl FROM pg_catalog.pg_namespace WHERE nspname=:schema"), {"schema": schema}).mappings().first()
        _require(ns is not None and schema not in {"pg_catalog", "information_schema"}, "Trusted schema required")
        _require(not db.execute(text("""
          SELECT EXISTS (SELECT 1 FROM pg_catalog.aclexplode(COALESCE(nspacl,pg_catalog.acldefault('n',nspowner))) a
            WHERE privilege_type='CREATE' AND grantee<>nspowner)
          FROM pg_catalog.pg_namespace WHERE oid=:oid
        """), {"oid": ns["oid"]}).scalar_one(), "Unexpected schema CREATE grant")
        db.exec_driver_sql(f"LOCK TABLE {patients}, {visits} IN ACCESS EXCLUSIVE MODE")
        tables = db.execute(text("""
          SELECT c.oid,c.relname,c.relowner,c.relrowsecurity,c.relforcerowsecurity
          FROM pg_catalog.pg_class c WHERE c.relnamespace=:schema AND c.relname IN ('patients','visits') AND c.relkind IN ('r','p')
        """), {"schema": ns["oid"]}).mappings().all()
        tables = {t["relname"]: t for t in tables}
        _require(set(tables) == {"patients", "visits"} and tables["visits"]["relrowsecurity"], "RLS-enabled visit table required")
        trusted_owners = {ns["nspowner"], tables["patients"]["relowner"], tables["visits"]["relowner"]}
        _require(cap["oid"] not in trusted_owners and runtime["oid"] not in trusted_owners, "Capability and runtime cannot own schema or tables")
        _require(not db.execute(text("""
          SELECT EXISTS(SELECT 1 FROM pg_catalog.pg_roles r
            WHERE r.oid=ANY(:owners) AND NOT r.rolsuper AND r.rolcanlogin)
        """), {"owners": list(trusted_owners)}).scalar_one(), "Schema/table owners must be NOLOGIN or superuser")
        _require(not db.execute(text("""
          SELECT EXISTS(SELECT 1 FROM pg_catalog.pg_roles r
            WHERE NOT r.rolsuper AND r.oid<>ALL(:owners) AND
              ((pg_catalog.pg_has_role(r.oid,(:owners)[1],'MEMBER') AND r.rolname<>ALL(:allowed)) OR
               (pg_catalog.pg_has_role(r.oid,(:owners)[2],'MEMBER') AND
                ((:owners)[2]<>(:owners)[1] OR r.rolname<>ALL(:allowed))) OR
               (pg_catalog.pg_has_role(r.oid,(:owners)[3],'MEMBER') AND
                ((:owners)[3]<>(:owners)[1] OR r.rolname<>ALL(:allowed)))))
        """), {"owners": [ns["nspowner"], tables["patients"]["relowner"], tables["visits"]["relowner"]],
                 "allowed": list(trusted_owner_members)}).scalar_one(),
                 "Untrusted role can assume a schema or table owner")
        _require(not db.execute(text("""
          SELECT EXISTS(SELECT 1 FROM pg_catalog.pg_class c,
            LATERAL pg_catalog.aclexplode(COALESCE(c.relacl,pg_catalog.acldefault('r',c.relowner))) a
            WHERE c.oid=ANY(:tables) AND a.privilege_type='TRIGGER' AND a.grantee<>ALL(:owners))
        """), {"tables": [tables["patients"]["oid"], tables["visits"]["oid"]], "owners": list(trusted_owners)}).scalar_one(),
                 "Untrusted TRIGGER grant exists")
        _require(not db.execute(text("""
          SELECT EXISTS(SELECT 1 FROM pg_catalog.pg_trigger t JOIN pg_catalog.pg_proc p ON p.oid=t.tgfoid
            WHERE t.tgrelid=ANY(:tables) AND NOT t.tgisinternal AND p.proowner<>ALL(:owners))
        """), {"tables": [tables["patients"]["oid"], tables["visits"]["oid"]], "owners": list(trusted_owners | {cap["oid"]})}).scalar_one(),
                 "Untrusted existing trigger function")
        _require(not db.execute(text("""
          SELECT pg_catalog.has_table_privilege(:role,:visits,'SELECT,INSERT,UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER')
            OR pg_catalog.has_table_privilege(:role,:patients,'SELECT,INSERT,UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER')
        """), {"role": cap["oid"], "visits": tables["visits"]["oid"], "patients": tables["patients"]["oid"]}).scalar_one(),
                 "Capability owner has broad table access")
        allowed_select = ["id", "patient_id", "status", "confirmation_token", "reminder_generation"]
        allowed_update = ["confirmation_context_epoch", "confirmation_token", "confirmation_expires_at", "reminder_sent_at", "reminder_generation"]
        _require(not db.execute(text("""
          SELECT EXISTS(SELECT 1 FROM pg_catalog.pg_attribute a, LATERAL pg_catalog.aclexplode(a.attacl) x
            WHERE a.attrelid=ANY(:tables) AND a.attnum>0 AND NOT a.attisdropped AND x.grantee IN (0,:role)
              AND NOT (x.grantee=:role AND NOT x.is_grantable AND (
                (a.attrelid=:visits AND ((x.privilege_type='SELECT' AND a.attname=ANY(:sel)) OR
                                          (x.privilege_type='UPDATE' AND a.attname=ANY(:upd)))) OR
                (a.attrelid=:patient AND ((x.privilege_type='SELECT' AND a.attname IN ('id','is_deleted')) OR
                                           (x.privilege_type='UPDATE' AND a.attname='id'))))))
        """), {"tables": [tables["patients"]["oid"], tables["visits"]["oid"]], "role": cap["oid"],
                 "visits": tables["visits"]["oid"], "patient": tables["patients"]["oid"],
                 "sel": allowed_select, "upd": allowed_update}).scalar_one(),
                 "Unexpected patient/visit column grant")
        _require(not db.execute(text("""
          SELECT EXISTS (SELECT 1 FROM pg_catalog.pg_class c
            WHERE c.relowner=:role OR (c.oid NOT IN (:visits,pg_catalog.to_regclass(:seq)) AND EXISTS
              (SELECT 1 FROM pg_catalog.aclexplode(c.relacl) a WHERE a.grantee=:role)))
            OR EXISTS (SELECT 1 FROM pg_catalog.pg_attribute a, LATERAL pg_catalog.aclexplode(a.attacl) x
              WHERE a.attrelid NOT IN (:visits,:patient) AND x.grantee=:role)
            OR EXISTS (SELECT 1 FROM pg_catalog.pg_proc p WHERE p.proowner=:role
              AND p.oid NOT IN (pg_catalog.to_regprocedure(:function),pg_catalog.to_regprocedure(:patient_lock)))
        """), {"role": cap["oid"], "visits": tables["visits"]["oid"],
                 "patient": tables["patients"]["oid"], "seq": f"{qs}.visit_confirmation_generation_seq",
                 "function": function, "patient_lock": patient_lock}).scalar_one(),
                 "Capability role has unrelated ownership or grants")
        _require(not db.execute(text("""
          SELECT EXISTS(SELECT 1 FROM pg_catalog.pg_class c,
            LATERAL pg_catalog.aclexplode(COALESCE(c.relacl,pg_catalog.acldefault('S',c.relowner))) a
            WHERE c.oid=pg_catalog.to_regclass(:seq) AND a.grantee<>c.relowner
              AND NOT (a.grantee IN (:role,:runtime) AND a.privilege_type='USAGE' AND NOT a.is_grantable))
        """), {"seq": f"{qs}.visit_confirmation_generation_seq", "role": cap["oid"], "runtime": runtime["oid"]}).scalar_one(),
                 "Unexpected sequence grant")
        fn = db.execute(text("""
          SELECT oid,proowner,prosrc,prosecdef,proconfig FROM pg_catalog.pg_proc
          WHERE oid=pg_catalog.to_regprocedure(:name)
        """), {"name": function}).mappings().first()
        migration_schema = engine.dialect.identifier_preparer.quote_schema(schema)
        _require(fn is not None and fn["prosrc"] == _reviewed_body(migration_schema, private), "Trigger capability body differs from reviewed migration")
        _require(fn["proowner"] in trusted_owners | {cap["oid"]}, "Unexpected trigger function owner")
        expected_base = {"search_path=pg_catalog", "standard_conforming_strings=on"}
        config = set(fn["proconfig"] or ())
        _require((not fn["prosecdef"] and config == expected_base | {"row_security=off"})
                 or (fn["prosecdef"] and config == expected_base | {"row_security=on"}),
                 "Trigger capability configuration differs from reviewed policy")
        lock_fn = db.execute(text("""
          SELECT oid,proowner,prosrc,prosecdef,proconfig FROM pg_catalog.pg_proc
          WHERE oid=pg_catalog.to_regprocedure(:name)
        """), {"name": patient_lock}).mappings().first()
        _require(lock_fn is not None and lock_fn["proowner"] in trusted_owners | {cap["oid"]}
                 and lock_fn["prosrc"] == _reviewed_body(migration_schema, private, patient_lock=True),
                 "Patient lock capability differs from reviewed migration")
        lock_config = set(lock_fn["proconfig"] or ())
        _require((not lock_fn["prosecdef"] and lock_config == expected_base | {"row_security=off"})
                 or (lock_fn["prosecdef"] and lock_config == expected_base | {"row_security=on"}),
                 "Patient lock capability configuration differs from reviewed policy")
        _require(not db.execute(text("""
          SELECT EXISTS(SELECT 1 FROM pg_catalog.pg_proc p,
            LATERAL pg_catalog.aclexplode(COALESCE(p.proacl,pg_catalog.acldefault('f',p.proowner))) a
            WHERE p.oid=:fn AND a.grantee NOT IN (p.proowner,:cap,:runtime) AND a.privilege_type='EXECUTE')
        """), {"fn": lock_fn["oid"], "cap": cap["oid"], "runtime": runtime["oid"]}).scalar_one(),
                 "Unexpected patient lock EXECUTE grant")
        trigger_valid = db.execute(text("""
          SELECT t.tgenabled IN ('O','A') AND t.tgtype=17 AND t.tgqual IS NULL
            AND ARRAY(SELECT a.attname FROM pg_catalog.unnest(t.tgattr::smallint[]) x
              JOIN pg_catalog.pg_attribute a ON a.attrelid=t.tgrelid AND a.attnum=x ORDER BY a.attname)
                = ARRAY['is_deleted','user_id']::name[]
          FROM pg_catalog.pg_trigger t
          WHERE t.tgrelid=:patient AND t.tgname='trg_patient_owner_confirmation_context'
            AND t.tgfoid=:fn AND NOT t.tgisinternal
        """), {"patient": tables["patients"]["oid"], "fn": fn["oid"]}).scalar_one_or_none()
        _require(trigger_valid is True, "Patient owner trigger is missing, disabled, or altered")
        _require(not db.execute(text("""
          SELECT pg_catalog.has_table_privilege(:runtime,:patient,'TRUNCATE,TRIGGER')
            OR pg_catalog.has_table_privilege(:runtime,:visits,'TRUNCATE,TRIGGER')
            OR pg_catalog.has_parameter_privilege(:runtime,'session_replication_role','SET')
        """), {"runtime": runtime["oid"], "patient": tables["patients"]["oid"],
                 "visits": tables["visits"]["oid"]}).scalar_one(), "Runtime can bypass trigger execution")
        _require(not db.execute(text("""
          SELECT EXISTS(SELECT 1 FROM pg_catalog.pg_proc p,
            LATERAL pg_catalog.aclexplode(COALESCE(p.proacl,pg_catalog.acldefault('f',p.proowner))) a
            WHERE p.oid=:fn AND a.grantee NOT IN (p.proowner,:cap) AND a.privilege_type='EXECUTE')
        """), {"fn": fn["oid"], "cap": cap["oid"]}).scalar_one(), "Unexpected trigger function EXECUTE grant")
        _require(not db.execute(text("""
          SELECT EXISTS(SELECT 1 FROM pg_catalog.pg_policy p WHERE p.polrelid=:visits
            AND NOT p.polpermissive AND (0=ANY(p.polroles) OR :role=ANY(p.polroles)))
        """), {"visits": tables["visits"]["oid"], "role": cap["oid"]}).scalar_one(), "Restrictive capability policy would hide visits")
        _require(not db.execute(text("""
          SELECT EXISTS(SELECT 1 FROM pg_catalog.pg_policy p
            WHERE p.polrelid IN (:patient,:visits) AND NOT p.polpermissive
              AND (0=ANY(p.polroles) OR :cap=ANY(p.polroles) OR :runtime=ANY(p.polroles)))
        """), {"patient": tables["patients"]["oid"], "visits": tables["visits"]["oid"],
                 "cap": cap["oid"], "runtime": runtime["oid"]}).scalar_one(),
                 "Restrictive subject policy would hide rows")
        _require(not db.execute(text("""
          SELECT EXISTS(SELECT 1 FROM pg_catalog.pg_policy p WHERE p.polrelid=:patient
            AND p.polpermissive AND p.polcmd IN ('w','*') AND p.polname<>'owner_confirmation_patient_lock'
            AND (0=ANY(p.polroles) OR :cap=ANY(p.polroles)))
        """), {"patient": tables["patients"]["oid"], "cap": cap["oid"]}).scalar_one(),
                 "Another patient UPDATE policy applies to the lock capability")
        for name, command in (("owner_confirmation_role_select", "SELECT"), ("owner_confirmation_role_update", "UPDATE")):
            policy = db.execute(text("""
              SELECT p.polcmd,p.polpermissive,p.polroles,pg_catalog.pg_get_expr(p.polqual,p.polrelid) AS qual,
                     pg_catalog.pg_get_expr(p.polwithcheck,p.polrelid) AS checked
              FROM pg_catalog.pg_policy p WHERE p.polrelid=:visits AND p.polname=:name
            """), {"visits": tables["visits"]["oid"], "name": name}).mappings().first()
            if policy is None:
                check = " WITH CHECK (true)" if command == "UPDATE" else ""
                db.exec_driver_sql(f"CREATE POLICY {quote(name)} ON {visits} FOR {command} TO {qc} USING (true){check}")
            else:
                _require(policy["polcmd"] == ("r" if command == "SELECT" else "w") and policy["polpermissive"]
                         and policy["polroles"] == [cap["oid"]] and policy["qual"] == "true"
                         and policy["checked"] == (None if command == "SELECT" else "true"), "Existing policy differs from reviewed policy")
        for table, role, role_oid, name, command, check in (
            (patients, qc, cap["oid"], "owner_confirmation_patient_select", "SELECT", None),
            (patients, qc, cap["oid"], "owner_confirmation_patient_lock", "UPDATE", "false"),
            (patients, qr, runtime["oid"], "confirmation_backend_patient_select", "SELECT", None),
            (visits, qr, runtime["oid"], "confirmation_backend_visit_select", "SELECT", None),
        ):
            policy = db.execute(text("""
              SELECT p.polcmd,p.polpermissive,p.polroles,pg_catalog.pg_get_expr(p.polqual,p.polrelid) AS qual,
                     pg_catalog.pg_get_expr(p.polwithcheck,p.polrelid) AS checked
              FROM pg_catalog.pg_policy p WHERE p.polrelid=pg_catalog.to_regclass(:table) AND p.polname=:name
            """), {"table": table, "name": name}).mappings().first()
            if policy is None:
                check_sql = f" WITH CHECK ({check})" if check is not None else ""
                db.exec_driver_sql(f"CREATE POLICY {quote(name)} ON {table} FOR {command} TO {role} USING (true){check_sql}")
            else:
                _require(policy["polcmd"] == ("r" if command == "SELECT" else "w") and policy["polpermissive"]
                         and policy["polroles"] == [role_oid] and policy["qual"] == "true"
                         and policy["checked"] == check, "Existing subject policy differs from reviewed policy")
        db.exec_driver_sql(f"GRANT USAGE ON SCHEMA {qs} TO {qc}")
        db.exec_driver_sql(f"GRANT SELECT (id,patient_id,status,confirmation_token,reminder_generation) ON {visits} TO {qc}")
        db.exec_driver_sql(f"GRANT UPDATE (confirmation_context_epoch,confirmation_token,confirmation_expires_at,reminder_sent_at,reminder_generation) ON {visits} TO {qc}")
        db.exec_driver_sql(f"GRANT SELECT (id,is_deleted), UPDATE (id) ON {patients} TO {qc}")
        db.exec_driver_sql(f"GRANT SELECT ON {patients}, {visits} TO {qr}")
        db.exec_driver_sql(f"GRANT USAGE ON SEQUENCE {qs}.visit_confirmation_generation_seq TO {qc}")
        if fn["proowner"] != cap["oid"] or lock_fn["proowner"] != cap["oid"]:
            db.exec_driver_sql(f"GRANT CREATE ON SCHEMA {qp} TO {qc}")
            if fn["proowner"] != cap["oid"]:
                db.exec_driver_sql(f"ALTER FUNCTION {function} OWNER TO {qc}")
            if lock_fn["proowner"] != cap["oid"]:
                db.exec_driver_sql(f"ALTER FUNCTION {patient_lock} OWNER TO {qc}")
            db.exec_driver_sql(f"REVOKE CREATE ON SCHEMA {qp} FROM {qc}")
        for signature in (function, patient_lock):
            db.exec_driver_sql(f"ALTER FUNCTION {signature} SECURITY DEFINER")
            db.exec_driver_sql(f"ALTER FUNCTION {signature} SET row_security=on")
            db.exec_driver_sql(f"ALTER FUNCTION {signature} SET standard_conforming_strings=on")
        db.exec_driver_sql(f"REVOKE ALL ON FUNCTION {function} FROM PUBLIC, {qr}")
        db.exec_driver_sql(f"REVOKE ALL ON FUNCTION {patient_lock} FROM PUBLIC")
        db.exec_driver_sql(f"GRANT EXECUTE ON FUNCTION {patient_lock} TO {qr}")
        namespace.validate_namespace(db, schema, expected_owner=expected_owner,
                                     trusted_owner_members=trusted_owner_members)


def main() -> int:
    parser = argparse.ArgumentParser(description="Provision 0116 trigger capability; run with traffic drained")
    parser.add_argument("--schema", required=True)
    parser.add_argument("--schema-owner", required=True)
    parser.add_argument("--trusted-owner-member", action="append", default=[])
    parser.add_argument("--capability-role", required=True)
    parser.add_argument("--runtime-role", required=True)
    args = parser.parse_args()
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise ProvisionError("DATABASE_URL is required")
    engine = create_engine(url)
    try:
        provision(engine, args.schema, args.capability_role, args.runtime_role,
                  expected_owner=args.schema_owner, trusted_owner_members=tuple(args.trusted_owner_member))
    finally:
        engine.dispose()
    print("Confirmation trigger capability provisioned; public read capability is a separate step.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
