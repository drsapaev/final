"""QD-2A EXPAND: queue_resources table + dual-owner columns (additive only).

Owner decision 2026-09-06 (QD-2 FINAL D-spec, staged PRs). QD-2 replaces
the synthetic ``*_resource`` User+Doctor bridge with a dedicated
QueueResource routing entity. This first stage is EXPAND — purely
additive, old production code stays fully compatible:

- create ``queue_resources`` (code/queue_tag UNIQUE, display_name, active,
  start_number_online / max_online_per_day carried from the synthetic
  Doctor rows, default_cabinet, timestamps) + RLS parity with the
  0046/0050/0051 sweeps (the CI RLS guardrail requires it);
- add nullable ``daily_queues.queue_resource_id`` FK → queue_resources.id
  (+ ``ix_daily_queues_queue_resource_id``, the 0035 FK-index convention);
- relax ``daily_queues.specialist_id`` NOT NULL → NULL (doctorless rows
  only arrive with the QD-2B backfill).

Every step is inspector-guarded, so a re-run on a partially-migrated
environment is a no-op — the same already-migrated-pass contract as
0056/0057.

Deliberately NOT in this stage (per the D-spec):
- NO XOR CHECK (QD-2D, after backfill + runtime-switch proofs);
- NO uniqueness — neither UNIQUE(day, queue_resource_id) nor the partial
  active-unique index (QD-2D, after a deduplicated backfill);
- NO seeds — the registry is explicit and EMPTY here (QD-2B seeds proven
  doctorless tags only; stomatology/procedures/cosmetology are never
  auto-created);
- NO runtime switch, NO synthetic identity deletion (QD-2C/QD-2E).

Dialect notes:
- Online PostgreSQL (CI / production): direct ALTERs — add_column +
  create_foreign_key + alter_column DROP NOT NULL (the 0054 pattern).
- SQLite (module-level migration tests): the daily_queues expansion runs
  through batch_alter_table (table-recreate), which is the only way
  SQLite can add an FK / relax NOT NULL.
- Offline ``--sql`` mode renders the fresh-install path (0051 pattern).
- ``ALTER TABLE queue_resources ENABLE ROW LEVEL SECURITY`` is
  PostgreSQL-only — dialect-guarded here, rendered in offline mode, and
  proven by CI's disposable-Postgres run + RLS guard step.

Downgrade reverses exactly: re-tighten specialist_id to NOT NULL (fails
LOUDLY when any doctorless row exists — QD-2B+ data must never be
silently truncated), drop the FK, the column and its index, then drop
queue_resources with its index (RLS dies with the table).
"""
from __future__ import annotations

import sqlalchemy as sa

from alembic import context, op

# Revision identifiers — chained after 0057_lab_resource_internal_role.
revision = "0058_queue_resource_expand"
down_revision = "0057_lab_resource_internal_role"
branch_labels = None
depends_on = None

_MIGRATION_NAME = "0058_queue_resource_expand"


def _table_exists(conn, name: str) -> bool:
    return sa.inspect(conn).has_table(name)


def _columns(conn, table: str) -> dict[str, dict]:
    try:
        return {col["name"]: col for col in sa.inspect(conn).get_columns(table)}
    except Exception:  # noqa: BLE001 — inspector is best-effort by design
        return {}


def _index_names(conn, table: str) -> set[str]:
    try:
        return {idx["name"] for idx in sa.inspect(conn).get_indexes(table)}
    except Exception:  # noqa: BLE001
        return set()


def _has_fk_to(conn, table: str, referred_table: str) -> bool:
    try:
        fks = sa.inspect(conn).get_foreign_keys(table)
    except Exception:  # noqa: BLE001
        return False
    return any(fk.get("referred_table") == referred_table for fk in fks)


def _require_daily_queues(conn) -> None:
    """Loud abort before ANY DDL when daily_queues is missing — the
    migration expands an existing baseline-0001 table, it never creates
    it. Aborting first keeps the no-partial-changes contract."""
    if not _table_exists(conn, "daily_queues"):
        raise RuntimeError(
            f"{_MIGRATION_NAME}: daily_queues table not found — this migration "
            "expands the baseline-0001 table and refuses to run against a "
            "schema where it is absent (manual reconciliation required)"
        )


def _create_queue_resources_table(ops, conn) -> None:
    """Create the routing registry table (guarded no-op when present)."""
    if conn is not None and _table_exists(conn, "queue_resources"):
        return
    ops.create_table(
        "queue_resources",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("code", sa.String(length=50), nullable=False),
        sa.Column("queue_tag", sa.String(length=32), nullable=False),
        sa.Column("display_name", sa.String(length=100), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column(
            "start_number_online", sa.Integer(), nullable=False, server_default=sa.text("1")
        ),
        sa.Column(
            "max_online_per_day", sa.Integer(), nullable=False, server_default=sa.text("15")
        ),
        sa.Column("default_cabinet", sa.String(length=20), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=True,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=True,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_queue_resources"),
        sa.UniqueConstraint("code", name="uq_queue_resources_code"),
        sa.UniqueConstraint("queue_tag", name="uq_queue_resources_queue_tag"),
    )
    ops.create_index("ix_queue_resources_id", "queue_resources", ["id"], unique=False)


def _enable_queue_resources_rls(ops, conn) -> None:
    """RLS parity with the 0046/0050/0051 sweeps — PostgreSQL only (the
    SQLite test world has no RLS; offline --sql renders it)."""
    if conn is not None and conn.dialect.name != "postgresql":
        return
    ops.execute(sa.text("ALTER TABLE queue_resources ENABLE ROW LEVEL SECURITY"))


def _expand_daily_queues_direct(ops, conn) -> None:
    """PostgreSQL (online + offline render): direct ALTERs, each guarded."""
    add_column = conn is None or "queue_resource_id" not in _columns(conn, "daily_queues")
    if add_column:
        ops.add_column(
            "daily_queues",
            sa.Column("queue_resource_id", sa.Integer(), nullable=True),
        )
    if conn is None or "ix_daily_queues_queue_resource_id" not in _index_names(
        conn, "daily_queues"
    ):
        ops.create_index(
            "ix_daily_queues_queue_resource_id",
            "daily_queues",
            ["queue_resource_id"],
            unique=False,
        )
    if conn is None or not _has_fk_to(conn, "daily_queues", "queue_resources"):
        ops.create_foreign_key(
            "fk_daily_queues_queue_resource_id",
            "daily_queues",
            "queue_resources",
            ["queue_resource_id"],
            ["id"],
        )
    specialist = _columns(conn, "daily_queues").get("specialist_id") if conn else None
    if conn is None or (specialist is not None and not specialist.get("nullable", False)):
        ops.alter_column(
            "daily_queues",
            "specialist_id",
            existing_type=sa.Integer(),
            nullable=True,
        )


def _expand_daily_queues_batch(ops, conn) -> None:
    """SQLite: table-recreate via batch_alter_table — the only way the
    dialect can add an FK constraint / relax NOT NULL. Guards mirror the
    direct path so a re-run is a no-op batch."""
    cols = _columns(conn, "daily_queues")
    need_column = "queue_resource_id" not in cols
    need_fk = not _has_fk_to(conn, "daily_queues", "queue_resources")
    specialist = cols.get("specialist_id")
    need_relax = specialist is not None and not specialist.get("nullable", False)
    with ops.batch_alter_table("daily_queues") as batch:
        if need_column:
            batch.add_column(sa.Column("queue_resource_id", sa.Integer(), nullable=True))
        if need_fk:
            batch.create_foreign_key(
                "fk_daily_queues_queue_resource_id",
                "queue_resources",
                ["queue_resource_id"],
                ["id"],
            )
        if need_relax:
            batch.alter_column(
                "specialist_id", existing_type=sa.Integer(), nullable=True
            )
    if "ix_daily_queues_queue_resource_id" not in _index_names(conn, "daily_queues"):
        ops.create_index(
            "ix_daily_queues_queue_resource_id",
            "daily_queues",
            ["queue_resource_id"],
            unique=False,
        )


def _expand_daily_queues(ops, conn) -> None:
    if conn is None or conn.dialect.name == "postgresql":
        _expand_daily_queues_direct(ops, conn)
    else:
        _expand_daily_queues_batch(ops, conn)


def _doctorless_rows_exist(conn) -> bool:
    row = conn.execute(
        sa.text("SELECT COUNT(*) FROM daily_queues WHERE specialist_id IS NULL")
    ).scalar()
    return bool(row)


def _revert_daily_queues(ops, conn) -> None:
    """Downgrade half 1 — loud abort when doctorless rows exist (their
    specialist_id would violate the restored NOT NULL), then restore the
    pre-0058 shape."""
    if _doctorless_rows_exist(conn):
        raise RuntimeError(
            f"{_MIGRATION_NAME} downgrade: daily_queues contains rows with "
            "specialist_id IS NULL (QD-2B+ resource-owned data) — refusing to "
            "re-tighten NOT NULL and silently break them; drain/migrate those "
            "rows first"
        )
    cols = _columns(conn, "daily_queues")
    specialist = cols.get("specialist_id")
    if specialist is not None and specialist.get("nullable", False):
        if conn.dialect.name == "postgresql":
            ops.alter_column(
                "daily_queues",
                "specialist_id",
                existing_type=sa.Integer(),
                nullable=False,
            )
        else:
            with ops.batch_alter_table("daily_queues") as batch:
                batch.alter_column(
                    "specialist_id", existing_type=sa.Integer(), nullable=False
                )
    if _has_fk_to(conn, "daily_queues", "queue_resources"):
        if conn.dialect.name == "postgresql":
            ops.drop_constraint(
                "fk_daily_queues_queue_resource_id", "daily_queues", type_="foreignkey"
            )
        else:
            with ops.batch_alter_table("daily_queues") as batch:
                batch.drop_constraint(
                    "fk_daily_queues_queue_resource_id", type_="foreignkey"
                )
    if "ix_daily_queues_queue_resource_id" in _index_names(conn, "daily_queues"):
        ops.drop_index(
            "ix_daily_queues_queue_resource_id", table_name="daily_queues"
        )
    if "queue_resource_id" in cols:
        if conn.dialect.name == "postgresql":
            ops.drop_column("daily_queues", "queue_resource_id")
        else:
            with ops.batch_alter_table("daily_queues") as batch:
                batch.drop_column("queue_resource_id")


def _drop_queue_resources(ops, conn) -> None:
    """Downgrade half 2 — remove the registry table (guarded)."""
    if conn is not None and not _table_exists(conn, "queue_resources"):
        return
    if conn is None or "ix_queue_resources_id" in _index_names(conn, "queue_resources"):
        ops.drop_index("ix_queue_resources_id", table_name="queue_resources")
    ops.drop_table("queue_resources")


def upgrade() -> None:
    bind = op.get_bind()
    if context.is_offline_mode():
        # Offline --sql mode runs on a MockConnection with no inspector:
        # render the fresh-install path (0051 pattern) — full DDL + RLS.
        _create_queue_resources_table(op, None)
        _enable_queue_resources_rls(op, None)
        _expand_daily_queues(op, None)
        return
    _require_daily_queues(bind)
    _create_queue_resources_table(op, bind)
    _enable_queue_resources_rls(op, bind)
    _expand_daily_queues(op, bind)


def downgrade() -> None:
    bind = op.get_bind()
    if context.is_offline_mode():
        # Offline render: assume the fully-migrated shape and reverse it.
        _revert_daily_queues_offline(op)
        _drop_queue_resources(op, None)
        return
    _require_daily_queues(bind)
    _revert_daily_queues(op, bind)
    _drop_queue_resources(op, bind)


def _revert_daily_queues_offline(ops) -> None:
    """Offline downgrade render (PG dialect, no inspector): reverse the
    fresh-install shape directly."""
    ops.alter_column(
        "daily_queues", "specialist_id", existing_type=sa.Integer(), nullable=False
    )
    ops.drop_constraint(
        "fk_daily_queues_queue_resource_id", "daily_queues", type_="foreignkey"
    )
    ops.drop_index("ix_daily_queues_queue_resource_id", table_name="daily_queues")
    ops.drop_column("daily_queues", "queue_resource_id")
