"""Provision one least-privilege all-free backend role transactionally.

The migration's owner-only RLS templates are the policy authority. This tool
copies their predicates; it never deletes or weakens pre-existing grants or
policies. The operator must drain traffic while changing database roles/ACLs.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine, make_url

TABLES = ("all_free_requests", "all_free_request_lines", "all_free_request_events")
TEMPLATES = {"allfree_template_select": "r", "allfree_template_insert": "a"}
BACKEND = {"allfree_backend_select": "r", "allfree_backend_insert": "a"}


class ProvisionError(RuntimeError):
    """The existing database state is not safe to provision automatically."""


def _require(condition: object, message: str) -> None:
    if not condition:
        raise ProvisionError(message)


def _expected_insert_expression(db: Any, quoted_schema: str, quoted_table: str, owner: str, table: str) -> str:
    """Deparse the fixed reviewed predicate on the same relation, then roll it back."""
    if table == "all_free_requests":
        predicate = """status='pending' AND visit_id IS NOT NULL AND patient_id IS NOT NULL
            AND encounter_id IS NOT NULL AND requested_by_user_id IS NOT NULL
            AND decision_kind IS NULL AND decision_context_epoch IS NULL
            AND decided_by_user_id IS NULL AND decided_by_user_id_snapshot IS NULL
            AND decided_by_role_snapshot IS NULL AND decided_at IS NULL"""
    elif table == "all_free_request_lines":
        predicate = f"""EXISTS (
            SELECT 1 FROM {quoted_schema}.all_free_requests r
            JOIN {quoted_schema}.visit_services vs ON vs.id=all_free_request_lines.visit_service_id
            WHERE r.id=all_free_request_lines.request_id AND r.status='pending'
              AND r.visit_id=vs.visit_id AND r.visit_id_snapshot=all_free_request_lines.visit_id_snapshot
              AND vs.service_id=all_free_request_lines.service_id_snapshot
              AND vs.qty=all_free_request_lines.quantity AND vs.price=all_free_request_lines.unit_price
              AND vs.currency=all_free_request_lines.currency
        )"""
    else:
        predicate = f"""event_type='requested' AND EXISTS (
            SELECT 1 FROM {quoted_schema}.all_free_requests r
            WHERE r.id=all_free_request_events.request_id AND r.status='pending'
              AND r.requested_by_user_id=all_free_request_events.actor_user_id
              AND r.requested_by_user_id_snapshot=all_free_request_events.actor_user_id_snapshot
              AND r.requested_by_role_snapshot=all_free_request_events.actor_role_snapshot
        )"""
    nested = db.begin_nested()
    try:
        db.exec_driver_sql(
            f"CREATE POLICY allfree_validation_insert ON {quoted_table} FOR INSERT TO {owner} WITH CHECK ({predicate})"
        )
        expression = db.execute(text("""
            SELECT pg_catalog.pg_get_expr(p.polwithcheck,p.polrelid)
            FROM pg_catalog.pg_policy p WHERE p.polrelid=pg_catalog.to_regclass(:table)
              AND p.polname='allfree_validation_insert'
        """), {"table": quoted_table}).scalar_one()
    finally:
        nested.rollback()
    return expression


def _namespace_helper():
    path = Path(__file__).resolve().parent / "provision_capability_namespace.py"
    spec = importlib.util.spec_from_file_location("allfree_capability_namespace", path)
    if spec is None or spec.loader is None:
        raise ProvisionError("Reviewed capability namespace helper unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _ensure_cap_policy(db, qualified: str, name: str, command: str, role: str,
                       using: str | None, checked: str | None) -> None:
    """Create or verify one policy using this server's own SQL deparser."""
    clauses = (f" USING ({using})" if using else "") + (f" WITH CHECK ({checked})" if checked else "")
    existing = db.execute(text("""SELECT p.polcmd,p.polpermissive,p.polroles,
      pg_catalog.pg_get_expr(p.polqual,p.polrelid) AS qual,
      pg_catalog.pg_get_expr(p.polwithcheck,p.polrelid) AS checked
      FROM pg_catalog.pg_policy p WHERE p.polrelid=pg_catalog.to_regclass(:table) AND p.polname=:name"""),
                          {"table": qualified, "name": name}).mappings().first()
    if existing is None:
        db.exec_driver_sql(f"CREATE POLICY {name} ON {qualified} FOR {command} TO {role}{clauses}")
        return
    role_oid = db.execute(text("SELECT oid FROM pg_catalog.pg_roles WHERE rolname=:role"),
                          {"role": role[1:-1].replace('""', '"')}).scalar_one()
    nested = db.begin_nested()
    try:
        db.exec_driver_sql(f"CREATE POLICY allfree_cap_validation ON {qualified} FOR {command} TO {role}{clauses}")
        expected = db.execute(text("""SELECT pg_catalog.pg_get_expr(p.polqual,p.polrelid),
          pg_catalog.pg_get_expr(p.polwithcheck,p.polrelid) FROM pg_catalog.pg_policy p
          WHERE p.polrelid=pg_catalog.to_regclass(:table) AND p.polname='allfree_cap_validation'"""),
                              {"table": qualified}).one()
    finally:
        nested.rollback()
    _require(existing["polcmd"] == {"SELECT": "r", "UPDATE": "w", "INSERT": "a"}[command]
             and existing["polpermissive"] and existing["polroles"] == [role_oid]
             and (existing["qual"], existing["checked"]) == tuple(expected),
             "Existing decision policy differs from reviewed policy")


def _provision_decision(db, qs: str, qp: str, qr: str, qc: str, sequences: dict[str, str]) -> None:
    signature = "integer,text,text,integer,bigint,integer,integer,integer,bigint,bigint,bigint"
    name = f"{qp}.decide_all_free({signature})"
    function = db.execute(text("""SELECT p.proowner,p.prosecdef,p.prokind,p.provolatile,p.proconfig,
      p.prorettype='pg_catalog.int8'::pg_catalog.regtype AS returns_bigint
      FROM pg_catalog.pg_proc p WHERE p.oid=pg_catalog.to_regprocedure(:name)"""), {"name": name}).mappings().first()
    _require(function is not None and function["prosecdef"] and function["prokind"] == "f"
             and function["provolatile"] == "v" and function["returns_bigint"]
             and sorted(function["proconfig"] or []) == ["row_security=on", "search_path=pg_catalog"],
             "Decision capability unavailable or unsafe")
    cap_name = qc[1:-1].replace('""', '"')
    cap_oid = db.execute(text("SELECT oid FROM pg_catalog.pg_roles WHERE rolname=:name"), {"name": cap_name}).scalar_one()
    inherited = db.execute(text("""SELECT EXISTS (SELECT 1 FROM pg_catalog.pg_roles r
      WHERE r.oid<>:cap AND pg_catalog.pg_has_role(:cap,r.oid,'MEMBER'))"""), {"cap": cap_oid}).scalar_one()
    _require(not inherited, "Decision owner must not inherit other roles")
    table_owner = db.execute(text("SELECT relowner FROM pg_catalog.pg_class WHERE oid=pg_catalog.to_regclass(:name)"),
                             {"name": f"{qs}.all_free_requests"}).scalar_one()
    _require(function["proowner"] in {table_owner, cap_oid}, "Unexpected decision capability owner")
    acl = db.execute(text("""SELECT a.grantee,a.privilege_type,a.is_grantable FROM pg_catalog.pg_proc p,
      LATERAL pg_catalog.aclexplode(COALESCE(p.proacl,pg_catalog.acldefault('f',p.proowner))) a
      WHERE p.oid=pg_catalog.to_regprocedure(:name)"""), {"name": name}).mappings().all()
    backend_oid = db.execute(text("SELECT oid FROM pg_catalog.pg_roles WHERE rolname=:name"),
                             {"name": qr[1:-1].replace('""', '"')}).scalar_one()
    _require(all(a["grantee"] == function["proowner"] or
                 (a["grantee"] == backend_oid and a["privilege_type"] == "EXECUTE" and not a["is_grantable"])
                 for a in acl), "Unexpected decision capability ACL")

    # Serialize policy/ACL inspection and changes with table DDL until commit.
    db.exec_driver_sql("LOCK TABLE " + ", ".join(f"{qs}.{table}" for table in
                       ("encounters", "patients", "users", "visits")) + " IN ACCESS EXCLUSIVE MODE")
    db.exec_driver_sql(f"GRANT USAGE ON SCHEMA {qs} TO {qc}")
    for table in TABLES:
        qualified = f"{qs}.{table}"
        db.exec_driver_sql(f"GRANT SELECT ON {qualified} TO {qc}")
        _ensure_cap_policy(db, qualified, "allfree_decision_select", "SELECT", qc, "true", None)
    request_table, event_table = f"{qs}.all_free_requests", f"{qs}.all_free_request_events"
    db.exec_driver_sql(f"GRANT UPDATE (status,decision_kind,decision_context_epoch,decided_by_user_id,"
                       f"decided_by_user_id_snapshot,decided_by_role_snapshot,decided_at) ON {request_table} TO {qc}")
    db.exec_driver_sql(f"GRANT INSERT (request_id,event_type,actor_user_id,actor_user_id_snapshot,actor_role_snapshot) ON {event_table} TO {qc}")
    db.exec_driver_sql(f"GRANT USAGE ON SEQUENCE {sequences['all_free_request_events']} TO {qc}")
    _ensure_cap_policy(db, request_table, "allfree_decision_update", "UPDATE", qc,
                       "status='pending'", "status IN ('approved','rejected')")
    _ensure_cap_policy(db, event_table, "allfree_decision_insert", "INSERT", qc,
                       None, "event_type IN ('approved','rejected')")
    for table, columns in (("users", "id,role,is_active,is_superuser,auth_epoch"),
                           ("patients", "id,is_deleted"),
                           ("visits", "id,patient_id,encounter_id,confirmation_context_epoch"),
                           ("encounters", "id,patient_id,generation")):
        qualified = f"{qs}.{table}"
        rls = db.execute(text("SELECT relrowsecurity FROM pg_catalog.pg_class WHERE oid=pg_catalog.to_regclass(:name)"),
                         {"name": qualified}).scalar_one_or_none()
        _require(rls is not None, "Decision subject table unavailable")
        subject_acl_bad = db.execute(text("""SELECT EXISTS (
          SELECT 1 FROM pg_catalog.pg_class c,
            LATERAL pg_catalog.aclexplode(COALESCE(c.relacl,pg_catalog.acldefault('r',c.relowner))) a
          WHERE c.oid=pg_catalog.to_regclass(:name) AND a.grantee IN (0,:cap)
        ) OR EXISTS (
          SELECT 1 FROM pg_catalog.pg_attribute col,LATERAL pg_catalog.aclexplode(col.attacl) a
          WHERE col.attrelid=pg_catalog.to_regclass(:name) AND col.attnum>0 AND NOT col.attisdropped
            AND a.grantee IN (0,:cap) AND (a.grantee=0 OR a.privilege_type<>'SELECT' OR a.is_grantable OR NOT (col.attname=ANY(:columns)))
        )"""), {"name": qualified, "cap": cap_oid, "columns": columns.split(",")}).scalar_one()
        _require(not subject_acl_bad, "Unexpected decision subject privileges")
        db.exec_driver_sql(f"GRANT SELECT ({columns}) ON {qualified} TO {qc}")
        if rls:
            _ensure_cap_policy(db, qualified, "allfree_decision_subject_select", "SELECT", qc, "true", None)
    # A restrictive policy for this NOLOGIN owner could hide a pending row or
    # the live actor/subject and must never be interpreted as complete proof.
    restricted = db.execute(text("""SELECT EXISTS (SELECT 1 FROM pg_catalog.pg_policy p
      JOIN pg_catalog.pg_class c ON c.oid=p.polrelid JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace
      WHERE n.nspname=:schema AND c.relname IN ('users','patients','visits','encounters',
        'all_free_requests','all_free_request_lines','all_free_request_events')
      AND NOT p.polpermissive AND EXISTS (SELECT 1 FROM pg_catalog.unnest(p.polroles) rid
        WHERE CASE WHEN rid=0 THEN true ELSE pg_catalog.pg_has_role(:cap,rid,'MEMBER') END))"""),
                            {"schema": qs[1:-1].replace('""', '"'), "cap": cap_oid}).scalar_one()
    _require(not restricted, "Restrictive policy affects decision owner")
    # ALTER OWNER requires CREATE on the private namespace; grant only within
    # this transaction and revoke before any caller can observe the new role.
    db.exec_driver_sql(f"GRANT CREATE ON SCHEMA {qp} TO {qc}")
    db.exec_driver_sql(f"ALTER FUNCTION {name} OWNER TO {qc}")
    db.exec_driver_sql(f"ALTER FUNCTION {qp}.all_free_pending_exists(integer) OWNER TO {qc}")
    db.exec_driver_sql(f"REVOKE CREATE ON SCHEMA {qp} FROM {qc}")
    db.exec_driver_sql(f"GRANT EXECUTE ON FUNCTION {name} TO {qr}")


def provision(engine: Engine, schema: str, role: str, *, expected_owner: str,
              decision_role: str | None = None, trusted_owner_members: tuple[str, ...] = ()) -> None:
    """Validate and provision exactly one existing backend role atomically."""
    _require(engine.dialect.name == "postgresql", "PostgreSQL is required")
    _require(bool(schema) and bool(role) and bool(expected_owner) and "\x00" not in schema + role + expected_owner,
             "Explicit schema, role and trusted owner are required")
    quote = engine.dialect.identifier_preparer.quote_identifier
    qs, qr = quote(schema), quote(role)
    helper = _namespace_helper()
    private = helper.capability_schema_name(schema)
    qp = quote(private)
    with engine.begin() as db:
        # All SQL-generated expressions are deparsed with a trusted fixed path.
        db.execute(text("SET LOCAL search_path = pg_catalog"))
        _require(decision_role is None or (bool(decision_role) and "\x00" not in decision_role and decision_role != role),
                 "Invalid decision role")
        try:
            helper.merge_namespace_roles(db, schema, expected_owner=expected_owner,
                                         backend_roles=(role,), capability_owner_roles=(decision_role,) if decision_role else (),
                                         trusted_owner_members=trusted_owner_members)
        except helper.CapabilityNamespaceError as exc:
            raise ProvisionError(str(exc)) from exc
        cap_oid = None
        qc = None
        if decision_role:
            cap_oid = db.execute(text("SELECT oid FROM pg_catalog.pg_roles WHERE rolname=:name"),
                                 {"name": decision_role}).scalar_one()
            qc = quote(decision_role)
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
              ('all_free_requests','all_free_request_lines','all_free_request_events')
              AND c.relkind IN ('r','p')
        """), {"schema_oid": namespace["oid"]}).mappings().all()
        tables = {row["relname"]: row for row in rows}
        _require(set(tables) == set(TABLES), "All three request tables are required")
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
                AND ((pg_catalog.pg_has_role(c.oid,:schema_owner,'MEMBER') AND NOT (c.rolname=ANY(:trusted)))
                     OR (pg_catalog.pg_has_role(c.oid,:table_owner,'MEMBER')
                         AND (:table_owner<>:schema_owner OR NOT (c.rolname=ANY(:trusted))))))
        """), {"schema_owner": namespace["nspowner"], "table_owner": table_owner,
                 "trusted": list(trusted_owner_members)}).scalar_one()
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
              WHERE n.oid=:oid AND a.privilege_type='CREATE' AND a.grantee NOT IN (n.nspowner,:table_owner))
        """), {"oid": namespace["oid"], "table_owner": table_owner}).scalar_one()
        _require(not schema_acl_bad, "Untrusted schema CREATE grant exists")
        function = db.execute(text("""
            SELECT p.oid,p.proowner,p.prosecdef,p.provolatile,p.proconfig,
                   p.prorettype='pg_catalog.bool'::pg_catalog.regtype AS returns_bool
            FROM pg_catalog.pg_proc p WHERE p.oid=pg_catalog.to_regprocedure(:name)
        """), {"name": f"{qp}.all_free_pending_exists(integer)"}).mappings().first()
        _require(function is not None and function["proowner"] in {table_owner, cap_oid} and function["prosecdef"]
                 and function["provolatile"] == "v" and function["returns_bool"]
                 and sorted(function["proconfig"] or []) == ["row_security=on", "search_path=pg_catalog"],
                 "Visibility capability is missing or has an unsafe owner/configuration")
        function_acl = db.execute(text("""
            SELECT a.grantee,a.privilege_type,a.is_grantable FROM pg_catalog.pg_proc p,
              LATERAL pg_catalog.aclexplode(COALESCE(p.proacl,pg_catalog.acldefault('f',p.proowner))) a
            WHERE p.oid=:oid
        """), {"oid": function["oid"]}).mappings().all()
        _require(all(a["grantee"] in {table_owner, cap_oid} or
                     (a["grantee"] == target["oid"] and a["privilege_type"] == "EXECUTE" and not a["is_grantable"])
                     for a in function_acl), "Unexpected function ACL; reconcile manually")

        contract_path = Path(__file__).resolve().parents[1] / "backend/app/db/financial_capability_contract.py"
        spec = importlib.util.spec_from_file_location("allfree_financial_contract", contract_path)
        if spec is None or spec.loader is None:
            raise ProvisionError("Reviewed financial capability contract unavailable")
        contract = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(contract)
        financial_oid = contract.financial_all_free_lock_role(
            db, schema=schema, private=private, quoted_schema=engine.dialect.identifier_preparer.quote_schema(schema),
            backend_role=role,
        )
        templates: dict[str, dict[str, Any]] = {}
        sequences: dict[str, str] = {}
        for table in TABLES:
            row = tables[table]
            financial_table = table == "all_free_requests" and financial_oid is not None
            acl = db.execute(text("""
                SELECT a.grantee,a.privilege_type,a.is_grantable FROM pg_catalog.pg_class c,
                  LATERAL pg_catalog.aclexplode(COALESCE(c.relacl,pg_catalog.acldefault('r',c.relowner))) a
                WHERE c.oid=:oid
            """), {"oid": row["oid"]}).mappings().all()
            _require(all(a["grantee"] == table_owner or
                         (cap_oid is not None and a["grantee"] == cap_oid and a["privilege_type"] == "SELECT" and not a["is_grantable"]) or
                         (financial_table and a["grantee"] == financial_oid and a["privilege_type"] == "SELECT" and not a["is_grantable"]) or
                         (a["grantee"] == target["oid"] and a["privilege_type"] in {"SELECT", "INSERT"} and not a["is_grantable"])
                         for a in acl), "Unexpected request-table ACL; reconcile manually")
            column_acl = db.execute(text("""
                SELECT col.attname,a.grantee,a.privilege_type,a.is_grantable FROM pg_catalog.pg_attribute col,
                  LATERAL pg_catalog.aclexplode(col.attacl) a
                WHERE col.attrelid=:oid AND col.attnum>0 AND NOT col.attisdropped
            """), {"oid": row["oid"]}).mappings().all()
            cap_update = {"status", "decision_kind", "decision_context_epoch", "decided_by_user_id",
                          "decided_by_user_id_snapshot", "decided_by_role_snapshot", "decided_at"}
            cap_insert = {"request_id", "event_type", "actor_user_id", "actor_user_id_snapshot", "actor_role_snapshot"}
            _require(all(a["grantee"] == table_owner or (not a["is_grantable"] and (
                         (cap_oid is not None and a["grantee"] == cap_oid and (
                             (table == "all_free_requests" and a["privilege_type"] == "UPDATE" and a["attname"] in cap_update)
                             or (table == "all_free_request_events" and a["privilege_type"] == "INSERT" and a["attname"] in cap_insert)))
                         or (financial_table and a["grantee"] == financial_oid and a["privilege_type"] == "UPDATE" and a["attname"] == "id")))
                         for a in column_acl),
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
            allowed_policies = set(TEMPLATES) | set(BACKEND)
            if cap_oid is not None:
                allowed_policies |= {"allfree_decision_select", "allfree_decision_update", "allfree_decision_insert"}
            if financial_table:
                allowed_policies |= {"financial_cap_select", "financial_cap_update"}
            _require(set(policies_by_name).issubset(allowed_policies), "Unexpected RLS policy; reconcile manually")
            _require(set(TEMPLATES).issubset(policies_by_name), "Owner template policies are missing")
            templates[table] = {}
            for name, command in TEMPLATES.items():
                policy = policies_by_name[name]
                _require(policy["polcmd"] == command and policy["polpermissive"] and policy["polroles"] == [table_owner],
                         "Owner template policy is unsafe")
                _require((policy["qual"] == "true" and policy["checked"] is None) if command == "r"
                         else (policy["qual"] is None and policy["checked"] is not None), "Owner template policy shape is invalid")
                templates[table][command] = policy
            expected = _expected_insert_expression(db, qs, f"{qs}.{quote(table)}", qo, table)
            _require(templates[table]["a"]["checked"] == expected,
                     "Owner template predicate differs from the reviewed policy")
            for name, command in BACKEND.items():
                if name not in policies_by_name:
                    continue
                policy, template = policies_by_name[name], templates[table][command]
                _require(policy["polcmd"] == command and policy["polpermissive"] and policy["polroles"] == [target["oid"]]
                         and policy["qual"] == template["qual"] and policy["checked"] == template["checked"],
                         "Existing backend policy differs from the trusted template")
            sequence = db.execute(text("SELECT pg_catalog.pg_get_serial_sequence(:table,'id')"),
                                  {"table": f"{qs}.{quote(table)}"}).scalar_one()
            _require(sequence is not None, "Request ID sequence is required")
            sequences[table] = sequence
            seq_acl = db.execute(text("""
                SELECT a.grantee,a.privilege_type,a.is_grantable,c.relowner FROM pg_catalog.pg_class c,
                  LATERAL pg_catalog.aclexplode(COALESCE(c.relacl,pg_catalog.acldefault('S',c.relowner))) a
                WHERE c.oid=pg_catalog.to_regclass(:sequence)
            """), {"sequence": sequence}).mappings().all()
            _require(bool(seq_acl) and all(a["grantee"] == a["relowner"] or
                     (cap_oid is not None and table == "all_free_request_events" and a["grantee"] == cap_oid
                      and a["privilege_type"] == "USAGE" and not a["is_grantable"]) or
                     (a["grantee"] == target["oid"] and a["privilege_type"] == "USAGE" and not a["is_grantable"])
                     for a in seq_acl), "Unexpected sequence ACL; reconcile manually")

        # No destructive changes. Any error rolls the entire grant/policy set back.
        db.exec_driver_sql(f"GRANT USAGE ON SCHEMA {qs} TO {qr}")
        db.exec_driver_sql(f"GRANT EXECUTE ON FUNCTION {qp}.all_free_pending_exists(integer) TO {qr}")
        for table in TABLES:
            qualified = f"{qs}.{quote(table)}"
            db.exec_driver_sql(f"GRANT SELECT, INSERT ON {qualified} TO {qr}")
            # pg_get_serial_sequence returns a server-quoted qualified identifier.
            db.exec_driver_sql(f"GRANT USAGE ON SEQUENCE {sequences[table]} TO {qr}")
            existing = db.execute(text("SELECT polname FROM pg_catalog.pg_policy WHERE polrelid=:oid"),
                                  {"oid": tables[table]["oid"]}).scalars().all()
            if "allfree_backend_select" not in existing:
                db.exec_driver_sql(f"CREATE POLICY allfree_backend_select ON {qualified} FOR SELECT TO {qr} USING ({templates[table]['r']['qual']})")
            if "allfree_backend_insert" not in existing:
                db.exec_driver_sql(f"CREATE POLICY allfree_backend_insert ON {qualified} FOR INSERT TO {qr} WITH CHECK ({templates[table]['a']['checked']})")
        if qc is not None:
            _provision_decision(db, qs, qp, qr, qc, sequences)
        helper.validate_namespace(db, schema, expected_owner=expected_owner,
                                  trusted_owner_members=trusted_owner_members)


def main() -> int:
    parser = argparse.ArgumentParser(description="Provision an existing backend role for all-free staging")
    parser.add_argument("--schema", required=True)
    parser.add_argument("--role", required=True)
    parser.add_argument("--expected-owner", required=True)
    parser.add_argument("--decision-role")
    parser.add_argument("--trusted-owner-members", default="[]", help="JSON array of trusted non-superuser owner members")
    args = parser.parse_args()
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        print("DATABASE_URL is required", file=sys.stderr)
        return 2
    try:
        members = json.loads(args.trusted_owner_members)
        _require(isinstance(members, list) and all(isinstance(value, str) for value in members),
                 "trusted-owner-members must be a JSON array of role names")
        url = make_url(database_url)
        _require(url.get_backend_name() == "postgresql", "PostgreSQL is required")
        engine = create_engine(url, hide_parameters=True)
        try:
            provision(engine, args.schema, args.role, expected_owner=args.expected_owner,
                      decision_role=args.decision_role, trusted_owner_members=tuple(members))
        finally:
            engine.dispose()
    except ProvisionError as exc:
        print(f"Provisioning refused: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:  # noqa: BLE001 - never expose connection data on unexpected failures
        # Avoid logging database URLs, provider data or untrusted server messages.
        print(f"Provisioning failed ({type(exc).__name__})", file=sys.stderr)
        return 1
    print("All-free backend role provisioned")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
