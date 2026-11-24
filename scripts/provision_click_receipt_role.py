"""Trusted-operator provisioning for encrypted Click receipts; no provider I/O."""
from __future__ import annotations

import argparse
import base64
import hmac
import os
import re
import sys
from pathlib import Path

from sqlalchemy import create_engine, text

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.services.click_receipt_service import (
    receipt_key_commitment,
    reconciliation_receipt_capability,
)
from provision_capability_namespace import _validate_owner_members


class ProvisionError(RuntimeError):
    pass


def _require(condition: object, message: str) -> None:
    if not condition:
        raise ProvisionError(message)


def provision(engine, *, schema: str, owner: str, role: str, version: str, key: bytes,
              trusted_owner_members: tuple[str, ...] = ()) -> None:
    """Create only reviewed grants and register one immutable key commitment."""
    _require(engine.dialect.name == "postgresql", "PostgreSQL required")
    _require(all(isinstance(s, str) and s and "\x00" not in s for s in (schema, owner, role, version)), "Explicit names required")
    _require(re.fullmatch(r"[a-z0-9][a-z0-9._-]{0,31}", version) is not None, "Invalid key version")
    _require(role.lower() not in {"public", "anon", "authenticated"}, "Reserved backend role")
    commitment = receipt_key_commitment(key)
    quote = engine.dialect.identifier_preparer.quote_identifier
    qs, qr = quote(schema), quote(role)
    tables = ("click_receipt_key_versions", "click_callback_receipts")
    with engine.begin() as db:
        db.execute(text("SET LOCAL search_path=pg_catalog"))
        identity = db.execute(text("""
          SELECT CURRENT_USER AS caller, n.oid AS namespace_oid, n.nspowner,
                 o.oid AS owner_oid, a.oid AS role_oid, a.rolcanlogin,
                 pg_catalog.pg_has_role(CURRENT_USER,o.oid,'USAGE') AS owner_access,
                 a.rolsuper OR a.rolbypassrls OR a.rolcreaterole OR a.rolcreatedb OR a.rolreplication AS elevated,
                 pg_catalog.has_schema_privilege(a.oid,n.oid,'CREATE') AS role_create
          FROM pg_catalog.pg_namespace n, pg_catalog.pg_roles o, pg_catalog.pg_roles a
          WHERE n.nspname=:schema AND o.rolname=:owner AND a.rolname=:role
        """), {"schema": schema, "owner": owner, "role": role}).mappings().first()
        _require(identity is not None and identity["owner_access"] and identity["nspowner"] == identity["owner_oid"], "Trusted schema owner required")
        _validate_owner_members(db, identity["owner_oid"], trusted_owner_members)
        _require(identity["rolcanlogin"] and not identity["elevated"] and not identity["role_create"] and role != owner, "Unsafe backend role")
        elevated = db.execute(text("""
          SELECT EXISTS (SELECT 1 FROM pg_catalog.pg_roles r WHERE
            ((r.rolsuper OR r.rolbypassrls OR r.rolcreaterole OR r.rolcreatedb OR r.rolreplication) AND pg_catalog.pg_has_role(:role,r.oid,'MEMBER'))
            OR (NOT r.rolsuper AND r.oid<>:role AND pg_catalog.pg_has_role(r.oid,:role,'MEMBER')))
        """), {"role": identity["role_oid"]}).scalar_one()
        _require(not elevated, "Unsafe inherited role")
        schema_bad = db.execute(text("""
          SELECT EXISTS (SELECT 1 FROM pg_catalog.pg_namespace n,
            LATERAL pg_catalog.aclexplode(COALESCE(n.nspacl,pg_catalog.acldefault('n',n.nspowner))) x
            WHERE n.oid=:ns AND x.privilege_type='CREATE' AND x.grantee<>n.nspowner)
        """), {"ns": identity["namespace_oid"]}).scalar_one()
        _require(not schema_bad, "Untrusted schema CREATE grant")
        db.exec_driver_sql("LOCK TABLE " + ", ".join(f"{qs}.{quote(t)}" for t in tables) + " IN ACCESS EXCLUSIVE MODE")
        capability_id = reconciliation_receipt_capability(db, schema, backend_role=role)
        rows = db.execute(text("""
          SELECT c.oid,c.relname,c.relowner,c.relrowsecurity,c.relforcerowsecurity FROM pg_catalog.pg_class c
          WHERE c.relnamespace=:ns AND c.relname IN ('click_receipt_key_versions','click_callback_receipts') AND c.relkind='r'
        """), {"ns": identity["namespace_oid"]}).mappings().all()
        _require(len(rows) == 2 and all(r["relowner"] == identity["owner_oid"] and r["relrowsecurity"] and r["relforcerowsecurity"] for r in rows), "Receipt tables or forced RLS unavailable")
        for row in rows:
            name, oid = row["relname"], row["oid"]
            allowed = {"SELECT", "INSERT"} if name == "click_callback_receipts" else {"SELECT"}
            acl = db.execute(text("""
              SELECT x.grantee,x.privilege_type,x.is_grantable FROM pg_catalog.pg_class c,
                LATERAL pg_catalog.aclexplode(COALESCE(c.relacl,pg_catalog.acldefault('r',c.relowner))) x WHERE c.oid=:oid
            """), {"oid": oid}).mappings().all()
            _require(all(x["grantee"] == identity["owner_oid"] or
                         (x["grantee"] == identity["role_oid"] and x["privilege_type"] in allowed and not x["is_grantable"]) for x in acl), "Unexpected receipt grant")
            column_acl = db.execute(text("""
              SELECT EXISTS (SELECT 1 FROM pg_catalog.pg_attribute a,LATERAL pg_catalog.aclexplode(a.attacl) x
                WHERE a.attrelid=:oid AND a.attnum>0 AND NOT a.attisdropped AND x.grantee<>:owner
                  AND NOT (a.attname='phase' AND x.grantee=CAST(:cap AS oid)
                           AND x.privilege_type='SELECT' AND NOT x.is_grantable))
            """), {"oid": oid, "owner": identity["owner_oid"], "cap": capability_id}).scalar_one()
            _require(not column_acl, "Unexpected column grant")
            policies = db.execute(text("""
              SELECT p.polname,p.polcmd,p.polpermissive,p.polroles,pg_catalog.pg_get_expr(p.polqual,p.polrelid) AS q,
                     pg_catalog.pg_get_expr(p.polwithcheck,p.polrelid) AS chk
              FROM pg_catalog.pg_policy p WHERE p.polrelid=:oid
            """), {"oid": oid}).mappings().all()
            for p in policies:
                if p["polname"] == "reconciliation_cap_select" and name == "click_callback_receipts" and capability_id is not None:
                    continue  # The complete definition and role were checked above.
                is_owner = p["polname"] in {"click_receipt_owner_select", "click_receipt_owner_insert"}
                expected_id = identity["owner_oid"] if is_owner else identity["role_oid"]
                _require(p["polname"] in {"click_receipt_owner_select", "click_receipt_owner_insert", "click_receipt_backend_select", "click_receipt_backend_insert"}
                         and p["polpermissive"] and p["polroles"] == [expected_id], "Unexpected RLS policy")
                if p["polname"].endswith("select"):
                    _require(p["polcmd"] == "r" and p["q"] == "true" and p["chk"] is None, "Invalid RLS select policy")
                else:
                    _require(p["polcmd"] == "a" and p["q"] is None and p["chk"] == "true", "Invalid RLS insert policy")
                    _require(is_owner or name == "click_callback_receipts", "Key registry must be read-only")
            existing = {p["polname"] for p in policies}
            _require({"click_receipt_owner_select", "click_receipt_owner_insert"}.issubset(existing), "Owner policies missing")
            if "click_receipt_backend_select" not in existing:
                db.exec_driver_sql(f"CREATE POLICY click_receipt_backend_select ON {qs}.{quote(name)} FOR SELECT TO {qr} USING (true)")
            if name == "click_callback_receipts" and "click_receipt_backend_insert" not in existing:
                db.exec_driver_sql(f"CREATE POLICY click_receipt_backend_insert ON {qs}.{quote(name)} FOR INSERT TO {qr} WITH CHECK (true)")
            db.exec_driver_sql(f"GRANT SELECT ON {qs}.{quote(name)} TO {qr}")
            if name == "click_callback_receipts":
                db.exec_driver_sql(f"GRANT INSERT ON {qs}.{quote(name)} TO {qr}")
        seq = f"{qs}.click_callback_receipts_id_seq"
        _require(not db.execute(text("SELECT pg_catalog.has_sequence_privilege(:role,pg_catalog.to_regclass(:seq),'UPDATE')"), {"role": role, "seq": seq}).scalar_one(), "Unsafe sequence grant")
        seq_acl = db.execute(text("""
          SELECT c.relowner,x.grantee,x.privilege_type,x.is_grantable FROM pg_catalog.pg_class c,
            LATERAL pg_catalog.aclexplode(COALESCE(c.relacl,pg_catalog.acldefault('S',c.relowner))) x
          WHERE c.oid=pg_catalog.to_regclass(:seq) AND c.relkind='S'
        """), {"seq": seq}).mappings().all()
        _require(bool(seq_acl) and all(x["relowner"] == identity["owner_oid"] and
            (x["grantee"] == identity["owner_oid"] or (x["grantee"] == identity["role_oid"]
             and x["privilege_type"] == "USAGE" and not x["is_grantable"])) for x in seq_acl), "Unexpected sequence grant")
        db.exec_driver_sql(f"GRANT USAGE ON SEQUENCE {seq} TO {qr}")
        db.exec_driver_sql(f"GRANT USAGE ON SCHEMA {qs} TO {qr}")
        db.execute(text(f"INSERT INTO {qs}.click_receipt_key_versions (version,commitment) VALUES (:version,:commitment) ON CONFLICT(version) DO NOTHING"), {"version": version, "commitment": commitment})
        saved = db.execute(text(f"SELECT commitment FROM {qs}.click_receipt_key_versions WHERE version=:version"), {"version": version}).scalar_one()
        _require(hmac.compare_digest(saved, commitment), "Key version conflicts with existing commitment")


def main() -> int:
    parser = argparse.ArgumentParser(description="Provision encrypted Click receipt privileges")
    parser.add_argument("--schema", required=True)
    parser.add_argument("--owner", required=True)
    parser.add_argument("--role", required=True)
    parser.add_argument("--trusted-owner-member", action="append", default=[])
    parser.add_argument("--key-version", required=True)
    args = parser.parse_args()
    engine = None
    try:
        key = base64.b64decode(os.environ.get("CLICK_RECEIPT_KEY_B64", ""), validate=True)
        engine = create_engine(os.environ["DATABASE_URL"])
        provision(engine, schema=args.schema, owner=args.owner, role=args.role, version=args.key_version, key=key, trusted_owner_members=tuple(args.trusted_owner_member))
    except Exception as exc:  # noqa: BLE001 - no database URL, key, payload, or server detail in output
        print(f"Receipt provisioning failed ({type(exc).__name__})", file=sys.stderr)
        return 1
    finally:
        if engine is not None:
            engine.dispose()
    print("Receipt backend role provisioned")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
