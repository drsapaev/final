"""QD-2D: daily_queues owner CONTRACT — XOR CHECK + partial active uniqueness.

Stage D of the QD-2 staged rollout (QueueResource architecture FINAL,
2026-09-07, ADR-001 addendum stage table). Stages A (0058: registry +
dual-owner columns), B (0059: lab/ecg seeds + backfill) and C (the runtime
switch, PR #3114) landed; this revision closes the dual-ownership BRIDGE
and writes the ownership contract into the schema.

The terminal state per the ADR decision is an XOR — exactly one owner per
queue: a doctor (``specialist_id``, ADR-001/PR-26 semantics unchanged) or
a resource (``queue_resource_id``). The bridge (BOTH set, the 0059
backfill shape) was documented for stages B–C only: stage C made the
runtime tag-first (the specialist on a bridged row is never consulted for
routing — resolvers, cabinet filters, statistics, the output contract and
the completion policy all key off ``queue_resource_id`` / the tag), so
stage D consumes the bridge's specialist link and locks the shape:

Upgrade (single transaction — every migration runs inside the alembic
transaction; PG DDL/DML is transactional):

1. Inventory-before-mutation, LOUD ABORT (RuntimeError, no rows changed —
   the 0059 policy; D never invents owners, never dedups, never severs a
   human doctor's link):

   - ORPHAN rows (``specialist_id IS NULL AND queue_resource_id IS
     NULL``) — the XOR needs exactly one owner and the migration cannot
     pick one; the operator assigns an owner or deletes the row, then
     re-runs;
   - ACTIVE duplicates (more than one ACTIVE queue per (day,
     queue_resource_id)) — the partial unique index would reject them;
     the 0059 no-dedup contract holds, the repair (deactivate or
     reassign) is an explicit operator decision, reported with the full
     per-row inventory (id/day/tag/owner/active/entry counts/cabinet);
   - CORRUPT bridge reference — a both-set row whose queue_tag is NULL
     or does not match its linked resource's queue_tag (the 0059
     exact-tag-wins contract; 0059 never linked NULL-tag rows);
   - NON-CANONICAL bridge owner — a both-set row whose specialist is a
     human doctor, a doctor without user linkage or a user outside the
     0055 synthetic vocabulary (``lab_resource`` / ``ecg_resource`` /
     ``general_resource``). Which axis such a row belongs to is an
     operator decision, not a migration default.

2. Bridge conversion — for every CANONICAL bridge (owner in the
   synthetic vocabulary, tag matching the linked resource):
   ``UPDATE daily_queues SET specialist_id = NULL WHERE id = :queue_id``,
   ordered (day, id), re-verified after the write (the 0059
   postcondition pattern). The full per-row inventory (old specialist +
   username, resource code, active, entry counts) is printed to the
   migration log BEFORE the mutation — the log IS the audit trail; a
   pre-D backup is the restore path (restoring only the DATA into a
   post-0063 schema now fails loudly on the CHECK — see below). QueueEntry
   rows are never touched (the 0059 contract).

3. Contract DDL:

   - ``ck_daily_queues_owner_xor`` — CHECK (owner CASE-sum = 1). The
     CASE-sum form (not PG-only ``num_nonnulls``) compiles on both the
     runtime PostgreSQL schema and the SQLite test dialect; the same
     expression is declared on the ORM model (app/models/online_queue.py)
     so the model and the migration cannot drift;
   - ``uq_daily_queues_active_resource_day`` — partial UNIQUE (day,
     queue_resource_id) WHERE active AND queue_resource_id IS NOT NULL
     (the ADR stage-table predicate verbatim). Only ACTIVE resource rows
     participate: inactive rows and NULL-resource rows stay
     duplicate-legal (history preservation first).

Post-0063 the both-set shape cannot re-enter: the CHECK rejects it at the
DB level on PostgreSQL, at the ORM level on SQLite, and a pre-D DATA-only
restore into a post-0063 schema fails on the same CHECK loudly. A FULL
backup restore (schema + data) lands on the pre-0063 schema and re-runs
alembic head — the conversion is deterministic and idempotent (a clean
second pass converts nothing).

Downgrade is conservative (the 0059 ruling philosophy — strict where data
can be lost, conservative where it cannot): it drops the index and the
CHECK only. The bridge specialist links consumed by the upgrade are NOT
restorable by the downgrade (the values no longer exist; the upgrade log
inventory and a pre-D backup are the recovery paths), and restoring them
would recreate the exact shape the contract forbids. Re-upgrading after
the downgrade is clean: no bridges remain (the conversion is
single-pass), the abort checks re-validate, the DDL is re-created.

The upgrade/downgrade data logic lives in module-level functions so tests
can run them against a scratch SQLite connection without an alembic
context (the 0056/0057/0059 pattern). The DDL lives in
``_emit_contract_ddl`` (pure ``op.*`` calls) so the offline PG-dialect
render is pinnable (the QF-1 pattern); CI runs the authoritative
``alembic upgrade head`` on real PostgreSQL.

Revision-id note: ``0063_queue_resource_contract`` is 29 chars — the
alembic_version.version_num VARCHAR(32) limit (the 0059 PR #3101 CI
round-1 lesson).
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

# Revision identifiers — chained after 0062_telegram_webhook_dedup.
revision = "0063_queue_resource_contract"
down_revision = "0062_telegram_webhook_dedup"
branch_labels = None
depends_on = None

_MIGRATION_NAME = "0063_queue_resource_contract"

# The 0055 synthetic routing vocabulary (the only owners the 0059 backfill
# bridged): the dedicated lab/ecg synthetics and the general_resource
# universal fallback. A both-set row carrying any OTHER owner is drift —
# the operator decides which axis it belongs to.
_SYNTHETIC_OWNER_USERNAMES = frozenset(
    {"lab_resource", "ecg_resource", "general_resource"}
)

# The XOR CHECK, byte-identical to the ORM model declaration
# (app/models/online_queue.py, _OWNER_XOR_CHECK) so the migration and
# the model cannot drift. CASE-sum, not num_nonnulls: the model
# CheckConstraint must also compile on the SQLite test dialect.
_OWNER_XOR_CHECK = (
    "(CASE WHEN specialist_id IS NULL THEN 0 ELSE 1 END)"
    " + (CASE WHEN queue_resource_id IS NULL THEN 0 ELSE 1 END) = 1"
)

# The ADR-001 stage-table predicate, verbatim.
_ACTIVE_RESOURCE_UNIQUE_WHERE = "active AND queue_resource_id IS NOT NULL"

_SELECT_ORPHANS = sa.text("""
    SELECT id, day, queue_tag, specialist_id, queue_resource_id, active
    FROM daily_queues
    WHERE specialist_id IS NULL AND queue_resource_id IS NULL
    ORDER BY day, id
    """)

_SELECT_ACTIVE_DUPLICATES = sa.text("""
    SELECT day, queue_resource_id, COUNT(*) AS dup_count
    FROM daily_queues
    WHERE active = true AND queue_resource_id IS NOT NULL
    GROUP BY day, queue_resource_id
    HAVING COUNT(*) > 1
    ORDER BY day, queue_resource_id
    """)

_SELECT_DUPLICATE_INVENTORY = sa.text("""
    SELECT
        q.id AS queue_id,
        q.day,
        q.queue_tag,
        q.specialist_id,
        q.queue_resource_id,
        q.active,
        q.cabinet_number,
        u.username AS owner_username,
        (SELECT COUNT(*) FROM queue_entries e WHERE e.queue_id = q.id)
            AS entry_count,
        (SELECT COUNT(*) FROM queue_entries e
            WHERE e.queue_id = q.id
              AND e.status IN ('waiting', 'called', 'in_service',
                               'diagnostics')
        ) AS live_entry_count
    FROM daily_queues q
    LEFT JOIN doctors d ON d.id = q.specialist_id
    LEFT JOIN users u ON u.id = d.user_id
    WHERE q.day = :day AND q.queue_resource_id = :queue_resource_id
    ORDER BY q.id
    """)

_SELECT_BRIDGES = sa.text("""
    SELECT
        q.id AS queue_id,
        q.day,
        q.queue_tag,
        q.specialist_id,
        q.queue_resource_id,
        q.active,
        r.code AS resource_code,
        r.queue_tag AS resource_tag,
        u.username AS owner_username,
        (SELECT COUNT(*) FROM queue_entries e WHERE e.queue_id = q.id)
            AS entry_count,
        (SELECT COUNT(*) FROM queue_entries e
            WHERE e.queue_id = q.id
              AND e.status IN ('waiting', 'called', 'in_service',
                               'diagnostics')
        ) AS live_entry_count
    FROM daily_queues q
    JOIN queue_resources r ON r.id = q.queue_resource_id
    LEFT JOIN doctors d ON d.id = q.specialist_id
    LEFT JOIN users u ON u.id = d.user_id
    WHERE q.specialist_id IS NOT NULL AND q.queue_resource_id IS NOT NULL
    ORDER BY q.day, q.id
    """)

_UPDATE_BRIDGE = sa.text("""
    UPDATE daily_queues SET specialist_id = NULL WHERE id = :queue_id
    """)

_SELECT_QUEUE_STATE = sa.text("""
    SELECT id, day, queue_tag, specialist_id, queue_resource_id, active
    FROM daily_queues WHERE id = :queue_id
    """)


def _abort(message: str) -> None:
    raise RuntimeError(f"{_MIGRATION_NAME} abort: {message}")


def _row_inventory(row) -> str:
    """Render one daily_queues row for abort/log messages (inventory
    before mutation — the 0059 duplicate policy)."""
    owner = row.owner_username
    if owner is None:
        owner = (
            f"doctor:{row.specialist_id}(no user link)"
            if getattr(row, "specialist_id", None) is not None
            else "none"
        )
    return (
        f"queue id={row.queue_id} day={row.day} tag={row.queue_tag!r} "
        f"active={bool(row.active)} owner={owner} "
        f"specialist_id={row.specialist_id} "
        f"queue_resource_id={row.queue_resource_id} "
        f"entries={row.entry_count}/live={row.live_entry_count}"
    )


def _assert_no_orphans(conn) -> None:
    """XOR = 0 is unfixable by the migration (no owner to pick)."""
    rows = conn.execute(_SELECT_ORPHANS).fetchall()
    if rows:
        inventory = "; ".join(
            f"queue id={row.id} day={row.day} tag={row.queue_tag!r} "
            f"active={bool(row.active)}"
            for row in rows
        )
        _abort(
            f"{len(rows)} ownerless daily_queues row(s) "
            "(specialist_id IS NULL AND queue_resource_id IS NULL) — the "
            "XOR contract requires exactly one owner and this migration "
            "never invents one; assign an owner or delete the row, then "
            "re-run; inventory: " + inventory + "; aborting with no rows "
            "changed"
        )


def _assert_no_active_duplicates(conn) -> None:
    """The partial unique would reject ACTIVE (day, resource) duplicates;
    no dedup ever — the 0059 contract, the operator repairs."""
    dups = conn.execute(_SELECT_ACTIVE_DUPLICATES).fetchall()
    if not dups:
        return
    parts: list[str] = []
    for dup in dups:
        rows = conn.execute(
            _SELECT_DUPLICATE_INVENTORY,
            {"day": dup.day, "queue_resource_id": dup.queue_resource_id},
        ).fetchall()
        parts.append(
            f"day={dup.day} queue_resource_id={dup.queue_resource_id} "
            f"({dup.dup_count} ACTIVE rows): "
            + "; ".join(_row_inventory(row) for row in rows)
        )
    _abort(
        "more than one ACTIVE queue for one (day, queue_resource_id) — "
        "the partial active uniqueness would reject them; no dedup in "
        "stage D (the 0059 contract), repair is an explicit operator "
        "decision (deactivate or reassign, then re-run): "
        + " | ".join(parts)
        + "; aborting with no rows changed"
    )


def _convert_bridges(conn) -> dict[str, int]:
    """Close the dual-ownership bridge: specialist_id → NULL on every
    canonical bridge row.

    Canonical = the 0059 backfill shape: owner in the synthetic
    vocabulary (dedicated lab/ecg synthetics or the general_resource
    fallback) AND the row's queue_tag matching the linked resource's
    queue_tag (exact-tag-wins). Anything else is drift and aborts
    (see the docstring taxonomy). Deterministic (day, id) order, every
    mutation targets an exact queue id and is re-verified after the
    write; the per-row inventory is printed BEFORE the mutation — the
    migration log is the audit trail (a pre-D backup is the restore
    path; the downgrade cannot rebuild consumed values).
    """
    rows = conn.execute(_SELECT_BRIDGES).fetchall()
    converted = 0
    for row in rows:
        if row.queue_tag is None or row.queue_tag != row.resource_tag:
            _abort(
                "corrupt bridge reference: queue "
                f"id={row.queue_id} (day={row.day}) carries "
                f"queue_tag={row.queue_tag!r} but references the "
                f"{row.resource_code!r} resource (queue_tag="
                f"{row.resource_tag!r}) — exact-tag-wins, the 0059 "
                "contract; operator decides; "
                f"{_row_inventory(row)}; aborting with no rows changed"
            )
        if row.owner_username not in _SYNTHETIC_OWNER_USERNAMES:
            owner = row.owner_username
            if owner is None:
                owner = (
                    f"doctor:{row.specialist_id}(no user link)"
                    if row.specialist_id is not None
                    else "none"
                )
            _abort(
                "bridge with a non-canonical owner: queue "
                f"id={row.queue_id} (day={row.day}, tag="
                f"{row.queue_tag!r}) owner={owner!r} is not in the "
                "synthetic vocabulary "
                f"{sorted(_SYNTHETIC_OWNER_USERNAMES)} — a human doctor's "
                "link is never severed by a migration; operator decides "
                "which axis the row belongs to; "
                f"{_row_inventory(row)}; aborting with no rows changed"
            )

        print(
            f"{_MIGRATION_NAME}: converting bridge queue id={row.queue_id} "
            f"day={row.day} tag={row.queue_tag!r} owner="
            f"{row.owner_username!r} specialist_id={row.specialist_id} -> "
            f"NULL (resource={row.resource_code!r}, active="
            f"{bool(row.active)}, entries={row.entry_count}"
            f"/live={row.live_entry_count})"
        )
        conn.execute(_UPDATE_BRIDGE, {"queue_id": row.queue_id})
        converted += 1
        after = conn.execute(_SELECT_QUEUE_STATE, {"queue_id": row.queue_id}).fetchone()
        if (
            after.specialist_id is not None
            or after.queue_resource_id != row.queue_resource_id
            or after.queue_tag != row.queue_tag
            or bool(after.active) != bool(row.active)
        ):
            _abort(
                f"postcondition failed for queue id={row.queue_id} after "
                f"bridge conversion: stored={tuple(after)!r}; aborting "
                "with no rows changed"
            )
    return {"bridges_converted": converted}


def _emit_contract_ddl() -> None:
    """The stage D contract DDL (pure op.* — offline-pinnable, the QF-1
    pattern). Order: the CHECK first, the partial unique second — on a
    fresh failure of the unique the CHECK has already locked the owner
    shape."""
    op.create_check_constraint(
        "ck_daily_queues_owner_xor",
        "daily_queues",
        _OWNER_XOR_CHECK,
    )
    op.create_index(
        "uq_daily_queues_active_resource_day",
        "daily_queues",
        ["day", "queue_resource_id"],
        unique=True,
        postgresql_where=sa.text(_ACTIVE_RESOURCE_UNIQUE_WHERE),
    )


def upgrade() -> None:
    conn = op.get_bind()
    _assert_no_orphans(conn)
    _assert_no_active_duplicates(conn)
    _convert_bridges(conn)
    _emit_contract_ddl()


def downgrade() -> None:
    op.drop_index("uq_daily_queues_active_resource_day", table_name="daily_queues")
    op.drop_constraint(
        "ck_daily_queues_owner_xor",
        "daily_queues",
        type_="check",
    )
