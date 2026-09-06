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

Drift safety (Codex round-1 P1/P2): a pre-existing queue_resources table
(manual/interrupted rollout) is adopted only when its full shape matches
this migration's contract — columns, nullability, UNIQUE code/queue_tag;
anything else aborts loudly BEFORE any DDL (the 0051 adoption-validation
pattern — the chain is never stamped against an incompatible registry).
Any FK to queue_resources on daily_queues that is not exactly
fk_daily_queues_queue_resource_id (queue_resource_id) → queue_resources
(id) is drift: a wrong-column FK would leave the owner unenforced, a
differently-named FK would break the name-based downgrade — abort.
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

# The canonical daily_queues → queue_resources FK (QD-2D partial-unique/
# XOR follow-ups and the downgrade reference this exact name).
_FK_NAME = "fk_daily_queues_queue_resource_id"

# Full queue_resources contract (name → expected nullable) — the adoption
# validation for a pre-existing table (Codex round-1 P1).
_EXPECTED_QUEUE_RESOURCES_NULLABLE = {
    "id": False,
    "code": False,
    "queue_tag": False,
    "display_name": False,
    "active": False,
    "start_number_online": False,
    "max_online_per_day": False,
    "default_cabinet": True,
    "created_at": True,
    "updated_at": True,
}


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


def _foreign_keys(conn, table: str) -> list[dict]:
    try:
        return sa.inspect(conn).get_foreign_keys(table)
    except Exception:  # noqa: BLE001
        return []


def _is_canonical_resource_fk(fk: dict) -> bool:
    """Exact match: name + constrained columns + referred table/columns.
    SQLite and PostgreSQL both reflect FK constraint names (verified by
    the suite's naming-contract pin)."""
    return (
        fk.get("name") == _FK_NAME
        and fk.get("referred_table") == "queue_resources"
        and (fk.get("constrained_columns") or []) == ["queue_resource_id"]
        and (fk.get("referred_columns") or []) == ["id"]
    )


def _resource_owner_fks(conn) -> list[dict]:
    return [
        fk
        for fk in _foreign_keys(conn, "daily_queues")
        if fk.get("referred_table") == "queue_resources"
    ]


def _canonical_resource_fk_present(conn) -> bool:
    return any(_is_canonical_resource_fk(fk) for fk in _resource_owner_fks(conn))


def _require_no_unexpected_resource_fks(conn) -> None:
    """Codex round-1 P2: every FK to queue_resources must BE the canonical
    constraint. A different name or different columns is drift (manual
    patching / interrupted rollout) — abort loudly instead of silently
    skipping the canonical create or breaking the name-based downgrade."""
    for fk in _resource_owner_fks(conn):
        if not _is_canonical_resource_fk(fk):
            raise RuntimeError(
                f"{_MIGRATION_NAME}: daily_queues has an unexpected foreign key "
                f"to queue_resources ({fk.get('name')!r} on "
                f"{fk.get('constrained_columns')}) — expected exactly "
                f"{_FK_NAME!r} on ['queue_resource_id'] referencing ['id']; "
                "manual reconciliation required"
            )


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


def _validate_queue_resources_contract(conn) -> None:
    """Codex round-1 P1: a pre-existing queue_resources table (manual or
    interrupted rollout) is adopted ONLY when its full shape matches the
    0058 contract — column set, nullability, UNIQUE coverage of code and
    queue_tag (by constraint name or as a unique index, dialect-agnostic).
    Any drift aborts loudly BEFORE any DDL, mirroring the 0051 adoption
    validation, so the chain is never stamped against an incompatible
    registry."""
    cols = _columns(conn, "queue_resources")
    expected = _EXPECTED_QUEUE_RESOURCES_NULLABLE
    missing = sorted(set(expected) - set(cols))
    unexpected = sorted(set(cols) - set(expected))
    if missing or unexpected:
        raise RuntimeError(
            f"{_MIGRATION_NAME}: pre-existing queue_resources table does not "
            f"match the 0058 contract (missing={missing}, unexpected={unexpected}) "
            "— manual reconciliation required before this migration can adopt it"
        )
    for name, nullable in expected.items():
        if bool(cols[name].get("nullable")) is not nullable:
            raise RuntimeError(
                f"{_MIGRATION_NAME}: pre-existing queue_resources table has "
                f"{name!r} nullable={cols[name].get('nullable')}, expected "
                f"nullable={nullable} — manual reconciliation required"
            )
    unique_sets: set[frozenset[str]] = set()
    try:
        for uc in sa.inspect(conn).get_unique_constraints("queue_resources"):
            unique_sets.add(frozenset(uc.get("column_names") or []))
    except Exception:  # noqa: BLE001 — constraint reflection is best-effort
        pass
    try:
        for idx in sa.inspect(conn).get_indexes("queue_resources"):
            if idx.get("unique"):
                unique_sets.add(frozenset(idx.get("column_names") or []))
    except Exception:  # noqa: BLE001
        pass
    if (
        frozenset({"code"}) not in unique_sets
        or frozenset({"queue_tag"}) not in unique_sets
    ):
        raise RuntimeError(
            f"{_MIGRATION_NAME}: pre-existing queue_resources table lacks the "
            "UNIQUE contract on code/queue_tag — manual reconciliation required"
        )


def _create_queue_resources_table(ops, conn) -> None:
    """Create the routing registry table. A pre-existing table is adopted
    only after full contract validation (Codex round-1 P1: loud abort on
    drift instead of a silent skip); the id index is ensured either way."""
    if conn is not None and _table_exists(conn, "queue_resources"):
        _validate_queue_resources_contract(conn)
    else:
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
    if conn is None or "ix_queue_resources_id" not in _index_names(
        conn, "queue_resources"
    ):
        ops.create_index("ix_queue_resources_id", "queue_resources", ["id"], unique=False)


def _enable_queue_resources_rls(ops, conn) -> None:
    """RLS parity with the 0046/0050/0051 sweeps — PostgreSQL only (the
    SQLite test world has no RLS; offline --sql renders it)."""
    if conn is not None and conn.dialect.name != "postgresql":
        return
    ops.execute(sa.text("ALTER TABLE queue_resources ENABLE ROW LEVEL SECURITY"))


def _expand_daily_queues_direct(ops, conn) -> None:
    """PostgreSQL (online + offline render): direct ALTERs, each guarded."""
    if conn is not None:
        _require_no_unexpected_resource_fks(conn)
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
    if conn is None or not _canonical_resource_fk_present(conn):
        ops.create_foreign_key(
            _FK_NAME,
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
    direct path (the FK drift check runs first, exactly like the PG path)
    so a re-run is a no-op batch."""
    _require_no_unexpected_resource_fks(conn)
    cols = _columns(conn, "daily_queues")
    need_column = "queue_resource_id" not in cols
    need_fk = not _canonical_resource_fk_present(conn)
    specialist = cols.get("specialist_id")
    need_relax = specialist is not None and not specialist.get("nullable", False)
    with ops.batch_alter_table("daily_queues") as batch:
        if need_column:
            batch.add_column(sa.Column("queue_resource_id", sa.Integer(), nullable=True))
        if need_fk:
            batch.create_foreign_key(
                _FK_NAME,
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
    _require_no_unexpected_resource_fks(conn)
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
    if _canonical_resource_fk_present(conn):
        if conn.dialect.name == "postgresql":
            ops.drop_constraint(
                _FK_NAME, "daily_queues", type_="foreignkey"
            )
        else:
            with ops.batch_alter_table("daily_queues") as batch:
                batch.drop_constraint(
                    _FK_NAME, type_="foreignkey"
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
        _FK_NAME, "daily_queues", type_="foreignkey"
    )
    ops.drop_index("ix_daily_queues_queue_resource_id", table_name="daily_queues")
    ops.drop_column("daily_queues", "queue_resource_id")
