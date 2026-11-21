"""Owner-only validation and transactional provisioning of private namespaces.

All callers must drain application traffic and supply trusted deployment values.
These helpers never commit and never grant EXECUTE on any function. A capability
owner provisions its explicit function grants in the *same* transaction.
"""
from __future__ import annotations

import hashlib

from sqlalchemy import text
from sqlalchemy.engine import Connection


class CapabilityNamespaceError(RuntimeError):
    pass


def _require(value: object, message: str) -> None:
    if not value:
        raise CapabilityNamespaceError(message)


def _identifier(value: str) -> str:
    _require(isinstance(value, str) and bool(value) and "\0" not in value, "Invalid identifier")
    try:
        _require(len(value.encode("utf-8")) <= 63, "Identifier is too long")
    except UnicodeError:
        raise CapabilityNamespaceError("Invalid identifier") from None
    return value


def capability_schema_name(application_schema: str) -> str:
    # Frozen v1, matching migration 0112 and app.db.capability_namespace.
    raw = _identifier(application_schema).encode("utf-8")
    return "clinic_internal_" + hashlib.sha256(b"clinic-capability-schema-v1\0" + raw).hexdigest()[:32]


_COLUMNS = {
    "clinic_capability_namespace": [("id", "smallint", True), ("format_version", "smallint", True),
        ("application_schema", "text", True), ("private_schema", "text", True)],
    "clinic_capability_role_profile": [("role_name", "text", True), ("role_kind", "text", True)],
}
_CONSTRAINTS = {
    "clinic_capability_namespace": {
        ("p", "PRIMARY KEY (id)"), ("c", "CHECK ((id = 1))"),
        ("c", "CHECK ((format_version = 1))"),
        ("c", "CHECK (((octet_length(application_schema) >= 1) AND (octet_length(application_schema) <= 63)))"),
        ("c", "CHECK (((octet_length(private_schema) >= 1) AND (octet_length(private_schema) <= 63)))"),
    },
    "clinic_capability_role_profile": {
        ("p", "PRIMARY KEY (role_name)"),
        ("c", "CHECK (((octet_length(role_name) >= 1) AND (octet_length(role_name) <= 63)))"),
        ("c", "CHECK ((role_kind = ANY (ARRAY['backend'::text, 'capability_owner'::text])))"),
    },
}


def _inspect_role(db: Connection, name: str, kind: str, owner_oid: int) -> int:
    _identifier(name)
    _require(name.lower() not in {"public", "anon", "authenticated"}, "Forbidden capability role")
    role = db.execute(text("""
      SELECT oid,rolcanlogin,rolsuper,rolbypassrls,rolcreaterole,rolcreatedb,rolreplication
      FROM pg_catalog.pg_roles WHERE rolname=:name
    """), {"name": name}).mappings().first()
    _require(role is not None, "Configured capability role does not exist")
    _require(role["oid"] != owner_oid and role["rolcanlogin"] == (kind == "backend")
             and not any(role[key] for key in ("rolsuper", "rolbypassrls", "rolcreaterole", "rolcreatedb", "rolreplication")),
             "Capability role has unsafe attributes")
    # A role able to SET ROLE to a trusted owner/admin, or any nonsuperuser
    # role able to assume this profile role, bypasses the intended boundary.
    unsafe = db.execute(text("""
      SELECT EXISTS (SELECT 1 FROM pg_catalog.pg_roles r
        WHERE r.oid<>:role AND (
          (NOT r.rolsuper AND pg_catalog.pg_has_role(r.oid,:role,'MEMBER')) OR
          ((r.oid=:owner OR r.rolsuper OR r.rolbypassrls OR r.rolcreaterole OR r.rolcreatedb OR r.rolreplication)
             AND pg_catalog.pg_has_role(:role,r.oid,'MEMBER'))))
    """), {"role": role["oid"], "owner": owner_oid}).scalar_one()
    _require(not unsafe, "Capability role has unsafe membership")
    return role["oid"]


def _validate_owner_members(db: Connection, owner_oid: int, trusted_owner_members: tuple[str, ...]) -> None:
    _require(isinstance(trusted_owner_members, (tuple, list)), "Invalid owner-member allowlist")
    expected = [_identifier(name) for name in trusted_owner_members]
    _require(len(set(expected)) == len(expected)
             and all(name.lower() not in {"public", "anon", "authenticated"} for name in expected),
             "Invalid owner-member allowlist")
    actual = db.execute(text("""
      SELECT r.rolname,r.rolbypassrls,r.rolcreaterole,r.rolcreatedb,r.rolreplication
      FROM pg_catalog.pg_roles r WHERE r.oid<>:owner AND NOT r.rolsuper
        AND pg_catalog.pg_has_role(r.oid,:owner,'MEMBER')
    """), {"owner": owner_oid}).mappings().all()
    _require({row["rolname"] for row in actual} == set(expected)
             and all(not any(row[key] for key in ("rolbypassrls", "rolcreaterole", "rolcreatedb", "rolreplication"))
                     for row in actual), "Owner membership does not match trusted profile")


def validate_namespace(db: Connection, application_schema: str, *, expected_owner: str,
                       trusted_owner_members: tuple[str, ...] = ()) -> str:
    """Validate marker, profile, ACLs and roles on a trusted owner connection."""
    _require(db.dialect.name == "postgresql" and db.in_transaction(), "PostgreSQL owner transaction required")
    app = _identifier(application_schema)
    _require(app != "information_schema" and not app.startswith("pg_"), "Application schema must not be a system schema")
    owner = _identifier(expected_owner)
    private = capability_schema_name(app)
    rows = db.execute(text("""
      SELECT n.oid,n.nspname,n.nspowner,r.rolname,
             pg_catalog.pg_has_role(current_user,n.nspowner,'USAGE') AS owner_access
      FROM pg_catalog.pg_namespace n JOIN pg_catalog.pg_roles r ON r.oid=n.nspowner
      WHERE n.nspname IN (:app,:private)
    """), {"app": app, "private": private}).mappings().all()
    by_name = {row["nspname"]: row for row in rows}
    _require(set(by_name) == {app, private} and app != private, "Capability namespaces unavailable")
    app_row, private_row = by_name[app], by_name[private]
    _require(app_row["rolname"] == owner and private_row["nspowner"] == app_row["nspowner"]
             and app_row["owner_access"] and private_row["owner_access"], "Capability owner mismatch")
    owner_oid, namespace_oid = app_row["nspowner"], private_row["oid"]
    _validate_owner_members(db, owner_oid, trusted_owner_members)
    _require(not db.execute(text("""
      SELECT EXISTS(SELECT 1 FROM pg_catalog.pg_namespace n,
        LATERAL pg_catalog.aclexplode(COALESCE(n.nspacl,pg_catalog.acldefault('n',n.nspowner))) a
        WHERE n.oid=:oid AND a.privilege_type='CREATE' AND a.grantee<>n.nspowner)
    """), {"oid": app_row["oid"]}).scalar_one(), "Application schema has unsafe CREATE grant")
    quote = db.dialect.identifier_preparer.quote_identifier
    qp = quote(private)
    # Owner callers hold these locks until their outer transaction completes.
    # This prevents metadata DML/DDL from changing between catalog and row checks.
    db.exec_driver_sql(f"LOCK TABLE {qp}.clinic_capability_namespace, {qp}.clinic_capability_role_profile IN SHARE MODE")
    for table, expected_columns in _COLUMNS.items():
        relation = db.execute(text("""
          SELECT c.oid,c.relowner,c.relkind,c.relrowsecurity,c.relforcerowsecurity
          FROM pg_catalog.pg_class c WHERE c.relnamespace=:schema AND c.relname=:table
        """), {"schema": namespace_oid, "table": table}).mappings().first()
        _require(relation is not None and relation["relowner"] == owner_oid and relation["relkind"] == "r"
                 and not relation["relrowsecurity"] and not relation["relforcerowsecurity"], "Invalid capability metadata table")
        oid = relation["oid"]
        columns = db.execute(text("""
          SELECT a.attname,pg_catalog.format_type(a.atttypid,a.atttypmod),a.attnotnull
          FROM pg_catalog.pg_attribute a WHERE a.attrelid=:oid AND a.attnum>0 AND NOT a.attisdropped
          ORDER BY a.attnum
        """), {"oid": oid}).all()
        _require([tuple(row) for row in columns] == expected_columns, "Invalid capability metadata columns")
        constraints = db.execute(text("""
          SELECT c.contype,pg_catalog.pg_get_constraintdef(c.oid),c.convalidated,c.condeferrable
          FROM pg_catalog.pg_constraint c WHERE c.conrelid=:oid
        """), {"oid": oid}).all()
        _require(len(constraints) == len(_CONSTRAINTS[table])
                 and all(row.convalidated and not row.condeferrable for row in constraints)
                 and {(row.contype, row[1]) for row in constraints} == _CONSTRAINTS[table],
                 "Invalid capability metadata constraints")
        unsafe_table = db.execute(text("""
          SELECT EXISTS(SELECT 1 FROM pg_catalog.pg_class c,
            LATERAL pg_catalog.aclexplode(COALESCE(c.relacl,pg_catalog.acldefault('r',c.relowner))) a
            WHERE c.oid=:oid AND a.grantee<>c.relowner)
          OR EXISTS(SELECT 1 FROM pg_catalog.pg_attribute a WHERE a.attrelid=:oid AND a.attacl IS NOT NULL)
          OR EXISTS(SELECT 1 FROM pg_catalog.pg_attribute a WHERE a.attrelid=:oid AND a.attnum>0
                    AND (a.attisdropped OR a.atthasdef OR a.attidentity<>'' OR a.attgenerated<>''))
          OR EXISTS(SELECT 1 FROM pg_catalog.pg_trigger t WHERE t.tgrelid=:oid AND NOT t.tgisinternal)
          OR EXISTS(SELECT 1 FROM pg_catalog.pg_rewrite r WHERE r.ev_class=:oid)
        """), {"oid": oid}).scalar_one()
        _require(not unsafe_table, "Capability metadata is not owner-only")
    marker = db.execute(text(f"SELECT id,format_version,application_schema,private_schema FROM {qp}.clinic_capability_namespace")).all()
    _require(len(marker) == 1 and tuple(marker[0]) == (1, 1, app, private), "Capability namespace marker mismatch")
    profile_rows = db.execute(text(f"SELECT role_name,role_kind FROM {qp}.clinic_capability_role_profile ORDER BY role_name")).all()
    profile = {name: kind for name, kind in profile_rows}
    _require(len(profile) == len(profile_rows), "Duplicate capability role")
    role_oids = {name: _inspect_role(db, name, kind, owner_oid) for name, kind in profile.items()}
    for first in role_oids.values():
        for second in role_oids.values():
            if first != second:
                _require(not db.execute(text("SELECT pg_catalog.pg_has_role(:a,:b,'MEMBER')"),
                                        {"a": first, "b": second}).scalar_one(), "Capability roles overlap")
    grants = db.execute(text("""
      SELECT a.grantee,a.privilege_type,a.is_grantable FROM pg_catalog.pg_namespace n,
        LATERAL pg_catalog.aclexplode(COALESCE(n.nspacl,pg_catalog.acldefault('n',n.nspowner))) a
      WHERE n.oid=:oid AND a.grantee<>n.nspowner
    """), {"oid": namespace_oid}).all()
    _require(len(grants) == len(role_oids) and
             {(row.grantee, row.privilege_type, row.is_grantable) for row in grants}
             == {(oid, "USAGE", False) for oid in role_oids.values()}, "Capability schema ACL does not match profile")
    capability_oids = [role_oids[name] for name, kind in profile.items() if kind == "capability_owner"]
    unsafe_functions = db.execute(text("""
      SELECT EXISTS(SELECT 1 FROM pg_catalog.pg_proc p WHERE p.pronamespace=:schema
        AND p.proowner<>:owner AND p.proowner<>ALL(:capability_owners))
      OR EXISTS(SELECT 1 FROM pg_catalog.pg_proc p,
        LATERAL pg_catalog.aclexplode(COALESCE(p.proacl,pg_catalog.acldefault('f',p.proowner))) a
        WHERE p.pronamespace=:schema AND a.grantee<>p.proowner
          AND (a.grantee=0 OR a.grantee<>ALL(:roles) OR a.is_grantable))
    """), {"schema": namespace_oid, "owner": owner_oid, "capability_owners": capability_oids,
             "roles": list(role_oids.values())}).scalar_one()
    _require(not unsafe_functions, "Capability function has an unapproved grantee")
    return private


def reconcile_namespace_roles(db: Connection, application_schema: str, *, expected_owner: str,
                              backend_roles: tuple[str, ...], capability_owner_roles: tuple[str, ...],
                              trusted_owner_members: tuple[str, ...] = ()) -> None:
    """Reconcile the exact namespace USAGE profile inside the caller's txn."""
    _require(db.dialect.name == "postgresql" and db.in_transaction(), "PostgreSQL owner transaction required")
    private = capability_schema_name(application_schema)
    quote = db.dialect.identifier_preparer.quote_identifier
    qp = quote(private)
    # Take the stronger lock first so concurrent reconciliations don't both
    # attempt to upgrade SHARE locks after inspecting the same profile.
    db.exec_driver_sql(f"LOCK TABLE {qp}.clinic_capability_namespace, {qp}.clinic_capability_role_profile IN ACCESS EXCLUSIVE MODE")
    private = validate_namespace(db, application_schema, expected_owner=expected_owner,
                                 trusted_owner_members=trusted_owner_members)
    requested = {name: "backend" for name in backend_roles}
    _require(len(requested) == len(backend_roles), "Duplicate backend role")
    for name in capability_owner_roles:
        _require(name not in requested, "Duplicate capability role")
        requested[name] = "capability_owner"
    owner_oid = db.execute(text("SELECT oid FROM pg_catalog.pg_roles WHERE rolname=:owner"), {"owner": expected_owner}).scalar_one()
    role_oids = {name: _inspect_role(db, name, kind, owner_oid) for name, kind in requested.items()}
    for first in role_oids.values():
        for second in role_oids.values():
            if first != second:
                _require(not db.execute(text("SELECT pg_catalog.pg_has_role(:a,:b,'MEMBER')"),
                                        {"a": first, "b": second}).scalar_one(), "Capability roles overlap")
    existing = {row[0] for row in db.execute(text(f"SELECT role_name FROM {qp}.clinic_capability_role_profile"))}
    for name in existing - requested.keys():
        db.exec_driver_sql(f"REVOKE ALL ON SCHEMA {qp} FROM {quote(name)}")
    db.execute(text(f"DELETE FROM {qp}.clinic_capability_role_profile"))
    for name, kind in requested.items():
        db.execute(text(f"INSERT INTO {qp}.clinic_capability_role_profile(role_name,role_kind) VALUES (:name,:kind)"),
                   {"name": name, "kind": kind})
        db.exec_driver_sql(f"GRANT USAGE ON SCHEMA {qp} TO {quote(name)}")
    validate_namespace(db, application_schema, expected_owner=expected_owner,
                       trusted_owner_members=trusted_owner_members)


def merge_namespace_roles(db: Connection, application_schema: str, *, expected_owner: str,
                          backend_roles: tuple[str, ...], capability_owner_roles: tuple[str, ...],
                          trusted_owner_members: tuple[str, ...] = ()) -> None:
    """Atomically add this feature's roles while retaining all other profiles.

    Use full reconciliation only for a deliberate, coordinated role removal.
    """
    _require(db.dialect.name == "postgresql" and db.in_transaction(), "PostgreSQL owner transaction required")
    private = capability_schema_name(application_schema)
    quote = db.dialect.identifier_preparer.quote_identifier
    qp = quote(private)
    db.exec_driver_sql(f"LOCK TABLE {qp}.clinic_capability_namespace, {qp}.clinic_capability_role_profile IN ACCESS EXCLUSIVE MODE")
    validate_namespace(db, application_schema, expected_owner=expected_owner,
                       trusted_owner_members=trusted_owner_members)
    desired = dict(db.execute(text(f"SELECT role_name,role_kind FROM {qp}.clinic_capability_role_profile")).all())
    additions = [(name, "backend") for name in backend_roles] + [(name, "capability_owner") for name in capability_owner_roles]
    seen: set[str] = set()
    for name, kind in additions:
        _identifier(name)
        _require(name not in seen and (name not in desired or desired[name] == kind), "Conflicting capability role kind")
        seen.add(name)
        desired[name] = kind
    reconcile_namespace_roles(
        db, application_schema, expected_owner=expected_owner,
        backend_roles=tuple(sorted(name for name, kind in desired.items() if kind == "backend")),
        capability_owner_roles=tuple(sorted(name for name, kind in desired.items() if kind == "capability_owner")),
        trusted_owner_members=trusted_owner_members,
    )
