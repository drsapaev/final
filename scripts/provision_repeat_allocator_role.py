"""Grant reviewed repeat-evidence allocator usage; run with traffic drained.

This operator tool never connects unless explicitly invoked. It imports the
exact reviewed 0103 preflight from verified bytes and grants only requested
runtime roles; unexpected roles, grants or allocator state fail closed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
from types import ModuleType, SimpleNamespace

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

MIGRATION_SHA256 = "e5ffac186b1086a0b9ac94bfa5b542adbdd41bff1ad3c69e226e46d237a8cf29"
MIGRATION_PATH = Path(__file__).resolve().parents[1] / "backend/alembic/versions/0103_visit_consultation_completion.py"


class ProvisionError(RuntimeError):
    """The allocator or the explicitly reviewed role profile is unsafe."""


def _migration() -> ModuleType:
    try:
        source = MIGRATION_PATH.read_bytes()
    except OSError:
        raise ProvisionError("Reviewed allocator migration is unavailable") from None
    if hashlib.sha256(source).hexdigest() != MIGRATION_SHA256:
        raise ProvisionError("Reviewed allocator migration has changed")
    module = ModuleType("reviewed_repeat_allocator_0103")
    module.__file__ = str(MIGRATION_PATH)
    exec(compile(source, str(MIGRATION_PATH), "exec"), module.__dict__)  # noqa: S102 — verified immutable migration
    if module.revision != "0103_visit_repeat_evidence":
        raise ProvisionError("Unexpected allocator revision")
    return module


def provision(
    engine: Engine, *, schema: str, expected_owner: str,
    runtime_roles: tuple[str, ...], trusted_owner_members: tuple[str, ...] = (),
) -> None:
    """Provision exact reviewed roles transactionally; never revoke grants."""
    if engine.dialect.name != "postgresql":
        raise ProvisionError("PostgreSQL is required")
    if not runtime_roles or not schema or not expected_owner:
        raise ProvisionError("Explicit schema, owner and runtime roles are required")
    if len(runtime_roles) != len(set(runtime_roles)) or len(trusted_owner_members) != len(set(trusted_owner_members)):
        raise ProvisionError("Role lists must not contain duplicates")
    module = _migration()
    # Module-local configuration avoids changing the process environment when
    # this function is imported by tests or operator tooling.
    module.os = SimpleNamespace(environ={
        "REPEAT_ALLOCATOR_TRUSTED_OWNER_MEMBERS": json.dumps(trusted_owner_members),
        "REPEAT_ALLOCATOR_TRUSTED_SEQUENCE_USERS": json.dumps(runtime_roles),
    })
    quote = engine.dialect.identifier_preparer.quote_identifier
    with engine.begin() as db:
        module.op = Operations(MigrationContext.configure(db, opts={"version_table_schema": schema}))
        qualified, owner, _ = module._pg_allocator_preflight()
        if owner != expected_owner:
            raise ProvisionError("Allocator owner differs from reviewed owner")
        if db.execute(text("SELECT pg_catalog.to_regclass(:name)"), {"name": qualified}).scalar_one_or_none() is None:
            raise ProvisionError("Allocator sequence does not exist")
        # Acquire the sequence DDL lock before repeating the preflight. Cache
        # is exactly one and NO CYCLE was already checked; this does not reset
        # or advance the counter. Role/ACL DDL requires drained traffic.
        db.exec_driver_sql(f"ALTER SEQUENCE {qualified} NO CYCLE")
        module._pg_allocator_preflight()
        for role in runtime_roles:
            db.exec_driver_sql(f"GRANT USAGE ON SEQUENCE {qualified} TO {quote(role)}")
        module._pg_allocator_preflight(require_complete=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Provision repeat allocator roles while traffic is drained")
    parser.add_argument("--schema", required=True)
    parser.add_argument("--schema-owner", required=True)
    parser.add_argument("--runtime-role", action="append", required=True,
                        help="Reviewed runtime LOGIN; repeat for every existing or desired sequence user")
    parser.add_argument("--trusted-owner-member", action="append", default=[])
    args = parser.parse_args()
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise ProvisionError("DATABASE_URL is required")
    engine = create_engine(url)
    try:
        provision(engine, schema=args.schema, expected_owner=args.schema_owner,
                  runtime_roles=tuple(args.runtime_role), trusted_owner_members=tuple(args.trusted_owner_member))
    finally:
        engine.dispose()
    print("Repeat allocator roles provisioned; verify runtime access before enabling traffic.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
