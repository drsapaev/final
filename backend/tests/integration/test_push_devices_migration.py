"""PR-6: push_devices migration — offline PG-dialect DDL validation.

The SQLite chain cannot host this DDL (partial unique index with WHERE,
RLS statements); CI runs the authoritative ``alembic upgrade head`` on
real PostgreSQL (plus the gate_d disposable-DB probe in
``test_push_devices_pg.py``). Here we validate the exact DDL the
migration renders under the PostgreSQL dialect, offline — the QF-1 0054
pattern already used by test_queue_resource_expand.py.

Contract pinned by the owner:
- table created ONLY by Alembic (no create_all in production paths);
- RLS enabled in the SAME creating migration (relrowsecurity=true is
  asserted against a disposable PG by the gate_d probe);
- token is TEXT, not VARCHAR(255);
- one ACTIVE credential must not duplicate: partial unique index over
  (provider, token) WHERE invalidated_at IS NULL;
- closed enums provider IN (fcm, webpush) / platform IN (android, web).
"""

from __future__ import annotations

import importlib.util
import io
import os
import re

MIGRATION_0064 = os.path.join(
    os.path.dirname(__file__),
    "..",
    "..",
    "alembic",
    "versions",
    "0064_push_devices_registry.py",
)


def _load_migration_0064():
    spec = importlib.util.spec_from_file_location(
        "migration_0064_push_devices_registry", MIGRATION_0064
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _offline_pg_sql(fn) -> str:
    from alembic.migration import MigrationContext
    from alembic.operations import Operations

    buffer = io.StringIO()
    context = MigrationContext.configure(
        dialect_name="postgresql",
        opts={"as_sql": True, "output_buffer": buffer},
    )
    with Operations.context(context):
        fn()
    return buffer.getvalue()


def _normalize(sql: str) -> str:
    return re.sub(r"\s+", " ", sql)


def test_migration_module_chain_ids() -> None:
    module = _load_migration_0064()
    assert module.revision == "0064_push_devices_registry"
    assert module.down_revision == "0063_queue_resource_contract"


def test_upgrade_renders_registry_ddl_with_rls() -> None:
    module = _load_migration_0064()
    sql = _normalize(_offline_pg_sql(module.upgrade))

    # Registry table, canonical multi-device shape
    assert "CREATE TABLE push_devices" in sql
    assert "id SERIAL NOT NULL" in sql
    assert "user_id INTEGER NOT NULL" in sql
    assert "provider VARCHAR(16) NOT NULL" in sql
    assert "platform VARCHAR(16) NOT NULL" in sql
    assert "device_id VARCHAR(128)" in sql
    # TEXT — the credential column must NOT inherit a legacy width.
    assert "token TEXT NOT NULL" in sql
    assert "VARCHAR(255)" not in sql
    assert "credential JSON" in sql
    assert "enabled BOOLEAN DEFAULT true NOT NULL" in sql
    assert "last_seen_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL" in sql
    assert "invalidated_at TIMESTAMP WITH TIME ZONE" in sql

    # Closed enums as CHECK constraints
    assert (
        "CONSTRAINT ck_push_devices_provider CHECK (provider IN ('fcm', 'webpush'))"
        in sql
    )
    assert (
        "CONSTRAINT ck_push_devices_platform CHECK (platform IN ('android', 'web'))"
        in sql
    )

    # FK to users with cascade (device rows die with the account)
    assert "FOREIGN KEY(user_id) REFERENCES users (id)" in sql
    assert "ON DELETE CASCADE" in sql

    # One ACTIVE credential must not duplicate — partial unique index.
    assert (
        "CREATE UNIQUE INDEX uq_push_devices_active_credential ON push_devices "
        "(provider, token) WHERE invalidated_at IS NULL" in sql
    )
    assert "CREATE INDEX ix_push_devices_user_id ON push_devices (user_id)" in sql
    assert (
        "CREATE INDEX ix_push_devices_user_device ON push_devices (user_id, device_id)"
        in sql
    )

    # RLS in the SAME migration that creates the table (0046 contract)
    assert "ALTER TABLE public.push_devices ENABLE ROW LEVEL SECURITY" in sql


def test_downgrade_renders_reverse_ddl() -> None:
    module = _load_migration_0064()
    sql = _normalize(_offline_pg_sql(module.downgrade))

    assert "DROP INDEX uq_push_devices_active_credential" in sql
    assert "DROP INDEX ix_push_devices_user_device" in sql
    assert "DROP INDEX ix_push_devices_user_id" in sql
    assert "DROP TABLE push_devices" in sql
    # Legacy column untouched — its destructive removal is a SEPARATE PR
    # after the post-census channel decision.
    assert "users" not in sql.replace("push_devices", "")


def test_model_and_migration_agree_on_core_shape() -> None:
    """create_all (test world) and Alembic (production) must produce the
    same essential schema for push_devices."""
    from app.db import base  # noqa: F401 - registers models
    from app.db.base_class import Base

    table = Base.metadata.tables["push_devices"]
    columns = {c.name: c for c in table.columns}
    assert set(columns) == {
        "id",
        "user_id",
        "provider",
        "platform",
        "device_id",
        "token",
        "credential",
        "enabled",
        "last_seen_at",
        "invalidated_at",
        "created_at",
        "updated_at",
    }
    # token is Text in the ORM too (not String(255)).
    assert columns["token"].type.__class__.__name__ == "Text"
    constraint_names = {c.name for c in table.constraints if c.name}
    assert "ck_push_devices_provider" in constraint_names
    assert "ck_push_devices_platform" in constraint_names
    index_names = {i.name for i in table.indexes}
    assert {
        "uq_push_devices_active_credential",
        "ix_push_devices_user_device",
        "ix_push_devices_user_id",
    } <= index_names
