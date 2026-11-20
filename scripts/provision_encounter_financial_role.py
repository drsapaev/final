"""Provision explicit, narrow financial visibility roles transactionally.

Operators must drain traffic and supply pre-created roles. This script is not
run by a migration or application startup and never targets an implicit role.
"""
from __future__ import annotations

import argparse
import importlib.util
import os
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

TABLES = (
    "visits", "encounters", "visit_services", "payment_invoices", "payment_invoice_visits",
    "payments", "payment_visits", "payment_webhooks", "payment_transactions", "invoices",
    "provider_active_visit_reservations", "provider_attempt_visits", "provider_reconciliation_events",
    "all_free_requests", "refund_requests", "deposit_transactions",
)
BACKEND_TABLES = ("visits", "encounters", "visit_services", "payment_invoices", "payment_invoice_visits")
BACKEND_COLUMN_TABLES = {
    "payments": ("id", "visit_id", "status", "provider_payment_id", "created_at", "currency", "amount", "method", "refunded_amount"),
    "payment_visits": ("id", "payment_id", "visit_id", "amount"),
    "provider_active_visit_reservations": ("visit_id",),
    "refund_requests": ("id", "payment_id", "status"),
    "deposit_transactions": ("id", "payment_id", "transaction_type"),
}
BACKEND_ONLY_TABLES = ("refund_requests", "deposit_transactions")
LOCK_TABLES = ("visits", "encounters", "payment_invoices", "all_free_requests")
FUNCTIONS = (
    "financial_encounter_generation_fence()",
    "financial_visit_membership_fence()",
    "financial_visit_reference_fence()",
    "financial_lock_rows(text,integer[])",
    "financial_probe_group(integer)",
)


class ProvisionError(RuntimeError):
    pass


def _require(value: object, message: str) -> None:
    if not value:
        raise ProvisionError(message)


def provision(engine: Engine, *, schema: str, backend_role: str, capability_role: str, expected_owner: str,
              trusted_owner_members: tuple[str, ...] = ()) -> None:
    _require(engine.dialect.name == "postgresql", "PostgreSQL required")
    _require(all(isinstance(x, str) and x and "\x00" not in x for x in (schema, backend_role, capability_role, expected_owner)), "Explicit schema, owner and roles required")
    _require(backend_role != capability_role and schema not in {"pg_catalog", "information_schema"}, "Distinct trusted roles and application schema required")
    _require(backend_role.lower() not in {"public", "anon", "authenticated"}, "Reserved backend role")
    quote = engine.dialect.identifier_preparer.quote_identifier
    qs, qb, qc = map(quote, (schema, backend_role, capability_role))
    helper_path = Path(__file__).resolve().parent / "provision_capability_namespace.py"
    spec = importlib.util.spec_from_file_location("financial_capability_namespace", helper_path)
    _require(spec is not None and spec.loader is not None, "Capability namespace helper unavailable")
    namespace_helper = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(namespace_helper)
    qp = quote(namespace_helper.capability_schema_name(schema))
    contract_path = Path(__file__).resolve().parents[1] / "backend/app/db/financial_capability_contract.py"
    contract_spec = importlib.util.spec_from_file_location("financial_capability_contract", contract_path)
    _require(contract_spec is not None and contract_spec.loader is not None, "Financial contract unavailable")
    contract = importlib.util.module_from_spec(contract_spec)
    contract_spec.loader.exec_module(contract)
    with engine.begin() as db:
        db.execute(text("SET LOCAL search_path=pg_catalog"))
        namespace_helper.merge_namespace_roles(db, schema, expected_owner=expected_owner, trusted_owner_members=trusted_owner_members,
                                               backend_roles=(backend_role,), capability_owner_roles=(capability_role,))
        rows = db.execute(text("""
          SELECT oid,rolname,rolcanlogin,rolsuper,rolbypassrls,rolcreaterole,rolcreatedb,rolreplication
          FROM pg_catalog.pg_roles WHERE rolname IN (:backend,:capability)
        """), {"backend": backend_role, "capability": capability_role}).mappings().all()
        roles = {r["rolname"]: r for r in rows}
        _require(set(roles) == {backend_role, capability_role}, "Both roles must already exist")
        backend, cap = roles[backend_role], roles[capability_role]
        _require(backend["rolcanlogin"] and not cap["rolcanlogin"], "Backend must be LOGIN and capability NOLOGIN")
        _require(all(not r[key] for r in rows for key in ("rolsuper", "rolbypassrls", "rolcreaterole", "rolcreatedb", "rolreplication")), "Administrative role attributes are forbidden")
        memberships = db.execute(text("""
          SELECT EXISTS (SELECT 1 FROM pg_catalog.pg_roles candidate
            WHERE NOT candidate.rolsuper AND candidate.oid<>:cap
              AND pg_catalog.pg_has_role(candidate.oid,:cap,'MEMBER'))
            OR EXISTS (SELECT 1 FROM pg_catalog.pg_roles inherited
              WHERE inherited.oid<>:cap AND pg_catalog.pg_has_role(:cap,inherited.oid,'MEMBER'))
            OR EXISTS (SELECT 1 FROM pg_catalog.pg_roles inherited
              WHERE inherited.oid<>:backend AND pg_catalog.pg_has_role(:backend,inherited.oid,'MEMBER'))
            OR EXISTS (SELECT 1 FROM pg_catalog.pg_roles candidate
              WHERE NOT candidate.rolsuper AND candidate.oid<>:backend
                AND pg_catalog.pg_has_role(candidate.oid,:backend,'MEMBER'))
        """), {"cap": cap["oid"], "backend": backend["oid"]}).scalar_one()
        _require(not memberships, "Role memberships must be explicitly reconciled")
        namespace = db.execute(text("""
          SELECT n.oid,n.nspowner,owner.rolsuper,owner.rolcanlogin,
            pg_catalog.has_schema_privilege(:backend,n.oid,'CREATE') AS backend_create,
            pg_catalog.has_schema_privilege(:capability,n.oid,'CREATE') AS cap_create,
            EXISTS (SELECT 1 FROM pg_catalog.aclexplode(COALESCE(n.nspacl,pg_catalog.acldefault('n',n.nspowner))) a
              WHERE a.privilege_type='CREATE' AND a.grantee<>n.nspowner) AS unexpected_create
          FROM pg_catalog.pg_namespace n JOIN pg_catalog.pg_roles owner ON owner.oid=n.nspowner
          WHERE n.nspname=:schema
        """), {"schema": schema, "backend": backend_role, "capability": capability_role}).mappings().one_or_none()
        _require(namespace is not None and (namespace["rolsuper"] or not namespace["rolcanlogin"]), "Schema owner must be trusted NOLOGIN or superuser")
        _require(not namespace["backend_create"] and not namespace["cap_create"] and not namespace["unexpected_create"], "Schema CREATE must remain owner-only")
        db.exec_driver_sql("LOCK TABLE " + ", ".join(f"{qs}.{quote(table)}" for table in TABLES) + " IN ACCESS EXCLUSIVE MODE")
        _require(contract.financial_contract_is_valid(
            db, schema=schema, private=namespace_helper.capability_schema_name(schema),
            quoted_schema=engine.dialect.identifier_preparer.quote_schema(schema), backend_oid=backend["oid"],
            allowed_owner_oids=(namespace["nspowner"], cap["oid"]),
        ), "Financial functions or trigger bindings differ from the reviewed contract")
        table_rows = db.execute(text("""
          SELECT c.relname,c.relrowsecurity,c.relowner FROM pg_catalog.pg_class c
          WHERE c.relnamespace=:schema AND c.relname=ANY(:tables) AND c.relkind IN ('r','p')
        """), {"schema": namespace["oid"], "tables": list(TABLES)}).mappings().all()
        tables = {r["relname"]: r for r in table_rows}
        _require(set(tables) == set(TABLES), "All financial evidence tables are required")
        caller = db.execute(text("SELECT oid,rolsuper FROM pg_catalog.pg_roles WHERE rolname=CURRENT_USER")).mappings().one()
        _require(caller["rolsuper"] or all(row["relowner"] == caller["oid"] for row in table_rows), "Caller must control every table")
        db.exec_driver_sql(f"GRANT USAGE ON SCHEMA {qs} TO {qc}, {qb}")
        for table in TABLES:
            qt = f"{qs}.{quote(table)}"
            if table not in BACKEND_ONLY_TABLES:
                db.exec_driver_sql(f"GRANT SELECT ON {qt} TO {qc}")
            if table in BACKEND_TABLES:
                db.exec_driver_sql(f"GRANT SELECT ON {qt} TO {qb}")
            if table in BACKEND_COLUMN_TABLES:
                columns = ", ".join(quote(column) for column in BACKEND_COLUMN_TABLES[table])
                db.exec_driver_sql(f"GRANT SELECT ({columns}) ON {qt} TO {qb}")
            if table in LOCK_TABLES:
                column = "generation" if table == "encounters" else "id"
                db.exec_driver_sql(f"GRANT UPDATE ({quote(column)}) ON {qt} TO {qc}")
            if tables[table]["relrowsecurity"]:
                if table not in BACKEND_ONLY_TABLES:
                    _ensure_policy(db, qt, "financial_cap_select", "SELECT", qc, "true", None, cap["oid"])
                if table in LOCK_TABLES:
                    check = "true" if table == "encounters" else "false"
                    _ensure_policy(db, qt, "financial_cap_update", "UPDATE", qc, "true", check, cap["oid"])
                if table in BACKEND_TABLES or table in BACKEND_COLUMN_TABLES:
                    _ensure_policy(db, qt, "financial_backend_select", "SELECT", qb, "true", None, backend["oid"])
        db.exec_driver_sql(f"GRANT UPDATE (status) ON {qs}.payments TO {qb}")
        if tables["payments"]["relrowsecurity"]:
            _ensure_policy(db, f"{qs}.payments", "financial_backend_update", "UPDATE", qb, "true", "true", backend["oid"])
        # The existing 0114 role provisioning owns the all-free SELECT policy.
        _require(db.execute(text("""
          SELECT pg_catalog.has_table_privilege(:role,:table,'SELECT') AND EXISTS (
            SELECT 1 FROM pg_catalog.pg_policy p WHERE p.polrelid=pg_catalog.to_regclass(:table)
              AND p.polcmd='r' AND p.polpermissive AND :oid=ANY(p.polroles)
              AND pg_catalog.pg_get_expr(p.polqual,p.polrelid)='true')
        """), {"role": backend_role, "table": f"{qs}.all_free_requests", "oid": backend["oid"]}).scalar_one(),
                 "Provision the existing all-free backend SELECT policy first")
        for table, column in (("payment_invoices", "total_amount"), ("payment_invoice_visits", "visit_amount")):
            qt = f"{qs}.{quote(table)}"
            db.exec_driver_sql(f"GRANT UPDATE ({quote(column)}) ON {qt} TO {qb}")
            if tables[table]["relrowsecurity"]:
                _ensure_policy(db, qt, "financial_backend_update", "UPDATE", qb, "true", "true", backend["oid"])
        # SQLAlchemy's onupdate hook writes this timestamp with total_amount.
        db.exec_driver_sql(f"GRANT UPDATE (updated_at) ON {qs}.payment_invoices TO {qb}")
        db.exec_driver_sql(f"GRANT USAGE ON SEQUENCE {qs}.encounter_financial_generation_seq TO {qc}")
        # New function owner must temporarily possess schema CREATE. Revoke it
        # in the same transaction, so the backend never observes that grant.
        db.exec_driver_sql(f"GRANT CREATE ON SCHEMA {qp} TO {qc}")
        for signature in FUNCTIONS:
            db.exec_driver_sql(f"ALTER FUNCTION {qp}.{signature} OWNER TO {qc}")
        db.exec_driver_sql(f"REVOKE CREATE ON SCHEMA {qp} FROM {qc}")
        for signature in FUNCTIONS[-2:]:
            db.exec_driver_sql(f"GRANT EXECUTE ON FUNCTION {qp}.{signature} TO {qb}")
        namespace_helper.validate_namespace(db, schema, expected_owner=expected_owner, trusted_owner_members=trusted_owner_members)
        _require(contract.financial_contract_is_valid(
            db, schema=schema, private=namespace_helper.capability_schema_name(schema),
            quoted_schema=engine.dialect.identifier_preparer.quote_schema(schema), backend_oid=backend["oid"],
            allowed_owner_oids=(cap["oid"],),
        ), "Provisioned financial functions or trigger bindings are unsafe")


def _ensure_policy(db, table: str, name: str, command: str, role: str, qual: str, check: str | None, role_oid: int) -> None:
    existing = db.execute(text("""
      SELECT p.polcmd,p.polpermissive,p.polroles,pg_catalog.pg_get_expr(p.polqual,p.polrelid) AS qual,
             pg_catalog.pg_get_expr(p.polwithcheck,p.polrelid) AS checked
      FROM pg_catalog.pg_policy p WHERE p.polrelid=pg_catalog.to_regclass(:table) AND p.polname=:name
    """), {"table": table, "name": name}).mappings().one_or_none()
    if existing:
        _require(existing["polcmd"] == {"SELECT": "r", "UPDATE": "w"}[command]
                 and existing["polpermissive"] and list(existing["polroles"]) == [role_oid]
                 and existing["qual"] == qual and existing["checked"] == check,
                 "Existing financial policy differs; reconcile manually")
        return
    check_sql = f" WITH CHECK ({check})" if check is not None else ""
    db.exec_driver_sql(f"CREATE POLICY {name} ON {table} FOR {command} TO {role} USING ({qual}){check_sql}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--schema", required=True)
    parser.add_argument("--backend-role", required=True)
    parser.add_argument("--capability-role", required=True)
    parser.add_argument("--schema-owner", required=True)
    parser.add_argument("--trusted-owner-member", action="append", default=[])
    args = parser.parse_args()
    url = os.environ.get("DATABASE_URL")
    _require(bool(url), "DATABASE_URL must be configured")
    engine = create_engine(url)
    try:
        provision(engine, schema=args.schema, backend_role=args.backend_role, capability_role=args.capability_role, expected_owner=args.schema_owner,
                  trusted_owner_members=tuple(args.trusted_owner_member))
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
