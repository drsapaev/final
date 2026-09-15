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
- DATED REFINEMENT (owner decisions, 2026-09-15, recorded in
  ``evidence/stage_e_operator_map_refinement_20260915.json``): 19 of the
  21 null surfaces are now decided — O10 -> Doctor 17 (UZD, requires_doctor
  True), O20 -> Doctor 18 (Невролог, requires_doctor True), S10 ->
  Doctor 16 (Stomatolog), and the 16 procedure services move onto the
  resource axis (requires_doctor False, doctor_id NULL, tag 'procedures',
  routed via the QueueResource('procedures') seeded by this revision with
  the 0059 defaults — operator-editable; no operator-approved values yet).
  The original 2026-09-12 snapshot file is kept verbatim; REMAINING
  UNDECIDED: S01 (Консультация стоматолога) and D01 (Консультация
  дерматолога-косметолога) — the migration still aborts on production
  until the owner approves those two;
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
     IDENTITY carries no decision in the embedded tables: every
     decision binds the exact (snapshot id, code) object it was
     approved for (thread 3995689408), so a different live row
     re-using a mapped code is UNDECIDED for the map's purposes — the
     decision approved for id=21/code='L03' never covers a replacement
     id=999. The 2026-09-12 production state (21 null decisions:
     procedures x16, stomatology x2, dermatology, ultrason,
     neurology) makes the migration ABORT loudly on production until
     the map is completed — this is deliberate: the runtime half of
     the cutover (fail-closed owner resolution, the same PR) turns
     those surfaces into explicit configuration errors, so the catalog
     half must not strand them silently. CI runs ``alembic upgrade
     head`` on an EMPTY database — no surfaces, no decisions to apply,
     a clean pass.

2. Decision application — SNAPSHOT-IDENTITY-BOUND (thread
   3995689408, P1) AND exact-row expected-state-guarded
   (``UPDATE ... WHERE id = :id AND code = :code AND <expected source
   state>``, exactly one affected row verified — thread 3995689409,
   P1: alembic runs while uvicorn is still serving in the deploy script,
   so an operator catalog edit can land between the pre-state check and
   the write; the guarded predicate makes the UPDATE match zero rows
   instead of overwriting the newer edit, and a rowcount != 1 is either
   PROVEN to be the exact post-state — an idempotent no-op — or aborts
   the whole map with no rows changed), deterministic (code order),
   postcondition re-verified after every write, per-row inventory
   printed BEFORE the mutation (the migration log is the audit trail; a
   pre-E backup is the restore path).

   Identity resolution (3995689408): the write target is resolved by
   the snapshot (id, code) pair from the approved map, NEVER by
   re-looking the code up among the live rows at application time.
   The concrete scenario closed: the map approves a decision for
   id=21/code='L03'; the original object is later deleted or
   disabled; a NEW row id=999/code='L03' appears — the migration must
   NOT apply the old decision to id=999. Resolution outcomes: the
   snapshot row live and code-matched → the write target; its code
   changed → identity drift, abort; the snapshot row gone/disabled
   with a live code carrier → abort (the decision was never approved
   for the carrier); gone/disabled with NO carrier → inert, printed,
   nothing written. The same identity rule runs in the D-08 coverage
   gate above and in the by-code pre-state validation.

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

Boundary (documented per the fix directive): the snapshot ids are
PRODUCTION identities from the 2026-09-12 map; this map is NOT a
universal id map for every installation. A database whose active
rows carry the mapped codes under different ids does not match the
approved map — the D-08 coverage gate aborts for those identities and
the operator must re-run the inventory and carry the decisions for
HIS database's identities (the runbook cycle). The CI empty database
remains a clean no-op pass (no surfaces, no code carriers, every
decision inert).

Downgrade is CONSERVATIVE, VALIDATE-ONLY (Codex round-1 P1; the 0059
round-2 ruling and the 0063 downgrade philosophy): it writes NOTHING.
A data downgrade cannot prove which rows THIS revision changed — a
mapped code sitting on the post-state tag is either a row the upgrade
retagged (restorable) or one the operator hand-moved to the same tag
before the cutover (the upgrade treated it as an inert no-op and must
not be clobbered), and the database carries no marker distinguishing
the two. The downgrade therefore validates the state and prints the
exact per-code pre-E values; the recovery paths are the upgrade's
per-row inventory (the migration log is the audit trail) and a pre-E
backup (the full restore). Re-upgrading after the downgrade is a
clean no-op, and the rolled-back runtime serves the retagged catalog
identically (the lab/ecg resource axis predates this revision; the
pre-E fallback code returns with the rolled-back revision).

The data logic lives in module-level functions so tests can run them
against a scratch SQLite connection without an alembic context (the
0056/0057/0059/0063 pattern). No DDL: stage E-b is data-only (the 0063
contract already carries the schema; RQ-15.c/d add the archival and
deletion revisions later).

Revision-id note: ``0066_general_retirement_cutover`` is 31 chars —
the alembic_version.version_num VARCHAR(32) limit (the 0059 CI
lesson). Originally authored as ``0064_general_retirement_cutover``;
renumbered to 0065 when main merged ``0064_push_devices_registry``
(PR-6), and renumbered again to 0066 when main merged
``0065_queue_numbering_unique`` (RQ-14.a.1, #3252) — both times the
two migrations claimed the same revision slot from the same parent,
and the chain must stay single-headed.
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

# QD-2E review P1 (e0248660a): the mapped assign targets are validated
# against the canonical doctor-family vocabulary (see _assert_target_doctor).
from app.core.roles import is_doctor_role_spelling
from app.core.specialties import INCOMPLETE_DOCTOR_SPECIALTY

# Revision identifiers — chained after 0065_queue_numbering_unique
# (renumbered from 0064/0065 after the PR-6 registry and main's
# RQ-14.a.1 numbering UNIQUE landed on main).
revision = "0066_general_retirement_cutover"
down_revision = "0065_queue_numbering_unique"
branch_labels = None
depends_on = None

_MIGRATION_NAME = "0066_general_retirement_cutover"

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
#
# IDENTITY (thread 3995689408, P1): every decision row carries the
# SNAPSHOT SERVICE ID from the approved map alongside the code. The
# approved decision binds (id, code) — an exact object — and is
# NEVER re-pointed at whatever row happens to carry the code at
# application time. The concrete loss this closes: the map approved
# a decision for id=21/code='L03'; the operator later deletes or
# disables id=21 and a NEW row id=999/code='L03' appears — a
# code-only lookup would apply the old decision to the new object it
# was never approved for. The resolution and coverage logic below
# therefore key decisions by (snapshot_id, code):
#
# - an ACTIVE general-fallback surface is covered ONLY by the
#   decision carrying ITS OWN (id, code) — a different live object
#   with a mapped code is UNDECIDED for the map's purposes and
#   aborts the cutover;
# - the application target is resolved by snapshot id first (the
#   row must still carry the mapped code): a vanished/disabled
#   approved object with a live code carrier aborts, a vanished or
#   disabled object with no carrier is inert, and a row whose id
#   matched but whose code changed is identity drift and aborts.
#
# BOUNDARY (documented per the fix directive): the snapshot ids are
# PRODUCTION identities. This map is NOT a universal id map for
# every installation — another database whose active rows carry the
# mapped codes under different ids does not match the approved map
# and must re-run the inventory and carry its own decision tables
# (the D-08 runbook cycle). The CI empty database stays a clean
# no-op pass: no surfaces, no carriers, every decision inert.
# ============================================================================

# (snapshot_id, service_code, from_tag, to_tag) — 33 lab services;
# the ids are the 2026-09-12 production snapshot identities.
_RETAG_DECISIONS: tuple[tuple[int, str, str, str], ...] = (
    (21, "L03", "general", "lab"),
    (11, "L14", "general", "lab"),
    (27, "L15", "general", "lab"),
    (22, "L16", "general", "lab"),
    (24, "L17", "general", "lab"),
    (23, "L18", "general", "lab"),
    (20, "L19", "general", "lab"),
    (28, "L20", "general", "lab"),
    (29, "L21", "general", "lab"),
    (52, "L22", "general", "lab"),
    (63, "L23", "general", "lab"),
    (53, "L24", "general", "lab"),
    (12, "L25", "general", "lab"),
    (72, "L26", "general", "lab"),
    (30, "L27", "general", "lab"),
    (32, "L28", "general", "lab"),
    (73, "L29", "general", "lab"),
    (44, "L30", "general", "lab"),
    (74, "L31", "general", "lab"),
    (62, "L32", "general", "lab"),
    (61, "L33", "general", "lab"),
    (60, "L34", "general", "lab"),
    (33, "L35", "general", "lab"),
    (25, "LAB_ALT", "general", "lab"),
    (26, "LAB_AST", "general", "lab"),
    (36, "LAB_BILE_URINE", "general", "lab"),
    (31, "LAB_CA", "general", "lab"),
    (51, "LAB_CRP", "general", "lab"),
    (70, "LAB_FUNGI", "general", "lab"),
    (34, "LAB_HBA1C", "general", "lab"),
    (75, "LAB_IGE", "general", "lab"),
    (71, "LAB_MALAS", "general", "lab"),
    (50, "LAB_RF", "general", "lab"),
)

# (snapshot_id, service_code, target_doctor_id, original_doctor_id,
# snapshot_tag) — the single real cardiologist (production id 10;
# validated against the LIVE database below — never re-pointed by
# the migration). The snapshot tag is part of the stale-map contract:
# an active mapped service sitting on ANY other tag is drift, not an
# inert decision (Codex round-3 P1). The snapshot ids (K01=2, K11=127)
# are the 2026-09-12 production identities (thread 3995689408).
_ASSIGN_DOCTOR_DECISIONS: tuple[
    tuple[int, str, int, int | None, int | None, str, bool | None], ...
] = (
    # (snapshot_id, code, target_doctor_id, original_doctor_id,
    #  expected_user_id | None, snapshot_tag, set_requires_doctor | None).
    # original_doctor_id: the 12.09 snapshot pre-state (None for all the
    # current entries) — the guarded UPDATE and the downgrade report it.
    # expected_user_id: the D-08 refinement (2026-09-15) pins the
    # doctor-to-owner linkage (abort on a foreign owner). set_requires_doctor
    # is the same refinement: an assigned EXPLICIT doctor makes the service
    # doctor-required — O10/O20 flip False -> True with the confirmed source
    # state guarded in the UPDATE; None leaves the flag untouched (K01/K11
    # were already True; S10 stays True as decided).
    (2, "K01", 10, None, None, "cardio", None),
    (127, "K11", 10, None, None, "cardio", None),
    (125, "O10", 17, None, 29, "ultrason", True),
    (126, "O20", 18, None, 30, "neurology", True),
    (90, "S10", 16, None, 27, "stomatology", None),
)

# The approved doctor-to-owner linkage for the refinement decisions
# (doctor_id -> user_id): part of the owner-approved identity, validated
# by _assert_target_doctor at application time.
_REFINEMENT_DOCTOR_USER_LINKAGE = {17: 29, 18: 30, 16: 27}

# (snapshot_id, service_code) — none in the 2026-09-12 map; supported
# for the remaining 21 operator decisions (same identity contract).
_DISABLE_DECISIONS: tuple[tuple[int, str], ...] = ()

# D-08 refinement (owner, 2026-09-15): the 16 procedure services are
# performed by non-doctor staff of the procedures cabinet — the resource
# axis, NOT a doctor. Target state: requires_doctor False (flipped from
# the confirmed True), doctor_id stays NULL, queue_tag stays 'procedures';
# routing goes through the ACTIVE QueueResource('procedures') seeded by
# this revision (see _REGISTRY_SEED_TAG). The snapshot ids are the
# 2026-09-12 production identities; any row differing from the listed
# group/tag is shown as a discrepancy and STOPS the refinement (never a
# silent extension).
_CLEAR_DOCTOR_REQUIREMENT_DECISIONS: tuple[tuple[int, str, str], ...] = (
    (100, "P08", "procedures"),
    (101, "P03", "procedures"),
    (102, "P09", "procedures"),
    (103, "P07", "procedures"),
    (104, "P10", "procedures"),
    (110, "C07", "procedures"),
    (111, "C08", "procedures"),
    (112, "C03", "procedures"),
    (113, "C06", "procedures"),
    (114, "C09", "procedures"),
    (115, "C12", "procedures"),
    (116, "C11", "procedures"),
    (117, "C10", "procedures"),
    (120, "D06", "procedures"),
    (121, "D05", "procedures"),
    (122, "D07", "procedures"),
)

# The procedures resource the D-08 refinement routes the 16 services onto.
# SEED DEFAULTS (start_number_online=1, max_online_per_day=15) mirror the
# 0059 lab/ecg precedent — the operator has NOT approved specific cabinet /
# limit / numbering values yet; that gap is flagged here explicitly and
# remains an operator decision (the row is editable without a migration).
_REGISTRY_SEED_TAG = "procedures"

# {profile_key: decision} — "keep_profile" writes nothing;
# "retire_profile" deactivates the profile (not used by the current
# map; supported for the remaining decisions).
_PROFILE_DECISIONS: dict[str, str] = {"general": "keep_profile"}

# ============================================================================
# SQL — inventory, validation, application. Every mutation is guarded by
# exact identity (id + code) AND the expected source state, verifies
# exactly one affected row, and is re-verified after the write (the 0063
# pattern). The guarded predicates close the preflight→write race the
# review exposed (thread 3995689409, P1): the deploy reality is that
# scripts/deploy_restart.ps1 runs alembic at lines 170–180 while uvicorn
# is only stopped at lines 191–204, so catalog writes CAN interleave —
# an ID-only UPDATE would overwrite a newer operator edit that landed
# after ``_assert_decision_pre_states`` read the row. With the expected
# source state in the WHERE clause the concurrent edit makes the UPDATE
# match zero rows instead, and a rowcount != 1 is never accepted blindly:
# the row is re-read and the no-op is PROVEN (the exact post-state) or
# the whole map aborts with no rows changed.
# NULL comparison semantics (thread 3995689409): ``col = :param`` never
# matches NULL on either engine, and a bare ``:param IS NULL`` arm is
# untypable for the PostgreSQL server-side parameter binding. Every
# nullable expected column therefore carries a PRECOMPUTED NULL flag
# (1/0) plus the exact comparison arm — the flag is Python-side truth,
# the SQL stays engine-portable (see ``_is_null_flag`` below).

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
    SELECT id, code, queue_tag, department_key, doctor_id, active
    FROM services
    WHERE code = :code AND active = true
    ORDER BY id
    """)

# the downgrade's read-only reporting variant (any active state)
_SELECT_SERVICE_BY_CODE_ANY = sa.text("""
    SELECT id, code, queue_tag, department_key, doctor_id, active
    FROM services
    WHERE code = :code
    ORDER BY id
    """)

_SELECT_SERVICE_BY_ID = sa.text("""
    SELECT id, code, queue_tag, department_key, doctor_id,
           requires_doctor, active
    FROM services
    WHERE id = :id
    """)

_UPDATE_SERVICE_QUEUE_TAG = sa.text("""
    UPDATE services
    SET queue_tag = :to_tag
    WHERE id = :id
      AND code = :code
      AND ((:expected_queue_tag_is_null = 1 AND queue_tag IS NULL)
           OR (:expected_queue_tag_is_null = 0
               AND queue_tag IS NOT NULL
               AND queue_tag = :expected_queue_tag))
    """)

_UPDATE_SERVICE_DOCTOR = sa.text("""
    UPDATE services
    SET doctor_id = :doctor_id,
        requires_doctor = (CASE WHEN :set_requires_doctor = 1
                                THEN true
                                ELSE requires_doctor END)
    WHERE id = :id
      AND code = :code
      AND ((:expected_doctor_id_is_null = 1 AND doctor_id IS NULL)
           OR (:expected_doctor_id_is_null = 0
               AND doctor_id IS NOT NULL
               AND doctor_id = :expected_doctor_id))
      AND ((:expected_queue_tag_is_null = 1 AND queue_tag IS NULL)
           OR (:expected_queue_tag_is_null = 0
               AND queue_tag IS NOT NULL
               AND queue_tag = :expected_queue_tag))
      AND ((:requires_doctor_decision = 0)
           OR (:expected_requires_doctor_is_null = 1
               AND requires_doctor IS NULL)
           OR (:expected_requires_doctor_is_null = 0
               AND requires_doctor IS NOT NULL
               AND requires_doctor = :expected_requires_doctor))
    """).bindparams(
        # review P1 (055a7c7ec): PostgreSQL binds a Python int as smallint
        # and `boolean = smallint` does not exist — type the boolean-column
        # bind explicitly instead of relying on the Python value
        sa.bindparam("expected_requires_doctor", type_=sa.Boolean())
    )

_UPDATE_SERVICE_REQUIRES_DOCTOR = sa.text("""
    UPDATE services
    SET requires_doctor = false
    WHERE id = :id
      AND code = :code
      AND requires_doctor = true
      AND doctor_id IS NULL
      AND queue_tag = :expected_queue_tag
    """)

_UPDATE_SERVICE_ACTIVE = sa.text("""
    UPDATE services
    SET active = :active
    WHERE id = :id
      AND code = :code
      AND active = :expected_active
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
        d.specialty,
        d.user_id,
        u.username,
        u.role,
        u.is_active
    FROM doctors d
    LEFT JOIN users u ON u.id = d.user_id
    WHERE d.id = :doctor_id
    """)

_SELECT_REGISTRY_BY_TAG_ANY = sa.text("""
    SELECT id, code, queue_tag, active FROM queue_resources
    WHERE queue_tag = :queue_tag
    ORDER BY id
    """)

# Review round 4 (P1): the seed-tag coverage gate must see the services
# ON the tag regardless of whether the tag already resolves to an ACTIVE
# queue_resources row — _SELECT_SURFACES deliberately EXCLUDES resolved
# tags, so this dedicated inventory is the only D-08 view that stays
# closed once the resource exists.
_SELECT_SEED_TAG_SERVICES = sa.text("""
    SELECT id, code, name, queue_tag, department_key, doctor_id,
           requires_doctor
    FROM services
    WHERE active = true AND queue_tag = :queue_tag
    ORDER BY id
    """)

_INSERT_REGISTRY_RESOURCE = sa.text("""
    INSERT INTO queue_resources
        (code, queue_tag, display_name, active,
         start_number_online, max_online_per_day, default_cabinet)
    VALUES
        (:code, :queue_tag, :display_name, true,
         :start_number_online, :max_online_per_day, NULL)
    """)

_SELECT_PROFILE_BY_KEY = sa.text("""
    SELECT id, key, is_active FROM queue_profiles WHERE key = :key
    """)

_UPDATE_PROFILE_ACTIVE = sa.text("""
    UPDATE queue_profiles
    SET is_active = :active
    WHERE id = :id
      AND key = :key
      AND is_active = :expected_active
    """)


def _abort(message: str) -> None:
    raise RuntimeError(f"{_MIGRATION_NAME} abort: {message}")


def _is_null_flag(value) -> int:
    """Python-side NULL truth for the guarded expected-state predicates —
    the portable engine-agnostic form of ``:param IS NULL``."""
    return 1 if value is None else 0


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
    every ACTIVE general-fallback service must carry a decision —
    carrying ITS OWN identity (thread 3995689408): a decision approved
    for (id=21, code='L03') does not cover a different live object
    (id=999) that merely re-uses the code."""
    rows = conn.execute(
        _SELECT_SURFACES,
        {"synthetic_usernames": sorted(_SYNTHETIC_OWNER_USERNAMES)},
    ).fetchall()

    # (snapshot_id, code) -> decision kind — the approved identity keys
    decided_identities: dict[tuple[int, str], str] = {}
    for snapshot_id, code, _from_tag, _to_tag in _RETAG_DECISIONS:
        decided_identities[(snapshot_id, code)] = "retag_resource"
    for (
        snapshot_id,
        code,
        _target_doctor_id,
        _original_doctor_id,
        _expected_user_id,
        _snapshot_tag,
        _set_requires_doctor,
    ) in _ASSIGN_DOCTOR_DECISIONS:
        decided_identities[(snapshot_id, code)] = "assign_doctor"
    for snapshot_id, code in _DISABLE_DECISIONS:
        decided_identities[(snapshot_id, code)] = "disable_service"
    for snapshot_id, code, _snapshot_tag in _CLEAR_DOCTOR_REQUIREMENT_DECISIONS:
        decided_identities[(snapshot_id, code)] = "clear_requires_doctor"
    decided_codes = {code for _snapshot_id, code in decided_identities}
    decided_ids_by_code: dict[str, list[int]] = {}
    for snapshot_id, code in decided_identities:
        decided_ids_by_code.setdefault(code, []).append(snapshot_id)

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
        if (row.id, row.code) in decided_identities:
            continue
        if row.code in decided_codes:
            # a different live object under a mapped code — the
            # decision was approved for the snapshot identity, never
            # for this row (thread 3995689408: id=21 deleted, id=999
            # re-using the code must NOT inherit the decision)
            decided_for = ", ".join(
                str(i) for i in sorted(decided_ids_by_code[row.code])
            )
            undecided.append(
                f"code={row.code!r} (id={row.id}): the map decides "
                f"id(s) {decided_for} for that code — a DIFFERENT "
                "object carries it now"
            )
        else:
            undecided.append(f"code={row.code!r} (id={row.id}, tag={row.queue_tag!r})")

    if undecided:
        _abort(
            f"{len(undecided)} ACTIVE general-fallback service(s) with "
            "NO operator decision for their identity: "
            + "; ".join(undecided)
            + " — D-08 forbids inference; complete the operator map "
            "(evidence/stage_e_operator_map), append the decisions to "
            "this revision's tables and re-run the inventory; the "
            "runtime cutover in this same PR turns undecided surfaces "
            "into explicit configuration errors, so the catalog half "
            "must not strand them silently; aborting with no rows "
            "changed"
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


def _assert_target_doctor(
    conn, doctor_id: int, expected_user_id: int | None = None
) -> None:
    """The assign target must be a real, active, user-linked Doctor with a
    completed profile (the canonical eligibility contract) — never a 0055
    synthetic (D-08: the map names a REAL doctor). ``expected_user_id``
    pins the doctor-to-owner linkage when the refinement carries it."""
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
    # QD-2E review P1 (e0248660a): a mapped target whose owner was DEMOTED
    # to a non-doctor role must not receive permanent service assignments —
    # the canonical appointment/QR eligibility would reject that owner.
    if not is_doctor_role_spelling(row.role):
        _abort(
            f"assign_doctor target doctor id={doctor_id} owner role "
            f"{row.role!r} is not a doctor-family role — the cutover "
            "never assigns services to a non-doctor owner; re-run the "
            "inventory; aborting with no rows changed"
        )
    # Review round 4 (P2): the SAME completed-profile contract the
    # canonical booking eligibility (ensure_doctor_eligible_for_appointment
    # -> is_doctor_profile_incomplete) enforces — the 'general'
    # onboarding sentinel and a blank/whitespace specialty are INCOMPLETE
    # profiles: such a doctor is not selectable for ordinary booking, so
    # the cutover must not permanently assign services to it either.
    # The check mirrors the SSOT constant from app.core.specialties
    # (import-light — shared by CRUD, services and migrations alike).
    specialty_cleaned = (row.specialty or "").strip()
    if (
        not specialty_cleaned
        or specialty_cleaned == INCOMPLETE_DOCTOR_SPECIALTY
    ):
        _abort(
            f"assign_doctor target doctor id={doctor_id} has an "
            f"incomplete profile (specialty={row.specialty!r}) — the "
            "canonical eligibility contract treats the 'general' "
            "onboarding sentinel and a blank specialty as incomplete "
            "(the runtime would reject this doctor at booking time); "
            "aborting with no rows changed"
        )
    if expected_user_id is not None and row.user_id != expected_user_id:
        _abort(
            f"assign_doctor target doctor id={doctor_id} is linked to "
            f"user id={row.user_id}, but the refinement approves the "
            f"doctor of user id={expected_user_id} — the (doctor, owner) "
            "identity is part of the approved decision; aborting with "
            "no rows changed"
        )


def _verify_service_state(
    conn,
    *,
    service_id: int,
    queue_tag: str | None = ...,
    doctor_id: int | None = ...,
    requires_doctor: bool | None = ...,
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
    if requires_doctor is not ... and bool(row.requires_doctor) is not requires_doctor:
        _abort(
            f"postcondition failed for service id={service_id}: "
            f"requires_doctor stored={bool(row.requires_doctor)!r} "
            f"expected={requires_doctor!r}; aborting with no rows changed"
        )
    if active is not None and bool(row.active) is not active:
        _abort(
            f"postcondition failed for service id={service_id}: "
            f"active stored={bool(row.active)!r} expected={active!r}; "
            "aborting with no rows changed"
        )


def _assert_registry_seed_tag_coverage(conn) -> None:
    """Review round 4 (P1): the D-08 coverage gate for the seed tag
    ITSELF, independent of whether the resource already exists.

    ``_SELECT_SURFACES`` EXCLUDES services whose tag resolves to an
    ACTIVE ``queue_resources`` row — once ``QueueResource('procedures')``
    exists (seeded by an earlier pass, pre-created by an operator, or
    left by a manual repair), every ACTIVE service on the tag becomes
    INVISIBLE to the general coverage inventory. Without this dedicated
    check the resource would effectively extend the 16 approved
    ``(id, code)`` decisions to the WHOLE tag: a 17th, never-approved
    procedure would silently ride the resource axis with no operator
    decision and no abort (the review's P1 — the D-08 "only explicitly
    approved services move" contract broken by resource creation).

    Every ACTIVE service on the seed tag must therefore carry its OWN
    decided identity — an (id, code) pair ANY decision table of the
    operator map names (a mapped service that drifted onto the seed tag
    is NOT silently approved: the pre-state validation diagnoses it as a
    stale map and aborts). Anything genuinely undecided aborts BEFORE
    the resource is created or mutated: the runbook is a new operator
    decision, never a silent tag-wide approval."""
    approved: set[tuple[int, str]] = set()
    for snapshot_id, code, _from_tag, _to_tag in _RETAG_DECISIONS:
        approved.add((snapshot_id, code))
    for (
        snapshot_id,
        code,
        _target_doctor_id,
        _original_doctor_id,
        _expected_user_id,
        _snapshot_tag,
        _set_requires_doctor,
    ) in _ASSIGN_DOCTOR_DECISIONS:
        approved.add((snapshot_id, code))
    for snapshot_id, code, _snapshot_tag in _CLEAR_DOCTOR_REQUIREMENT_DECISIONS:
        approved.add((snapshot_id, code))
    for snapshot_id, code in _DISABLE_DECISIONS:
        approved.add((snapshot_id, code))

    rows = conn.execute(
        _SELECT_SEED_TAG_SERVICES, {"queue_tag": _REGISTRY_SEED_TAG}
    ).fetchall()
    undecided: list[str] = []
    for row in rows:
        print(
            f"{_MIGRATION_NAME}: registry seed tag service "
            f"id={row.id} code={row.code!r} tag={row.queue_tag!r} "
            f"dept={row.department_key!r} doctor_id={row.doctor_id} "
            f"requires_doctor={row.requires_doctor} "
            f"approved={(row.id, row.code) in approved}"
        )
        if (row.id, row.code) in approved:
            continue
        undecided.append(
            f"code={row.code!r} (id={row.id}, tag={row.queue_tag!r})"
        )

    if undecided:
        _abort(
            f"{len(undecided)} ACTIVE service(s) on the registry seed "
            f"tag {_REGISTRY_SEED_TAG!r} with NO operator decision for "
            "their identity: "
            + "; ".join(undecided)
            + " — creating/keeping the QueueResource would route them "
            "onto the resource axis WITHOUT an approved decision: D-08 "
            "forbids tag-wide inference (only the explicit (id, code) "
            "pairs of the operator map are covered); complete the "
            "operator map (evidence/stage_e_operator_map), append the "
            "decisions to this revision's tables and re-run the "
            "inventory; aborting with no rows changed"
        )


def _ensure_procedures_registry_resource(conn) -> None:
    """D-08 refinement (owner, 2026-09-15): the 16 procedure services
    route through the ACTIVE QueueResource('procedures'). Idempotent,
    guarded seed:

    - absent -> INSERT with the 0059 seed defaults (start_number_online=1,
      max_online_per_day=15). The operator has NOT approved specific
      cabinet/limit/numbering values for this resource yet — the defaults
      are the 0059 precedent and stay operator-editable without a
      migration (flagged in the migration log);
    - an ACTIVE row with the same (code, queue_tag) -> proven no-op;
    - an INACTIVE row, or a row with a foreign code on the tag -> abort
      (operator decision, never silently re-activated or re-pointed)."""
    rows = conn.execute(
        _SELECT_REGISTRY_BY_TAG_ANY, {"queue_tag": _REGISTRY_SEED_TAG}
    ).fetchall()
    if len(rows) == 1:
        row = rows[0]
        if bool(row.active) and row.code == _REGISTRY_SEED_TAG:
            print(
                f"{_MIGRATION_NAME}: registry resource {_REGISTRY_SEED_TAG!r} "
                f"(code={row.code!r}, id={row.id}) already ACTIVE — seed no-op"
            )
            return
        _abort(
            f"registry seed target {_REGISTRY_SEED_TAG!r} exists as "
            f"code={row.code!r} active={bool(row.active)} (id={row.id}) — "
            "a disabled or foreign-coded resource is an operator decision "
            "(re-activate/repair it, then re-run); aborting with no rows "
            "changed"
        )
    if len(rows) > 1:
        _abort(
            f"registry seed target {_REGISTRY_SEED_TAG!r} is ambiguous: "
            f"{len(rows)} rows carry the tag — repair the registry, then "
            "re-run; aborting with no rows changed"
        )
    conn.execute(
        _INSERT_REGISTRY_RESOURCE,
        {
            "code": _REGISTRY_SEED_TAG,
            "queue_tag": _REGISTRY_SEED_TAG,
            "display_name": "Процедуры",
            "start_number_online": 1,
            "max_online_per_day": 15,
        },
    )
    check = conn.execute(
        _SELECT_ACTIVE_REGISTRY_ROW, {"queue_tag": _REGISTRY_SEED_TAG}
    ).fetchall()
    if len(check) != 1:
        _abort(
            "registry seed postcondition failed: the procedures resource "
            "is not resolvable as exactly one ACTIVE row; aborting with "
            "no rows changed"
        )
    print(
        f"{_MIGRATION_NAME}: registry seed created QueueResource("
        f"code='procedures', queue_tag='procedures', active=true, "
        "start_number_online=1, max_online_per_day=15) — SEED DEFAULTS, "
        "operator-editable (no operator-approved values yet)"
    )


def _assert_decision_pre_states(conn, surfaces: dict) -> None:
    """Codex round-1 P1 + round-2 P1 (source-tag / source-doctor
    validation): every EXTANT ACTIVE service carrying a mapped code
    must sit on the EMBEDDED pre-state or on the exact post-state (the
    idempotent no-op — the 0057 ruling); anything else is a stale map
    / foreign state and aborts BEFORE any mutation, so a newer
    operator decision is never overwritten.

    The check reads the catalog BY CODE — deliberately NOT via the
    fallback-surface inventory: a mapped service the operator moved
    onto ANOTHER ACTIVE resource tag ('L03' -> 'ecg') is invisible to
    _SELECT_SURFACES (the tag resolves), and treating it as inert
    would let the cutover mutate the other mapped rows despite the
    stale map."""
    for snapshot_id, code, from_tag, to_tag in _RETAG_DECISIONS:
        rows = conn.execute(_SELECT_SERVICE_BY_CODE, {"code": code}).fetchall()
        for row in rows:
            if row.id != snapshot_id:
                _abort(
                    f"stale operator map for {code!r}: the live service "
                    f"(id={row.id}) carries the code but the embedded "
                    f"map decides id={snapshot_id} for it (thread "
                    "3995689408) — a different object must not inherit "
                    "the approved decision; re-run the inventory and "
                    "update the decision tables; aborting with no rows "
                    "changed"
                )
            if row.queue_tag not in (from_tag, to_tag):
                _abort(
                    f"stale operator map for {code!r}: the live service "
                    f"(id={row.id}) carries queue_tag={row.queue_tag!r} "
                    f"but the embedded map says from {from_tag!r} to "
                    f"{to_tag!r} — a newer operator change must not be "
                    "overwritten by the cutover; re-run the inventory "
                    "and update the decision tables; aborting with no "
                    "rows changed"
                )

    for (
        snapshot_id,
        code,
        target_doctor_id,
        original_doctor_id,
        _expected_user_id,
        snapshot_tag,
        _set_requires_doctor,
    ) in _ASSIGN_DOCTOR_DECISIONS:
        rows = conn.execute(_SELECT_SERVICE_BY_CODE, {"code": code}).fetchall()
        for row in rows:
            if row.id != snapshot_id:
                _abort(
                    f"stale operator map for {code!r}: the live service "
                    f"(id={row.id}) carries the code but the embedded "
                    f"map decides id={snapshot_id} for it (thread "
                    "3995689408) — a different object must not inherit "
                    "the approved decision; re-run the inventory and "
                    "update the decision tables; aborting with no rows "
                    "changed"
                )
            if row.queue_tag != snapshot_tag:
                _abort(
                    f"stale operator map for {code!r}: the live service "
                    f"(id={row.id}) carries queue_tag={row.queue_tag!r} "
                    f"but the embedded map decided it on {snapshot_tag!r} "
                    "— a newer operator change must not be overwritten "
                    "by the cutover; re-run the inventory and update the "
                    "decision tables; aborting with no rows changed"
                )
            if row.doctor_id not in (original_doctor_id, target_doctor_id):
                _abort(
                    f"stale operator map for {code!r}: the live service "
                    f"(id={row.id}) carries doctor_id={row.doctor_id!r} "
                    f"but the embedded map assigns from "
                    f"{original_doctor_id!r} to {target_doctor_id!r} — a "
                    "newer operator assignment must not be overwritten "
                    "by the cutover; re-run the inventory and update the "
                    "decision tables; aborting with no rows changed"
                )

    for snapshot_id, code, snapshot_tag in _CLEAR_DOCTOR_REQUIREMENT_DECISIONS:
        rows = conn.execute(_SELECT_SERVICE_BY_CODE, {"code": code}).fetchall()
        for row in rows:
            if row.id != snapshot_id:
                _abort(
                    f"stale operator map for {code!r}: the live service "
                    f"(id={row.id}) carries the code but the embedded "
                    f"refinement decides id={snapshot_id} for it (thread "
                    "3995689408) — a different object must not inherit "
                    "the approved decision; re-run the inventory and "
                    "update the decision tables; aborting with no rows "
                    "changed"
                )
            if row.queue_tag != snapshot_tag:
                _abort(
                    f"refinement discrepancy for {code!r}: the live "
                    f"service (id={row.id}) carries queue_tag="
                    f"{row.queue_tag!r} but the refinement decided it on "
                    f"{snapshot_tag!r} — the row differs from the listed "
                    "group; show the discrepancy to the operator instead "
                    "of extending the decision silently; aborting with "
                    "no rows changed"
                )

    for snapshot_id, code, snapshot_tag in _CLEAR_DOCTOR_REQUIREMENT_DECISIONS:
        rows = conn.execute(_SELECT_SERVICE_BY_CODE, {"code": code}).fetchall()
        for row in rows:
            if row.id != snapshot_id:
                _abort(
                    f"stale operator map for {code!r}: the live service "
                    f"(id={row.id}) carries the code but the embedded "
                    f"refinement decides id={snapshot_id} for it (thread "
                    "3995689408) — a different object must not inherit "
                    "the approved decision; re-run the inventory and "
                    "update the decision tables; aborting with no rows "
                    "changed"
                )
            if row.queue_tag != snapshot_tag:
                _abort(
                    f"refinement discrepancy for {code!r}: the live "
                    f"service (id={row.id}) carries queue_tag="
                    f"{row.queue_tag!r} but the refinement decided it on "
                    f"{snapshot_tag!r} — the row differs from the listed "
                    "group; show the discrepancy to the operator instead "
                    "of extending the decision silently; aborting with "
                    "no rows changed"
                )


def _resolve_decision_target(
    conn,
    *,
    snapshot_id: int,
    code: str,
    decision: str,
):
    """Resolve ONE decision's application target by the approved
    identity (thread 3995689408, P1): the snapshot (id, code) pair
    from the map — never "whatever row currently carries the code".

    Returns the LIVE identity row (the write target), or None when
    the decision is inert. Resolution outcomes:

    - the snapshot row exists, still carries the mapped code and is
      ACTIVE -> the write target (the guarded UPDATE and the
      pre-state checks below take it from here);
    - the snapshot row exists but its CODE changed -> identity
      drift: abort (the catalog row id=21 is no longer the object the
      operator approved);
    - the snapshot row is gone or disabled while a DIFFERENT active
      row carries the code -> abort: the decision was approved for
      another object and is never re-pointed at the carrier;
    - the snapshot row is gone or disabled and NO active row carries
      the code -> inert (the operator resolved the object out of the
      catalog himself); nothing is written and the cutover proceeds.
    """
    identity = conn.execute(_SELECT_SERVICE_BY_ID, {"id": snapshot_id}).fetchone()
    carriers = conn.execute(_SELECT_SERVICE_BY_CODE, {"code": code}).fetchall()
    carrier_ids = [row.id for row in carriers]

    if identity is None:
        if carrier_ids:
            _abort(
                f"stale operator map for {code!r}: the approved service "
                f"id={snapshot_id} no longer exists but {len(carriers)} "
                f"ACTIVE row(s) carry the code (ids "
                f"{', '.join(str(i) for i in carrier_ids)}) — the "
                f"decision was never approved for them ({decision} is "
                "bound to the snapshot identity); re-run the inventory "
                "and update the decision tables; aborting with no rows "
                "changed"
            )
        print(
            f"{_MIGRATION_NAME}: {decision} decision for id={snapshot_id} "
            f"code={code!r} is inert — the snapshot object is gone and "
            "no ACTIVE service carries the code; no rows changed for it"
        )
        return None

    if identity.code != code:
        _abort(
            f"stale operator map for {code!r}: service id={snapshot_id} "
            f"now carries code={identity.code!r} — the approved decision "
            f"binds id={snapshot_id} to {code!r}; the catalog identity "
            "drifted after the map was approved; re-run the inventory "
            "and update the decision tables; aborting with no rows "
            "changed"
        )

    if not identity.active:
        if carrier_ids:
            _abort(
                f"stale operator map for {code!r}: the approved service "
                f"id={snapshot_id} is disabled while {len(carriers)} "
                f"ACTIVE row(s) carry the code (ids "
                f"{', '.join(str(i) for i in carrier_ids)}) — the "
                f"{decision} decision does not cover them; re-run the "
                "inventory and update the decision tables; aborting "
                "with no rows changed"
            )
        print(
            f"{_MIGRATION_NAME}: {decision} decision for id={snapshot_id} "
            f"code={code!r} is inert — the approved object is disabled "
            "(the operator's own resolution) and no ACTIVE service "
            "carries the code; no rows changed for it"
        )
        return None

    return identity


def _guarded_service_update(
    conn,
    *,
    statement,
    params,
    service_id: int,
    service_code: str,
    decision: str,
    expected_description: str,
    post_state_check,
    post_state_description: str,
) -> bool:
    """Run ONE catalog mutation guarded by identity + expected source
    state and verify exactly one affected row (thread 3995689409, P1).

    Returns True when the row changed. A rowcount of anything else is
    NEVER accepted blindly — the row is re-read and the outcome proven:

    - the exact post-state of THIS decision → a concurrent operator (or
      an earlier pass) already applied it — an idempotent no-op, printed
      as such (returns False, nothing written for the row);
    - anything else — a vanished row, a changed identity (id+code) or a
      foreign source state — is a NEWER operator edit that must not be
      overwritten: the whole map aborts with no rows changed (the raise
      propagates; alembic rolls the single transaction back — there are
      no partial commits anywhere in this revision).
    """
    result = conn.execute(statement, params)
    if result.rowcount == 1:
        return True
    after = conn.execute(_SELECT_SERVICE_BY_ID, {"id": service_id}).fetchone()
    if after is None:
        _abort(
            f"{decision} target service id={service_id} "
            f"code={service_code!r} vanished between the pre-state check "
            "and the guarded write — the identity (id+code) matched no "
            "row; re-run the inventory (never widen the predicate); "
            "aborting with no rows changed"
        )
    if after.code != service_code:
        _abort(
            f"{decision} target service id={service_id} changed identity "
            f"between the pre-state check and the guarded write (code "
            f"stored={after.code!r}, expected {service_code!r}); aborting "
            "with no rows changed"
        )
    if post_state_check(after):
        print(
            f"{_MIGRATION_NAME}: {decision} service id={service_id} "
            f"code={service_code!r} concurrently arrived at the exact "
            f"post-state ({post_state_description}) — proven idempotent "
            "no-op, nothing written for it"
        )
        return False
    _abort(
        f"{decision} target service id={service_id} code={service_code!r} "
        "was concurrently modified between the pre-state check and the "
        f"guarded write (live queue_tag={after.queue_tag!r}, "
        f"doctor_id={after.doctor_id!r}, active={bool(after.active)}; the "
        f"embedded map expected {expected_description}) — a newer operator "
        "edit is never overwritten by the cutover; re-run the inventory "
        "and update the decision tables; aborting with no rows changed"
    )


def _apply_service_decisions(conn, surfaces: dict) -> dict[str, int]:
    """Apply the embedded operator map, exact-row, deterministic.

    Pre-flight ordering (the 0063 no-rows-changed contract): the
    coverage, identity resolution, pre-state and target validations
    (registry resource, real doctor) ALL run BEFORE the first mutation
    — a stale map or an invalid target aborts with the catalog
    untouched, not half-converted.

    Identity (thread 3995689408, P1): each decision resolves its write
    target by the SNAPSHOT (id, code) pair from the approved map —
    ``_resolve_decision_target`` never falls back to a code-only
    lookup, so a replacement row re-using a mapped code can never
    inherit the old decision. The ``surfaces`` inventory stays the D-08
    coverage gate (and prints it), but is no longer the write-target
    resolver.

    Write phase (thread 3995689409, P1): every UPDATE carries the exact
    identity (id + code) AND the expected source state read by the
    identity resolution, and must affect exactly one row. A concurrent
    catalog edit that lands between the pre-state check and the write
    makes the guarded UPDATE match zero rows; the mismatch is then
    PROVEN to be either the exact post-state (an idempotent no-op) or
    it aborts the whole map — a newer operator edit is never
    overwritten, and the map is never partially applied."""
    counts = {
        "retag_resource": 0,
        "assign_doctor": 0,
        "clear_requires_doctor": 0,
        "disable_service": 0,
    }

    # Phase order (the race contract, thread 3995689409): the identity
    # rows are read FIRST — the expected source state for the guarded
    # writes is the state at THIS earliest read, so any catalog edit
    # landing between here and a write makes the guarded predicate
    # match zero rows and abort (or proves the idempotent no-op). A
    # later re-read would silently absorb the concurrent edit into
    # the expected state and clobber it.
    targets: dict[str, object] = {}
    for snapshot_id, code, _from_tag, _to_tag in _RETAG_DECISIONS:
        targets[code] = _resolve_decision_target(
            conn, snapshot_id=snapshot_id, code=code, decision="retag_resource"
        )
    for (
        snapshot_id,
        code,
        _target_doctor_id,
        _original_doctor_id,
        _expected_user_id,
        _snapshot_tag,
        _set_requires_doctor,
    ) in _ASSIGN_DOCTOR_DECISIONS:
        targets[code] = _resolve_decision_target(
            conn, snapshot_id=snapshot_id, code=code, decision="assign_doctor"
        )
    for snapshot_id, code in _DISABLE_DECISIONS:
        targets[code] = _resolve_decision_target(
            conn, snapshot_id=snapshot_id, code=code, decision="disable_service"
        )
    for snapshot_id, code, _snapshot_tag in _CLEAR_DOCTOR_REQUIREMENT_DECISIONS:
        targets[code] = _resolve_decision_target(
            conn,
            snapshot_id=snapshot_id,
            code=code,
            decision="clear_requires_doctor",
        )

    _assert_decision_pre_states(conn, surfaces)
    for _snapshot_id, code, _from_tag, to_tag in _RETAG_DECISIONS:
        if targets[code] is not None:
            _assert_registry_target(conn, to_tag)
    for (
        _snapshot_id,
        code,
        target_doctor_id,
        _original_doctor_id,
        expected_user_id,
        _snapshot_tag,
        _set_requires_doctor,
    ) in _ASSIGN_DOCTOR_DECISIONS:
        if targets[code] is not None:
            _assert_target_doctor(conn, target_doctor_id, expected_user_id)

    for _snapshot_id, code, _from_tag, to_tag in _RETAG_DECISIONS:
        row = targets[code]
        if row is None:
            continue
        if row.queue_tag == to_tag:
            # idempotent second pass — the decision is already applied
            print(
                f"{_MIGRATION_NAME}: retag_resource service id={row.id} "
                f"code={code!r} already on {to_tag!r} — no-op"
            )
            continue
        print(
            f"{_MIGRATION_NAME}: retag_resource service id={row.id} "
            f"code={code!r} queue_tag {row.queue_tag!r} -> {to_tag!r} "
            f"(doctor_id={row.doctor_id}, requires_doctor="
            f"{row.requires_doctor})"
        )
        applied = _guarded_service_update(
            conn,
            statement=_UPDATE_SERVICE_QUEUE_TAG,
            params={
                "id": row.id,
                "code": row.code,
                "to_tag": to_tag,
                "expected_queue_tag": row.queue_tag,
                "expected_queue_tag_is_null": _is_null_flag(row.queue_tag),
            },
            service_id=row.id,
            service_code=row.code,
            decision="retag_resource",
            expected_description=f"queue_tag={row.queue_tag!r}",
            post_state_check=(
                lambda after, _to_tag=to_tag: after.queue_tag == _to_tag
            ),
            post_state_description=f"queue_tag={to_tag!r}",
        )
        if applied:
            counts["retag_resource"] += 1
            _verify_service_state(conn, service_id=row.id, queue_tag=to_tag)

    for (
        _snapshot_id,
        code,
        target_doctor_id,
        _original_doctor_id,
        _expected_user_id,
        _snapshot_tag,
        set_requires_doctor,
    ) in _ASSIGN_DOCTOR_DECISIONS:
        row = targets[code]
        if row is None:
            continue
        fully_applied = row.doctor_id == target_doctor_id and (
            set_requires_doctor is None
            or bool(row.requires_doctor) == set_requires_doctor
        )
        if fully_applied:
            # idempotent second pass — the decision is already applied
            print(
                f"{_MIGRATION_NAME}: assign_doctor service id={row.id} "
                f"code={code!r} already on doctor_id={target_doctor_id} — no-op"
            )
            continue
        print(
            f"{_MIGRATION_NAME}: assign_doctor service id={row.id} "
            f"code={code!r} doctor_id {row.doctor_id} -> "
            f"{target_doctor_id} (tag={row.queue_tag!r}, "
            f"set_requires_doctor={set_requires_doctor})"
        )
        applied = _guarded_service_update(
            conn,
            statement=_UPDATE_SERVICE_DOCTOR,
            params={
                "id": row.id,
                "code": row.code,
                "doctor_id": target_doctor_id,
                "expected_doctor_id": row.doctor_id,
                "expected_doctor_id_is_null": _is_null_flag(row.doctor_id),
                "expected_queue_tag": row.queue_tag,
                "expected_queue_tag_is_null": _is_null_flag(row.queue_tag),
                "set_requires_doctor": 0 if set_requires_doctor is None else 1,
                "requires_doctor_decision": 0 if set_requires_doctor is None else 1,
                # a REAL Python bool: PG binds int 0 as smallint and the
                # boolean comparison fails with `boolean = smallint` (the
                # review P1 on 055a7c7ec, reproduced on PostgreSQL 17)
                "expected_requires_doctor": (
                    False if set_requires_doctor is not None else None
                ),
                "expected_requires_doctor_is_null": _is_null_flag(
                    0 if set_requires_doctor is not None else None
                ),
            },
            service_id=row.id,
            service_code=row.code,
            decision="assign_doctor",
            expected_description=(
                f"doctor_id={row.doctor_id!r} on queue_tag={row.queue_tag!r}"
                + (
                    f", requires_doctor={bool(row.requires_doctor)}"
                    if set_requires_doctor is not None
                    else ""
                )
            ),
            post_state_check=(
                lambda after, _doctor=target_doctor_id, _tag=row.queue_tag, _req=set_requires_doctor: (
                    after.doctor_id == _doctor
                    and after.queue_tag == _tag
                    and (_req is None or bool(after.requires_doctor) == _req)
                )
            ),
            post_state_description=(
                f"doctor_id={target_doctor_id} on queue_tag={row.queue_tag!r}"
                + (f", requires_doctor={set_requires_doctor}" if set_requires_doctor is not None else "")
            ),
        )
        if applied:
            counts["assign_doctor"] += 1
            _verify_service_state(
                conn,
                service_id=row.id,
                doctor_id=target_doctor_id,
                requires_doctor=set_requires_doctor if set_requires_doctor is not None else ...,
            )

    for _snapshot_id, code, snapshot_tag in _CLEAR_DOCTOR_REQUIREMENT_DECISIONS:
        row = targets[code]
        if row is None:
            continue
        if row.doctor_id is not None:
            _abort(
                f"clear_requires_doctor target service id={row.id} "
                f"code={code!r} carries doctor_id={row.doctor_id} — the "
                "refinement approves doctor_id=NULL (the procedures "
                "cabinet staff execute these); a Doctor-linked row is a "
                "discrepancy for the operator, never auto-cleared; "
                "aborting with no rows changed"
            )
        if row.requires_doctor is None or not bool(row.requires_doctor):
            print(
                f"{_MIGRATION_NAME}: clear_requires_doctor service "
                f"id={row.id} code={code!r} already requires_doctor=false "
                "— no-op"
            )
            continue
        print(
            f"{_MIGRATION_NAME}: clear_requires_doctor service id={row.id} "
            f"code={code!r} requires_doctor true -> false "
            f"(tag={row.queue_tag!r}, doctor_id stays NULL)"
        )
        applied = _guarded_service_update(
            conn,
            statement=_UPDATE_SERVICE_REQUIRES_DOCTOR,
            params={
                "id": row.id,
                "code": row.code,
                "expected_queue_tag": row.queue_tag,
            },
            service_id=row.id,
            service_code=row.code,
            decision="clear_requires_doctor",
            expected_description=(
                f"requires_doctor=True on queue_tag={row.queue_tag!r} "
                "with doctor_id=NULL"
            ),
            post_state_check=(
                # Review round 4 (P2): the loop variable must be CAPTURED
                # by the callback — the bare ``_expected_tag`` name was
                # never defined, so the idempotent-race path (a concurrent
                # transaction already arrived at the exact approved
                # post-state) raised NameError instead of proving the
                # no-op and crashed the upgrade (the e0248660a "bind the
                # race-callback expected tag" fix only bound the GQL
                # resolver argument — this migration callback was missed).
                lambda after, _expected_tag=snapshot_tag: (
                    not bool(after.requires_doctor)
                    and after.doctor_id is None
                    and after.queue_tag == _expected_tag
                )
            ),
            post_state_description=(
                "requires_doctor=False, doctor_id=NULL, "
                f"queue_tag={snapshot_tag!r}"
            ),
        )
        if applied:
            counts["clear_requires_doctor"] += 1
            _verify_service_state(conn, service_id=row.id, requires_doctor=False)

    for _snapshot_id, code in _DISABLE_DECISIONS:
        row = targets[code]
        if row is None:
            continue
        print(
            f"{_MIGRATION_NAME}: disable_service service id={row.id} "
            f"code={code!r} (tag={row.queue_tag!r})"
        )
        applied = _guarded_service_update(
            conn,
            statement=_UPDATE_SERVICE_ACTIVE,
            params={
                "id": row.id,
                "code": row.code,
                "active": False,
                "expected_active": True,
            },
            service_id=row.id,
            service_code=row.code,
            decision="disable_service",
            expected_description="active=True",
            post_state_check=lambda after: not bool(after.active),
            post_state_description="active=False",
        )
        if applied:
            counts["disable_service"] += 1
            _verify_service_state(conn, service_id=row.id, active=False)

    return counts


def _apply_profile_decisions(conn) -> int:
    """keep_profile writes nothing; retire_profile deactivates (guarded
    by key identity + expected is_active, the same 3995689409 contract).

    Same-error-class audit (thread 3995689408, "check every decision
    table of this migration"): profile decisions are keyed by the
    NATURAL key ``queue_profiles.key`` (a stable business identity,
    not a surrogate row id), and the only current decision
    (``general`` -> keep_profile) writes NOTHING — so no
    re-created-profile exposure exists in the current map. A future
    ``retire_profile`` row inherits the guarded-write contract above:
    key identity + expected is_active in the UPDATE predicate, exactly
    one affected row, idempotent no-op proven on rowcount != 1 — a
    re-created profile is only ever deactivated when the operator's map
    still names its key, and the validate-only downgrade reports it."""
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
        result = conn.execute(
            _UPDATE_PROFILE_ACTIVE,
            {
                "id": row.id,
                "key": profile_key,
                "active": False,
                "expected_active": True,
            },
        )
        if result.rowcount == 1:
            retired += 1
        else:
            after = conn.execute(
                _SELECT_PROFILE_BY_KEY, {"key": profile_key}
            ).fetchone()
            if after is not None and not bool(after.is_active):
                print(
                    f"{_MIGRATION_NAME}: retire_profile profile "
                    f"id={row.id} key={profile_key!r} concurrently "
                    "arrived at is_active=false — proven idempotent no-op"
                )
                continue
            _abort(
                f"retire_profile target profile id={row.id} "
                f"key={profile_key!r} was concurrently modified between "
                "the read and the guarded write (is_active="
                f"{bool(after.is_active) if after is not None else 'row vanished'}"
                ") — a newer operator edit is never overwritten; aborting "
                "with no rows changed"
            )
        after = conn.execute(_SELECT_PROFILE_BY_KEY, {"key": profile_key}).fetchone()
        if after is None or bool(after.is_active):
            _abort(
                f"postcondition failed for profile {profile_key!r}: "
                "still active after retire_profile; aborting with no "
                "rows changed"
            )
    return retired


def upgrade_with_conn(conn) -> dict[str, int]:
    """The testable cutover entry (the 0063 module-level pattern)."""
    _assert_no_active_general_queues(conn)
    # Review round 4 (P1): the D-08 coverage inventory runs BEFORE the
    # procedures registry resource is seeded. _SELECT_SURFACES EXCLUDES
    # services whose tag resolves to an ACTIVE queue_resources row, so
    # seeding the resource FIRST would hide EVERY active service on the
    # 'procedures' tag from the coverage gate — an unapproved 17th
    # procedure (added to the catalog after the map was approved) would
    # silently ride the resource axis with no operator decision and no
    # abort. With the inventory first, the sixteen approved procedures
    # appear as general-fallback surfaces (all decided identities — no
    # abort), and the dedicated seed-tag check below keeps the same gate
    # closed even when the resource ALREADY exists (pre-created by an
    # operator or left by a manual repair).
    surfaces = _inventory_and_assert_coverage(conn)
    _assert_registry_seed_tag_coverage(conn)
    # D-08 refinement (owner, 2026-09-15): the 16 procedure services
    # route through the ACTIVE QueueResource('procedures'). Idempotent,
    # guarded seed (absent -> INSERT with the 0059 defaults; ACTIVE
    # same-code -> no-op; anything else -> operator decision).
    _ensure_procedures_registry_resource(conn)
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
    """Conservative validate-only downgrade — writes NOTHING (Codex
    round-1 P1; the 0059 round-2 ruling and the 0063 downgrade
    philosophy verbatim).

    A data downgrade CANNOT prove which rows THIS revision changed: a
    mapped code sitting on the post-state tag is either a row the
    upgrade retagged (restorable) or one the operator hand-moved to
    the same tag before the cutover (the upgrade treated it as an
    inert no-op and MUST NOT touch it) — the database carries no
    marker distinguishing the two, so a blanket restore would corrupt
    pre-existing catalog state. The downgrade therefore only VALIDATES
    the state and prints the exact per-code original values; the
    recovery paths are the upgrade's per-row inventory (the migration
    log is the audit trail) and a pre-E backup (the full restore).
    Re-upgrading after this downgrade is a clean no-op (every mapped
    code is on its post-state) and the rolled-back runtime serves the
    retagged catalog identically (the lab/ecg resource axis predates
    this revision; the pre-E fallback code returns with the
    rolled-back revision)."""
    print(
        f"{_MIGRATION_NAME} downgrade: validate-only, NO catalog writes "
        "(the 0059/0063 conservative ruling — the upgrade log inventory "
        "and a pre-E backup are the restore paths)"
    )
    for snapshot_id, code, from_tag, to_tag in _RETAG_DECISIONS:
        rows = conn.execute(_SELECT_SERVICE_BY_CODE_ANY, {"code": code}).fetchall()
        for row in rows:
            if row.queue_tag == to_tag:
                print(
                    f"{_MIGRATION_NAME} downgrade: service id={row.id} "
                    f"code={code!r} (snapshot id={snapshot_id}) sits on "
                    f"the retagged state {to_tag!r} — the pre-E value "
                    f"was {from_tag!r} "
                    "(see the upgrade log inventory; restore manually or "
                    "from the pre-E backup if required)"
                )
    for (
        snapshot_id,
        code,
        target_doctor_id,
        original_doctor_id,
        _expected_user_id,
        _snapshot_tag,
        _set_requires_doctor,
    ) in _ASSIGN_DOCTOR_DECISIONS:
        rows = conn.execute(_SELECT_SERVICE_BY_CODE_ANY, {"code": code}).fetchall()
        for row in rows:
            if row.doctor_id == target_doctor_id:
                print(
                    f"{_MIGRATION_NAME} downgrade: service id={row.id} "
                    f"code={code!r} (snapshot id={snapshot_id}) sits on "
                    f"the assigned doctor {target_doctor_id} — the pre-E "
                    f"value was "
                    f"{original_doctor_id!r} (see the upgrade log "
                    "inventory; restore manually or from the pre-E "
                    "backup if required)"
                )
    for snapshot_id, code in _DISABLE_DECISIONS:
        rows = conn.execute(_SELECT_SERVICE_BY_CODE_ANY, {"code": code}).fetchall()
        for row in rows:
            if not bool(row.active):
                print(
                    f"{_MIGRATION_NAME} downgrade: service id={row.id} "
                    f"code={code!r} (snapshot id={snapshot_id}) is "
                    "disabled by the cutover decision "
                    "— re-activate manually if the rollback requires it"
                )


def downgrade() -> None:
    downgrade_with_conn(op.get_bind())
