"""Provision one least-privilege doctor-price backend role transactionally.

The migration's owner-only RLS templates are the policy authority. This tool
copies their predicates; it never deletes or weakens pre-existing grants or
policies. The operator must drain traffic while changing database roles/ACLs.
"""
from __future__ import annotations

import argparse
import os
import sys
from typing import Any

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine, make_url

TABLES = ("doctor_price_hmac_key_versions", "doctor_price_intents", "doctor_price_intent_keys", "doctor_price_intent_lines")
TEMPLATES = {"doctor_price_template_select": "r", "doctor_price_template_insert": "a"}
BACKEND = {"doctor_price_backend_select": "r", "doctor_price_backend_insert": "a"}


class ProvisionError(RuntimeError):
    """The existing database state is not safe to provision automatically."""


def _require(condition: object, message: str) -> None:
    if not condition:
        raise ProvisionError(message)


def provision(engine: Engine, schema: str, role: str) -> None:
    """Validate and provision exactly one existing backend role atomically."""
    _require(engine.dialect.name == "postgresql", "PostgreSQL is required")
    _require(bool(schema) and bool(role) and "\x00" not in schema + role, "Explicit schema and role are required")
    quote = engine.dialect.identifier_preparer.quote_identifier
    qs, qr = quote(schema), quote(role)
    with engine.begin() as db:
        # All SQL-generated expressions are deparsed with a trusted fixed path.
        db.execute(text("SET LOCAL search_path = pg_catalog"))
        roles = db.execute(text("""
            SELECT r.oid, r.rolname, r.rolcanlogin, r.rolsuper, r.rolbypassrls, r.rolcreaterole, r.rolcreatedb, r.rolreplication
            FROM pg_catalog.pg_roles r WHERE r.rolname IN (:role, CURRENT_USER)
        """), {"role": role}).mappings().all()
        by_name = {row["rolname"]: row for row in roles}
        current = db.execute(text("SELECT CURRENT_USER")).scalar_one()
        _require(role in by_name and current in by_name, "Role or current database user does not exist")
        target, caller = by_name[role], by_name[current]
        _require(target["rolcanlogin"] and not any(target[key] for key in
                 ("rolsuper", "rolbypassrls", "rolcreaterole", "rolcreatedb", "rolreplication")),
                 "Backend role must be LOGIN without administrative attributes")
        _require(role.casefold() not in {"anon", "authenticated", "public"}, "Reserved role is not a backend role")
        elevated = db.execute(text("""
            SELECT EXISTS (SELECT 1 FROM pg_catalog.pg_roles c
              WHERE (c.rolsuper OR c.rolbypassrls OR c.rolcreaterole OR c.rolcreatedb OR c.rolreplication)
                AND pg_catalog.pg_has_role(:target,c.oid,'MEMBER'))
        """), {"target": target["oid"]}).scalar_one()
        _require(not elevated, "Backend can assume an administrative role")
        memberships = db.execute(text("SELECT EXISTS (SELECT 1 FROM pg_catalog.pg_auth_members WHERE member=:target)"), {"target": target["oid"]}).scalar_one()
        _require(not memberships, "Backend role must not inherit any other role")
        namespace = db.execute(text("""
            SELECT n.oid, n.nspowner, pg_catalog.has_schema_privilege(:role,n.oid,'CREATE') AS target_create
            FROM pg_catalog.pg_namespace n WHERE n.nspname=:schema
        """), {"schema": schema, "role": role}).mappings().first()
        _require(namespace is not None and schema not in {"pg_catalog", "information_schema"}, "Trusted application schema is required")
        _require(not namespace["target_create"], "Backend role must not have schema CREATE")
        # Serialize all ACL/policy changes with other table DDL and provisioners.
        db.exec_driver_sql("LOCK TABLE " + ", ".join(f"{qs}.{quote(table)}" for table in TABLES) + " IN ACCESS EXCLUSIVE MODE")
        rows = db.execute(text("""
            SELECT c.oid, c.relname, c.relowner, c.relrowsecurity, c.relforcerowsecurity,
                   owner.rolsuper, owner.rolbypassrls, owner.rolcanlogin
            FROM pg_catalog.pg_class c JOIN pg_catalog.pg_roles owner ON owner.oid=c.relowner
            WHERE c.relnamespace=:schema_oid AND c.relname IN
              ('doctor_price_hmac_key_versions','doctor_price_intents','doctor_price_intent_keys','doctor_price_intent_lines')
              AND c.relkind IN ('r','p')
        """), {"schema_oid": namespace["oid"]}).mappings().all()
        tables = {row["relname"]: row for row in rows}
        _require(set(tables) == set(TABLES), "All four price request tables are required")
        owners = {row["relowner"] for row in rows}
        _require(len(owners) == 1, "Request tables must share one trusted owner")
        table_owner = next(iter(owners))
        owner_name = db.execute(text("SELECT rolname FROM pg_catalog.pg_roles WHERE oid=:oid"), {"oid": table_owner}).scalar_one()
        qo = quote(owner_name)
        _require(caller["rolsuper"] or caller["oid"] == table_owner, "Caller must own the request tables or be a superuser")
        _require(target["oid"] not in {table_owner, namespace["nspowner"]}, "Backend cannot own the schema or request tables")
        _require(all(row["relrowsecurity"] for row in rows), "RLS must be enabled on every request table")
        _require(all(row["rolsuper"] or not row["rolcanlogin"] for row in rows), "Request owner must be NOLOGIN or superuser")
        schema_owner = db.execute(text("SELECT rolsuper,rolcanlogin FROM pg_catalog.pg_roles WHERE oid=:owner"),
                                  {"owner": namespace["nspowner"]}).mappings().one()
        _require(schema_owner["rolsuper"] or not schema_owner["rolcanlogin"], "Schema owner must be NOLOGIN or superuser")
        unsafe_members = db.execute(text("""
            SELECT EXISTS (SELECT 1 FROM pg_catalog.pg_roles c
              WHERE NOT c.rolsuper AND c.oid NOT IN (:schema_owner,:table_owner)
                AND (pg_catalog.pg_has_role(c.oid,:schema_owner,'MEMBER')
                     OR pg_catalog.pg_has_role(c.oid,:table_owner,'MEMBER')))
        """), {"schema_owner": namespace["nspowner"], "table_owner": table_owner}).scalar_one()
        _require(not unsafe_members, "Untrusted role can assume a privileged owner role")
        inherited = db.execute(text("""
            SELECT EXISTS (SELECT 1 FROM pg_catalog.pg_roles c WHERE NOT c.rolsuper AND c.oid<>:target
              AND pg_catalog.pg_has_role(c.oid,:target,'MEMBER'))
        """), {"target": target["oid"]}).scalar_one()
        _require(not inherited, "Other non-superuser roles may not inherit the backend role")
        reserved_role_risk = db.execute(text("""
            SELECT EXISTS (SELECT 1 FROM pg_catalog.pg_roles c
              WHERE pg_catalog.lower(c.rolname) IN ('anon','authenticated')
                AND (c.rolsuper OR c.rolbypassrls
                     OR pg_catalog.pg_has_role(c.oid,:target,'MEMBER')))
        """), {"target": target["oid"]}).scalar_one()
        _require(not reserved_role_risk, "Anonymous roles must not inherit or bypass backend protections")
        schema_acl_bad = db.execute(text("""
            SELECT EXISTS (SELECT 1 FROM pg_catalog.pg_namespace n,
              LATERAL pg_catalog.aclexplode(COALESCE(n.nspacl,pg_catalog.acldefault('n',n.nspowner))) a
              WHERE n.oid=:oid AND a.privilege_type='CREATE' AND a.grantee <> n.nspowner)
        """), {"oid": namespace["oid"], "table_owner": table_owner}).scalar_one()
        _require(not schema_acl_bad, "Untrusted schema CREATE grant exists")
        templates: dict[str, dict[str, Any]] = {}
        sequences: dict[str, str] = {}
        for table in TABLES:
            row = tables[table]
            acl = db.execute(text("""
                SELECT a.grantee,a.privilege_type,a.is_grantable FROM pg_catalog.pg_class c,
                  LATERAL pg_catalog.aclexplode(COALESCE(c.relacl,pg_catalog.acldefault('r',c.relowner))) a
                WHERE c.oid=:oid
            """), {"oid": row["oid"]}).mappings().all()
            _require(all(a["grantee"] == table_owner or
                         (a["grantee"] == target["oid"] and a["privilege_type"] in {"SELECT", "INSERT"} and not a["is_grantable"])
                         for a in acl), "Unexpected request-table ACL; reconcile manually")
            column_acl = db.execute(text("""
                SELECT a.grantee,a.privilege_type,a.is_grantable FROM pg_catalog.pg_attribute col,
                  LATERAL pg_catalog.aclexplode(col.attacl) a
                WHERE col.attrelid=:oid AND col.attnum>0 AND NOT col.attisdropped
            """), {"oid": row["oid"]}).mappings().all()
            _require(all(a["grantee"] == table_owner for a in column_acl),
                     "Unexpected request-column ACL; reconcile manually")
            dangerous = db.execute(text("""
                SELECT pg_catalog.has_table_privilege(:role,:oid,'UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER')
                    OR pg_catalog.has_any_column_privilege(:role,:oid,'UPDATE,REFERENCES')
            """), {"role": role, "oid": row["oid"]}).scalar_one()
            _require(not dangerous, "Backend has dangerous inherited table or column privileges")
            policies = db.execute(text("""
                SELECT p.polname,p.polcmd,p.polpermissive,p.polroles,
                       pg_catalog.pg_get_expr(p.polqual,p.polrelid) AS qual,
                       pg_catalog.pg_get_expr(p.polwithcheck,p.polrelid) AS checked
                FROM pg_catalog.pg_policy p WHERE p.polrelid=:oid
            """), {"oid": row["oid"]}).mappings().all()
            policies_by_name = {p["polname"]: p for p in policies}
            _require(set(policies_by_name).issubset(set(TEMPLATES) | set(BACKEND)), "Unexpected RLS policy; reconcile manually")
            _require(set(TEMPLATES).issubset(policies_by_name), "Owner template policies are missing")
            templates[table] = {}
            for name, command in TEMPLATES.items():
                policy = policies_by_name[name]
                _require(policy["polcmd"] == command and policy["polpermissive"] and policy["polroles"] == [table_owner],
                         "Owner template policy is unsafe")
                _require((policy["qual"] == "true" and policy["checked"] is None) if command == "r"
                         else (policy["qual"] is None and policy["checked"] is not None), "Owner template policy shape is invalid")
                templates[table][command] = policy
            _require(templates[table]["a"]["checked"] == "true",
                     "Owner template predicate differs from the reviewed policy")
            for name, command in BACKEND.items():
                if name not in policies_by_name:
                    continue
                policy, template = policies_by_name[name], templates[table][command]
                _require(policy["polcmd"] == command and policy["polpermissive"] and policy["polroles"] == [target["oid"]]
                         and policy["qual"] == template["qual"] and policy["checked"] == template["checked"],
                         "Existing backend policy differs from the trusted template")
            if table != "doctor_price_hmac_key_versions":
                sequence = db.execute(text("SELECT pg_catalog.pg_get_serial_sequence(:table,'id')"),
                                      {"table": f"{qs}.{quote(table)}"}).scalar_one()
                _require(sequence is not None, "Price request ID sequence is required")
                sequences[table] = sequence
                seq_acl = db.execute(text("""
                    SELECT a.grantee,a.privilege_type,a.is_grantable,c.relowner FROM pg_catalog.pg_class c,
                      LATERAL pg_catalog.aclexplode(COALESCE(c.relacl,pg_catalog.acldefault('S',c.relowner))) a
                    WHERE c.oid=pg_catalog.to_regclass(:sequence)
                """), {"sequence": sequence}).mappings().all()
                _require(bool(seq_acl) and all(a["grantee"] == a["relowner"] or
                         (a["grantee"] == target["oid"] and a["privilege_type"] == "USAGE" and not a["is_grantable"])
                         for a in seq_acl), "Unexpected sequence ACL; reconcile manually")

        # No destructive changes. Any error rolls the entire grant/policy set back.
        db.exec_driver_sql(f"GRANT USAGE ON SCHEMA {qs} TO {qr}")
        for table in TABLES:
            qualified = f"{qs}.{quote(table)}"
            db.exec_driver_sql(f"GRANT SELECT, INSERT ON {qualified} TO {qr}")
            # pg_get_serial_sequence returns a server-quoted qualified identifier.
            if table in sequences:
                db.exec_driver_sql(f"GRANT USAGE ON SEQUENCE {sequences[table]} TO {qr}")
            existing = db.execute(text("SELECT polname FROM pg_catalog.pg_policy WHERE polrelid=:oid"),
                                  {"oid": tables[table]["oid"]}).scalars().all()
            if "doctor_price_backend_select" not in existing:
                db.exec_driver_sql(f"CREATE POLICY doctor_price_backend_select ON {qualified} FOR SELECT TO {qr} USING ({templates[table]['r']['qual']})")
            if "doctor_price_backend_insert" not in existing:
                db.exec_driver_sql(f"CREATE POLICY doctor_price_backend_insert ON {qualified} FOR INSERT TO {qr} WITH CHECK ({templates[table]['a']['checked']})")


def main() -> int:
    parser = argparse.ArgumentParser(description="Provision an existing backend role for doctor-price request identity")
    parser.add_argument("--schema", required=True)
    parser.add_argument("--role", required=True)
    args = parser.parse_args()
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        print("DATABASE_URL is required", file=sys.stderr)
        return 2
    try:
        url = make_url(database_url)
        _require(url.get_backend_name() == "postgresql", "PostgreSQL is required")
        engine = create_engine(url, hide_parameters=True)
        try:
            provision(engine, args.schema, args.role)
        finally:
            engine.dispose()
    except ProvisionError as exc:
        print(f"Provisioning refused: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:  # noqa: BLE001 - never expose connection data on unexpected failures
        # Avoid logging database URLs, provider data or untrusted server messages.
        print(f"Provisioning failed ({type(exc).__name__})", file=sys.stderr)
        return 1
    print("Doctor-price backend role provisioned")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
