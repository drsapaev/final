"""Restrict default TRUNCATE grants for a PostgreSQL financial table creator."""

from __future__ import annotations

import argparse
import os

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError

_GATEWAY_ROLES = ("anon", "authenticated", "service_role")

_TARGET = text("""
    SELECT namespaces.oid AS schema_oid, creator.oid AS creator_oid,
           pg_catalog.format(
               'ALTER DEFAULT PRIVILEGES FOR ROLE %I IN SCHEMA %I '
               'REVOKE TRUNCATE ON TABLES FROM %s RESTRICT',
               creator.rolname, namespaces.nspname,
               pg_catalog.concat_ws(', ', 'PUBLIC', (
                   SELECT pg_catalog.string_agg(
                       pg_catalog.quote_ident(gateway.rolname), ', ' ORDER BY gateway.rolname
                   )
                   FROM pg_catalog.pg_roles gateway
                   WHERE gateway.rolname = ANY(:gateway_roles)
               ))
           ) AS statement
    FROM pg_catalog.pg_namespace namespaces
    CROSS JOIN pg_catalog.pg_roles creator
    WHERE pg_catalog.current_database() = :database
      AND creator.rolname = CURRENT_USER AND creator.rolname = :creator
      AND namespaces.nspname = :schema
      AND namespaces.nspname !~ '^pg_' AND namespaces.nspname <> 'information_schema'
      AND pg_catalog.has_schema_privilege(creator.oid, namespaces.oid, 'CREATE')
""")

_REMAINING_ACCESS = text("""
    WITH activatable AS (
        SELECT DISTINCT candidate.oid
        FROM pg_catalog.pg_roles gateway
        JOIN pg_catalog.pg_roles candidate
          ON candidate.oid = gateway.oid
          OR pg_catalog.pg_has_role(gateway.oid, candidate.oid, :activation)
        WHERE gateway.rolname = ANY(:gateway_roles)
    ), gateway_access AS (
        SELECT DISTINCT inherited.oid
        FROM activatable
        JOIN pg_catalog.pg_roles inherited
          ON inherited.oid = activatable.oid
          OR pg_catalog.pg_has_role(activatable.oid, inherited.oid, 'USAGE')
    )
    SELECT EXISTS (
        SELECT 1 FROM gateway_access WHERE oid = :creator_oid
    ) AS creator_access,
    COALESCE(pg_catalog.bool_or(defaults.defaclnamespace = 0), false) AS global_grant,
    COALESCE(pg_catalog.bool_or(defaults.defaclnamespace <> 0), false) AS schema_grant
    FROM pg_catalog.pg_default_acl defaults
    CROSS JOIN LATERAL pg_catalog.aclexplode(defaults.defaclacl) acl
    WHERE defaults.defaclrole = :creator_oid
      AND defaults.defaclnamespace IN (0, :schema_oid)
      AND defaults.defaclobjtype = 'r' AND acl.privilege_type = 'TRUNCATE'
      AND (acl.grantee = 0 OR acl.grantee IN (SELECT oid FROM gateway_access))
""")


class DefaultAclError(RuntimeError):
    """The requested PostgreSQL privilege boundary could not be verified."""


def provision(engine: Engine, *, database: str, schema: str, creator: str) -> None:
    """Revoke the creator's scoped default grant between schema changes."""
    if engine.dialect.name != "postgresql":
        raise DefaultAclError("PostgreSQL required")

    with (
        engine.connect() as connection,
        connection.execution_options(isolation_level="READ COMMITTED").begin(),
    ):
        roles = list(_GATEWAY_ROLES)
        target = (
            connection.execute(
                _TARGET,
                {
                    "database": database,
                    "schema": schema,
                    "creator": creator,
                    "gateway_roles": roles,
                },
            )
            .mappings()
            .one_or_none()
        )
        if target is None:
            raise DefaultAclError(
                "Expected database, active creator, and schema CREATE access required"
            )

        connection.exec_driver_sql(
            target["statement"], execution_options={"no_parameters": True}
        )
        activation = (
            "SET" if connection.dialect.server_version_info >= (16,) else "MEMBER"
        )
        remaining = (
            connection.execute(
                _REMAINING_ACCESS,
                {
                    "schema_oid": target["schema_oid"],
                    "creator_oid": target["creator_oid"],
                    "activation": activation,
                    "gateway_roles": roles,
                },
            )
            .mappings()
            .one()
        )
        if remaining["creator_access"]:
            raise DefaultAclError("A gateway role can act as the table creator")
        if remaining["global_grant"]:
            raise DefaultAclError("Global default TRUNCATE requires separate review")
        if remaining["schema_grant"]:
            raise DefaultAclError(
                "Indirect default TRUNCATE remains in the requested schema"
            )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", required=True)
    parser.add_argument("--schema", required=True)
    parser.add_argument("--creator", required=True)
    args = parser.parse_args()
    url = os.getenv("DATABASE_URL")
    if not url:
        parser.error("DATABASE_URL must be configured")

    try:
        engine = create_engine(url, hide_parameters=True)
        try:
            provision(
                engine, database=args.database, schema=args.schema, creator=args.creator
            )
        finally:
            engine.dispose()
    except DefaultAclError as exc:
        parser.exit(1, f"{exc}\n")
    except SQLAlchemyError:
        parser.exit(1, "PostgreSQL default privilege operation failed\n")


if __name__ == "__main__":
    main()
