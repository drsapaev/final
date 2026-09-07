"""QD-2B: queue_resources seed (lab/ecg) + deterministic backfill.

Stage B of the QD-2 staged rollout (QueueResource architecture FINAL,
2026-09-07). Stage A (0058, PR #3093) added the physical registry and
the dual-owner columns; this revision gives the registry its first
canonical rows and bridges existing synthetic-owned queues onto the
resource axis — WITHOUT switching any runtime path (resolvers, morning
pre-create, API identity and the output contract are QD-2C; the
XOR/uniqueness contract is QD-2D; the synthetic identities themselves
retire only in QD-2E and are NOT touched here).

Seeds — exactly two registry rows, each gated on live data:

- ``lab``  (code 'lab', queue_tag 'lab') and ``ecg`` (code 'ecg',
  queue_tag 'ecg'). A tag is seeded ONLY when the live ``services``
  table proves it doctorless: at least one ACTIVE service with that
  queue_tag and requires_doctor = false, and ZERO active
  requires_doctor = true services with it (mixed semantics inside one
  tag abort the migration — the operator fixes the catalog first).
  Unproven tags seed nothing: no services at all (CI postgres runs
  upgrade head on an empty catalog), a doctor-required tag, or the
  ``laboratory`` alias spelling are all out of scope — exact-tag
  matching, never prefix or alias inference.
- ``general`` is deliberately NOT seeded (ADR-001 addendum: it is
  conditional, an explicit operator decision that must land before
  stage E can retire general_resource). procedures / cosmetology /
  stomatology are never inferred — stomatology requires a real
  dentist (the 0055 contract).
- Seed values TRANSFER the actually-used configuration of the
  synthetic pair: start_number_online / max_online_per_day are read
  from the exact synthetic Doctor row (the values queue_svc and the
  GraphQL mutations read today; the 0055 seed is 1/15 but a drifted
  environment transfers its real values, not the seed constants),
  display_name comes from the canonical 0055 vocabulary
  (departments/queue_profiles: 'Лаборатория' / 'ЭКГ'), active is
  true, and default_cabinet stays NULL — no canonical cabinet source
  exists (Doctor.cabinet is NULL in the seed; the runtime cabinet is
  per-day DailyQueue state, not registry config).
- Idempotency: a row already occupying code/queue_tag with exactly the
  expected identity (derived from the same live synthetic Doctor) is a
  safe no-op — protects incident-drifted environments that applied the
  seed by hand. An INCOMPATIBLE occupant aborts loudly; user or
  unexpected configuration is never overwritten.

Backfill — deterministic, inventory-before-mutation, no .first():

For every processed tag (seeded resource), all ``daily_queues`` rows
with that queue_tag are fetched ordered (day, id) and classified by
owner:

- the exact dedicated synthetic Doctor (lab_resource / ecg_resource),
  or the general_resource universal fallback (the morning pre-create
  owner) → queue_resource_id is set. The destination is determined by
  ``queue.queue_tag`` (exact-tag-wins), NEVER by the owner username:
  a general_resource-owned 'lab' queue lands on the lab resource.
- ``specialist_id`` is NEVER nulled — stage B is the dual-ownership
  bridge (old synthetic Doctor + new QueueResource both set), the
  exact expand/migrate shape the ADR documents for stages B–C.
- QueueEntry rows are never merged, moved or rewritten; entry counts
  appear only in abort inventory output.

Abort rules (RuntimeError, no rows changed — every migration runs
inside the alembic transaction; PG DDL/DML is transactional):

- mixed requires_doctor semantics inside a seeded tag;
- missing or malformed synthetic pair for a proven doctorless tag
  (exactly one active user row, exactly one linked Doctor row with
  the tag specialty and active numbering config — the old runtime
  resolves doctorless tags through this pair, so drift is loud);
- an incompatible row already occupying the registry code/queue_tag;
- a dedicated synthetic owning a queue whose tag is NOT its own
  (foreign, unknown or NULL tag — including a lab_resource-owned
  'laboratory' alias row: alias spellings are not silently adopted);
- more than one ACTIVE queue for one (day, resource tag) — NO dedup
  in stage B: duplicates abort with the full per-row inventory
  (id/day/owner/active/entry counts/cabinet) and the repair is an
  explicit operator decision (deactivate or reassign, then re-run);
- an active resource-tag queue whose owner is neither the dedicated
  synthetic nor general_resource (a human doctor, a doctor without
  user linkage, a NULL-NULL row, or a foreign synthetic) — ownership
  conflict, operator decides;
- an existing queue_resource_id reference pointing at a different
  registry row than the tag's resource (corrupt reference).

Inactive rows with an unclassifiable owner are historical artifacts
outside the routing surface: they stay untouched and do not abort
(abort scope is the ACTIVE routing state stage C will switch). The
'morning fallback to any active doctor' path (morning_assignment.py
when general_resource is missing) is exactly the drift these aborts
surface on staging databases — repair is explicit, never silent.

Downgrade is strict where data can be lost and conservative where it
cannot (the Codex round-1 P2 ruling): it refuses to strip a reference
that would leave a queue with BOTH owners NULL (the QD-2A
backup-restore P1 lesson: an ownerless queue with live entries),
then nulls exactly the references this revision wrote — and NEVER
deletes the registry rows: an exact-identity occupant may pre-date
this revision (the upgrade no-op path deliberately accepts
hand-applied rows — the 0056 incident-drift precedent), and no
provenance marker distinguishes them from rows this revision
inserted, so deleting possibly-pre-existing registry data is worse
than leaving two inert rows (nothing reads them until QD-2C, and
downgrading further drops the queue_resources table itself). It
exists for schema-history reversibility, not as a routine production
operation.

The upgrade/downgrade logic lives in module-level functions so tests
can run them against a scratch SQLite connection without an alembic
context (the 0056/0057 pattern). No DDL is emitted anywhere: the
chain head moves 0058 → 0059 with data-only statements, and CI runs
the authoritative ``alembic upgrade head`` on real PostgreSQL.

Revision-id note: alembic's auto-created ``alembic_version.version_num``
column is VARCHAR(32) — the id is deliberately
``0059_resource_seed_backfill`` (27 chars; the 0055
queue_resource_provisioning precedent already sits at exactly 32).
A 33-char first draft passed every scratch-SQLite test (SQLite
ignores VARCHAR widths) and failed only on real PostgreSQL at the
version stamp (PR #3101 CI round-1); the regression pin lives in the
test suite.
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

# Revision identifiers — chained after 0058_queue_resource_expand.
# The id must stay <= 32 chars: alembic_version.version_num is
# VARCHAR(32) — scratch SQLite tests do not enforce the width, real
# PostgreSQL does (PR #3101 CI round-1).
revision = "0059_resource_seed_backfill"
down_revision = "0058_queue_resource_expand"
branch_labels = None
depends_on = None

_MIGRATION_NAME = "0059_resource_seed_backfill"

# The two canonical seed specs (QD-2B FINAL). display_name values are
# the canonical 0055 vocabulary (departments.name_ru / queue_profiles
# .title_ru — both sources agree for both tags).
_SEED_SPECS = (
    {
        "code": "lab",
        "queue_tag": "lab",
        "username": "lab_resource",
        "display_name": "Лаборатория",
    },
    {
        "code": "ecg",
        "queue_tag": "ecg",
        "username": "ecg_resource",
        "display_name": "ЭКГ",
    },
)

# The universal doctorless fallback owner (morning pre-create writes
# every service-tag queue under it when the dedicated synthetic is
# absent; the wizard maps only lab/ecg to their dedicated synthetics).
_GENERAL_RESOURCE_USERNAME = "general_resource"

_SELECT_SERVICE_GATE = sa.text("""
    SELECT
        SUM(CASE WHEN requires_doctor = false THEN 1 ELSE 0 END)
            AS doctorless_active,
        SUM(CASE WHEN requires_doctor = true THEN 1 ELSE 0 END)
            AS doctor_required_active
    FROM services
    WHERE queue_tag = :queue_tag AND active = true
    """)

_SELECT_USER = sa.text("""
    SELECT id, is_active FROM users WHERE username = :username
    """)

_SELECT_LINKED_DOCTORS = sa.text("""
    SELECT id, specialty, active, start_number_online, max_online_per_day
    FROM doctors
    WHERE user_id = :user_id
    ORDER BY id
    """)

_SELECT_EXISTING_RESOURCE = sa.text("""
    SELECT id, code, queue_tag, display_name, active,
           start_number_online, max_online_per_day, default_cabinet
    FROM queue_resources
    WHERE code = :code OR queue_tag = :queue_tag
    ORDER BY id
    """)

_INSERT_RESOURCE = sa.text("""
    INSERT INTO queue_resources
        (code, queue_tag, display_name, active,
         start_number_online, max_online_per_day, default_cabinet,
         created_at, updated_at)
    SELECT :code, :queue_tag, :display_name, true,
           :start_number_online, :max_online_per_day, NULL,
           CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
    """)

_SELECT_SYNTHETIC_FOREIGN_TAG_QUEUES = sa.text("""
    SELECT q.id, q.day, q.queue_tag, q.specialist_id, q.active
    FROM daily_queues q
    JOIN doctors d ON d.id = q.specialist_id
    JOIN users u ON u.id = d.user_id
    WHERE u.username = :username
      AND (q.queue_tag IS NULL OR q.queue_tag <> :queue_tag)
    ORDER BY q.id
    """)

_SELECT_TAG_QUEUES = sa.text("""
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
    WHERE q.queue_tag = :queue_tag
    ORDER BY q.day, q.id
    """)

_UPDATE_QUEUE_RESOURCE = sa.text("""
    UPDATE daily_queues SET queue_resource_id = :queue_resource_id
    WHERE id = :queue_id
    """)

_SELECT_QUEUE_OWNER_STATE = sa.text("""
    SELECT id, day, queue_tag, specialist_id, queue_resource_id, active
    FROM daily_queues WHERE id = :queue_id
    """)

_SELECT_REFERENCING_QUEUES = sa.text("""
    SELECT id, day, queue_tag, specialist_id, queue_resource_id, active
    FROM daily_queues
    WHERE queue_resource_id = :queue_resource_id
    ORDER BY id
    """)

_CLEAR_QUEUE_RESOURCE = sa.text("""
    UPDATE daily_queues SET queue_resource_id = NULL WHERE id = :queue_id
    """)

# NOTE: no DELETE statement exists in this revision by design — the
# downgrade conserves the registry rows (provenance cannot be proven;
# see _restore_pre_seed_state).


def _abort(message: str) -> None:
    raise RuntimeError(f"{_MIGRATION_NAME} abort: {message}")


def _queue_inventory(row) -> str:
    """Render one daily_queues row for abort messages (inventory
    before mutation — the QD-2 duplicate policy)."""
    owner = row.owner_username
    if owner is None:
        owner = (
            f"doctor:{row.specialist_id}(no user link)"
            if row.specialist_id is not None
            else "none"
        )
    return (
        f"queue id={row.queue_id} day={row.day} tag={row.queue_tag!r} "
        f"active={bool(row.active)} owner={owner} "
        f"specialist_id={row.specialist_id} "
        f"queue_resource_id={row.queue_resource_id} "
        f"entries={row.entry_count}/live={row.live_entry_count} "
        f"cabinet={row.cabinet_number!r}"
    )


def _evaluate_service_gate(conn, queue_tag: str) -> tuple[int, int] | None:
    """Live proof gate for one tag.

    Returns (doctorless_active, doctor_required_active) when the tag
    is proven doctorless (>=1 active doctorless service, 0 active
    doctor-required services), or None when the tag must NOT be seeded
    (no doctorless evidence). Mixed semantics abort the migration.
    """
    row = conn.execute(_SELECT_SERVICE_GATE, {"queue_tag": queue_tag}).fetchone()
    doctorless = int(row.doctorless_active or 0)
    doctor_required = int(row.doctor_required_active or 0)

    if doctorless > 0 and doctor_required > 0:
        _abort(
            f"mixed requires_doctor semantics for queue_tag={queue_tag!r} "
            f"({doctorless} active doctorless / {doctor_required} active "
            "doctor-required services) — fix the service catalog first; "
            "aborting with no rows changed"
        )
    if doctorless == 0:
        # Not proven doctorless: no services at all (fresh CI database),
        # a doctor-required tag, or an alias spelling ('laboratory' is
        # NOT 'lab'). Deterministic skip, no abort, no seed.
        return None
    return doctorless, doctor_required


def _validate_synthetic_pair(conn, spec: dict) -> dict:
    """Validate the exact synthetic pair and return its live config.

    The old runtime resolves doctorless tags through
    username -> User -> Doctor, so a proven doctorless tag with a
    missing or malformed pair is loud drift, not a skip.
    """
    username = spec["username"]
    queue_tag = spec["queue_tag"]

    user_rows = conn.execute(_SELECT_USER, {"username": username}).fetchall()
    if len(user_rows) != 1:
        _abort(
            f"expected exactly one user row for username={username!r} "
            f"(queue_tag={queue_tag!r} is proven doctorless), found "
            f"{len(user_rows)}; aborting with no rows changed"
        )
    user_id, user_active = user_rows[0].id, user_rows[0].is_active
    if not user_active:
        _abort(
            f"username={username!r} is inactive — the queue resolution "
            "requires an active user; aborting with no rows changed"
        )

    doctor_rows = conn.execute(_SELECT_LINKED_DOCTORS, {"user_id": user_id}).fetchall()
    if len(doctor_rows) != 1:
        _abort(
            f"expected exactly one linked Doctor row for "
            f"username={username!r}, found {len(doctor_rows)}; aborting "
            "with no rows changed"
        )
    doctor = doctor_rows[0]
    if doctor.specialty != queue_tag:
        _abort(
            f"the linked Doctor row for username={username!r} carries "
            f"specialty={doctor.specialty!r}, expected {queue_tag!r}; "
            "aborting with no rows changed"
        )
    if not doctor.active:
        _abort(
            f"the linked Doctor row for username={username!r} is "
            "inactive; aborting with no rows changed"
        )
    if doctor.start_number_online is None or doctor.max_online_per_day is None:
        _abort(
            f"the linked Doctor row for username={username!r} has NULL "
            "numbering config (start_number_online / max_online_per_day); "
            "aborting with no rows changed"
        )

    return {
        "user_id": user_id,
        "doctor_id": doctor.id,
        "start_number_online": doctor.start_number_online,
        "max_online_per_day": doctor.max_online_per_day,
    }


def _seed_resource(conn, spec: dict, synthetic: dict) -> int:
    """Seed one registry row (or accept an exact identity match).

    Returns the queue_resources.id. INSERT is the only write; an
    existing occupant with the exact expected identity is a no-op
    (hand-applied incident fixes stay), anything else aborts.
    """
    expected = {
        "code": spec["code"],
        "queue_tag": spec["queue_tag"],
        "display_name": spec["display_name"],
        "active": True,
        "start_number_online": synthetic["start_number_online"],
        "max_online_per_day": synthetic["max_online_per_day"],
        "default_cabinet": None,
    }

    existing = conn.execute(
        _SELECT_EXISTING_RESOURCE,
        {"code": spec["code"], "queue_tag": spec["queue_tag"]},
    ).fetchall()

    if not existing:
        conn.execute(
            _INSERT_RESOURCE,
            {
                "code": expected["code"],
                "queue_tag": expected["queue_tag"],
                "display_name": expected["display_name"],
                "start_number_online": expected["start_number_online"],
                "max_online_per_day": expected["max_online_per_day"],
            },
        )
        inserted = conn.execute(
            _SELECT_EXISTING_RESOURCE,
            {"code": spec["code"], "queue_tag": spec["queue_tag"]},
        ).fetchall()
        if len(inserted) != 1:
            _abort(
                f"seed insert for code={spec['code']!r} did not produce "
                f"exactly one registry row (found {len(inserted)}); "
                "aborting with no rows changed"
            )
        return int(inserted[0].id)

    if len(existing) > 1:
        _abort(
            f"expected at most one registry row for code={spec['code']!r} "
            f"/ queue_tag={spec['queue_tag']!r}, found {len(existing)}; "
            "aborting with no rows changed"
        )

    row = existing[0]
    drift = [
        f"{field}: stored={getattr(row, field)!r} " f"expected={expected_value!r}"
        for field, expected_value in expected.items()
        if getattr(row, field) != expected_value
    ]
    if drift:
        _abort(
            f"queue_resources already holds an incompatible row for "
            f"code={spec['code']!r} / queue_tag={spec['queue_tag']!r} "
            f"(registry id={row.id}): "
            + "; ".join(drift)
            + " — refusing to overwrite it; aborting with no rows changed"
        )
    return int(row.id)


def _audit_dedicated_synthetic_tags(conn, spec: dict) -> None:
    """A dedicated synthetic may only own queues of its own tag.

    Foreign, unknown or NULL queue_tag rows under the dedicated
    synthetic (alias spellings included) are ownership drift: abort
    with the full inventory.
    """
    rows = conn.execute(
        _SELECT_SYNTHETIC_FOREIGN_TAG_QUEUES,
        {"username": spec["username"], "queue_tag": spec["queue_tag"]},
    ).fetchall()
    if rows:
        inventory = "; ".join(
            f"queue id={row.id} day={row.day} tag={row.queue_tag!r} "
            f"active={bool(row.active)} specialist_id={row.specialist_id}"
            for row in rows
        )
        _abort(
            f"the dedicated synthetic username={spec['username']!r} owns "
            f"{len(rows)} queue(s) whose tag is not its own "
            f"{spec['queue_tag']!r} (foreign/unknown/NULL tag): "
            f"{inventory}; aborting with no rows changed"
        )


def _classify_owner(row, spec: dict) -> str:
    """Owner classification for one candidate queue row."""
    if row.owner_username == spec["username"]:
        return "dedicated"
    if row.owner_username == _GENERAL_RESOURCE_USERNAME:
        return "general"
    if row.owner_username is None:
        return "none" if row.specialist_id is None else "unlinked"
    return "foreign"


def _backfill_tag(conn, spec: dict, resource_id: int) -> int:
    """Set queue_resource_id on classified queues for one tag.

    Deterministic: all rows are fetched ordered (day, id) — no
    .first() semantics; every mutation targets an exact queue id and
    is re-verified after the write. Returns the number of rows
    backfilled (0 is a clean no-op — production today has no
    daily_queues rows).
    """
    rows = conn.execute(_SELECT_TAG_QUEUES, {"queue_tag": spec["queue_tag"]}).fetchall()

    by_day: dict[str, list] = {}
    for row in rows:
        by_day.setdefault(str(row.day), []).append(row)

    backfilled = 0
    for day in sorted(by_day):
        day_rows = by_day[day]
        active_rows = [row for row in day_rows if row.active]

        if len(active_rows) > 1:
            _abort(
                f"multiple ACTIVE queues for day={day} resource tag="
                f"{spec['queue_tag']!r} — no dedup in stage B, repair is "
                "an explicit operator decision; inventory: "
                + "; ".join(_queue_inventory(row) for row in day_rows)
                + "; aborting with no rows changed"
            )

        for row in day_rows:
            owner_kind = _classify_owner(row, spec)

            if row.queue_resource_id is not None:
                if row.queue_resource_id != resource_id:
                    _abort(
                        f"queue id={row.queue_id} (day={day}, tag="
                        f"{spec['queue_tag']!r}) references registry row "
                        f"{row.queue_resource_id}, expected the "
                        f"{spec['queue_tag']!r} resource {resource_id} — "
                        "corrupt reference; aborting with no rows changed"
                    )
                if owner_kind in ("dedicated", "general"):
                    continue  # already bridged by a previous run
                if row.active:
                    _abort(
                        "active resource-tag queue with an unexpected "
                        f"owner state: {_queue_inventory(row)}; aborting "
                        "with no rows changed"
                    )
                continue  # inactive historical artifact, leave untouched

            if owner_kind in ("dedicated", "general"):
                conn.execute(
                    _UPDATE_QUEUE_RESOURCE,
                    {"queue_resource_id": resource_id, "queue_id": row.queue_id},
                )
                backfilled += 1
                after = conn.execute(
                    _SELECT_QUEUE_OWNER_STATE, {"queue_id": row.queue_id}
                ).fetchone()
                if (
                    after.queue_resource_id != resource_id
                    or after.specialist_id != row.specialist_id
                    or after.queue_tag != row.queue_tag
                    or bool(after.active) != bool(row.active)
                ):
                    _abort(
                        f"postcondition failed for queue id={row.queue_id} "
                        f"after backfill: stored={tuple(after)!r}; "
                        "aborting with no rows changed"
                    )
                continue

            if row.active:
                _abort(
                    "active resource-tag queue with an unknown/conflicting "
                    f"owner ({owner_kind}): {_queue_inventory(row)} — the "
                    "owner is neither the dedicated synthetic nor the "
                    "general_resource fallback; operator decides; "
                    "aborting with no rows changed"
                )
            # Inactive row with an unclassifiable owner: history outside
            # the routing surface — untouched, no abort.

    return backfilled


def _apply_seed_and_backfill(conn) -> dict[str, int]:
    """Upgrade core: seed lab/ecg and bridge their queues."""
    report: dict[str, int] = {}
    for spec in _SEED_SPECS:
        gate = _evaluate_service_gate(conn, spec["queue_tag"])
        if gate is None:
            continue
        synthetic = _validate_synthetic_pair(conn, spec)
        resource_id = _seed_resource(conn, spec, synthetic)
        _audit_dedicated_synthetic_tags(conn, spec)
        report[spec["queue_tag"]] = _backfill_tag(conn, spec, resource_id)
    return report


def _restore_pre_seed_state(conn) -> None:
    """Downgrade core: reverse the backfill, CONSERVE the registry.

    Strict where data can be lost, conservative where it cannot:

    - refuses to strip a reference that would leave BOTH owners NULL —
    an ownerless queue is the QD-2A backup-restore P1 shape and is
    never produced silently (such rows are written by a later stage,
    not by this revision);
    - nulls exactly the references this revision backfilled
    (specialist_id was preserved by construction, so every 0059
    reference still has its doctor owner);
    - NEVER deletes the registry rows. An exact-identity occupant may
    pre-date this revision (the upgrade no-op path deliberately
    accepts hand-applied rows — the 0056 incident-drift precedent),
    and no provenance marker distinguishes them from rows this
    revision inserted; deleting possibly-pre-existing registry data
    is worse than leaving two inert rows. Nothing reads the registry
    until QD-2C, and downgrading further (0058) drops the
    queue_resources table itself.
    """
    for spec in _SEED_SPECS:
        existing = conn.execute(
            _SELECT_EXISTING_RESOURCE,
            {"code": spec["code"], "queue_tag": spec["queue_tag"]},
        ).fetchall()
        targets = [
            row
            for row in existing
            if row.code == spec["code"] and row.queue_tag == spec["queue_tag"]
        ]
        if not targets:
            continue
        if len(targets) > 1:
            _abort(
                f"downgrade found {len(targets)} registry rows for code="
                f"{spec['code']!r} + queue_tag={spec['queue_tag']!r}; "
                "aborting with no rows changed"
            )

        resource_id = int(targets[0].id)
        referencing = conn.execute(
            _SELECT_REFERENCING_QUEUES, {"queue_resource_id": resource_id}
        ).fetchall()
        orphans = [row for row in referencing if row.specialist_id is None]
        if orphans:
            _abort(
                "downgrade refuses to orphan resource-owned queues "
                "(specialist_id IS NULL with queue_resource_id set — "
                "written by a later stage, not by this revision): "
                + "; ".join(
                    f"queue id={row.id} day={row.day} tag={row.queue_tag!r}"
                    for row in orphans
                )
                + "; downgrade the later stage first; aborting with no "
                "rows changed"
            )

        for row in referencing:
            conn.execute(_CLEAR_QUEUE_RESOURCE, {"queue_id": row.id})
        # deliberately no DELETE: the registry rows stay (see the
        # docstring — provenance cannot be proven, so data wins)


def upgrade() -> None:
    _apply_seed_and_backfill(op.get_bind())


def downgrade() -> None:
    _restore_pre_seed_state(op.get_bind())
