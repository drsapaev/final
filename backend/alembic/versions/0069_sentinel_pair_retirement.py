"""RQ-15.d (ADR-001 stage E): retire the 0055 synthetic User+Doctor pairs.

The terminal step of the QD-2 staged rollout (ADR-001 "Queue ownership
and specialty architecture", stage table row E): "Retire the synthetic
User+Doctor pairs (paired deletion), remove the bridge vocabulary."
Doctorless queues are owned by ``queue_resources`` rows — a reference
registry with no User, no role, no login — so the three synthetic pairs
provisioned by ``0055_queue_resource_provisioning``
(``ecg_resource``/``lab_resource``/``general_resource``) are deleted,
PAIR BY PAIR (the User row and its linked Doctor row together).

The pre-state this migration requires was verified on production by the
2026-09-12 inventory (``evidence/stage_e_inventory_20260912_rerun.json``):

- ``daily_queues`` carries ZERO references to the synthetic doctors:
  0063 consumed every canonical dual-ownership bridge
  (``specialist_id`` -> NULL on rows whose owner is in the synthetic
  vocabulary and whose tag matches the linked resource), and the
  inventory reports ``general_queues.total = 0`` — the ADR stage-E
  claim "the paired deletion now faces zero daily_queues references";
- no ACTIVE service points at a synthetic doctor — the 0066 operator
  map moved every active general-fallback surface onto the resource
  axis or a real doctor (33 retag / 7 assign / 16 procedures);
- across the 103 FK surfaces the inventory introspected, the ONLY
  inbound reference was ``login_attempts.user_id`` — one failed-login
  probe row for ``ecg_resource``. That FK is declared
  ``ON DELETE SET NULL`` on purpose ("SECURITY: SET NULL to preserve
  failed attempts even if user deleted"), so the deletion anonymizes
  the probe row instead of losing it. It is the ONLY surface allowed
  to carry rows at retirement time.

The runtime half needs no code change: since RQ-15.b the owner
resolution is fail-closed (``queue_owner_policy``) and the internal
account guards are ROLE-based, not username-based (the ADR gate-5
vocabulary ruling) — deleting the rows leaves no dangling vocabulary
in runtime code. The 0056/0057 'Resource' role machinery stays: it
guards any FUTURE internal account the operator may provision.

Upgrade contract (single transaction; PG DDL/DML is transactional):

1. ALL-OR-NOTHING pair resolution, inventory-before-mutation, behind
   a table lock, on rows locked FOR UPDATE (PostgreSQL; the P1-b
   hardening of the owner closure plan + the review rounds 2/3, all
   applied in the post-merge window BEFORE the production application
   — after that the migration body is frozen):

   - the migration transaction OPENS with ``LOCK TABLE users,
     doctors IN SHARE ROW EXCLUSIVE MODE`` (the review-round-3 P2-B
     hardening): row locks only fix the rows they SEE, so every
     read-to-commit window — the locks->resolution gap the P2-1 set
     equality closes, the final-guard->commit gap, and the whole
     already-retired no-op pass where there are no rows to lock at
     all — stayed open to a concurrent INSERT (a restored pair, an
     orphaned bridge-vocabulary Doctor) that would silently
     invalidate the verdict Alembic is about to stamp. SHARE ROW
     EXCLUSIVE conflicts with every ROW EXCLUSIVE taker — every
     concurrent INSERT/UPDATE/DELETE on the two tables — while plain
     readers (ACCESS SHARE) and row-lockers (ROW SHARE) are
     unaffected: from the first statement to the commit, no
     concurrent writer can land inside the window. The downgrade
     opens with the same lock (its postcondition window is the same
     class of phantom);
   - the three User rows and their linked Doctor rows are locked
     ``FOR UPDATE`` (users first, then doctors, each ordered by id — a
     deterministic acquisition order) BEFORE the resolution SELECT and
     every guard runs: FOR UPDATE conflicts with every concurrent row
     writer (a re-purpose of ``users.role``, an orphaning UPDATE of
     ``doctors.user_id``) AND with the FOR KEY SHARE lock an
     FK-referencing INSERT takes on the parent row, so from the first
     lock to the commit the inventory, the guards, and the deletion
     all see ONE stable world — the "verified 0055 shape" contract
     holds at DELETE time, not just at CHECK time;
   - the locked id sets are RETURNED and the resolution must prove
     EXACT set equality with them (the P2-1 phantom hardening): row
     locks only fix the rows they SEE, so a pair that appeared AFTER
     the lock selects (a concurrent restore of a missing half
     committing between the locks and the resolution read) was never
     locked — the retirement deletes only rows it locked, and the
     mismatch is a LOUD abort (re-run the migration once the
     concurrent writer is done), never a silent deletion of an
     unlocked row;
   - the rowcount verification and the postcondition re-check stay in
     place as the backstop (defense in depth), not the primary lock;
   - non-PostgreSQL dialects (the SQLite scratch harness) skip the
     locking with a printed note — single-connection harnesses cannot
     race (the P1-2 dialect-gate precedent) — but still read the ids
     the same way, so the phantom-set comparison below runs everywhere;

   - all three pairs present and shape-valid (linked doctor, the
     expected 0055 specialty, the post-0057 'Resource' role, not a
     superuser) -> the guarded paired deletion below;
   - ALL three absent -> the terminal verdict is PROVABLE, not
     assumed (the P2-2 hardening, review round 3 narrowed to the
     ACTIVE half): any ACTIVE Doctor row still carrying the bridge
     vocabulary (a specialty from the 0055 mapping) with NO User
     link aborts loudly. The ``active`` flag is the provenance-honest
     discriminator the specialty alone cannot be: the sanctioned
     user-deletion path DEACTIVATES the profile before deleting the
     owner, so an INACTIVE userless bridge-specialty row is preserved
     clinical history ('general' doubles as the live
     INCOMPLETE_DOCTOR_SPECIALTY onboarding sentinel a Registrar->
     Doctor promotion provisions) and does NOT block the verdict,
     while a raw hand-deleted User (the ``doctors.user_id`` FK is ON
     DELETE SET NULL, nothing deactivates the row) leaves the half
     ACTIVE — and an ACTIVE userless row is drift either way
     (decision #13 already treats it as a linkage-contract
     violation the pre-deploy reconciler blocks on), so the abort
     names the unprovable state, never the origin. The same proof
     runs when the pairs are present: the bridge vocabulary must
     leave WITH the pairs, never stranded;
   - a PARTIAL set (someone hand-deleted one pair before the
     retirement) or any shape drift (orphan user without a doctor, a
     foreign specialty, a re-purposed role, a superuser flag) -> a
     LOUD abort with nothing changed (the 0063/0066 taxonomy: the
     repair is an explicit operator decision, never a migration
     guess). The all-or-nothing invariant is also what keeps the
     downgrade a TRUE inverse.

2. Semantic reference guards (plain SQL, both dialects):

   - ANY ``services.doctor_id`` row referencing a synthetic doctor —
     active OR historical — aborts with the full per-row inventory:
     the catalog is never silently doctor-stripped (an inactive
     historical assignment is still catalog state the operator owns);
   - ANY ``daily_queues.specialist_id`` row referencing a synthetic
     doctor — active OR historical — aborts with the per-row
     inventory: 0063 consumed every canonical bridge, so any survivor
     is drift the operator must resolve explicitly, and the NO ACTION
     FK would block the deletion anyway.

3. PostgreSQL FK introspection (the future-proof catch-all): every
   FK surface referencing ``users.id``/``doctors.id`` is enumerated
   from ``pg_catalog`` (direct ``pg_constraint`` discovery,
   schema-scoped on the source and the reference side) and counted
   against the resolved pair ids BEFORE the deletion:

   - a NO ACTION/RESTRICT surface with rows aborts (the FK would
     fire mid-delete);
   - a CASCADE surface with rows aborts — the retirement NEVER
     silently cascade-deletes history;
   - ``login_attempts`` is the only SET NULL surface allowed to carry
     rows (the designed security semantic — the rows survive,
     anonymized);
   - any OTHER SET NULL surface with rows aborts loudly (a surface
     that did not exist at design time is an operator decision, not a
     silent anonymization);
   - the pair's own ``doctors.user_id`` self-reference is excluded;
   - a composite (multi-column) FK referencing the pairs aborts as
     unsupported — never guessed;
   - non-PostgreSQL dialects (the SQLite scratch harness) skip the
     introspection with a printed note — the semantic guards above
     still run (the P1-2 dialect-gate precedent from 0066).

4. The paired deletion: ``DELETE FROM doctors`` then ``DELETE FROM
   users`` (the self FK never fires), each rowcount verified against
   the resolved inventory, postcondition re-verified (the usernames
   are gone, no doctor remains linked). The migration log carries the
   full per-pair inventory and per-surface counts — the audit trail
   (a pre-deletion backup is the restore path).

Downgrade — a TRUE inverse of the all-or-nothing upgrade: it
re-provisions the three pairs in the exact 0055+0057 shape (username,
``!disabled:queue-resource`` unusable hash, the internal 'Resource'
role, the 0055 specialty mapping, active, caps 1/15) with
``ON CONFLICT DO NOTHING`` (idempotent). No ids are invented and no
sequences are touched: the pairs are identified by USERNAME, and at
upgrade time zero FK references exist to the old numeric ids (the
guards proved it) — the anonymized ``login_attempts`` rows stay
anonymized (a downgrade restores PAIRS, not per-row audit links).
An EXISTING username is an idempotent no-op only after the full
0055+0057 shape is verified field-by-field (the P2-3 hardening: hash,
role, is_active, is_superuser, must_change_password, exactly one
linked Doctor, the 0055 specialty, active, caps 1/15) — a username
captured by a foreign row (an Admin account, a live password, a
caps-drifted doctor) is a LOUD abort, never a silent skip; a final
postcondition re-verifies all three pairs before the migration
claims the restore.

2026-09-18 Supabase compatibility fix (guard implementation only): the
PostgreSQL FK discovery moved from multi-view information_schema joins
to direct pg_catalog queries (pg_constraint / pg_class / pg_namespace /
pg_attribute) — the multi-view join hung on the production Supabase
catalog before the deletion. The REFERENCE side is strictly scoped to
current_schema(); the SOURCE side is deliberately UNRESTRICTED: an FK
from ANY schema landing on the pairs (a ``reporting.audit_rows`` ->
``public.users`` CASCADE on a multi-schema Supabase) is inventoried,
counted and fail-closed exactly like a local surface — a foreign
schema's silence can never turn a live FK into a silent cascade. The
per-surface counting is schema-qualified, the self-reference exclusion
and the login_attempts SET NULL allowlist apply ONLY to the current
schema (name collisions across schemas do not inherit the exemption),
and a surface the migration role cannot SELECT is a loud abort, not a
skip. All other guard semantics are unchanged: the composite-FK abort,
the all-or-nothing deletion contract (the composite column_count now
reports the FK's own column count instead of the pre-fix cross-product
inflation).
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

# Revision identifiers — chained after 0068 (the direction public-address
# registry, RQ-16.c), which follows 0067 (the day start-number snapshot,
# RQ-13.b).
revision = "0069_sentinel_pair_retirement"
down_revision = "0068_direction_public_address"
branch_labels = None
depends_on = None

_MIGRATION_NAME = "0069_sentinel_pair_retirement"

# The exact 0055 identities (parity pinned by the test suite against
# the 0055 source): username -> the specialty of its linked Doctor row.
SYNTHETIC_PAIR_SPECIALTIES: dict[str, str] = {
    "ecg_resource": "ecg",
    "lab_resource": "lab",
    "general_resource": "general",
}
SYNTHETIC_PAIR_USERNAMES: tuple[str, ...] = tuple(SYNTHETIC_PAIR_SPECIALTIES)

# The 0055 unusable-password marker (the accounts own queues, they are
# not logins) and the post-0056/0057 internal sentinel role.
SYNTHETIC_PAIR_DISABLED_HASH = "!disabled:queue-resource"
SYNTHETIC_PAIR_ROLE = "Resource"

# The ONLY SET NULL surface allowed to carry rows at retirement time
# (the 2026-09-12 production inventory found exactly one probe row
# there; the FK semantic "preserve failed attempts even if user
# deleted" is the designed behavior).
_SET_NULL_ROW_ALLOWLIST = {("login_attempts", "user_id")}

# The pair's own doctor link (doctors.user_id -> users.id) is a
# self-reference of the deleted rows, not an inbound reference.
_SELF_REFERENCE_SURFACES = {("doctors", "user_id", "users")}

_SELECT_PAIRS = sa.text("""
    SELECT u.id AS user_id,
           u.username AS username,
           u.role AS role,
           u.is_active AS is_active,
           u.is_superuser AS is_superuser,
           u.hashed_password AS hashed_password,
           u.must_change_password AS must_change_password,
           d.id AS doctor_id,
           d.specialty AS specialty,
           d.active AS doctor_active,
           d.start_number_online AS start_number_online,
           d.max_online_per_day AS max_online_per_day
    FROM users u
    LEFT JOIN doctors d ON d.user_id = u.id
    WHERE u.username IN :usernames
    ORDER BY u.username
    """).bindparams(sa.bindparam("usernames", expanding=True))

# Review round 3 (P2-A): the ACTIVE discriminator is the honest
# provenance the vocabulary alone cannot provide. The sanctioned
# user-deletion path DEACTIVATES the doctor profile before the owner
# is deleted (an inactive userless row is preserved clinical history
# — a Registrar promoted to Doctor carries the 'general' onboarding
# sentinel specialty, INCOMPLETE_DOCTOR_SPECIALTY, and its sanctioned
# deletion leaves exactly that inactive historical row), while a raw
# DELETE that bypasses the API leaves the half ACTIVE (the
# doctors.user_id FK is ON DELETE SET NULL, nothing deactivates the
# row). An ACTIVE userless row is drift either way — decision #13
# already treats it as a linkage-contract violation the pre-deploy
# reconciler blocks on — so the guard flags the drift shape without
# claiming to know which of the two worlds the row came from.
_SELECT_ORPHAN_BRIDGE_DOCTORS = sa.text("""
    SELECT id, specialty, active, start_number_online, max_online_per_day
    FROM doctors
    WHERE user_id IS NULL AND active AND specialty IN :specialties
    ORDER BY id
    """).bindparams(sa.bindparam("specialties", expanding=True))

# Review round 3 (P2-B): a SHARE ROW EXCLUSIVE table lock on the two
# tables every verdict reasons about, taken as the FIRST statement of
# the migration transaction. Row locks (FOR UPDATE) only fix the rows
# they SEE — on the already-retired no-op pass there are no pair rows
# to lock at all, so a pair (or an orphaned bridge-vocabulary Doctor)
# INSERTED after the final read could commit before this migration and
# silently invalidate the verdict Alembic is about to stamp. SHARE ROW
# EXCLUSIVE conflicts with every ROW EXCLUSIVE taker — every concurrent
# INSERT/UPDATE/DELETE on users/doctors — while plain readers (ACCESS
# SHARE) and row-lockers (ROW SHARE) are unaffected (PostgreSQL only,
# the P1-2 dialect-gate precedent; the single-connection SQLite scratch
# harness cannot race).
_LOCK_PAIR_TABLES = sa.text("LOCK TABLE users, doctors IN SHARE ROW EXCLUSIVE MODE")

# The P1-b hardening: lock the pair rows BEFORE the resolution reads
# them (PostgreSQL only — the dialect gate prints a note and skips on
# the single-connection SQLite scratch harnesses). Users first, then
# their linked doctors, each ordered by id — a deterministic
# acquisition order; FOR UPDATE blocks every concurrent row writer
# and every FK-referencing INSERT (FOR KEY SHARE) until this
# transaction ends.
_LOCK_PAIR_USERS = sa.text(
    "SELECT id FROM users WHERE username IN :usernames ORDER BY id FOR UPDATE"
).bindparams(sa.bindparam("usernames", expanding=True))

_LOCK_PAIR_DOCTORS = sa.text("""
    SELECT d.id
    FROM doctors d
    JOIN users u ON d.user_id = u.id
    WHERE u.username IN :usernames
    ORDER BY d.id
    FOR UPDATE
    """).bindparams(sa.bindparam("usernames", expanding=True))

# The same identification reads WITHOUT the locking clause — the
# non-PostgreSQL scratch harnesses cannot race (single connection),
# but the phantom-set comparison still runs, so the ids are collected
# the same way (the P1-2 dialect-gate precedent: skip the LOCK, never
# the CHECK).
_SELECT_PAIR_USER_IDS = sa.text(
    "SELECT id FROM users WHERE username IN :usernames ORDER BY id"
).bindparams(sa.bindparam("usernames", expanding=True))

_SELECT_PAIR_DOCTOR_IDS = sa.text("""
    SELECT d.id
    FROM doctors d
    JOIN users u ON d.user_id = u.id
    WHERE u.username IN :usernames
    ORDER BY d.id
    """).bindparams(sa.bindparam("usernames", expanding=True))

_SELECT_SERVICE_REFERENCES = sa.text("""
    SELECT sv.id, sv.code, sv.active, sv.queue_tag, sv.doctor_id
    FROM services sv
    WHERE sv.doctor_id IN :doctor_ids
    ORDER BY sv.id
    """).bindparams(sa.bindparam("doctor_ids", expanding=True))

_SELECT_QUEUE_REFERENCES = sa.text("""
    SELECT q.id, q.day, q.queue_tag, q.specialist_id, q.active
    FROM daily_queues q
    WHERE q.specialist_id IN :doctor_ids
    ORDER BY q.day, q.id
    """).bindparams(sa.bindparam("doctor_ids", expanding=True))

# Every single-column FK surface referencing users.id / doctors.id in
# the CURRENT schema, from ANY source schema, with its ON DELETE rule.
#
# Direct pg_catalog discovery (the 2026-09-18 Supabase compatibility
# fix): the multi-view information_schema join hung on the production
# Supabase catalog (permission-checked views over every internal
# schema) before the deletion. The REFERENCE side is strictly scoped
# to current_schema() — a bare table-name match would pull in foreign
# "users" worlds (Supabase's auth.users is a real one). The SOURCE
# side is deliberately UNRESTRICTED: an FK from ANY schema landing on
# the pairs (a reporting.audit_rows -> public.users CASCADE on a
# multi-schema Supabase) is inventoried and fail-closed like a local
# surface — a silently skipped foreign-schema child would make the
# pair DELETE fire a cross-schema cascade the migration never saw.
# src_schema travels with every row so the per-surface counting can
# address the table schema-qualified (review of PR #3324, P1).
_SELECT_FK_SURFACES = sa.text("""
    SELECT DISTINCT
           src_ns.nspname AS src_schema,
           src.relname AS table_name,
           att.attname AS column_name,
           ref.relname AS ref_table,
           CASE con.confdeltype
                WHEN 'a' THEN 'NO ACTION'
                WHEN 'r' THEN 'RESTRICT'
                WHEN 'c' THEN 'CASCADE'
                WHEN 'n' THEN 'SET NULL'
                WHEN 'd' THEN 'SET DEFAULT'
           END AS delete_rule
    FROM pg_constraint con
    JOIN pg_class src ON src.oid = con.conrelid
    JOIN pg_namespace src_ns ON src_ns.oid = src.relnamespace
    JOIN pg_class ref ON ref.oid = con.confrelid
    JOIN pg_namespace ref_ns ON ref_ns.oid = ref.relnamespace
    JOIN unnest(con.conkey) WITH ORDINALITY AS ck(attnum, ord) ON true
    JOIN pg_attribute att
      ON att.attrelid = con.conrelid AND att.attnum = ck.attnum
    WHERE con.contype = 'f'
      AND ref_ns.nspname = current_schema()
      AND ref.relname IN ('users', 'doctors')
    ORDER BY src_schema, table_name, column_name
    """)

# Composite FK guard: any constraint referencing the pairs that spans
# more than one column is unsupported surface — never guessed.
# column_count is the FK's OWN column count (cardinality of conkey);
# the pre-fix information_schema join inflated it by multiplying with
# the referenced-side columns of the composite unique constraint. The
# source side is unrestricted (any schema), mirroring the surface
# query: a foreign-schema composite FK is unsupported surface too.
_SELECT_COMPOSITE_FK_CONSTRAINTS = sa.text("""
    SELECT src_ns.nspname AS src_schema,
           con.conname AS constraint_name,
           cardinality(con.conkey) AS column_count
    FROM pg_constraint con
    JOIN pg_class src ON src.oid = con.conrelid
    JOIN pg_namespace src_ns ON src_ns.oid = src.relnamespace
    JOIN pg_class ref ON ref.oid = con.confrelid
    JOIN pg_namespace ref_ns ON ref_ns.oid = ref.relnamespace
    WHERE con.contype = 'f'
      AND ref_ns.nspname = current_schema()
      AND ref.relname IN ('users', 'doctors')
      AND cardinality(con.conkey) > 1
    ORDER BY src_schema, constraint_name
    """)

_DELETE_DOCTORS = sa.text("DELETE FROM doctors WHERE id IN :doctor_ids").bindparams(
    sa.bindparam("doctor_ids", expanding=True)
)

_DELETE_USERS = sa.text("DELETE FROM users WHERE id IN :user_ids").bindparams(
    sa.bindparam("user_ids", expanding=True)
)

# The downgrade re-provisioning — the exact 0055 shape with the
# post-0056/0057 'Resource' role (idempotent, username-identified).
_REPROVISION_USERS = sa.text("""
    INSERT INTO users (username, hashed_password, role, is_active,
                       is_superuser, must_change_password)
    VALUES (:username, :hash, :role, true, false, false)
    ON CONFLICT (username) DO NOTHING
    """)

_REPROVISION_DOCTORS = sa.text("""
    INSERT INTO doctors (user_id, specialty, active,
                         start_number_online, max_online_per_day)
    SELECT u.id, :specialty, true, 1, 15
    FROM users u
    WHERE u.username = :username
    ON CONFLICT (user_id) DO NOTHING
    """)


def _abort(message: str) -> None:
    raise RuntimeError(f"{_MIGRATION_NAME} abort: {message}")


# The tail every downgrade shape abort shares: what an existing
# username must be to qualify as the idempotent no-op, and who owns
# the decision when it is not (the P2-3 hardening).
_FOREIGN_CAPTURE_TAIL = (
    "an existing username is an idempotent no-op only in the exact "
    "0055+0057 shape — a foreign capture is an explicit operator "
    "decision, never a migration guess; refusing with no rows changed"
)


def _lock_pair_tables(conn) -> None:
    """Review round 3 (P2-B): take the predicate-level lock FIRST. Row
    locks fix only the rows they SEE, so every read-to-commit window —
    locks -> resolution, final guard -> commit, and the whole
    already-retired no-op pass where there are no rows to lock at all
    — stayed open to a concurrent INSERT (a restored pair, an orphaned
    bridge-vocabulary Doctor) that would silently invalidate the
    verdict this migration is about to stamp. SHARE ROW EXCLUSIVE
    closes the window at the table level: no concurrent
    INSERT/UPDATE/DELETE on users/doctors can land from this statement
    to the transaction's commit (PostgreSQL only — the dialect-gate
    precedent; the single-connection SQLite scratch cannot race)."""
    if conn.dialect.name != "postgresql":
        print(
            f"{_MIGRATION_NAME}: pair-table locking skipped on dialect "
            f"{conn.dialect.name!r} (PostgreSQL-only surface; the "
            "single-connection scratch harness cannot race — the "
            "semantic shape guards still run)"
        )
        return
    conn.execute(_LOCK_PAIR_TABLES)
    print(
        f"{_MIGRATION_NAME}: took SHARE ROW EXCLUSIVE on users, doctors "
        "— every concurrent INSERT/UPDATE/DELETE on the two tables "
        "blocks until this transaction ends, so the verdict this "
        "migration stamps is true of a world no concurrent writer "
        "can change"
    )


def _lock_pair_rows(conn) -> tuple[set[int], set[int]]:
    """P1-b + P2-1: serialize every concurrent writer away from the
    pairs BEFORE the resolution reads them (PostgreSQL; the SQLite
    scratch harnesses print a note and read the ids WITHOUT locking
    — single-connection harnesses cannot race, the P1-2 dialect-gate
    precedent) and RETURN the locked id sets, so the resolution can
    prove it only ever deletes rows it locked."""
    usernames = list(SYNTHETIC_PAIR_USERNAMES)
    if conn.dialect.name != "postgresql":
        print(
            f"{_MIGRATION_NAME}: pair-row locking skipped on dialect "
            f"{conn.dialect.name!r} (PostgreSQL-only surface; the "
            "single-connection scratch harness cannot race — the "
            "semantic shape guards still run)"
        )
        user_rows = conn.execute(
            _SELECT_PAIR_USER_IDS, {"usernames": usernames}
        ).fetchall()
        doctor_rows = conn.execute(
            _SELECT_PAIR_DOCTOR_IDS, {"usernames": usernames}
        ).fetchall()
        return (
            {int(row.id) for row in user_rows},
            {int(row.id) for row in doctor_rows},
        )
    locked_users = conn.execute(_LOCK_PAIR_USERS, {"usernames": usernames}).fetchall()
    locked_doctors = conn.execute(
        _LOCK_PAIR_DOCTORS, {"usernames": usernames}
    ).fetchall()
    print(
        f"{_MIGRATION_NAME}: locked {len(locked_users)} User row(s) and "
        f"{len(locked_doctors)} Doctor row(s) FOR UPDATE — concurrent "
        "pair-row writers and FK-referencing inserts block until this "
        "transaction ends; the inventory, the guards, and the deletion "
        "see one stable world"
    )
    return (
        {int(row.id) for row in locked_users},
        {int(row.id) for row in locked_doctors},
    )


def _assert_lock_covers_resolution(
    rows: list, locked_user_ids: set[int], locked_doctor_ids: set[int]
) -> None:
    """P2-1: the resolved pair set must BE the locked pair set, exactly.
    Row locks only fix the rows they SEE — a pair that appeared AFTER
    the lock selects (a concurrent restore of the missing half
    committing between the locks and this read) was never locked, and
    deleting it would race every concurrent writer the locking exists
    to stop. The retirement deletes only rows it locked: the mismatch
    is a loud abort, never a silent inclusion of an unlocked row."""
    resolved_user_ids = {int(row.user_id) for row in rows}
    resolved_doctor_ids = {
        int(row.doctor_id) for row in rows if row.doctor_id is not None
    }
    phantom_users = resolved_user_ids - locked_user_ids
    phantom_doctors = resolved_doctor_ids - locked_doctor_ids
    vanished_users = locked_user_ids - resolved_user_ids
    if not (phantom_users or phantom_doctors or vanished_users):
        return
    _abort(
        "the resolved pair set is NOT the locked pair set — users that "
        f"appeared after the locks: {sorted(phantom_users)}, doctors "
        "that appeared after the locks: "
        f"{sorted(phantom_doctors)}, locked users that vanished: "
        f"{sorted(vanished_users)} (locked users "
        f"{sorted(locked_user_ids)} / doctors {sorted(locked_doctor_ids)} "
        f"vs resolved users {sorted(resolved_user_ids)} / doctors "
        f"{sorted(resolved_doctor_ids)}). A row that appeared after the "
        "FOR UPDATE selects was never locked — the retirement deletes "
        "only rows it locked; re-run the migration once the concurrent "
        "writer is done; refusing with no rows changed"
    )


def _assert_no_orphaned_bridge_doctors(conn) -> None:
    """P2-2 (review round 3 narrowed to the ACTIVE half): the terminal
    'already retired' verdict is PROVABLE, not assumed — but the
    provenance-honest discriminator is the ``active`` flag, not the
    specialty alone. A userless INACTIVE Doctor row is the sanctioned
    shape of preserved clinical history ('general' doubles as the live
    INCOMPLETE_DOCTOR_SPECIALTY onboarding sentinel; the sanctioned
    owner deletion deactivates and detaches the profile, it never
    deletes it), so it does NOT block the verdict. A userless ACTIVE
    bridge-specialty row is the exact drift shape a raw hand-deleted
    User leaves behind (the doctors.user_id FK is ON DELETE SET NULL,
    nothing deactivates the row) — and an ACTIVE userless row already
    violates the linkage contract on its own (decision #13, the
    pre-deploy reconciler), so it is drift whichever world it came
    from. The retirement never declares the pairs gone over such
    halves, and never strands one next to the pairs it retires."""
    rows = conn.execute(
        _SELECT_ORPHAN_BRIDGE_DOCTORS,
        {"specialties": list(SYNTHETIC_PAIR_SPECIALTIES.values())},
    ).fetchall()
    if not rows:
        return
    for row in rows:
        print(
            f"{_MIGRATION_NAME}: orphaned bridge-vocabulary doctor — "
            f"id={row.id} specialty={row.specialty!r} "
            f"active={bool(row.active)} "
            f"caps=({int(row.start_number_online)}, "
            f"{int(row.max_online_per_day)}) user_id=NULL"
        )
    _abort(
        f"{len(rows)} ACTIVE Doctor row(s) with NO User link still "
        f"carry the bridge vocabulary (specialty in "
        f"{sorted(SYNTHETIC_PAIR_SPECIALTIES.values())}) — the "
        "sanctioned user-deletion path DEACTIVATES the profile before "
        "deleting the owner (an inactive userless row is preserved "
        "clinical history), so an active userless half is exactly the "
        "drift a raw hand-deleted User leaves behind (the "
        "doctors.user_id FK is ON DELETE SET NULL), and decision #13 "
        "already treats an ACTIVE userless row as a linkage-contract "
        "violation. Specialty is NOT provenance — 'general' is also "
        "the live onboarding sentinel (INCOMPLETE_DOCTOR_SPECIALTY) — "
        "so this abort names the unprovable state, never the origin "
        "(deactivate the row if it is preserved history, re-link it "
        "to a restored User, or re-specialty a real doctor that "
        "collided with the vocabulary — an explicit operator "
        "decision); refusing with no rows changed"
    )


def _resolve_and_assert_pairs(conn) -> list:
    """Resolve the three pairs; enforce the all-or-nothing shape."""
    locked_user_ids, locked_doctor_ids = _lock_pair_rows(conn)
    rows = conn.execute(
        _SELECT_PAIRS, {"usernames": list(SYNTHETIC_PAIR_USERNAMES)}
    ).fetchall()

    # P2-1: the resolved world must BE the locked world, exactly — a
    # pair that appeared after the lock selects was never locked.
    _assert_lock_covers_resolution(rows, locked_user_ids, locked_doctor_ids)

    present = {row.username for row in rows}
    expected = set(SYNTHETIC_PAIR_USERNAMES)
    missing = expected - present

    if not present:
        # P2-2 (review round 3 narrowed): the terminal verdict is
        # PROVABLE — over ACTIVE halves only. An inactive userless
        # bridge-specialty row is the sanctioned shape of preserved
        # clinical history ('general' doubles as the onboarding
        # sentinel); an ACTIVE one is the raw hand-delete shape.
        _assert_no_orphaned_bridge_doctors(conn)
        print(
            f"{_MIGRATION_NAME}: all three synthetic pairs are absent — "
            "already retired, clean no-op pass"
        )
        return []

    if missing:
        _abort(
            "the synthetic pair set is PARTIAL — present "
            f"{sorted(present)}, missing {sorted(missing)}. The retirement "
            "is all-or-nothing: a hand-deleted pair is drift the operator "
            "must resolve explicitly (restore the pair from the 0055 shape "
            "or retire all three together); refusing with no rows changed"
        )

    for row in rows:
        if row.doctor_id is None:
            _abort(
                f"pair {row.username!r}: the User row (id={row.user_id}) has "
                "NO linked Doctor row — an orphan half-pair is drift; "
                "restore the pair or remove the User explicitly; refusing "
                "with no rows changed"
            )
        expected_specialty = SYNTHETIC_PAIR_SPECIALTIES[row.username]
        if row.specialty != expected_specialty:
            _abort(
                f"pair {row.username!r}: Doctor id={row.doctor_id} carries "
                f"specialty {row.specialty!r}, expected "
                f"{expected_specialty!r} (the 0055 seed shape) — drift; "
                "refusing with no rows changed"
            )
        if row.role != SYNTHETIC_PAIR_ROLE:
            _abort(
                f"pair {row.username!r}: User id={row.user_id} carries role "
                f"{row.role!r}, expected the internal {SYNTHETIC_PAIR_ROLE!r} "
                "sentinel spelling (the 0056/0057 shape) — a re-purposed "
                "account is NOT the 0055 pair; refusing with no rows changed"
            )
        if bool(row.is_superuser):
            _abort(
                f"pair {row.username!r}: User id={row.user_id} is a "
                "superuser — refusing with no rows changed"
            )
        print(
            f"{_MIGRATION_NAME}: pair {row.username!r} resolved — "
            f"user_id={row.user_id} role={row.role!r} "
            f"is_active={bool(row.is_active)} | doctor_id={row.doctor_id} "
            f"specialty={row.specialty!r} active={bool(row.doctor_active)}"
        )

    # P2-2 (the symmetric proof, ACTIVE halves only — see the guard):
    # the bridge vocabulary must leave WITH the pairs — an orphaned
    # ACTIVE half next to three valid pairs is drift too, invisible
    # to every reference guard (nothing links to it).
    _assert_no_orphaned_bridge_doctors(conn)
    return rows


def _assert_no_service_references(conn, doctor_ids: list[int]) -> None:
    rows = conn.execute(
        _SELECT_SERVICE_REFERENCES, {"doctor_ids": doctor_ids}
    ).fetchall()
    if not rows:
        return
    for row in rows:
        print(
            f"{_MIGRATION_NAME}: service reference — id={row.id} "
            f"code={row.code!r} active={bool(row.active)} "
            f"queue_tag={row.queue_tag!r} doctor_id={row.doctor_id}"
        )
    _abort(
        f"{len(rows)} services row(s) still reference a synthetic doctor "
        f"(codes: {sorted({row.code for row in rows})}) — "
        "the catalog is never silently doctor-stripped; re-run the catalog "
        "decision for these codes (assign a doctor / retag to an active "
        "resource / disable), then re-run the retirement; refusing with no "
        "rows changed"
    )


def _assert_no_queue_references(conn, doctor_ids: list[int]) -> None:
    rows = conn.execute(_SELECT_QUEUE_REFERENCES, {"doctor_ids": doctor_ids}).fetchall()
    if not rows:
        return
    for row in rows:
        print(
            f"{_MIGRATION_NAME}: daily_queues reference — id={row.id} "
            f"day={row.day} queue_tag={row.queue_tag!r} "
            f"specialist_id={row.specialist_id} active={bool(row.active)}"
        )
    _abort(
        f"{len(rows)} daily_queues row(s) still reference a synthetic "
        "doctor — 0063 consumed every canonical bridge, so any survivor is "
        "drift the operator must resolve explicitly (re-point the queue or "
        "deactivate it); refusing with no rows changed"
    )


def _quote_ident(name: str) -> str:
    """A pg_catalog identifier is catalog data, not trusted SQL text:
    quoted and quote-doubled into a safe identifier."""
    return '"' + name.replace('"', '""') + '"'


def _inventory_fk_surfaces(conn, user_ids: list[int], doctor_ids: list[int]) -> None:
    """The PostgreSQL catch-all: every FK surface referencing the pairs
    is counted before the deletion (dialect-gated — the P1-2 precedent;
    SQLite scratch harnesses skip it, the semantic guards still run).

    Sources in ANY schema are inventoried (the 2026-09-18 review P1:
    a foreign-schema child landing on the pairs is a live FK surface —
    silently skipping it would turn the pair DELETE into a cross-schema
    cascade). Foreign surfaces are addressed schema-qualified, and the
    self-reference / login_attempts exemptions are LOCAL to the current
    schema: name collisions across schemas never inherit them. A
    surface the migration role cannot SELECT is a loud abort, never an
    empty count."""
    if conn.dialect.name != "postgresql":
        print(
            f"{_MIGRATION_NAME}: FK introspection skipped on dialect "
            f"{conn.dialect.name!r} (PostgreSQL-only surface; the semantic "
            "service/queue guards above still ran)"
        )
        return

    (current_schema,) = conn.execute(sa.text("SELECT current_schema()")).fetchone()

    composite = conn.execute(_SELECT_COMPOSITE_FK_CONSTRAINTS).fetchall()
    if composite:
        for row in composite:
            label = row.constraint_name
            if row.src_schema != current_schema:
                label = f"{row.src_schema}.{label}"
            print(
                f"{_MIGRATION_NAME}: composite FK constraint "
                f"{label!r} spans {row.column_count} columns "
                "referencing users/doctors"
            )
        _abort(
            "a composite (multi-column) FK references users/doctors — "
            "unsupported surface, the retirement never guesses; the "
            "operator handles it explicitly; refusing with no rows changed"
        )

    surfaces = conn.execute(_SELECT_FK_SURFACES).fetchall()
    for surface in surfaces:
        src_schema, table = surface.src_schema, surface.table_name
        column = surface.column_name
        ref_table, delete_rule = surface.ref_table, surface.delete_rule
        local = src_schema == current_schema
        # Audit-display name: bare inside the current schema (log
        # parity with the pre-fix inventory), schema-qualified outside.
        display = table if local else f"{src_schema}.{table}"

        # The self-reference exclusion is a statement about THE pairs'
        # own tables: a foreign-schema "doctors" must not inherit it by
        # name collision (review P1).
        if local and (table, column, ref_table) in _SELF_REFERENCE_SURFACES:
            print(
                f"{_MIGRATION_NAME}: FK surface {display}.{column} -> "
                f"{ref_table} (ON DELETE {delete_rule}) — the pair's own "
                "self-reference, excluded"
            )
            continue

        ids = user_ids if ref_table == "users" else doctor_ids
        if not ids:
            continue

        qualified = f"{_quote_ident(src_schema)}.{_quote_ident(table)}"
        (readable,) = conn.execute(
            sa.text(
                "SELECT has_table_privilege(CAST(:qualified AS regclass), 'SELECT')"
            ),
            {"qualified": qualified},
        ).fetchone()
        if not readable:
            print(
                f"{_MIGRATION_NAME}: FK surface {display}.{column} -> "
                f"{ref_table} (ON DELETE {delete_rule}) — NOT SELECT-"
                "readable by the migration role"
            )
            _abort(
                f"FK surface {display}.{column} (ON DELETE {delete_rule}) "
                "is not SELECT-privileged for the migration role — the "
                "inventory cannot count it, and an uncountable FK "
                "surface is never assumed empty; refusing with no rows "
                "changed"
            )

        (count,) = conn.execute(
            sa.text(
                f"SELECT COUNT(*) FROM {qualified} WHERE "
                f"{_quote_ident(column)} IN :ids"
            ).bindparams(sa.bindparam("ids", expanding=True)),
            {"ids": ids},
        ).fetchone()
        count = int(count)

        if count == 0:
            print(
                f"{_MIGRATION_NAME}: FK surface {display}.{column} -> "
                f"{ref_table} (ON DELETE {delete_rule}) — 0 rows, pass"
            )
            continue

        # The SET NULL anonymization exemption is a statement about THE
        # migration's own login_attempts: a foreign-schema
        # "login_attempts" must not inherit it by name collision
        # (review P1).
        if (
            local
            and (table, column) in _SET_NULL_ROW_ALLOWLIST
            and delete_rule == "SET NULL"
        ):
            print(
                f"{_MIGRATION_NAME}: FK surface {display}.{column} -> "
                f"{ref_table} (ON DELETE SET NULL) — {count} row(s) "
                "survive the deletion ANONYMIZED (the designed security "
                "semantic: failed-login probes are preserved)"
            )
            continue

        print(
            f"{_MIGRATION_NAME}: FK surface {display}.{column} -> "
            f"{ref_table} (ON DELETE {delete_rule}) — {count} row(s) "
            "reference the synthetic pairs"
        )
        _abort(
            f"FK surface {display}.{column} (ON DELETE {delete_rule}) holds "
            f"{count} row(s) referencing the synthetic pairs — only "
            f"login_attempts may carry rows (SET NULL anonymization); "
            "every other surface is an explicit operator decision; "
            "refusing with no rows changed"
        )


def _delete_pairs(conn, rows: list) -> dict[str, int]:
    doctor_ids = [int(row.doctor_id) for row in rows]
    user_ids = [int(row.user_id) for row in rows]

    result_doctors = conn.execute(_DELETE_DOCTORS, {"doctor_ids": doctor_ids})
    if result_doctors.rowcount != len(doctor_ids):
        _abort(
            f"doctor deletion rowcount {result_doctors.rowcount} != "
            f"{len(doctor_ids)} — concurrent modification; refusing with "
            "no rows changed"
        )
    result_users = conn.execute(_DELETE_USERS, {"user_ids": user_ids})
    if result_users.rowcount != len(user_ids):
        _abort(
            f"user deletion rowcount {result_users.rowcount} != "
            f"{len(user_ids)} — concurrent modification; refusing with "
            "no rows changed"
        )

    # Postcondition: the usernames are gone and nothing stays linked.
    leftover = conn.execute(
        _SELECT_PAIRS, {"usernames": list(SYNTHETIC_PAIR_USERNAMES)}
    ).fetchall()
    if leftover:
        _abort(
            f"postcondition failed — rows remain for usernames "
            f"{[row.username for row in leftover]}; refusing with no rows "
            "changed"
        )

    print(
        f"{_MIGRATION_NAME}: retired {len(user_ids)} synthetic pair(s) — "
        f"users {sorted(user_ids)}, doctors {sorted(doctor_ids)} "
        "(the per-pair inventory above is the audit trail; a "
        "pre-deletion backup is the restore path)"
    )
    return {"users_deleted": len(user_ids), "doctors_deleted": len(doctor_ids)}


def upgrade_with_conn(conn) -> dict[str, int]:
    """The testable retirement entry (the 0063/0066 module pattern).

    Review round 3 (P2-B): the SHARE ROW EXCLUSIVE table lock is the
    FIRST statement of the transaction — before the row locks, the
    resolution, the guards, and the deletion — so the whole
    read-to-commit window is closed at the table level, including the
    no-op pass where there are no rows to lock at all."""
    _lock_pair_tables(conn)
    rows = _resolve_and_assert_pairs(conn)
    if not rows:
        return {"users_deleted": 0, "doctors_deleted": 0}

    doctor_ids = [int(row.doctor_id) for row in rows]
    user_ids = [int(row.user_id) for row in rows]

    _assert_no_service_references(conn, doctor_ids)
    _assert_no_queue_references(conn, doctor_ids)
    _inventory_fk_surfaces(conn, user_ids, doctor_ids)

    return _delete_pairs(conn, rows)


def upgrade() -> None:
    upgrade_with_conn(op.get_bind())


def _assert_downgrade_pair_shape(row) -> None:
    """P2-3: an existing username is an idempotent no-op ONLY in the
    exact 0055+0057 shape — every field is verified before the
    downgrade may skip the pair, and any drift is a foreign capture
    the operator must resolve explicitly (the downgrade restores
    PAIRS, it does not heal or skip drift)."""
    username = row.username
    if row.hashed_password != SYNTHETIC_PAIR_DISABLED_HASH:
        _abort(
            f"downgrade: pair {username!r}: User id={row.user_id} carries "
            f"hashed_password {row.hashed_password!r}, expected the "
            f"unusable {SYNTHETIC_PAIR_DISABLED_HASH!r} marker — "
            f"{_FOREIGN_CAPTURE_TAIL}"
        )
    if row.role != SYNTHETIC_PAIR_ROLE:
        _abort(
            f"downgrade: pair {username!r}: User id={row.user_id} carries "
            f"role {row.role!r}, expected the internal "
            f"{SYNTHETIC_PAIR_ROLE!r} sentinel spelling — "
            f"{_FOREIGN_CAPTURE_TAIL}"
        )
    if not bool(row.is_active):
        _abort(
            f"downgrade: pair {username!r}: User id={row.user_id} is "
            "inactive (is_active=false), expected the active 0055 shape "
            f"— {_FOREIGN_CAPTURE_TAIL}"
        )
    if bool(row.is_superuser):
        _abort(
            f"downgrade: pair {username!r}: User id={row.user_id} is a "
            f"superuser — {_FOREIGN_CAPTURE_TAIL}"
        )
    if bool(row.must_change_password):
        _abort(
            f"downgrade: pair {username!r}: User id={row.user_id} has "
            "must_change_password=true, expected false (the 0055 shape) "
            f"— {_FOREIGN_CAPTURE_TAIL}"
        )
    if row.doctor_id is None:
        _abort(
            f"downgrade: pair {username!r}: the User row (id={row.user_id}) "
            "has NO linked Doctor row — exactly one linked Doctor is part "
            f"of the 0055+0057 shape — {_FOREIGN_CAPTURE_TAIL}"
        )
        return  # unreachable: keeps the flow below readable
    expected_specialty = SYNTHETIC_PAIR_SPECIALTIES[username]
    if row.specialty != expected_specialty:
        _abort(
            f"downgrade: pair {username!r}: Doctor id={row.doctor_id} "
            f"carries specialty {row.specialty!r}, expected "
            f"{expected_specialty!r} (the 0055 seed shape) — "
            f"{_FOREIGN_CAPTURE_TAIL}"
        )
    if not bool(row.doctor_active):
        _abort(
            f"downgrade: pair {username!r}: Doctor id={row.doctor_id} is "
            f"inactive — {_FOREIGN_CAPTURE_TAIL}"
        )
    if int(row.start_number_online) != 1 or int(row.max_online_per_day) != 15:
        _abort(
            f"downgrade: pair {username!r}: Doctor id={row.doctor_id} "
            f"carries caps ({int(row.start_number_online)}, "
            f"{int(row.max_online_per_day)}), expected (1, 15) — "
            f"{_FOREIGN_CAPTURE_TAIL}"
        )


def downgrade_with_conn(conn) -> None:
    """A TRUE inverse of the all-or-nothing upgrade: re-provision the
    three pairs in the exact 0055+0057 shape, username-identified,
    idempotent (ON CONFLICT DO NOTHING). No ids are invented, no
    sequences are touched — at upgrade time zero FK references existed
    to the old numeric ids (the guards proved it), so fresh serial ids
    are correct; the anonymized login_attempts rows stay anonymized
    (a downgrade restores PAIRS, not per-row audit links).

    P2-3: an existing username is an idempotent no-op ONLY after the
    full shape is verified field-by-field, and a final postcondition
    re-verifies all three pairs before the restore is claimed.

    Review round 3 (P2-B): the downgrade opens with the same SHARE
    ROW EXCLUSIVE table lock — the postcondition window (a pair
    deleted or a foreign capture inserted between the final read and
    the commit) is the same class of phantom the upgrade closes."""
    _lock_pair_tables(conn)
    for username, specialty in SYNTHETIC_PAIR_SPECIALTIES.items():
        row = conn.execute(_SELECT_PAIRS, {"usernames": [username]}).fetchone()
        if row is not None:
            _assert_downgrade_pair_shape(row)
            print(
                f"{_MIGRATION_NAME} downgrade: pair {username!r} already "
                "present in the exact 0055+0057 shape (user "
                f"id={row.user_id}) — idempotent no-op"
            )
            continue
        conn.execute(
            _REPROVISION_USERS,
            {
                "username": username,
                "hash": SYNTHETIC_PAIR_DISABLED_HASH,
                "role": SYNTHETIC_PAIR_ROLE,
            },
        )
        conn.execute(
            _REPROVISION_DOCTORS,
            {"username": username, "specialty": specialty},
        )
        print(
            f"{_MIGRATION_NAME} downgrade: re-provisioned pair "
            f"{username!r} (role {SYNTHETIC_PAIR_ROLE!r}, specialty "
            f"{specialty!r}, unusable hash, active, caps 1/15)"
        )

    # P2-3 postcondition: all three pairs, the exact shape, no more and
    # no less — the loop above proved each pair, this proves the SET.
    rows = conn.execute(
        _SELECT_PAIRS, {"usernames": list(SYNTHETIC_PAIR_USERNAMES)}
    ).fetchall()
    if len(rows) != len(SYNTHETIC_PAIR_USERNAMES):
        _abort(
            "downgrade postcondition failed — "
            f"{len(rows)} pair(s) resolved for usernames "
            f"{[row.username for row in rows]}, expected exactly "
            f"{len(SYNTHETIC_PAIR_USERNAMES)}; refusing with no rows "
            "changed"
        )
    for row in rows:
        _assert_downgrade_pair_shape(row)
    print(
        f"{_MIGRATION_NAME} downgrade: the three synthetic pairs are "
        "restored to the 0055+0057 shape (postcondition verified)"
    )


def downgrade() -> None:
    downgrade_with_conn(op.get_bind())
