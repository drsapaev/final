"""RQ-14.a.1 — DB-level UNIQUE for queue numbering and the doctor axis.

The #3248 transactional fix serialized queue numbering (FOR UPDATE on
the queue row for every writer) and the doctor branch of
get_or_create_daily_queue (advisory lock keyed by (day, specialist)).
These unique indexes are the DB-level second line of defence behind
those locks, registered in PROGRESS E-035 as a deferred operator step
(now that revision 0064 has landed via #3215):

1. ``uq_queue_entries_queue_number`` — a UNIQUE CONSTRAINT (DEFERRABLE
   INITIALLY DEFERRED — PostgreSQL allows DEFERRABLE only on constraints,
   not plain indexes) over ``(queue_id,
   number)`` on ``queue_entries``. The per-queue numbering contract
   (calculate_next_number reads MAX(number) over ALL rows of the queue,
   cancelled included — numbers are never reused) makes a full unique —
   NOT a partial one — the correct shape. Numbers may still repeat
   ACROSS queues (per-queue scope pinned by the RQ-14.a suite).

2. ``uq_daily_queues_active_doctor_day_tag`` — mirror of the 0063
   resource index (``uq_daily_queues_active_resource_day``) for the
   doctor axis: one ACTIVE queue per (day, doctor, effective tag),
   where the effective tag is ``COALESCE(queue_tag, '')`` so the
   queue_batch_repository NULL-tag writers share the key with a no-tag
   queue. Partial (``active AND specialist_id IS NOT NULL``), mirroring
   the 0063 shape: historical inactive rows of the same day are never
   blocked, and re-opening a queue after closing it stays legal.
   This is NOT a D-01 decision: it enforces the identity the existing
   get_or_create_daily_queue lookup already implements.

SAFETY (no silent data repair):
- the upgrade runs a duplicate pre-check over BOTH keys BEFORE any DDL;
- if any duplicates exist, the migration FAILS LOUDLY with technical
  identifiers and counts only (queue_id, number, day, specialist_id,
  tag — no PII whatsoever) and leaves every row untouched; resolving
  pre-existing duplicates is a separate, operator-owned step;
- nothing is deleted, merged, or renumbered here.

Production/staging application is NOT part of this change: merging the
PR does not authorize running this migration against a live database.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0065_queue_numbering_unique"
down_revision = "0064_push_devices_registry"
branch_labels = None
depends_on = None

_ENTRY_DUPES_SQL = """
SELECT queue_id, number, COUNT(*) AS dup_count
FROM queue_entries
GROUP BY queue_id, number
HAVING COUNT(*) > 1
ORDER BY dup_count DESC, queue_id, number
"""

_DOCTOR_DUPES_SQL = """
SELECT day, specialist_id, COALESCE(queue_tag, '') AS effective_tag, COUNT(*) AS dup_count
FROM daily_queues
WHERE active AND specialist_id IS NOT NULL
GROUP BY day, specialist_id, COALESCE(queue_tag, '')
HAVING COUNT(*) > 1
ORDER BY dup_count DESC, day, specialist_id
"""

_MAX_REPORTED_GROUPS = 10


def _fail_on_duplicates(conn, sql: str, label: str, columns: list[str]) -> None:
    rows = conn.execute(sa.text(sql)).fetchall()
    if not rows:
        return
    reported = rows[:_MAX_REPORTED_GROUPS]
    details = "; ".join(
        "(" + ", ".join(f"{col}={val!r}" for col, val in zip(columns, row)) + ")"
        for row in reported
    )
    extra = (
        f"; and {len(rows) - _MAX_REPORTED_GROUPS} more groups"
        if len(rows) > _MAX_REPORTED_GROUPS
        else ""
    )
    raise RuntimeError(
        f"RQ-14.a.1 duplicate pre-check FAILED for {label}: {len(rows)} duplicate "
        f"group(s) would violate the new UNIQUE index. NO data was modified. "
        f"Resolve the duplicates with a separate operator-owned step first. "
        f"Details: {details}{extra}"
    )


def _assert_no_duplicates(conn) -> None:
    _fail_on_duplicates(
        conn,
        _ENTRY_DUPES_SQL,
        "queue numbering (queue_entries.queue_id + number)",
        ["queue_id", "number", "count"],
    )
    _fail_on_duplicates(
        conn,
        _DOCTOR_DUPES_SQL,
        "doctor-owned daily queue identity (day + specialist_id + effective tag)",
        ["day", "specialist_id", "effective_tag", "count"],
    )


def _emit_unique_ddl() -> None:
    # DEFERRABLE INITIALLY DEFERRED: reorder/move rewrite the number
    # slots of one queue inside a single transaction (intermediate
    # duplicate states are legal mid-swap, e.g. two entries trading
    # places); the uniqueness is enforced at COMMIT. A non-deferred
    # index would reject the swap mid-flight. SQLAlchemy 2.0 Index
    # dialect kwargs cannot express this, hence the explicit DDL.
    op.execute(
        "ALTER TABLE queue_entries ADD CONSTRAINT "
        "uq_queue_entries_queue_number UNIQUE (queue_id, number) "
        "DEFERRABLE INITIALLY DEFERRED"
    )
    op.create_index(
        "uq_daily_queues_active_doctor_day_tag",
        "daily_queues",
        ["day", "specialist_id", sa.text("COALESCE(queue_tag, '')")],
        unique=True,
        postgresql_where=sa.text("active AND specialist_id IS NOT NULL"),
    )


def upgrade() -> None:
    conn = op.get_bind()
    _assert_no_duplicates(conn)
    _emit_unique_ddl()


def downgrade() -> None:
    op.drop_index("uq_daily_queues_active_doctor_day_tag", table_name="daily_queues")
    op.drop_constraint(
        "uq_queue_entries_queue_number", table_name="queue_entries"
    )
