"""QD-2E (RQ-15.b): the `general` retirement catalog cutover.

Stage E of the QD-2 staged rollout (ADR-001 "Stage E ``general``
decision", owner decision D-08, 2026-09-12): ``general`` is retired as
a routing destination. It is not a real standalone queue, a bookable
specialty or an active ``QueueResource``; the string survives only as
the incomplete-Doctor onboarding sentinel. A real general-practice
service must receive a distinct canonical key (``family_medicine``)
and a real Doctor.

This revision applies the CATALOG half of the cutover — EXACTLY the
operator map, nothing more:

- source of truth: ``evidence/stage_e_operator_map_20260912.json``
  (the completed-map snapshot of the 2026-09-12 production inventory,
  PR #3209; 36 of 57 items decided, 21 remain ``null``);
- D-08: no inference from service names or codes. The map is the only
  source of retag/assign/disable decisions; this migration implements
  it verbatim and refuses to proceed while any ACTIVE general-fallback
  surface has no decision (the map is completed by the operator, the
  decisions are appended HERE in the same tables, the inventory is
  re-run — the runbook cycle).

Upgrade (single transaction — every migration runs inside the alembic
transaction; PG DDL/DML is transactional):

1. Inventory-before-mutation, LOUD ABORT (RuntimeError, no rows
   changed — the 0063 policy):

   - ACTIVE general-surface queues — any ACTIVE ``daily_queues`` row
     tagged ``general`` or owned by a 0055 synthetic Doctor. The ADR
     decision: a queue with live entries blocks the cutover until an
     operator resolves it explicitly; an active empty one needs its
     own operator decision too (resolve_entries_then_deactivate /
     deactivate). The production inventory of 2026-09-12 reports ZERO
     such rows — this guard keeps it that way;
   - UNDECIDED active services — an ACTIVE service on the
     general-fallback surface (its ``queue_tag`` has no ACTIVE
     ``queue_resources`` row, or ``department_key = 'general'``, or its
     ``doctor_id`` is a synthetic Doctor — the exact
     ``inventory_general_retirement.py`` surface definition) whose
     code carries no decision in the embedded tables. The 2026-09-12
     production state (21 null decisions: procedures x16, stomatology
     x2, dermatology, ultrason, neurology) makes the migration ABORT
     loudly on production until the map is completed — this is
     deliberate: the runtime half of the cutover (fail-closed owner
     resolution, the same PR) turns those surfaces into explicit
     configuration errors, so the catalog half must not strand them
     silently. CI runs ``alembic upgrade head`` on an EMPTY database —
     no surfaces, no decisions to apply, a clean pass.

2. Decision application — exact-row (``UPDATE ... WHERE id = :id``),
   deterministic (code order), postcondition re-verified after every
   write, per-row inventory printed BEFORE the mutation (the migration
   log is the audit trail; a pre-E backup is the restore path):

   - ``retag_resource`` (33 lab services L03-L35 / LAB_*): the service
     ``queue_tag`` moves from ``general`` to ``lab`` — validated
     against a LIVE ACTIVE registry row for the exact target tag
     (abort if the resource was deactivated; the operator re-runs the
     inventory);
   - ``assign_doctor`` (K01 consultation + K11 EchoCG → the single
     real cardiologist): the service ``doctor_id`` is set — validated
     against the LIVE database (the doctor exists, is active, is
     user-linked and is NOT a 0055 synthetic; abort otherwise). The
     embedded target is the production doctor id from the operator
     map — a different database identity means the map is stale and
     the inventory must be re-run, never re-pointed by the migration;
   - ``disable_service`` (none in the current map; supported for the
     remaining 21 decisions): the service is deactivated;
   - ``keep_profile`` (the ``general`` queue profile): no write — the
     profile stays as the operator decided (``retire_profile`` would
     deactivate it; supported, not used by the current map).

3. Idempotence: a clean second pass applies nothing (every decision
   targets the already-mutated state and the coverage re-check passes
   — retagged services left the fallback surface, assigned services
   carry an explicit doctor, disabled services are inactive).

Downgrade is STRICT-RESTORE (the exact-row mirror of the upgrade):
every decision the upgrade applied is reverted — and ONLY rows still
in the upgraded state (``WHERE queue_tag = :to_tag`` /
``doctor_id = :target`` guards), so an operator change made AFTER the
upgrade is never clobbered. The restore re-creates the pre-E catalog
shape (services back on the ``general`` fallback tag, explicit doctors
cleared) which the ROLLED-BACK runtime serves exactly as before: the
synthetic pairs still exist until RQ-15.d, the legacy fallback code
returns with the deployed revision, and the resource axis (lab/ecg)
works in both revisions. A service deliberately re-disabled by the
operator after the upgrade must be re-disabled manually after the
downgrade — the guard cannot distinguish the two deactivations (the
0059 conservative-downgrade ruling philosophy, documented here).

The data logic lives in module-level functions so tests can run them
against a scratch SQLite connection without an alembic context (the
0056/0057/0059/0063 pattern). No DDL: stage E-b is data-only (the 0063
contract already carries the schema; RQ-15.c/d add the archival and
deletion revisions later).

Revision-id note: ``0064_general_retirement_cutover`` is 31 chars —
the alembic_version.version_num VARCHAR(32) limit (the 0059 CI
lesson).
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

# Revision identifiers — chained after 0063_queue_resource_contract.
revision = "0064_general_retirement_cutover"
down_revision = "0063_queue_resource_contract"
branch_labels = None
depends_on = None

_MIGRATION_NAME = "0064_general_retirement_cutover"

# The 0055 synthetic routing vocabulary (the exact identities the
# RQ-15.d deletion will target; here they only define the fallback
# surface — a service whose doctor_id points at one of them needs an
# operator decision exactly like an unresolvable tag).
_SYNTHETIC_OWNER_USERNAMES = frozenset(
    {"lab_resource", "ecg_resource", "general_resource"}
)

# ============================================================================
# The operator map, embedded verbatim from the completed-map snapshot
# evidence/stage_e_operator_map_20260912.json (2026-09-12 production
# inventory, PR #3209; 36/57 decided — 21 null decisions BLOCK this
# migration on production until the operator completes them and the
# decisions are appended to these tables, the D-08 runbook cycle).
# Parity with the evidence file is pinned by test (the map file and
# these tables cannot drift).
# ============================================================================

# (service_code, from_tag, to_tag) — 33 lab services.
_RETAG_DECISIONS: tuple[tuple[str, str, str], ...] = (
    ("L03", "general", "lab"),
    ("L14", "general", "lab"),
    ("L15", "general", "lab"),
    ("L16", "general", "lab"),
    ("L17", "general", "lab"),
    ("L18", "general", "lab"),
    ("L19", "general", "lab"),
    ("L20", "general", "lab"),
    ("L21", "general", "lab"),
    ("L22", "general", "lab"),
    ("L23", "general", "lab"),
    ("L24", "general", "lab"),
    ("L25", "general", "lab"),
    ("L26", "general", "lab"),
    ("L27", "general", "lab"),
    ("L28", "general", "lab"),
    ("L29", "general", "lab"),
    ("L30", "general", "lab"),
    ("L31", "general", "lab"),
    ("L32", "general", "lab"),
    ("L33", "general", "lab"),
    ("L34", "general", "lab"),
    ("L35", "general", "lab"),
    ("LAB_ALT", "general", "lab"),
    ("LAB_AST", "general", "lab"),
    ("LAB_BILE_URINE", "general", "lab"),
    ("LAB_CA", "general", "lab"),
    ("LAB_CRP", "general", "lab"),
    ("LAB_FUNGI", "general", "lab"),
    ("LAB_HBA1C", "general", "lab"),
    ("LAB_IGE", "general", "lab"),
    ("LAB_MALAS", "general", "lab"),
    ("LAB_RF", "general", "lab"),
)

# (service_code, target_doctor_id, original_doctor_id) — the single
# real cardiologist (production id 10; validated against the LIVE
# database below — never re-pointed by the migration).
_ASSIGN_DOCTOR_DECISIONS: tuple[tuple[str, int, int | None], ...] = (
    ("K01", 10, None),
    ("K11", 10, None),
)

# (service_code,) — none in the 2026-09-12 map; supported for the
# remaining 21 operator decisions.
_DISABLE_DECISIONS: tuple[str, ...] = ()

# {profile_key: decision} — "keep_profile" writes nothing;
# "retire_profile" deactivates the profile (not used by the current
# map; supported for the remaining decisions).
_PROFILE_DECISIONS: dict[str, str] = {"general": "keep_profile"}

# ============================================================================
# SQL — inventory, validation, application. Every mutation targets an
# exact row id and is re-verified after the write (the 0063 pattern).
# ============================================================================

_SELECT_ACTIVE_GENERAL_QUEUES = sa.text("""
    SELECT
        q.id AS queue_id,
        q.day,
        q.queue_tag,
        q.specialist_id,
        q.queue_resource_id,
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
    WHERE q.active = true
      AND (
            q.queue_tag = 'general'
         OR u.username IN :synthetic_usernames
      )
    ORDER BY q.day, q.id
    """).bindparams(sa.bindparam("synthetic_usernames", expanding=True))

# The exact inventory_general_retirement.py surface definition: an
# ACTIVE service is on the general-fallback surface when its queue_tag
# is non-NULL and NOT resolvable by an ACTIVE registry row (the runtime
# fallback was UNIVERSAL), or department_key='general', or its doctor_id
# is a synthetic Doctor.
_SELECT_SURFACES = sa.text("""
    SELECT
        s.id,
        s.code,
        s.name,
        s.queue_tag,
        s.department_key,
        s.doctor_id,
        s.requires_doctor,
        (CASE WHEN r.id IS NULL THEN 0 ELSE 1 END) AS registry_resolved,
        (CASE WHEN sd.id IS NULL THEN 0 ELSE 1 END) AS synthetic_doctor
    FROM services s
    LEFT JOIN queue_resources r
           ON r.queue_tag = s.queue_tag AND r.active = true
    LEFT JOIN doctors sd
           ON sd.id = s.doctor_id
    LEFT JOIN users su ON su.id = sd.user_id
    WHERE s.active = true
      AND (
            (s.queue_tag IS NOT NULL AND r.id IS NULL)
         OR s.department_key = 'general'
         OR su.username IN :synthetic_usernames
      )
    ORDER BY s.id
    """).bindparams(sa.bindparam("synthetic_usernames", expanding=True))

_SELECT_SERVICE_BY_CODE = sa.text("""
    SELECT id, code, name, queue_tag, department_key, doctor_id, active,
           requires_doctor
    FROM services
    WHERE code = :code
    ORDER BY id
    """)

_SELECT_SERVICE_BY_ID = sa.text("""
    SELECT id, code, queue_tag, department_key, doctor_id, active
    FROM services
    WHERE id = :id
    """)

_UPDATE_SERVICE_QUEUE_TAG = sa.text("""
    UPDATE services SET queue_tag = :to_tag WHERE id = :id
    """)

_UPDATE_SERVICE_DOCTOR = sa.text("""
    UPDATE services SET doctor_id = :doctor_id WHERE id = :id
    """)

_UPDATE_SERVICE_ACTIVE = sa.text("""
    UPDATE services SET active = :active WHERE id = :id
    """)

_SELECT_ACTIVE_REGISTRY_ROW = sa.text("""
    SELECT id, code, queue_tag FROM queue_resources
    WHERE queue_tag = :queue_tag AND active = true
    ORDER BY id
    """)

_SELECT_TARGET_DOCTOR = sa.text("""
    SELECT
        d.id,
        d.active,
        d.user_id,
        u.username,
        u.role,
        u.is_active
    FROM doctors d
    LEFT JOIN users u ON u.id = d.user_id
    WHERE d.id = :doctor_id
    """)

_SELECT_PROFILE_BY_KEY = sa.text("""
    SELECT id, key, is_active FROM queue_profiles WHERE key = :key
    """)

_UPDATE_PROFILE_ACTIVE = sa.text("""
    UPDATE queue_profiles SET is_active = :active WHERE id = :id
    """)


def _abort(message: str) -> None:
    raise RuntimeError(f"{_MIGRATION_NAME} abort: {message}")


def _assert_no_active_general_queues(conn) -> None:
    """Any ACTIVE general-surface queue blocks the cutover (the ADR
    decision: live entries need an explicit operator resolution;
    active empty ones need their own decision). Production 2026-09-12:
    zero rows — this guard keeps it that way."""
    rows = conn.execute(
        _SELECT_ACTIVE_GENERAL_QUEUES,
        {"synthetic_usernames": sorted(_SYNTHETIC_OWNER_USERNAMES)},
    ).fetchall()
    if not rows:
        return
    inventory = "; ".join(
        f"queue id={row.queue_id} day={row.day} tag={row.queue_tag!r} "
        f"active=true owner={row.owner_username or f'doctor:{row.specialist_id}'} "
        f"specialist_id={row.specialist_id} "
        f"queue_resource_id={row.queue_resource_id} "
        f"entries={row.entry_count}/live={row.live_entry_count}"
        for row in rows
    )
    _abort(
        f"{len(rows)} ACTIVE general-surface daily_queues row(s) — the "
        "ADR Stage E decision requires an explicit operator resolution "
        "for every live queue (resolve the entries, then deactivate; "
        "the operator map daily_queue decisions); inventory: "
        + inventory
        + "; aborting with no rows changed"
    )


def _inventory_and_assert_coverage(conn) -> dict:
    """Print the full surface inventory, then enforce the D-08 gate:
    every ACTIVE general-fallback service must carry a decision."""
    rows = conn.execute(
        _SELECT_SURFACES,
        {"synthetic_usernames": sorted(_SYNTHETIC_OWNER_USERNAMES)},
    ).fetchall()

    decided_codes: set[str] = set()
    for code, _from_tag, _to_tag in _RETAG_DECISIONS:
        decided_codes.add(code)
    for code, _target, _original in _ASSIGN_DOCTOR_DECISIONS:
        decided_codes.add(code)
    decided_codes.update(_DISABLE_DECISIONS)

    surfaces: dict = {}
    undecided: list[str] = []
    for row in rows:
        print(
            f"{_MIGRATION_NAME}: general-fallback surface service "
            f"id={row.id} code={row.code!r} tag={row.queue_tag!r} "
            f"dept={row.department_key!r} doctor_id={row.doctor_id} "
            f"requires_doctor={row.requires_doctor} "
            f"registry_resolved={bool(row.registry_resolved)} "
            f"synthetic_doctor={bool(row.synthetic_doctor)}"
        )
        if row.code in surfaces:
            _abort(
                "ambiguous service code "
                f"{row.code!r}: two ACTIVE general-fallback services "
                f"share it (ids {surfaces[row.code].id} and {row.id}) — "
                "the operator map is keyed by code; fix the catalog, "
                "re-run the inventory; aborting with no rows changed"
            )
        surfaces[row.code] = row
        if row.code not in decided_codes:
            undecided.append(f"code={row.code!r} (id={row.id}, tag={row.queue_tag!r})")

    if undecided:
        _abort(
            f"{len(undecided)} ACTIVE general-fallback service(s) with "
            "NO operator decision: "
            + "; ".join(undecided)
            + " — D-08 forbids inference; complete the operator map "
            "(evidence/stage_e_operator_map), append the decisions to "
            "this revision's tables and re-run the inventory; the "
            "runtime cutover in this same PR turns undecided surfaces "
            "into explicit configuration errors, so the catalog half "
            "must not strand them silently; aborting with no rows "
            "changed"
        )

    inert = sorted(decided_codes - set(surfaces))
    for code in inert:
        print(
            f"{_MIGRATION_NAME}: decision for {code!r} is inert on this "
            "database (no ACTIVE general-fallback service with that "
            "code) — no rows changed for it"
        )
    return surfaces


def _assert_registry_target(conn, to_tag: str) -> None:
    """The retag target must be a LIVE ACTIVE registry row."""
    rows = conn.execute(_SELECT_ACTIVE_REGISTRY_ROW, {"queue_tag": to_tag}).fetchall()
    if len(rows) != 1:
        _abort(
            f"retag_resource target {to_tag!r} must resolve to exactly "
            f"one ACTIVE queue_resources row (found {len(rows)}) — the "
            "operator map pointed at a live resource; deactivate/repair "
            "is an operator decision, then re-run the inventory; "
            "aborting with no rows changed"
        )


def _assert_target_doctor(conn, doctor_id: int) -> None:
    """The assign target must be a real, active, user-linked Doctor —
    never a 0055 synthetic (D-08: the map names a REAL doctor)."""
    row = conn.execute(_SELECT_TARGET_DOCTOR, {"doctor_id": doctor_id}).fetchone()
    if row is None:
        _abort(
            f"assign_doctor target doctor id={doctor_id} does not exist "
            "in this database — the operator map carries the PRODUCTION "
            "identity; a mismatched database means the map is stale, "
            "re-run the inventory (never re-point the target here); "
            "aborting with no rows changed"
        )
    if not row.active or not row.is_active:
        _abort(
            f"assign_doctor target doctor id={doctor_id} "
            f"(username={row.username!r}) is inactive — an explicit "
            "OWNER must be an active real Doctor; operator decision, "
            "then re-run; aborting with no rows changed"
        )
    if row.user_id is None or row.username is None:
        _abort(
            f"assign_doctor target doctor id={doctor_id} has no user "
            "linkage — an explicit OWNER must be a real user-linked "
            "Doctor; aborting with no rows changed"
        )
    if row.username in _SYNTHETIC_OWNER_USERNAMES or row.role == "Resource":
        _abort(
            f"assign_doctor target doctor id={doctor_id} "
            f"(username={row.username!r}, role={row.role!r}) is a "
            "synthetic/internal resource identity — D-08: the operator "
            "map names a REAL doctor; aborting with no rows changed"
        )


def _verify_service_state(
    conn,
    *,
    service_id: int,
    queue_tag: str | None = ...,
    doctor_id: int | None = ...,
    active: bool | None = None,
) -> None:
    """Postcondition re-verification after every mutation (0063)."""
    row = conn.execute(_SELECT_SERVICE_BY_ID, {"id": service_id}).fetchone()
    if row is None:
        _abort(f"postcondition failed: service id={service_id} vanished")
    if queue_tag is not ... and row.queue_tag != queue_tag:
        _abort(
            f"postcondition failed for service id={service_id}: "
            f"queue_tag stored={row.queue_tag!r} expected={queue_tag!r}; "
            "aborting with no rows changed"
        )
    if doctor_id is not ... and row.doctor_id != doctor_id:
        _abort(
            f"postcondition failed for service id={service_id}: "
            f"doctor_id stored={row.doctor_id!r} expected={doctor_id!r}; "
            "aborting with no rows changed"
        )
    if active is not None and bool(row.active) is not active:
        _abort(
            f"postcondition failed for service id={service_id}: "
            f"active stored={bool(row.active)!r} expected={active!r}; "
            "aborting with no rows changed"
        )


def _apply_service_decisions(conn, surfaces: dict) -> dict[str, int]:
    """Apply the embedded operator map, exact-row, deterministic.

    Pre-flight ordering (the 0063 no-rows-changed contract): EVERY
    decision is validated BEFORE the first mutation — a stale doctor
    target or a deactivated retag resource aborts with the catalog
    untouched, not half-converted."""
    counts = {"retag_resource": 0, "assign_doctor": 0, "disable_service": 0}

    for code, _from_tag, to_tag in _RETAG_DECISIONS:
        if surfaces.get(code) is not None:
            _assert_registry_target(conn, to_tag)
    for code, target_doctor_id, _original in _ASSIGN_DOCTOR_DECISIONS:
        if surfaces.get(code) is not None:
            _assert_target_doctor(conn, target_doctor_id)

    for code, _from_tag, to_tag in _RETAG_DECISIONS:
        row = surfaces.get(code)
        if row is None:
            continue
        print(
            f"{_MIGRATION_NAME}: retag_resource service id={row.id} "
            f"code={code!r} queue_tag {row.queue_tag!r} -> {to_tag!r} "
            f"(doctor_id={row.doctor_id}, requires_doctor="
            f"{row.requires_doctor})"
        )
        conn.execute(_UPDATE_SERVICE_QUEUE_TAG, {"id": row.id, "to_tag": to_tag})
        counts["retag_resource"] += 1
        _verify_service_state(conn, service_id=row.id, queue_tag=to_tag)

    for code, target_doctor_id, _original in _ASSIGN_DOCTOR_DECISIONS:
        row = surfaces.get(code)
        if row is None:
            continue
        print(
            f"{_MIGRATION_NAME}: assign_doctor service id={row.id} "
            f"code={code!r} doctor_id {row.doctor_id} -> "
            f"{target_doctor_id} (tag={row.queue_tag!r})"
        )
        conn.execute(
            _UPDATE_SERVICE_DOCTOR,
            {"id": row.id, "doctor_id": target_doctor_id},
        )
        counts["assign_doctor"] += 1
        _verify_service_state(conn, service_id=row.id, doctor_id=target_doctor_id)

    for code in _DISABLE_DECISIONS:
        row = surfaces.get(code)
        if row is None:
            continue
        print(
            f"{_MIGRATION_NAME}: disable_service service id={row.id} "
            f"code={code!r} (tag={row.queue_tag!r})"
        )
        conn.execute(_UPDATE_SERVICE_ACTIVE, {"id": row.id, "active": False})
        counts["disable_service"] += 1
        _verify_service_state(conn, service_id=row.id, active=False)

    return counts


def _apply_profile_decisions(conn) -> int:
    """keep_profile writes nothing; retire_profile deactivates."""
    retired = 0
    for profile_key, decision in _PROFILE_DECISIONS.items():
        if decision != "retire_profile":
            continue
        row = conn.execute(_SELECT_PROFILE_BY_KEY, {"key": profile_key}).fetchone()
        if row is None:
            print(
                f"{_MIGRATION_NAME}: retire_profile decision for "
                f"{profile_key!r} is inert (no such profile)"
            )
            continue
        print(
            f"{_MIGRATION_NAME}: retire_profile profile id={row.id} "
            f"key={profile_key!r} is_active={bool(row.is_active)} -> false"
        )
        conn.execute(_UPDATE_PROFILE_ACTIVE, {"id": row.id, "active": False})
        after = conn.execute(_SELECT_PROFILE_BY_KEY, {"key": profile_key}).fetchone()
        if after is None or bool(after.is_active):
            _abort(
                f"postcondition failed for profile {profile_key!r}: "
                "still active after retire_profile; aborting with no "
                "rows changed"
            )
        retired += 1
    return retired


def upgrade_with_conn(conn) -> dict[str, int]:
    """The testable cutover entry (the 0063 module-level pattern)."""
    _assert_no_active_general_queues(conn)
    surfaces = _inventory_and_assert_coverage(conn)
    counts = _apply_service_decisions(conn, surfaces)
    counts["retire_profile"] = _apply_profile_decisions(conn)
    print(
        f"{_MIGRATION_NAME}: cutover applied — "
        + ", ".join(f"{k}={v}" for k, v in counts.items())
    )
    return counts


def upgrade() -> None:
    upgrade_with_conn(op.get_bind())


def downgrade_with_conn(conn) -> None:
    """Strict-restore, exact-row, guarded (see the module docstring):
    only rows still in the state the upgrade left them are reverted."""
    for code, from_tag, to_tag in _RETAG_DECISIONS:
        rows = conn.execute(_SELECT_SERVICE_BY_CODE, {"code": code}).fetchall()
        for row in rows:
            if row.queue_tag != to_tag:
                continue
            print(
                f"{_MIGRATION_NAME} downgrade: restoring service "
                f"id={row.id} code={code!r} queue_tag {to_tag!r} -> "
                f"{from_tag!r}"
            )
            conn.execute(
                _UPDATE_SERVICE_QUEUE_TAG,
                {"id": row.id, "to_tag": from_tag},
            )
            _verify_service_state(conn, service_id=row.id, queue_tag=from_tag)

    for code, target_doctor_id, original_doctor_id in _ASSIGN_DOCTOR_DECISIONS:
        rows = conn.execute(_SELECT_SERVICE_BY_CODE, {"code": code}).fetchall()
        for row in rows:
            if row.doctor_id != target_doctor_id:
                continue
            print(
                f"{_MIGRATION_NAME} downgrade: restoring service "
                f"id={row.id} code={code!r} doctor_id {target_doctor_id} "
                f"-> {original_doctor_id!r}"
            )
            conn.execute(
                _UPDATE_SERVICE_DOCTOR,
                {"id": row.id, "doctor_id": original_doctor_id},
            )
            _verify_service_state(conn, service_id=row.id, doctor_id=original_doctor_id)

    for code in _DISABLE_DECISIONS:
        rows = conn.execute(_SELECT_SERVICE_BY_CODE, {"code": code}).fetchall()
        for row in rows:
            if bool(row.active):
                continue
            print(
                f"{_MIGRATION_NAME} downgrade: re-activating service "
                f"id={row.id} code={code!r} (disable_service restore; a "
                "service deliberately re-disabled by the operator after "
                "the upgrade must be re-disabled manually)"
            )
            conn.execute(_UPDATE_SERVICE_ACTIVE, {"id": row.id, "active": True})
            _verify_service_state(conn, service_id=row.id, active=True)

    for profile_key, decision in _PROFILE_DECISIONS.items():
        if decision != "retire_profile":
            continue
        row = conn.execute(_SELECT_PROFILE_BY_KEY, {"key": profile_key}).fetchone()
        if row is None or bool(row.is_active):
            continue
        print(
            f"{_MIGRATION_NAME} downgrade: re-activating profile "
            f"id={row.id} key={profile_key!r}"
        )
        conn.execute(_UPDATE_PROFILE_ACTIVE, {"id": row.id, "active": True})


def downgrade() -> None:
    downgrade_with_conn(op.get_bind())
