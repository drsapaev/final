"""Pin an explicitly trusted PostgreSQL schema before authentication reads.

This is a runtime check, not a provisioning or DDL helper. Owners must drain
traffic for schema, ACL and role changes. Callers supply trusted deployment
configuration and keep the same transaction through their protected reads.
"""
from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session


class TrustedSchemaUnavailable(RuntimeError):
    """Do not expose internal identifiers or database errors to clients."""


def _identifier(value: object) -> str:
    if not isinstance(value, str) or not value or "\0" in value:
        raise TrustedSchemaUnavailable("Trusted database schema unavailable")
    try:
        if len(value.encode("utf-8")) > 63:
            raise TrustedSchemaUnavailable("Trusted database schema unavailable")
    except UnicodeError:
        raise TrustedSchemaUnavailable("Trusted database schema unavailable") from None
    return value


def _names(values: object) -> tuple[str, ...]:
    if not isinstance(values, (tuple, list)):
        raise TrustedSchemaUnavailable("Trusted database schema unavailable")
    names = tuple(_identifier(value) for value in values)
    if len(set(names)) != len(names) or any(value.lower() in {"public", "anon", "authenticated"} for value in names):
        raise TrustedSchemaUnavailable("Trusted database schema unavailable")
    return names


def _check_owner_members(db: Session, owner_oid: int, expected: tuple[str, ...]) -> None:
    actual = db.execute(text("""
      SELECT r.rolname,r.rolbypassrls,r.rolcreaterole,r.rolcreatedb,r.rolreplication
      FROM pg_catalog.pg_roles r WHERE r.oid<>:owner_oid AND NOT r.rolsuper
        AND pg_catalog.pg_has_role(r.oid,:owner_oid,'MEMBER')
    """), {"owner_oid": owner_oid}).mappings().all()
    if ({item["rolname"] for item in actual} != set(expected)
        or any(any(item[key] for key in ("rolbypassrls", "rolcreaterole", "rolcreatedb", "rolreplication"))
               for item in actual)):
        raise TrustedSchemaUnavailable("Trusted database schema unavailable")


def _approved_roles(
    db: Session, *, owner_oid: int, owner_name: str, owner_members: tuple[str, ...],
    runtime_oid: int, runtime_name: str, role_groups: tuple[tuple[str, ...], ...],
) -> dict[str, int]:
    names = set().union(*role_groups)
    if owner_name in names or runtime_name in names:
        raise TrustedSchemaUnavailable("Trusted database schema unavailable")
    rows = db.execute(text("""
      SELECT oid,rolname,rolsuper,rolbypassrls,rolcreaterole,rolcreatedb,rolreplication
      FROM pg_catalog.pg_roles WHERE rolname = ANY(:names)
    """), {"names": list(names)}).mappings().all()
    if ({row["rolname"] for row in rows} != names
        or any(any(row[key] for key in ("rolsuper", "rolbypassrls", "rolcreaterole", "rolcreatedb", "rolreplication"))
               for row in rows)):
        raise TrustedSchemaUnavailable("Trusted database schema unavailable")
    oids = {row["rolname"]: row["oid"] for row in rows}
    all_oids = list(oids.values())
    unsafe_membership = db.execute(text("""
      SELECT EXISTS(SELECT 1 FROM pg_catalog.pg_roles r,
        pg_catalog.unnest(CAST(:role_oids AS oid[])) reviewed(oid)
        WHERE r.oid<>reviewed.oid AND pg_catalog.pg_has_role(reviewed.oid,r.oid,'MEMBER')
          AND (r.oid=:owner OR r.rolsuper OR r.rolbypassrls OR r.rolcreaterole OR r.rolcreatedb
               OR r.rolreplication OR r.oid<>ALL(CAST(:role_oids AS oid[]))))
    """), {"owner": owner_oid, "role_oids": all_oids}).scalar_one()
    if unsafe_membership:
        raise TrustedSchemaUnavailable("Trusted database schema unavailable")
    # Inherited access is reviewed separately for each privilege group: a
    # read-only role may not inherit an approved writer's authority.
    for group in role_groups:
        group_oids = [oids[name] for name in group]
        incoming = db.execute(text("""
          SELECT r.rolname FROM pg_catalog.pg_roles r
          WHERE NOT r.rolsuper AND r.oid<>:owner AND r.oid<>:runtime
            AND EXISTS(SELECT 1 FROM pg_catalog.unnest(CAST(:role_oids AS oid[])) approved(oid)
                       WHERE r.oid<>approved.oid AND pg_catalog.pg_has_role(r.oid,approved.oid,'MEMBER'))
        """), {"owner": owner_oid, "runtime": runtime_oid, "role_oids": group_oids}).scalars().all()
        if not set(incoming).issubset(set(group) | set(owner_members)):
            raise TrustedSchemaUnavailable("Trusted database schema unavailable")
    return oids


def _verify_blacklist_visibility(
    db: Session, *, schema: str, runtime_oid: int, runtime_name: str,
    expected_auth_owner: str | None, trusted_auth_owner_members: tuple[str, ...],
    trusted_auth_read_roles: tuple[str, ...], trusted_auth_write_roles: tuple[str, ...],
) -> None:
    """Hold a relation lock and prove the JTI query cannot hide a row."""
    owner = _identifier(expected_auth_owner)
    owner_members = _names(trusted_auth_owner_members)
    read_roles = _names(trusted_auth_read_roles)
    write_roles = _names(trusted_auth_write_roles)
    if owner == runtime_name:
        raise TrustedSchemaUnavailable("Trusted database schema unavailable")
    quote = db.get_bind().dialect.identifier_preparer.quote_identifier
    qualified = f"{quote(schema)}.token_blacklist"
    # Policy and owner DDL require stronger table locks. Retain this lock until
    # the same auth/JTI transaction commits or rolls back.
    db.execute(text(f"LOCK TABLE {qualified} IN ACCESS SHARE MODE"))
    relation = db.execute(text("""
      SELECT c.oid,c.relowner,c.relkind,c.relrowsecurity,c.relforcerowsecurity,r.rolname AS owner_name,
             pg_catalog.has_table_privilege(:runtime,c.oid,'SELECT') AS can_select,
             EXISTS(SELECT 1 FROM pg_catalog.pg_inherits i WHERE i.inhrelid=c.oid OR i.inhparent=c.oid) AS inherited
      FROM pg_catalog.pg_class c JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace
      JOIN pg_catalog.pg_roles r ON r.oid=c.relowner
      WHERE n.nspname=:schema AND c.relname='token_blacklist'
    """), {"runtime": runtime_oid, "schema": schema}).mappings().first()
    if (relation is None or relation["relkind"] != "r" or relation["inherited"]
        or relation["owner_name"] != owner or relation["relowner"] == runtime_oid or not relation["can_select"]):
        raise TrustedSchemaUnavailable("Trusted database schema unavailable")
    _check_owner_members(db, relation["relowner"], owner_members)
    approved = _approved_roles(db, owner_oid=relation["relowner"], owner_name=owner,
                               owner_members=owner_members, runtime_oid=runtime_oid,
                               runtime_name=runtime_name, role_groups=(read_roles, write_roles))
    grants = db.execute(text("""
      SELECT a.grantee,a.privilege_type,a.is_grantable FROM pg_catalog.pg_class c,
        LATERAL pg_catalog.aclexplode(COALESCE(c.relacl,pg_catalog.acldefault('r',c.relowner))) a
      WHERE c.oid=:oid AND a.grantee<>c.relowner
      UNION ALL
      SELECT a.grantee,a.privilege_type,a.is_grantable FROM pg_catalog.pg_attribute col,
        LATERAL pg_catalog.aclexplode(col.attacl) a
      WHERE col.attrelid=:oid AND col.attnum>0 AND NOT col.attisdropped
        AND a.grantee<>:owner
    """), {"oid": relation["oid"], "owner": relation["relowner"]}).all()
    readers = {runtime_oid, *(approved[name] for name in read_roles)}
    writers = {runtime_oid, *(approved[name] for name in write_roles)}
    if any(grant.is_grantable or grant.grantee not in (readers if grant.privilege_type == "SELECT" else writers)
           for grant in grants):
        raise TrustedSchemaUnavailable("Trusted database schema unavailable")
    if relation["relrowsecurity"]:
        policies = db.execute(text("""
          SELECT p.polpermissive,pg_catalog.pg_get_expr(p.polqual,p.polrelid) AS predicate
          FROM pg_catalog.pg_policy p WHERE p.polrelid=:oid AND p.polcmd IN ('r','*')
            AND (0=ANY(p.polroles) OR :runtime=ANY(p.polroles))
        """), {"oid": relation["oid"], "runtime": runtime_oid}).mappings().all()
        if (any(not policy["polpermissive"] for policy in policies)
            or not any(policy["polpermissive"] and policy["predicate"] == "true" for policy in policies)):
            raise TrustedSchemaUnavailable("Trusted database schema unavailable")


def _verify_users_integrity(
    db: Session, *, schema: str, runtime_oid: int, runtime_name: str,
    expected_users_owner: str | None, trusted_users_owner_members: tuple[str, ...],
    trusted_users_write_roles: tuple[str, ...],
) -> None:
    """Fence unauthorized writes to identity, privileges and auth epochs."""
    owner = _identifier(expected_users_owner)
    owner_members = _names(trusted_users_owner_members)
    write_roles = _names(trusted_users_write_roles)
    if owner == runtime_name:
        raise TrustedSchemaUnavailable("Trusted database schema unavailable")
    quote = db.get_bind().dialect.identifier_preparer.quote_identifier
    db.execute(text(f"LOCK TABLE {quote(schema)}.users IN ACCESS SHARE MODE"))
    relation = db.execute(text("""
      SELECT c.oid,c.relowner,c.relkind,r.rolname AS owner_name,
             pg_catalog.has_table_privilege(:runtime,c.oid,'SELECT') AS can_select,
             EXISTS(SELECT 1 FROM pg_catalog.pg_inherits i WHERE i.inhrelid=c.oid OR i.inhparent=c.oid) AS inherited
      FROM pg_catalog.pg_class c JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace
      JOIN pg_catalog.pg_roles r ON r.oid=c.relowner
      WHERE n.nspname=:schema AND c.relname='users'
    """), {"runtime": runtime_oid, "schema": schema}).mappings().first()
    if (relation is None or relation["relkind"] != "r" or relation["inherited"]
        or relation["owner_name"] != owner or relation["relowner"] == runtime_oid or not relation["can_select"]):
        raise TrustedSchemaUnavailable("Trusted database schema unavailable")
    _check_owner_members(db, relation["relowner"], owner_members)
    approved = _approved_roles(db, owner_oid=relation["relowner"], owner_name=owner,
                               owner_members=owner_members, runtime_oid=runtime_oid,
                               runtime_name=runtime_name, role_groups=(write_roles,))
    grants = db.execute(text("""
      SELECT a.grantee,a.is_grantable FROM pg_catalog.pg_class c,
        LATERAL pg_catalog.aclexplode(COALESCE(c.relacl,pg_catalog.acldefault('r',c.relowner))) a
      WHERE c.oid=:oid AND a.privilege_type<>'SELECT' AND a.grantee<>c.relowner
      UNION ALL
      SELECT a.grantee,a.is_grantable FROM pg_catalog.pg_attribute col,
        LATERAL pg_catalog.aclexplode(col.attacl) a
      WHERE col.attrelid=:oid AND col.attnum>0 AND NOT col.attisdropped
        AND a.privilege_type<>'SELECT' AND a.grantee<>:owner
    """), {"oid": relation["oid"], "owner": relation["relowner"]}).all()
    allowed = {runtime_oid, *(approved[name] for name in write_roles)}
    if any(grant.grantee not in allowed or grant.is_grantable for grant in grants):
        raise TrustedSchemaUnavailable("Trusted database schema unavailable")


def pin_application_schema(
    db: Session, *, schema: str | None, expected_owner: str | None,
    expected_runtime_role: str | None, trusted_owner_members: tuple[str, ...] = (),
    expected_auth_owner: str | None = None, trusted_auth_owner_members: tuple[str, ...] = (),
    trusted_auth_read_roles: tuple[str, ...] = (), trusted_auth_write_roles: tuple[str, ...] = (),
    expected_users_owner: str | None = None, trusted_users_owner_members: tuple[str, ...] = (),
    trusted_users_write_roles: tuple[str, ...] = (),
) -> None:
    """Validate the live deployment boundary and pin this transaction's path.

    A PostgreSQL runtime connection must be the explicit nonadministrative
    LOGIN and cannot assume the owner. The complete non-superuser transitive
    owner-members set must match independently configured names. PUBLIC may
    have application-schema USAGE, but no non-owner may have CREATE.
    """
    dialect = db.get_bind().dialect
    if dialect.name == "sqlite":
        return
    if dialect.name != "postgresql":
        raise TrustedSchemaUnavailable("Trusted database schema unavailable")
    name, owner, runtime = map(_identifier, (schema, expected_owner, expected_runtime_role))
    if (name == "information_schema" or name.startswith("pg_") or runtime == owner
        or runtime.lower() in {"public", "anon", "authenticated"}):
        raise TrustedSchemaUnavailable("Trusted database schema unavailable")
    members = _names(trusted_owner_members)
    try:
        row = db.execute(text("""
          SELECT n.oid AS schema_oid,n.nspowner,o.rolname AS owner_name,
                 r.oid AS runtime_oid,r.rolcanlogin,r.rolsuper,r.rolbypassrls,
                 r.rolcreaterole,r.rolcreatedb,r.rolreplication,
                 current_user AS active_name,session_user AS login_name,
                 pg_catalog.pg_has_role(r.oid,n.nspowner,'MEMBER') AS owns_by_membership,
                 pg_catalog.has_schema_privilege(r.oid,n.oid,'USAGE') AS can_use_schema,
                 EXISTS(SELECT 1 FROM pg_catalog.aclexplode(
                   COALESCE(n.nspacl,pg_catalog.acldefault('n',n.nspowner))) a
                   WHERE a.privilege_type='CREATE' AND a.grantee<>n.nspowner) AS unsafe_create
          FROM pg_catalog.pg_namespace n
          JOIN pg_catalog.pg_roles o ON o.oid=n.nspowner
          JOIN pg_catalog.pg_roles r ON r.rolname=:runtime
          WHERE n.nspname=:schema AND o.rolname=:owner
        """), {"runtime": runtime, "schema": name, "owner": owner}).mappings().first()
        if (row is None or row["active_name"] != runtime or row["login_name"] != runtime
            or not row["rolcanlogin"] or any(row[key] for key in (
                "rolsuper", "rolbypassrls", "rolcreaterole", "rolcreatedb", "rolreplication",
                "owns_by_membership", "unsafe_create")) or not row["can_use_schema"]):
            raise TrustedSchemaUnavailable("Trusted database schema unavailable")
        # A dedicated runtime LOGIN has no inherited roles and cannot be
        # assumed by an untrusted role. This conservative profile also fences
        # nonadministrative NOLOGIN capability owners, whose table privileges
        # are not visible from role attributes alone. Superusers remain the
        # trusted database-admin boundary.
        unsafe_runtime_membership = db.execute(text("""
          SELECT EXISTS(SELECT 1 FROM pg_catalog.pg_roles r WHERE r.oid<>:runtime_oid AND (
            (NOT r.rolsuper AND pg_catalog.pg_has_role(r.oid,:runtime_oid,'MEMBER')) OR
            pg_catalog.pg_has_role(:runtime_oid,r.oid,'MEMBER')))
        """), {"runtime_oid": row["runtime_oid"]}).scalar_one()
        if unsafe_runtime_membership:
            raise TrustedSchemaUnavailable("Trusted database schema unavailable")
        _check_owner_members(db, row["nspowner"], members)
        quoted = dialect.identifier_preparer.quote_identifier(name)
        db.execute(text("SELECT pg_catalog.set_config('search_path',:path,true)"),
                   {"path": f"pg_catalog, {quoted}, pg_temp"})
        state = db.execute(text("""
          SELECT pg_catalog.current_schemas(true) AS actual,
                 CASE WHEN pg_catalog.pg_my_temp_schema()=0 THEN NULL
                      ELSE (SELECT nspname FROM pg_catalog.pg_namespace WHERE oid=pg_catalog.pg_my_temp_schema()) END AS temp
        """)).mappings().one()
        expected = ["pg_catalog", name] + ([state["temp"]] if state["temp"] else [])
        if list(state["actual"]) != expected:
            raise TrustedSchemaUnavailable("Trusted database schema unavailable")
        _verify_blacklist_visibility(
            db, schema=name, runtime_oid=row["runtime_oid"], runtime_name=runtime,
            expected_auth_owner=expected_auth_owner, trusted_auth_owner_members=trusted_auth_owner_members,
            trusted_auth_read_roles=trusted_auth_read_roles, trusted_auth_write_roles=trusted_auth_write_roles,
        )
        _verify_users_integrity(
            db, schema=name, runtime_oid=row["runtime_oid"], runtime_name=runtime,
            expected_users_owner=expected_users_owner, trusted_users_owner_members=trusted_users_owner_members,
            trusted_users_write_roles=trusted_users_write_roles,
        )
    except DBAPIError:
        raise TrustedSchemaUnavailable("Trusted database schema unavailable") from None
