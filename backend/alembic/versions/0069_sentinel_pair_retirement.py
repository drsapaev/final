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

1. ALL-OR-NOTHING pair resolution, inventory-before-mutation, on rows
   locked FOR UPDATE first (PostgreSQL; the P1-b hardening of the
   owner closure plan, applied in the post-merge window BEFORE the
   production application — after that the migration body is frozen):

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
   - the rowcount verification and the postcondition re-check stay in
     place as the backstop (defense in depth), not the primary lock;
   - non-PostgreSQL dialects (the SQLite scratch harness) skip the
     locking with a printed note — single-connection harnesses cannot
     race (the P1-2 dialect-gate precedent);

   - all three pairs present and shape-valid (linked doctor, the
     expected 0055 specialty, the post-0057 'Resource' role, not a
     superuser) -> the guarded paired deletion below;
   - ALL three absent -> already retired: a printed clean no-op (the
     CI empty database passes the chain with zero rows here);
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
   from ``information_schema`` and counted against the resolved pair
   ids BEFORE the deletion:

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
           d.id AS doctor_id,
           d.specialty AS specialty,
           d.active AS doctor_active
    FROM users u
    LEFT JOIN doctors d ON d.user_id = u.id
    WHERE u.username IN :usernames
    ORDER BY u.username
    """).bindparams(sa.bindparam("usernames", expanding=True))

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
# the CURRENT schema, with its ON DELETE rule.
_SELECT_FK_SURFACES = sa.text("""
    SELECT DISTINCT
           tc.table_name AS table_name,
           kcu.column_name AS column_name,
           ccu.table_name AS ref_table,
           rc.delete_rule AS delete_rule
    FROM information_schema.table_constraints tc
    JOIN information_schema.key_column_usage kcu
      ON tc.constraint_name = kcu.constraint_name
     AND tc.constraint_schema = kcu.constraint_schema
    JOIN information_schema.referential_constraints rc
      ON tc.constraint_name = rc.constraint_name
     AND tc.constraint_schema = rc.constraint_schema
    JOIN information_schema.constraint_column_usage ccu
      ON rc.unique_constraint_name = ccu.constraint_name
     AND rc.unique_constraint_schema = ccu.constraint_schema
    WHERE tc.constraint_type = 'FOREIGN KEY'
      AND tc.table_schema = current_schema()
      AND ccu.table_name IN ('users', 'doctors')
    ORDER BY tc.table_name, kcu.column_name
    """)

# Composite FK guard: any constraint referencing the pairs that spans
# more than one column is unsupported surface — never guessed.
_SELECT_COMPOSITE_FK_CONSTRAINTS = sa.text("""
    SELECT tc.constraint_name, COUNT(kcu.column_name) AS column_count
    FROM information_schema.table_constraints tc
    JOIN information_schema.key_column_usage kcu
      ON tc.constraint_name = kcu.constraint_name
     AND tc.constraint_schema = kcu.constraint_schema
    JOIN information_schema.referential_constraints rc
      ON tc.constraint_name = rc.constraint_name
     AND tc.constraint_schema = rc.constraint_schema
    JOIN information_schema.constraint_column_usage ccu
      ON rc.unique_constraint_name = ccu.constraint_name
     AND rc.unique_constraint_schema = ccu.constraint_schema
    WHERE tc.constraint_type = 'FOREIGN KEY'
      AND tc.table_schema = current_schema()
      AND ccu.table_name IN ('users', 'doctors')
    GROUP BY tc.constraint_name
    HAVING COUNT(kcu.column_name) > 1
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


def _lock_pair_rows(conn) -> None:
    """P1-b: serialize every concurrent writer away from the pairs
    BEFORE the resolution reads them (PostgreSQL; the SQLite scratch
    harnesses print a note and skip — single-connection harnesses
    cannot race, the P1-2 dialect-gate precedent)."""
    if conn.dialect.name != "postgresql":
        print(
            f"{_MIGRATION_NAME}: pair-row locking skipped on dialect "
            f"{conn.dialect.name!r} (PostgreSQL-only surface; the "
            "single-connection scratch harness cannot race — the "
            "semantic shape guards still run)"
        )
        return
    usernames = list(SYNTHETIC_PAIR_USERNAMES)
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


def _resolve_and_assert_pairs(conn) -> list:
    """Resolve the three pairs; enforce the all-or-nothing shape."""
    _lock_pair_rows(conn)
    rows = conn.execute(
        _SELECT_PAIRS, {"usernames": list(SYNTHETIC_PAIR_USERNAMES)}
    ).fetchall()

    present = {row.username for row in rows}
    expected = set(SYNTHETIC_PAIR_USERNAMES)
    missing = expected - present

    if not present:
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


def _inventory_fk_surfaces(conn, user_ids: list[int], doctor_ids: list[int]) -> None:
    """The PostgreSQL catch-all: every FK surface referencing the pairs
    is counted before the deletion (dialect-gated — the P1-2 precedent;
    SQLite scratch harnesses skip it, the semantic guards still run)."""
    if conn.dialect.name != "postgresql":
        print(
            f"{_MIGRATION_NAME}: FK introspection skipped on dialect "
            f"{conn.dialect.name!r} (PostgreSQL-only surface; the semantic "
            "service/queue guards above still ran)"
        )
        return

    composite = conn.execute(_SELECT_COMPOSITE_FK_CONSTRAINTS).fetchall()
    if composite:
        for row in composite:
            print(
                f"{_MIGRATION_NAME}: composite FK constraint "
                f"{row.constraint_name!r} spans {row.column_count} columns "
                "referencing users/doctors"
            )
        _abort(
            "a composite (multi-column) FK references users/doctors — "
            "unsupported surface, the retirement never guesses; the "
            "operator handles it explicitly; refusing with no rows changed"
        )

    surfaces = conn.execute(_SELECT_FK_SURFACES).fetchall()
    for surface in surfaces:
        table, column = surface.table_name, surface.column_name
        ref_table, delete_rule = surface.ref_table, surface.delete_rule

        if (table, column, ref_table) in _SELF_REFERENCE_SURFACES:
            print(
                f"{_MIGRATION_NAME}: FK surface {table}.{column} -> "
                f"{ref_table} (ON DELETE {delete_rule}) — the pair's own "
                "self-reference, excluded"
            )
            continue

        ids = user_ids if ref_table == "users" else doctor_ids
        if not ids:
            continue
        (count,) = conn.execute(
            sa.text(
                f'SELECT COUNT(*) FROM "{table}" WHERE "{column}" IN :ids'
            ).bindparams(sa.bindparam("ids", expanding=True)),
            {"ids": ids},
        ).fetchone()
        count = int(count)

        if count == 0:
            print(
                f"{_MIGRATION_NAME}: FK surface {table}.{column} -> "
                f"{ref_table} (ON DELETE {delete_rule}) — 0 rows, pass"
            )
            continue

        if (table, column) in _SET_NULL_ROW_ALLOWLIST and delete_rule == "SET NULL":
            print(
                f"{_MIGRATION_NAME}: FK surface {table}.{column} -> "
                f"{ref_table} (ON DELETE SET NULL) — {count} row(s) "
                "survive the deletion ANONYMIZED (the designed security "
                "semantic: failed-login probes are preserved)"
            )
            continue

        print(
            f"{_MIGRATION_NAME}: FK surface {table}.{column} -> "
            f"{ref_table} (ON DELETE {delete_rule}) — {count} row(s) "
            "reference the synthetic pairs"
        )
        _abort(
            f"FK surface {table}.{column} (ON DELETE {delete_rule}) holds "
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
    """The testable retirement entry (the 0063/0066 module pattern)."""
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


def downgrade_with_conn(conn) -> None:
    """A TRUE inverse of the all-or-nothing upgrade: re-provision the
    three pairs in the exact 0055+0057 shape, username-identified,
    idempotent (ON CONFLICT DO NOTHING). No ids are invented, no
    sequences are touched — at upgrade time zero FK references existed
    to the old numeric ids (the guards proved it), so fresh serial ids
    are correct; the anonymized login_attempts rows stay anonymized
    (a downgrade restores PAIRS, not per-row audit links)."""
    for username, specialty in SYNTHETIC_PAIR_SPECIALTIES.items():
        existing = conn.execute(
            sa.text("SELECT id FROM users WHERE username = :u"), {"u": username}
        ).fetchone()
        if existing is not None:
            print(
                f"{_MIGRATION_NAME} downgrade: pair {username!r} already "
                f"present (user id={existing.id}) — idempotent no-op"
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
    print(
        f"{_MIGRATION_NAME} downgrade: the three synthetic pairs are "
        "restored to the 0055+0057 shape"
    )


def downgrade() -> None:
    downgrade_with_conn(op.get_bind())
