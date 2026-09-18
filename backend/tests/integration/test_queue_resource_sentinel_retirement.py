"""RQ-15.d (ADR-001 stage E): the 0055 synthetic pair retirement pins.

Migration ``0069_sentinel_pair_retirement`` completes the QD-2 staged
rollout (ADR-001 "Stage E"): the terminal state has doctorless queues
owned by ``queue_resources`` rows — a reference registry with no User,
no role, no login. The three synthetic User+Doctor pairs provisioned
by 0055 (``ecg_resource``/``lab_resource``/``general_resource``) are
retired by a PAIRED DELETION, exactly as the ADR stage table states:
"Retire the synthetic User+Doctor pairs (paired deletion), remove the
bridge vocabulary."

The pre-state the migration requires (verified on production by the
2026-09-12 inventory, ``evidence/stage_e_inventory_20260912_rerun.json``):

- ``daily_queues`` carries ZERO references to the synthetic doctors —
  0063 consumed every canonical bridge (``specialist_id`` -> NULL) and
  the inventory confirms ``general_queues.total = 0``;
- no ACTIVE service points at a synthetic doctor — the 0066 operator
  map moved every active service onto the resource axis or a real
  doctor (33 retag / 7 assign / 16 procedures);
- the ONLY inbound reference the inventory found across 103 FK
  surfaces was ``login_attempts.user_id`` (a failed-login probe row
  for ``ecg_resource``) — and that FK is declared ``ON DELETE SET
  NULL`` on purpose ("SECURITY: SET NULL to preserve failed attempts
  even if user deleted"), so the pair deletion anonymizes the probe
  row instead of losing it.

The migration contract pinned here:

- ALL-OR-NOTHING pair resolution: all three pairs present and
  shape-valid (linked doctor, expected specialty, the post-0057
  'Resource' role, not superuser) -> guarded deletion; ALL three
  absent -> already-retired clean no-op (the CI empty database); a
  PARTIAL set or any shape drift -> loud abort with nothing changed
  (the 0063/0066 taxonomy: the repair is an operator decision);
- P2-1 phantom-pair pin: the resolution may only see the rows the
  ``FOR UPDATE`` selects locked — a pair that APPEARS after the
  locks (a concurrent restore of the missing half committing between
  the lock selects and the resolution read) was never locked, and the
  upgrade aborts instead of deleting an unlocked row (re-run the
  migration once the concurrent writer is done);
- P2-2 provable terminal state (review round 3 narrowed to the ACTIVE
  half): ``all three usernames absent`` is the already-retired verdict
  ONLY while no ACTIVE Doctor row carries the bridge vocabulary
  without a User link — the sanctioned user-deletion path DEACTIVATES
  the profile before deleting the owner, so an INACTIVE userless
  bridge-specialty row is preserved clinical history ('general'
  doubles as the live INCOMPLETE_DOCTOR_SPECIALTY onboarding
  sentinel) and must NOT block the verdict, while a raw hand-deleted
  User (the ``doctors.user_id`` FK is ON DELETE SET NULL, nothing
  deactivates the row) leaves the half ACTIVE — drift either way
  (decision #13: an ACTIVE userless row already violates the linkage
  contract); the same proof runs when the pairs are present: the
  bridge vocabulary must leave WITH the pairs, never stranded;
- P2-B table-lock pins (review round 3): the migration transaction
  OPENS with ``LOCK TABLE users, doctors IN SHARE ROW EXCLUSIVE
  MODE`` — row locks only fix the rows they SEE, so on the
  already-retired no-op pass (no rows to lock at all) and between the
  final guard read and the commit, a concurrent INSERT (a restored
  pair, an orphaned bridge Doctor) could previously land and silently
  invalidate the verdict Alembic is about to stamp; now every
  concurrent INSERT/UPDATE/DELETE on the two tables blocks until the
  migration commits (upgrade AND downgrade alike);
- semantic reference guards: ANY ``services.doctor_id`` or
  ``daily_queues.specialist_id`` row referencing a synthetic doctor
  (active OR historical) aborts the deletion — the catalog and the
  queue history are never silently doctor-stripped;
- PostgreSQL FK introspection: every FK surface referencing
  ``users.id``/``doctors.id`` is counted before the deletion; a
  NO ACTION/RESTRICT surface with rows aborts (the FK would fire), a
  CASCADE surface with rows aborts (never silently cascade-delete
  history), ``login_attempts`` is the only SET NULL surface allowed
  to carry rows (the designed security semantic), any OTHER SET NULL
  surface with rows aborts loudly (future-proof). The pair's own
  ``doctors.user_id`` self-reference is excluded;
- the downgrade is a TRUE inverse of the all-or-nothing upgrade: it
  re-provisions the three pairs in the exact 0055+0057 shape
  (username, '!disabled:queue-resource' hash, 'Resource' role,
  specialty, caps 1/15) with ``ON CONFLICT DO NOTHING`` — no id
  invention, no sequence games; P2-3 exact-shape pin: an EXISTING
  username is an idempotent no-op only after the full shape is
  verified field-by-field (hash, role, is_active, is_superuser,
  must_change_password, exactly one linked Doctor, specialty,
  active, caps 1/15) — a username captured by a foreign row aborts
  the downgrade instead of being silently skipped, and a final
  postcondition re-verifies all three pairs before the migration
  claims the restore;
- the full alembic chain retires the pairs on a fresh database: after
  ``alembic upgrade head`` the three usernames are gone.
"""

from __future__ import annotations

import importlib.util
import os
import re
import subprocess
import sys
import uuid
from pathlib import Path

import pytest
import sqlalchemy as sa
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url

REPO_ROOT = Path(__file__).resolve().parents[3]
BACKEND_ROOT = REPO_ROOT / "backend"
MIGRATION_0069 = (
    BACKEND_ROOT / "alembic" / "versions" / "0069_sentinel_pair_retirement.py"
)
MIGRATION_0055 = (
    BACKEND_ROOT / "alembic" / "versions" / "0055_queue_resource_provisioning.py"
)

_PAIR_USERNAMES = ("ecg_resource", "lab_resource", "general_resource")
_PAIR_SPECIALTIES = {
    "ecg_resource": "ecg",
    "lab_resource": "lab",
    "general_resource": "general",
}
_DISABLED_HASH = "!disabled:queue-resource"


def _module():
    """Lazily import the migration module (RED-first: every test fails
    individually while the module does not exist)."""
    assert MIGRATION_0069.exists(), (
        "0069_sentinel_pair_retirement.py is missing from the alembic "
        "chain — the RQ-15.d retirement is not implemented"
    )
    spec = importlib.util.spec_from_file_location(
        "migration_0069_sentinel_pair_retirement", MIGRATION_0069
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# ===================== the minimal retirement world =====================


def _retirement_metadata() -> sa.MetaData:
    """The minimal tables the retirement touches (SQLite scratch and the
    isolated PostgreSQL schema of the FK-introspection proofs).

    FK ondelete semantics mirror the real schema exactly:
    ``services.doctor_id`` SET NULL, ``daily_queues.specialist_id`` NO
    ACTION, ``login_attempts.user_id`` SET NULL, ``doctors.user_id``
    SET NULL + UNIQUE (the post-0048 shape).
    """
    metadata = sa.MetaData()
    sa.Table(
        "users",
        metadata,
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("username", sa.String(64), nullable=False, unique=True),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("role", sa.String(32), nullable=False),
        sa.Column("is_active", sa.Boolean, nullable=False, default=True),
        sa.Column("is_superuser", sa.Boolean, nullable=False, default=False),
        sa.Column("must_change_password", sa.Boolean, nullable=False, default=False),
    )
    sa.Table(
        "doctors",
        metadata,
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "user_id",
            sa.Integer,
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
            unique=True,
        ),
        sa.Column("specialty", sa.String(64), nullable=False),
        sa.Column("active", sa.Boolean, nullable=False, default=True),
        sa.Column("start_number_online", sa.Integer, nullable=False, default=1),
        sa.Column("max_online_per_day", sa.Integer, nullable=False, default=15),
    )
    sa.Table(
        "services",
        metadata,
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("code", sa.String(32), nullable=True),
        sa.Column("queue_tag", sa.String(32), nullable=True),
        sa.Column("active", sa.Boolean, nullable=False, default=True),
        sa.Column(
            "doctor_id",
            sa.Integer,
            sa.ForeignKey("doctors.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("requires_doctor", sa.Boolean, nullable=False, default=False),
    )
    sa.Table(
        "daily_queues",
        metadata,
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("day", sa.Date, nullable=False),
        sa.Column("queue_tag", sa.String(32), nullable=True),
        sa.Column(
            "specialist_id",
            sa.Integer,
            sa.ForeignKey("doctors.id"),
            nullable=True,
        ),
        sa.Column("queue_resource_id", sa.Integer, nullable=True),
        sa.Column("active", sa.Boolean, nullable=False, default=True),
    )
    sa.Table(
        "login_attempts",
        metadata,
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "user_id",
            sa.Integer,
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("ip_address", sa.String(45), nullable=False),
        sa.Column("success", sa.Boolean, nullable=False, default=False),
    )
    return metadata


def _create_retirement_tables(engine) -> None:
    _retirement_metadata().create_all(engine)


def _scratch():
    engine = sa.create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=sa.pool.StaticPool,
    )
    _create_retirement_tables(engine)
    conn = engine.connect()
    # SET NULL must actually fire on the scratch dialect too — the
    # login_attempts survival pin depends on it.
    conn.execute(sa.text("PRAGMA foreign_keys=ON"))
    conn.commit()
    return conn


def _seed_pair(conn, username: str, *, role: str = "Resource") -> tuple[int, int]:
    """Seed one synthetic pair; returns (user_id, doctor_id)."""
    specialty = _PAIR_SPECIALTIES[username]
    conn.execute(
        sa.text(
            "INSERT INTO users (username, hashed_password, role, is_active,"
            " is_superuser, must_change_password)"
            " VALUES (:u, :p, :r, :a, :su, :m)"
        ),
        {
            "u": username,
            "p": _DISABLED_HASH,
            "r": role,
            "a": True,
            "su": False,
            "m": False,
        },
    )
    (user_id,) = conn.execute(
        sa.text("SELECT id FROM users WHERE username = :u"), {"u": username}
    ).fetchone()
    conn.execute(
        sa.text(
            "INSERT INTO doctors (user_id, specialty, active,"
            " start_number_online, max_online_per_day)"
            " VALUES (:uid, :s, :a, :sn, :mn)"
        ),
        {"uid": user_id, "s": specialty, "a": True, "sn": 1, "mn": 15},
    )
    (doctor_id,) = conn.execute(
        sa.text("SELECT id FROM doctors WHERE user_id = :uid"), {"uid": user_id}
    ).fetchone()
    return int(user_id), int(doctor_id)


def _seed_all_pairs(conn) -> dict[str, tuple[int, int]]:
    return {username: _seed_pair(conn, username) for username in _PAIR_USERNAMES}


def _seed_login_attempt(conn, user_id: int) -> int:
    conn.execute(
        sa.text(
            "INSERT INTO login_attempts (user_id, ip_address, success)"
            " VALUES (:uid, :ip, :s)"
        ),
        {"uid": user_id, "ip": "127.0.0.1", "s": False},
    )
    (attempt_id,) = conn.execute(
        sa.text("SELECT id FROM login_attempts ORDER BY id DESC LIMIT 1")
    ).fetchone()
    return int(attempt_id)


def _seed_historical_userless_doctor(conn, specialty: str, *, active: bool) -> int:
    """A userless Doctor row the way the SANCTIONED lifecycle leaves
    clinical history: a Registrar->Doctor promotion provisions the
    profile with the onboarding sentinel specialty, and the sanctioned
    owner deletion DEACTIVATES and DETACHES it (never deletes) —
    ``Doctor(active=False, user_id=NULL)``. The ``active`` flag is the
    discriminator between this documented history and the ACTIVE half a
    raw hand-deleted User leaves behind (review round 3, P2-A)."""
    conn.execute(
        sa.text(
            "INSERT INTO doctors (user_id, specialty, active,"
            " start_number_online, max_online_per_day)"
            " VALUES (NULL, :s, :a, 1, 15)"
        ),
        {"s": specialty, "a": active},
    )
    (doctor_id,) = conn.execute(
        sa.text("SELECT id FROM doctors ORDER BY id DESC LIMIT 1")
    ).fetchone()
    return int(doctor_id)


def _usernames_present(conn) -> set[str]:
    rows = conn.execute(
        sa.text("SELECT username FROM users WHERE username IN " "(:a, :b, :c)"),
        {"a": _PAIR_USERNAMES[0], "b": _PAIR_USERNAMES[1], "c": _PAIR_USERNAMES[2]},
    ).fetchall()
    return {row[0] for row in rows}


def _pair_doctor_count(conn) -> int:
    (count,) = conn.execute(
        sa.text(
            "SELECT COUNT(*) FROM doctors d JOIN users u ON u.id = d.user_id"
            " WHERE u.username IN (:a, :b, :c)"
        ),
        {"a": _PAIR_USERNAMES[0], "b": _PAIR_USERNAMES[1], "c": _PAIR_USERNAMES[2]},
    ).fetchone()
    return int(count)


def _probe_user_id(conn, probe_id: int):
    (user_id,) = conn.execute(
        sa.text("SELECT user_id FROM login_attempts WHERE id = :i"),
        {"i": probe_id},
    ).fetchone()
    return user_id


@pytest.fixture
def committed_scratch():
    """A scratch connection with the three pairs committed — abort-path
    tests verify NOTHING changed (the whole transaction discipline)."""
    conn = _scratch()
    _seed_all_pairs(conn)
    conn.commit()
    try:
        yield conn
    finally:
        conn.close()


# ===================== A. the retirement contract (scratch SQLite) =====================


@pytest.mark.integration
@pytest.mark.migration
def test_upgrade_deletes_all_three_pairs_and_anonymizes_login_attempts() -> None:
    """The happy path: three pairs retired, the failed-login probe
    survives the deletion ANONYMIZED (the designed SET NULL semantic
    — SECURITY: preserve failed attempts even if user deleted)."""
    module = _module()
    conn = _scratch()
    try:
        pairs = _seed_all_pairs(conn)
        probe_id = _seed_login_attempt(conn, pairs["ecg_resource"][0])
        conn.commit()

        result = module.upgrade_with_conn(conn)
        conn.commit()

        assert result == {"users_deleted": 3, "doctors_deleted": 3}
        assert _usernames_present(conn) == set()
        assert _pair_doctor_count(conn) == 0
        # the probe row itself survives, its user link does not
        (probe_count,) = conn.execute(
            sa.text("SELECT COUNT(*) FROM login_attempts WHERE id = :i"),
            {"i": probe_id},
        ).fetchone()
        assert int(probe_count) == 1
        assert _probe_user_id(conn, probe_id) is None
    finally:
        conn.close()


@pytest.mark.integration
@pytest.mark.migration
def test_upgrade_is_idempotent_on_the_retired_state() -> None:
    """A second pass over the retired state is a clean no-op — the
    re-deploy path (the operator may re-run the deploy script)."""
    module = _module()
    conn = _scratch()
    try:
        _seed_all_pairs(conn)
        conn.commit()

        first = module.upgrade_with_conn(conn)
        conn.commit()
        second = module.upgrade_with_conn(conn)
        conn.commit()

        assert first == {"users_deleted": 3, "doctors_deleted": 3}
        assert second == {"users_deleted": 0, "doctors_deleted": 0}
        assert _usernames_present(conn) == set()
        assert _pair_doctor_count(conn) == 0
    finally:
        conn.close()


@pytest.mark.integration
@pytest.mark.migration
def test_upgrade_clean_pass_on_empty_database() -> None:
    """The CI empty database passes the chain with zero rows here —
    all three pairs absent is already-retired, not drift."""
    module = _module()
    conn = _scratch()
    try:
        result = module.upgrade_with_conn(conn)
        conn.commit()
        assert result == {"users_deleted": 0, "doctors_deleted": 0}
        assert _usernames_present(conn) == set()
    finally:
        conn.close()


@pytest.mark.integration
@pytest.mark.migration
def test_sqlite_scratch_skips_pair_row_locking_with_a_note(capsys) -> None:
    """P1-b hardening, the dialect gate: the SQLite scratch harness is
    single-connection and cannot race, so the FOR UPDATE pair-row locking
    is skipped with a printed note (the P1-2 dialect-gate precedent) —
    the semantic shape guards still run."""
    module = _module()
    conn = _scratch()
    try:
        _seed_all_pairs(conn)
        conn.commit()
        module.upgrade_with_conn(conn)
        conn.commit()
        out = capsys.readouterr().out
        assert (
            "pair-row locking skipped" in out
        ), "the SQLite dialect gate must print its skip note"
        assert "FOR UPDATE" not in out.replace(
            "pair-row locking skipped", ""
        ), "no locking SQL may run on the SQLite scratch dialect"
        assert _usernames_present(conn) == set()
    finally:
        conn.close()


@pytest.mark.integration
@pytest.mark.migration
def test_upgrade_aborts_when_a_pair_appears_after_the_locks() -> None:
    """P2-1 (the phantom-pair pin): the resolution is only allowed to
    see the rows the lock selects locked. A pair that APPEARS after
    the locks — a concurrent restore of the missing half committing
    between the lock selects and the resolution read — is NOT locked,
    and the retirement must refuse to delete it, never silently
    proceed with an unlocked row (the promised "one stable world"
    would not exist for it: a concurrent writer could still land
    between the guard and the DELETE).

    The interposition is deterministic: the module's ``_lock_pair_rows``
    is wrapped to seed the missing third pair AFTER the original lock
    selects ran (the single-connection scratch sees its own seed —
    same phantom, same proof; the two-connection PostgreSQL variant
    below commits it from a rival session).
    """
    module = _module()
    conn = _scratch()
    try:
        _seed_pair(conn, "ecg_resource")
        _seed_pair(conn, "lab_resource")
        conn.commit()

        original_lock = module._lock_pair_rows

        def lock_then_phantom_appears(lock_conn):
            result = original_lock(lock_conn)  # locks 2 users + 2 doctors
            _seed_pair(lock_conn, "general_resource")  # the phantom
            return result

        module._lock_pair_rows = lock_then_phantom_appears

        with pytest.raises(RuntimeError, match="NOT the locked pair set"):
            module.upgrade_with_conn(conn)
        conn.rollback()
        # nothing was deleted: the two locked pairs survive the abort.
        # The phantom seed was part of the aborted migration transaction
        # on this single-connection scratch, so it unwinds with the
        # rollback — the two-connection PostgreSQL variant below proves
        # a COMMITTED phantom survives the abort untouched.
        assert _usernames_present(conn) == {"ecg_resource", "lab_resource"}
        assert _pair_doctor_count(conn) == 2
    finally:
        conn.close()


@pytest.mark.integration
@pytest.mark.migration
def test_upgrade_aborts_on_hand_deleted_users_with_orphan_doctor_halves() -> None:
    """P2-2 (the reviewer regression): create the pairs -> delete ONLY
    the Users -> the real ``ON DELETE SET NULL`` fires on the linked
    Doctors -> the upgrade MUST abort, not declare "already retired".

    ``doctors.user_id`` is nullable with ``ON DELETE SET NULL``, so a
    hand-deleted User leaves its Doctor half behind — a clean no-op
    verdict over that state would strand the halves forever while
    alembic stamps the retirement as done.
    """
    module = _module()
    conn = _scratch()
    try:
        _seed_all_pairs(conn)
        conn.commit()

        deleted = conn.execute(
            sa.text("DELETE FROM users WHERE username IN (:a, :b, :c)"),
            {
                "a": _PAIR_USERNAMES[0],
                "b": _PAIR_USERNAMES[1],
                "c": _PAIR_USERNAMES[2],
            },
        )
        conn.commit()
        assert int(deleted.rowcount) == 3

        # the real SET NULL fired: three doctor halves with no User link
        (orphan_halves,) = conn.execute(
            sa.text(
                "SELECT COUNT(*) FROM doctors WHERE user_id IS NULL"
                " AND specialty IN ('ecg', 'lab', 'general')"
            )
        ).fetchone()
        assert int(orphan_halves) == 3

        with pytest.raises(RuntimeError, match="bridge vocabulary"):
            module.upgrade_with_conn(conn)
        conn.rollback()

        # the migration changed nothing: the orphan halves remain
        (still_orphans,) = conn.execute(
            sa.text(
                "SELECT COUNT(*) FROM doctors WHERE user_id IS NULL"
                " AND specialty IN ('ecg', 'lab', 'general')"
            )
        ).fetchone()
        assert int(still_orphans) == 3
        assert _usernames_present(conn) == set()
    finally:
        conn.close()


@pytest.mark.integration
@pytest.mark.migration
def test_upgrade_aborts_on_an_orphan_bridge_doctor_alongside_valid_pairs(
    committed_scratch,
) -> None:
    """P2-2, the symmetric half: the bridge vocabulary must leave WITH
    the pairs. A bridge-specialty Doctor with no User link sitting NEXT
    TO the three valid pairs is also drift — retiring the pairs would
    strand the orphan forever, invisible to every guard (it is not
    linked, so no service/queue/FK surface ever counts it)."""
    module = _module()
    conn = committed_scratch
    conn.execute(
        sa.text(
            "INSERT INTO doctors (user_id, specialty, active,"
            " start_number_online, max_online_per_day)"
            " VALUES (NULL, 'lab', true, 1, 15)"
        )
    )
    conn.commit()

    with pytest.raises(RuntimeError, match="bridge vocabulary"):
        module.upgrade_with_conn(conn)
    conn.rollback()

    assert _usernames_present(conn) == set(_PAIR_USERNAMES)
    assert _pair_doctor_count(conn) == 3
    (total_doctors,) = conn.execute(sa.text("SELECT COUNT(*) FROM doctors")).fetchone()
    assert int(total_doctors) == 4  # three linked + the untouched orphan


@pytest.mark.integration
@pytest.mark.migration
def test_upgrade_retires_pairs_over_inactive_userless_general_doctor_history(
    committed_scratch,
) -> None:
    """Review round 3 (P2-A): 'general' is not only the 0055 bridge
    vocabulary — it is the LIVE onboarding sentinel
    (INCOMPLETE_DOCTOR_SPECIALTY) a Registrar->Doctor promotion
    provisions. The sanctioned user deletion DEACTIVATES and DETACHES
    that profile (preserved clinical history), leaving exactly
    ``Doctor(active=False, user_id=NULL, specialty='general')``. The
    orphaned-bridge-doctor guard must NOT flag it: a legitimate
    historical row is not a stranded pair half, and blocking the FIRST
    production run over it would be a false-positive availability
    abort. The pairs still retire; the history stays untouched."""
    module = _module()
    conn = committed_scratch
    history_id = _seed_historical_userless_doctor(conn, "general", active=False)
    conn.commit()

    result = module.upgrade_with_conn(conn)
    conn.commit()

    assert result == {"users_deleted": 3, "doctors_deleted": 3}
    assert _usernames_present(conn) == set()
    survivor = conn.execute(
        sa.text("SELECT active, user_id, specialty FROM doctors WHERE id = :i"),
        {"i": history_id},
    ).fetchone()
    assert bool(survivor.active) is False
    assert survivor.user_id is None
    assert survivor.specialty == "general"


@pytest.mark.integration
@pytest.mark.migration
def test_upgrade_clean_noop_over_inactive_userless_general_doctor_history() -> None:
    """Review round 3 (P2-A), the all-absent twin: the already-retired
    no-op verdict must stay provable without false-positiving on
    preserved clinical history — the inactive userless 'general' row
    is the DOCUMENTED historical shape (the sanctioned deletion path
    deactivates the profile; the reconciler's decision #13 tolerates
    inactive userless rows), so re-running the retirement over a
    database carrying such history is still a clean no-op."""
    module = _module()
    conn = _scratch()
    try:
        history_id = _seed_historical_userless_doctor(conn, "general", active=False)
        conn.commit()

        result = module.upgrade_with_conn(conn)
        conn.commit()

        assert result == {"users_deleted": 0, "doctors_deleted": 0}
        (doctor_count,) = conn.execute(
            sa.text("SELECT COUNT(*) FROM doctors")
        ).fetchone()
        assert int(doctor_count) == 1
        (still_there,) = conn.execute(
            sa.text("SELECT COUNT(*) FROM doctors WHERE id = :i"),
            {"i": history_id},
        ).fetchone()
        assert int(still_there) == 1
    finally:
        conn.close()


@pytest.mark.integration
@pytest.mark.migration
def test_upgrade_aborts_on_role_drift_with_nothing_changed(
    committed_scratch,
) -> None:
    """A re-purposed account is NOT the 0055 pair — the internal
    'Resource' sentinel spelling is part of the pair identity."""
    module = _module()
    conn = committed_scratch
    conn.execute(
        sa.text("UPDATE users SET role = :r WHERE username = :u"),
        {"r": "Doctor", "u": "lab_resource"},
    )
    conn.commit()

    with pytest.raises(RuntimeError, match="role"):
        module.upgrade_with_conn(conn)
    conn.rollback()
    assert _usernames_present(conn) == set(_PAIR_USERNAMES)
    assert _pair_doctor_count(conn) == 3
    (role,) = conn.execute(
        sa.text("SELECT role FROM users WHERE username = :u"),
        {"u": "lab_resource"},
    ).fetchone()
    assert role == "Doctor"


@pytest.mark.integration
@pytest.mark.migration
def test_upgrade_aborts_on_orphan_half_pair_with_nothing_changed(
    committed_scratch,
) -> None:
    """A User row without its linked Doctor row is drift — the
    retirement never deletes a half-pair it cannot reason about."""
    module = _module()
    conn = committed_scratch
    conn.execute(
        sa.text(
            "DELETE FROM doctors WHERE user_id ="
            " (SELECT id FROM users WHERE username = 'lab_resource')"
        )
    )
    conn.commit()

    with pytest.raises(RuntimeError, match="orphan half-pair"):
        module.upgrade_with_conn(conn)
    conn.rollback()
    assert _usernames_present(conn) == set(_PAIR_USERNAMES)
    assert _pair_doctor_count(conn) == 2
    (user_count,) = conn.execute(
        sa.text("SELECT COUNT(*) FROM users WHERE username = 'lab_resource'")
    ).fetchone()
    assert int(user_count) == 1


@pytest.mark.integration
@pytest.mark.migration
def test_upgrade_aborts_on_specialty_drift_with_nothing_changed(
    committed_scratch,
) -> None:
    """The 0055 seed specialty mapping is part of the pair identity —
    a re-pointed doctor row aborts the retirement."""
    module = _module()
    conn = committed_scratch
    conn.execute(
        sa.text(
            "UPDATE doctors SET specialty = :s WHERE user_id ="
            " (SELECT id FROM users WHERE username = 'ecg_resource')"
        ),
        {"s": "cardiology"},
    )
    conn.commit()

    with pytest.raises(RuntimeError, match="specialty"):
        module.upgrade_with_conn(conn)
    conn.rollback()
    assert _usernames_present(conn) == set(_PAIR_USERNAMES)
    assert _pair_doctor_count(conn) == 3


@pytest.mark.integration
@pytest.mark.migration
def test_upgrade_aborts_on_partial_pair_set_with_nothing_changed(
    committed_scratch,
) -> None:
    """Someone hand-deleted one pair — the retirement is
    all-or-nothing and refuses to finish a partial job."""
    module = _module()
    conn = committed_scratch
    conn.execute(sa.text("DELETE FROM users WHERE username = 'general_resource'"))
    conn.commit()

    with pytest.raises(RuntimeError, match="PARTIAL"):
        module.upgrade_with_conn(conn)
    conn.rollback()
    # the drift itself is untouched — the migration changed nothing
    assert _usernames_present(conn) == {"ecg_resource", "lab_resource"}
    assert _pair_doctor_count(conn) == 2


@pytest.mark.integration
@pytest.mark.migration
def test_upgrade_aborts_on_any_service_reference_with_nothing_changed(
    committed_scratch,
) -> None:
    """ANY services.doctor_id reference — active OR historical —
    aborts with the inventory: the catalog is never silently
    doctor-stripped."""
    module = _module()
    conn = committed_scratch
    doctor_id = _pair_ids(conn, "ecg_resource")[1]
    # an INACTIVE historical assignment is still catalog state
    conn.execute(
        sa.text(
            "INSERT INTO services (code, queue_tag, active, doctor_id,"
            " requires_doctor) VALUES (:c, :t, :a, :d, :rd)"
        ),
        {
            "c": "ecg_legacy",
            "t": "ecg",
            "a": False,
            "d": doctor_id,
            "rd": True,
        },
    )
    conn.commit()

    with pytest.raises(RuntimeError, match="services row"):
        module.upgrade_with_conn(conn)
    conn.rollback()
    assert _usernames_present(conn) == set(_PAIR_USERNAMES)
    assert _pair_doctor_count(conn) == 3
    (service_count,) = conn.execute(sa.text("SELECT COUNT(*) FROM services")).fetchone()
    assert int(service_count) == 1


@pytest.mark.integration
@pytest.mark.migration
def test_upgrade_aborts_on_any_daily_queue_reference_with_nothing_changed(
    committed_scratch,
) -> None:
    """ANY daily_queues.specialist_id reference — a past-day HISTORICAL
    row included — aborts: 0063 consumed every canonical bridge, so a
    survivor is drift the operator must resolve explicitly."""
    module = _module()
    conn = committed_scratch
    doctor_id = _pair_ids(conn, "lab_resource")[1]
    conn.execute(
        sa.text(
            "INSERT INTO daily_queues (day, queue_tag, specialist_id,"
            " queue_resource_id, active) VALUES (:d, :t, :s, :r, :a)"
        ),
        {
            "d": "2026-01-01",
            "t": "lab",
            "s": doctor_id,
            "r": None,
            "a": False,
        },
    )
    conn.commit()

    with pytest.raises(RuntimeError, match="daily_queues row"):
        module.upgrade_with_conn(conn)
    conn.rollback()
    assert _usernames_present(conn) == set(_PAIR_USERNAMES)
    assert _pair_doctor_count(conn) == 3
    (queue_count,) = conn.execute(
        sa.text("SELECT COUNT(*) FROM daily_queues")
    ).fetchone()
    assert int(queue_count) == 1


# ===================== B. the TRUE-inverse downgrade =====================


@pytest.mark.integration
@pytest.mark.migration
def test_downgrade_reprovisions_the_exact_0055_0057_shape() -> None:
    """upgrade -> downgrade lands back on the exact 0055+0057 shape:
    username, unusable hash, 'Resource' role, the 0055 specialty,
    active, caps 1/15 — and the anonymized login_attempts probe STAYS
    anonymized (a downgrade restores PAIRS, not per-row audit links)."""
    module = _module()
    conn = _scratch()
    try:
        pairs = _seed_all_pairs(conn)
        probe_id = _seed_login_attempt(conn, pairs["ecg_resource"][0])
        conn.commit()

        module.upgrade_with_conn(conn)
        conn.commit()
        assert _usernames_present(conn) == set()

        module.downgrade_with_conn(conn)
        conn.commit()

        assert _usernames_present(conn) == set(_PAIR_USERNAMES)
        assert _pair_doctor_count(conn) == 3
        rows = conn.execute(
            sa.text(
                "SELECT u.username, u.hashed_password, u.role, u.is_active,"
                " u.is_superuser, u.must_change_password, d.specialty,"
                " d.active, d.start_number_online, d.max_online_per_day"
                " FROM users u JOIN doctors d ON d.user_id = u.id"
                " WHERE u.username IN (:a, :b, :c) ORDER BY u.username"
            ),
            {
                "a": _PAIR_USERNAMES[0],
                "b": _PAIR_USERNAMES[1],
                "c": _PAIR_USERNAMES[2],
            },
        ).fetchall()
        assert len(rows) == 3
        for row in rows:
            assert row.hashed_password == _DISABLED_HASH
            assert row.role == "Resource"
            assert bool(row.is_active)
            assert not bool(row.is_superuser)
            assert not bool(row.must_change_password)
            assert row.specialty == _PAIR_SPECIALTIES[row.username]
            assert bool(row.active)
            assert row.start_number_online == 1
            assert row.max_online_per_day == 15
        # the anonymized probe is NOT re-linked
        assert _probe_user_id(conn, probe_id) is None
    finally:
        conn.close()


@pytest.mark.integration
@pytest.mark.migration
def test_downgrade_is_idempotent() -> None:
    """ON CONFLICT DO NOTHING + the username pre-check: a downgrade
    over the seeded state (pairs present) is a per-pair no-op, and a
    second downgrade after a restore changes nothing either."""
    module = _module()
    conn = _scratch()
    try:
        _seed_all_pairs(conn)
        conn.commit()

        # pairs already present: per-pair idempotent no-op
        module.downgrade_with_conn(conn)
        conn.commit()
        assert _pair_doctor_count(conn) == 3

        # retire, restore, restore again: still exactly three pairs
        module.upgrade_with_conn(conn)
        conn.commit()
        module.downgrade_with_conn(conn)
        conn.commit()
        module.downgrade_with_conn(conn)
        conn.commit()

        assert _usernames_present(conn) == set(_PAIR_USERNAMES)
        assert _pair_doctor_count(conn) == 3
        (user_count,) = conn.execute(
            sa.text("SELECT COUNT(*) FROM users WHERE username IN (:a, :b, :c)"),
            {
                "a": _PAIR_USERNAMES[0],
                "b": _PAIR_USERNAMES[1],
                "c": _PAIR_USERNAMES[2],
            },
        ).fetchone()
        assert int(user_count) == 3
    finally:
        conn.close()


@pytest.mark.integration
@pytest.mark.migration
def test_downgrade_aborts_on_username_captured_by_a_foreign_shape() -> None:
    """P2-3 (the reviewer counterexample): 0069 retired lab_resource;
    later the username exists again — but as a FOREIGN row (an Admin
    account with a real password and no Doctor). The downgrade must
    abort: silently skipping the captured username and still printing
    "the three pairs are restored" is exactly the broken contract this
    pin forbids."""
    module = _module()
    conn = _scratch()
    try:
        _seed_all_pairs(conn)
        conn.commit()
        module.upgrade_with_conn(conn)
        conn.commit()
        assert _usernames_present(conn) == set()

        # the capture: lab_resource exists, but as a foreign row
        conn.execute(
            sa.text(
                "INSERT INTO users (username, hashed_password, role,"
                " is_active, is_superuser, must_change_password)"
                " VALUES ('lab_resource', 'argon2$real$hash', 'Admin',"
                " true, false, false)"
            )
        )
        conn.commit()

        with pytest.raises(RuntimeError, match="foreign capture"):
            module.downgrade_with_conn(conn)
        conn.rollback()

        # the impostor is untouched and nothing was restored around it
        assert _usernames_present(conn) == {"lab_resource"}
        (role,) = conn.execute(
            sa.text("SELECT role FROM users WHERE username = :u"),
            {"u": "lab_resource"},
        ).fetchone()
        assert role == "Admin"
        (doctor_count,) = conn.execute(
            sa.text("SELECT COUNT(*) FROM doctors")
        ).fetchone()
        assert int(doctor_count) == 0
    finally:
        conn.close()


@pytest.mark.integration
@pytest.mark.migration
def test_downgrade_aborts_on_present_pair_with_drifted_doctor_caps(
    committed_scratch,
) -> None:
    """P2-3 variant: the username exists and the USER half is the exact
    0055 shape, but the linked Doctor carries drifted caps. The old
    contract skipped it as an "idempotent no-op" (username present is
    enough) and still declared the restore complete — the exact-shape
    pin must abort instead."""
    module = _module()
    conn = committed_scratch
    conn.execute(
        sa.text(
            "UPDATE doctors SET max_online_per_day = 30 WHERE user_id ="
            " (SELECT id FROM users WHERE username = 'lab_resource')"
        )
    )
    conn.commit()

    with pytest.raises(RuntimeError, match="caps"):
        module.downgrade_with_conn(conn)
    conn.rollback()

    assert _usernames_present(conn) == set(_PAIR_USERNAMES)
    assert _pair_doctor_count(conn) == 3
    (max_cap,) = conn.execute(
        sa.text(
            "SELECT max_online_per_day FROM doctors WHERE user_id ="
            " (SELECT id FROM users WHERE username = 'lab_resource')"
        )
    ).fetchone()
    assert int(max_cap) == 30  # the drift itself is untouched


def _pair_ids(conn, username: str) -> tuple[int, int]:
    """Resolve (user_id, doctor_id) for a seeded pair username."""
    (user_id,) = conn.execute(
        sa.text("SELECT id FROM users WHERE username = :u"), {"u": username}
    ).fetchone()
    (doctor_id,) = conn.execute(
        sa.text("SELECT id FROM doctors WHERE user_id = :uid"), {"uid": user_id}
    ).fetchone()
    return int(user_id), int(doctor_id)


@pytest.mark.integration
@pytest.mark.migration
def test_pair_vocabulary_matches_the_0055_seed() -> None:
    """The retirement targets EXACTLY the accounts 0055 provisioned —
    pinned against the 0055 source so a future edit of either side
    trips this parity pin."""
    module = _module()
    source = MIGRATION_0055.read_text(encoding="utf-8")
    seeded = set(re.findall(r"'(ecg_resource|lab_resource|general_resource)'", source))
    assert seeded == set(_PAIR_USERNAMES)
    assert set(module.SYNTHETIC_PAIR_USERNAMES) == set(_PAIR_USERNAMES)
    assert module.SYNTHETIC_PAIR_SPECIALTIES == _PAIR_SPECIALTIES
    assert module.SYNTHETIC_PAIR_DISABLED_HASH == _DISABLED_HASH
    assert module.SYNTHETIC_PAIR_ROLE == "Resource"


@pytest.mark.integration
@pytest.mark.migration
def test_alembic_chain_single_head_0069() -> None:
    """The chain stays single-headed with the retirement as the head
    (the sentinel-suite graph pattern)."""
    module = _module()
    versions = MIGRATION_0069.parent
    graph: dict[str, tuple[str, ...]] = {}
    for path in sorted(versions.glob("*.py")):
        source = path.read_text(encoding="utf-8")
        revision_match = re.search(r'^revision\s*=\s*["\']([^"\']+)["\']', source, re.M)
        if not revision_match:
            continue
        down_match = re.search(r"^down_revision\s*=\s*(.+)$", source, re.M)
        parents = (
            tuple(re.findall(r'["\']([^"\']+)["\']', down_match.group(1)))
            if down_match
            else ()
        )
        graph[revision_match.group(1)] = parents
    assert module.revision == "0069_sentinel_pair_retirement"
    assert module.down_revision == "0068_direction_public_address"
    assert graph["0069_sentinel_pair_retirement"] == ("0068_direction_public_address",)
    assert len(module.revision) <= 32
    referenced = {parent for parents in graph.values() for parent in parents}
    heads = sorted(revision for revision in graph if revision not in referenced)
    assert heads == ["0069_sentinel_pair_retirement"]


# ===================== C. PostgreSQL FK introspection =====================


@pytest.fixture
def retirement_pg_engine():
    """An isolated PostgreSQL schema with the minimal retirement tables
    (the cutover_pg_engine pattern)."""
    database_url = os.environ.get("DATABASE_URL", "sqlite:///:memory:")
    url = make_url(database_url)
    if url.get_backend_name() != "postgresql":
        pytest.skip("FK introspection proof requires PostgreSQL")
    if os.environ.get("CI", "").lower() != "true" and not (
        url.database or ""
    ).startswith("clinic_test"):
        pytest.skip("use CI or an explicitly disposable clinic_test database")

    from sqlalchemy.schema import CreateSchema, DropSchema

    schema = "test_retirement_" + uuid.uuid4().hex
    admin_engine = create_engine(url, pool_pre_ping=True)
    with admin_engine.begin() as connection:
        connection.execute(CreateSchema(schema))

    engine = create_engine(
        url,
        pool_pre_ping=True,
        connect_args={
            "options": (
                f"-csearch_path={schema} "
                "-cstatement_timeout=10000 -clock_timeout=8000"
            )
        },
    )
    try:
        _create_retirement_tables(engine)
        yield engine
    finally:
        engine.dispose()
        with admin_engine.begin() as connection:
            connection.execute(DropSchema(schema, cascade=True))
        admin_engine.dispose()


def _pg_scratch_table(
    engine, name: str, column: str, ref_table: str, ondelete: str | None
):
    """An EXTRA FK surface for the introspection proofs (NO ACTION or
    CASCADE — the abort classes), created via raw DDL so no metadata
    resolution is needed against the pre-existing retirement tables."""
    rule = f"ON DELETE {ondelete}" if ondelete else ""
    with engine.begin() as conn:
        conn.execute(
            sa.text(
                f'CREATE TABLE "{name}" ('
                f'"id" INTEGER PRIMARY KEY GENERATED BY DEFAULT AS IDENTITY,'
                f'"{column}" INTEGER REFERENCES "{ref_table}"(id) {rule}'
                f")"
            )
        )


@pytest.mark.integration
@pytest.mark.migration
def test_pg_introspection_blocks_a_no_action_surface_with_rows(
    retirement_pg_engine,
) -> None:
    module = _module()
    engine = retirement_pg_engine
    _pg_scratch_table(engine, "documents", "owner_id", "users", None)  # NO ACTION
    with engine.connect() as conn:
        _seed_all_pairs(conn)
        conn.execute(
            sa.text(
                "INSERT INTO documents (owner_id) VALUES"
                " ((SELECT id FROM users WHERE username = 'lab_resource'))"
            )
        )
        conn.commit()

        with pytest.raises(RuntimeError, match="documents"):
            module.upgrade_with_conn(conn)
        conn.rollback()
        assert _usernames_present(conn) == set(_PAIR_USERNAMES)


@pytest.mark.integration
@pytest.mark.migration
def test_pg_introspection_blocks_a_cascade_surface_with_rows(
    retirement_pg_engine,
) -> None:
    """A CASCADE surface holding rows aborts — the retirement never
    silently cascade-deletes history."""
    module = _module()
    engine = retirement_pg_engine
    _pg_scratch_table(engine, "cascade_notes", "user_id", "users", "CASCADE")
    with engine.connect() as conn:
        _seed_all_pairs(conn)
        conn.execute(
            sa.text(
                "INSERT INTO cascade_notes (user_id) VALUES"
                " ((SELECT id FROM users WHERE username = 'ecg_resource'))"
            )
        )
        conn.commit()

        with pytest.raises(RuntimeError, match="cascade_notes"):
            module.upgrade_with_conn(conn)
        conn.rollback()
        assert _usernames_present(conn) == set(_PAIR_USERNAMES)


@pytest.mark.integration
@pytest.mark.migration
def test_pg_introspection_blocks_an_unlisted_set_null_surface_with_rows(
    retirement_pg_engine,
) -> None:
    """Only login_attempts is allowed to carry SET NULL rows; any OTHER
    SET NULL surface with rows aborts loudly (future-proof)."""
    module = _module()
    engine = retirement_pg_engine
    _pg_scratch_table(engine, "audit_notes", "actor_id", "users", "SET NULL")
    with engine.connect() as conn:
        _seed_all_pairs(conn)
        conn.execute(
            sa.text(
                "INSERT INTO audit_notes (actor_id) VALUES"
                " ((SELECT id FROM users WHERE username = 'general_resource'))"
            )
        )
        conn.commit()

        with pytest.raises(RuntimeError, match="audit_notes"):
            module.upgrade_with_conn(conn)
        conn.rollback()
        assert _usernames_present(conn) == set(_PAIR_USERNAMES)


@pytest.mark.integration
@pytest.mark.migration
def test_pg_login_attempts_rows_survive_anonymized_in_bulk(
    retirement_pg_engine,
) -> None:
    """Multiple probe rows across the pairs — the designed allow-list
    semantic on real PostgreSQL FK machinery."""
    module = _module()
    engine = retirement_pg_engine
    with engine.connect() as conn:
        pairs = _seed_all_pairs(conn)
        ids = []
        for username in _PAIR_USERNAMES:
            for _ in range(2):
                ids.append(_seed_login_attempt(conn, pairs[username][0]))
        conn.commit()

        module.upgrade_with_conn(conn)
        conn.commit()

        assert _usernames_present(conn) == set()
        rows = conn.execute(
            sa.text("SELECT id, user_id FROM login_attempts ORDER BY id")
        ).fetchall()
        assert len(rows) == 6
        assert all(row[1] is None for row in rows)


@pytest.mark.integration
@pytest.mark.migration
def test_pg_resolution_holds_for_update_locks_until_commit(
    retirement_pg_engine,
) -> None:
    """P1-b hardening (owner closure plan, post-merge window before the
    production application): the pair resolution locks the three User
    rows and their linked Doctor rows FOR UPDATE — users first, then
    doctors, both ordered by id — BEFORE any shape check runs. A
    concurrent writer must BLOCK for the life of the migration
    transaction:

    - a re-purpose of a pair row (``UPDATE users SET role = ...``) —
      the verified 0055 shape must hold at DELETE time, not just at
      CHECK time;
    - an FK-referencing insert (``INSERT INTO services ... doctor_id``)
      — the referencing INSERT takes FOR KEY SHARE on the parent
      doctor row, which conflicts with the held FOR UPDATE, so the
      guard inventory cannot be raced by a late reference.

    The rowcount verification and the postcondition re-check stay in
    place as the backstop (defense in depth), not the primary lock."""
    module = _module()
    engine = retirement_pg_engine

    with engine.connect() as conn:
        _seed_all_pairs(conn)
        conn.commit()

    locked = engine.connect()
    trans = locked.begin()
    try:
        rows = module._resolve_and_assert_pairs(locked)
        assert len(rows) == 3

        rival = engine.connect()
        try:
            rival.exec_driver_sql("SET lock_timeout = '400ms'")

            # 1) a concurrent re-purpose of a pair row must BLOCK
            with pytest.raises(sa.exc.OperationalError, match="(?i)lock"):
                rival.execute(
                    sa.text(
                        "UPDATE users SET role = 'Doctor' "
                        "WHERE username = 'ecg_resource'"
                    )
                )
            rival.rollback()  # clear the aborted transaction state
            # a session-level SET executed inside a rolled-back
            # transaction unwinds with it (the GUC stack is tied to
            # the transaction), so the 400ms above no longer holds —
            # re-arm it or the second probe silently runs on the
            # fixture's 8000ms default
            rival.exec_driver_sql("SET lock_timeout = '400ms'")

            # 2) a concurrent FK-referencing insert must BLOCK as well
            with pytest.raises(sa.exc.OperationalError, match="(?i)lock"):
                rival.execute(
                    sa.text(
                        "INSERT INTO services (code, queue_tag, active,"
                        " doctor_id, requires_doctor) "
                        "SELECT 'X01', 'ecg', true, d.id, true "
                        "FROM doctors d JOIN users u ON d.user_id = u.id "
                        "WHERE u.username = 'ecg_resource'"
                    )
                )
        finally:
            rival.rollback()
            rival.close()
    finally:
        trans.rollback()
        locked.close()

    # nothing changed — the migration transaction was rolled back intact
    with engine.connect() as conn:
        assert _usernames_present(conn) == set(_PAIR_USERNAMES)


@pytest.mark.integration
@pytest.mark.migration
def test_pg_upgrade_aborts_when_a_rival_inserts_the_missing_pair_after_the_locks(
    retirement_pg_engine,
) -> None:
    """P2-1, the two-connection proof (the reviewer counterexample):
    the lock selects only fix the rows they SEE. Start with ecg + lab
    present and general missing; the migration takes the locks (2
    users + 2 doctors); a RIVAL then restores the missing full pair and
    commits; the resolution read now sees 3 valid pairs — the third one
    was NEVER locked. The upgrade must abort (nothing deleted): a
    phantom row is not part of the locked "one stable world", and the
    next concurrent writer could still land between the guard and the
    DELETE for it. Re-running the migration afterwards sees a stable
    full set and retires it correctly.

    Review round 3 (P2-B): the production window is now closed one
    level up — ``upgrade_with_conn`` opens with a SHARE ROW EXCLUSIVE
    table lock on users/doctors, so a rival INSERT can no longer
    commit between the lock selects and the resolution read (it blocks
    until the migration transaction ends; the no-op-window proof is
    the dedicated test below). The set-equality guard stays as
    DEFENSE-IN-DEPTH — if a future refactor ever drops or loosens the
    table lock, this pin must still hold — so this proof drives the
    resolution DIRECTLY (``_resolve_and_assert_pairs``, bypassing the
    table lock) to keep the guard covered at its own seam."""
    module = _module()
    engine = retirement_pg_engine

    with engine.connect() as conn:
        _seed_pair(conn, "ecg_resource")
        _seed_pair(conn, "lab_resource")
        conn.commit()

    locked_conn = engine.connect()
    rival = engine.connect()
    try:
        original_lock = module._lock_pair_rows

        def lock_then_rival_restores_the_missing_pair(lock_conn):
            result = original_lock(lock_conn)  # locks 2 users + 2 doctors
            _seed_pair(rival, "general_resource")  # the phantom pair
            rival.commit()  # committed between the locks and the read
            return result

        module._lock_pair_rows = lock_then_rival_restores_the_missing_pair

        with pytest.raises(RuntimeError, match="NOT the locked pair set"):
            module._resolve_and_assert_pairs(locked_conn)
        locked_conn.rollback()
    finally:
        module._lock_pair_rows = original_lock
        rival.close()
        locked_conn.close()

    # nothing was deleted — the rival's pair survives the abort too
    with engine.connect() as conn:
        assert _usernames_present(conn) == set(_PAIR_USERNAMES)
        assert _pair_doctor_count(conn) == 3


@pytest.mark.integration
@pytest.mark.migration
def test_pg_noop_verdict_blocks_a_rival_restore_until_commit(
    retirement_pg_engine,
) -> None:
    """Review round 3 (P2-B): ``FOR UPDATE`` locks only the rows they
    SEE — on the already-retired no-op pass there are no pair rows to
    lock at all, so a rival could INSERT a full pair (or an orphaned
    bridge-vocabulary Doctor) after the final guard read and commit
    before this migration, silently invalidating the "already
    retired" verdict Alembic is about to stamp. The migration
    transaction now OPENS with a SHARE ROW EXCLUSIVE table lock on
    users/doctors: every concurrent INSERT/UPDATE/DELETE on the two
    tables blocks until the migration commits, so the stamped verdict
    is true of a world no concurrent writer can change."""
    module = _module()
    engine = retirement_pg_engine

    mig = engine.connect()
    rival = engine.connect()
    try:
        result = module.upgrade_with_conn(mig)  # the no-op verdict; txn open
        assert result == {"users_deleted": 0, "doctors_deleted": 0}

        rival.exec_driver_sql("SET lock_timeout = '400ms'")

        # 1) the reviewer counterexample: a full pair restored after
        # the final read, before the migration commit — must BLOCK
        with pytest.raises(sa.exc.OperationalError, match="(?i)lock"):
            _seed_pair(rival, "general_resource")
        rival.rollback()  # the GUC unwinds with the transaction — re-arm
        rival.exec_driver_sql("SET lock_timeout = '400ms'")

        # 2) the same window for the orphaned-bridge-Doctor guard: an
        # ACTIVE userless bridge row inserted after the check — blocked
        with pytest.raises(sa.exc.OperationalError, match="(?i)lock"):
            rival.execute(
                sa.text(
                    "INSERT INTO doctors (user_id, specialty, active,"
                    " start_number_online, max_online_per_day)"
                    " VALUES (NULL, 'general', true, 1, 15)"
                )
            )
        rival.rollback()
        rival.exec_driver_sql("SET lock_timeout = '400ms'")

        mig.commit()  # the verdict is stamped over a stable world
    finally:
        rival.close()
        mig.close()

    # after the stamp the concurrent writer is free to land — and the
    # contract handles it: a FULL three-pair restore re-runs cleanly
    with engine.connect() as conn:
        _seed_pair(conn, "ecg_resource")
        _seed_pair(conn, "lab_resource")
        _seed_pair(conn, "general_resource")
        conn.commit()

    with engine.connect() as conn:
        result = module.upgrade_with_conn(conn)
        conn.commit()
        assert result == {"users_deleted": 3, "doctors_deleted": 3}
        assert _usernames_present(conn) == set()


@pytest.mark.integration
@pytest.mark.migration
def test_pg_downgrade_blocks_a_rival_deletion_until_commit(
    retirement_pg_engine,
) -> None:
    """Review round 3 (P2-B), the downgrade twin: the same phantom
    window sits between the downgrade's final postcondition read and
    its commit — a rival deleting a just-restored pair would leave
    "restored (postcondition verified)" stamped over a missing pair.
    The downgrade takes the same SHARE ROW EXCLUSIVE lock, so the
    deletion (and any pair INSERT) blocks until the restore commits."""
    module = _module()
    engine = retirement_pg_engine

    mig = engine.connect()
    rival = engine.connect()
    try:
        module.downgrade_with_conn(mig)  # pairs restored; txn open

        rival.exec_driver_sql("SET lock_timeout = '400ms'")
        with pytest.raises(sa.exc.OperationalError, match="(?i)lock"):
            rival.execute(sa.text("DELETE FROM users WHERE username = 'ecg_resource'"))
        rival.rollback()  # the GUC unwinds with the transaction — re-arm
        rival.exec_driver_sql("SET lock_timeout = '400ms'")

        mig.commit()  # the restore is stamped over a stable world
    finally:
        rival.close()
        mig.close()

    with engine.connect() as conn:
        assert _usernames_present(conn) == set(_PAIR_USERNAMES)
        assert _pair_doctor_count(conn) == 3


# ===================== D. the full alembic chain (live PostgreSQL) =====================


def _candidate_admin_urls() -> list[str]:
    """Admin DSNs for scratch provisioning — LOCAL servers only (the
    rq09 fixture pattern, plus this session's portable 55432 server)."""
    urls: list[str] = []

    explicit = os.getenv("RQ15D_PG_ADMIN_URL", "").strip()
    if explicit:
        urls.append(explicit)

    env_url = os.environ.get("DATABASE_URL", "").strip()
    if env_url:
        u = make_url(env_url)
        if (u.host or "") in {"localhost", "127.0.0.1", "::1"}:
            urls.append(
                f"postgresql://{u.username or ''}"
                f":{u.password or ''}@{u.host}:{u.port or 5432}/postgres"
            )

    # the portable zonky server used by local sessions (trust auth)
    urls.append("postgresql://postgres@127.0.0.1:55432/postgres")
    return urls


@pytest.mark.integration
@pytest.mark.migration
def test_full_chain_retires_the_sentinel_pairs_on_a_fresh_database() -> None:
    """``alembic upgrade head`` on a fresh scratch database: 0055
    provisions the pairs somewhere mid-chain, 0069 retires them at the
    head — the end state has zero synthetic usernames and zero doctors
    linked to them."""
    module = _module()
    import psycopg

    admin_url = None
    for candidate in _candidate_admin_urls():
        try:
            with psycopg.connect(candidate, connect_timeout=3, autocommit=True) as c:
                c.execute("SELECT 1")
            admin_url = candidate
            break
        except Exception:  # noqa: BLE001
            continue
    if admin_url is None:
        pytest.skip("disposable PostgreSQL unavailable — full-chain NOT_RUN")

    scratch_db = "clinic_test_rq15d_chain"
    with psycopg.connect(admin_url, autocommit=True) as c:
        c.execute(f'DROP DATABASE IF EXISTS "{scratch_db}"')
        c.execute(f'CREATE DATABASE "{scratch_db}"')

    u = make_url(admin_url)
    # render_as_string(hide_password=False): plain str(URL) masks the
    # password as *** (SQLAlchemy 2.0) — the subprocess would then try
    # to authenticate with the literal asterisks and fail. The local
    # portable server (trust auth, no password) never surfaced this;
    # the CI service (password auth) did.
    sa_url = u.set(
        drivername="postgresql+psycopg", database=scratch_db
    ).render_as_string(hide_password=False)
    try:
        env = dict(os.environ, DATABASE_URL=sa_url, TESTING="1")
        result = subprocess.run(
            [sys.executable, "-m", "alembic", "-c", "alembic.ini", "upgrade", "head"],
            capture_output=True,
            text=True,
            cwd=str(BACKEND_ROOT),
            env=env,
            timeout=600,
        )
        assert (
            result.returncode == 0
        ), f"alembic upgrade head failed:\n{result.stdout[-2000:]}\n{result.stderr[-2000:]}"

        engine = create_engine(sa_url, future=True)
        try:
            with engine.connect() as conn:
                version = conn.execute(
                    sa.text("SELECT version_num FROM alembic_version")
                ).scalar()
                assert version == module.revision

                usernames = {
                    row[0]
                    for row in conn.execute(
                        sa.text(
                            "SELECT username FROM users WHERE username IN"
                            " ('ecg_resource','lab_resource','general_resource')"
                        )
                    ).fetchall()
                }
                assert usernames == set()

                (linked_doctors,) = conn.execute(
                    sa.text(
                        "SELECT COUNT(*) FROM doctors d JOIN users u"
                        " ON u.id = d.user_id WHERE u.username IN"
                        " ('ecg_resource','lab_resource','general_resource')"
                    )
                ).fetchone()
                assert int(linked_doctors) == 0
        finally:
            engine.dispose()
    finally:
        with psycopg.connect(admin_url, autocommit=True) as c:
            c.execute(f'DROP DATABASE IF EXISTS "{scratch_db}"')


# ========= E. Supabase-compat regression pins (2026-09-18 FK fix) =========
#
# The pre-fix PostgreSQL FK inventory enumerated surfaces through
# multi-view information_schema joins. On the production Supabase
# catalog this introspection hung / lost the connection BEFORE the
# deletion (the transaction rolled back cleanly to 0068). The fix moves
# the discovery to pg_catalog scoped to the current schema on BOTH the
# source and the reference side. These pins make the rewritten SQL's
# contract explicit so a future rewrite cannot silently weaken the
# catch-all guard:
#
# - A. schema isolation: foreign-schema worlds (their own users + FKs)
#   are invisible to the inventory, on the SOURCE side and — the
#   pre-fix false-positive — on the REFERENCE side (a current-schema
#   table pointing at a foreign "users" table is NOT a pair surface);
# - B. composite-FK catch-all still detects multi-column FKs and
#   aborts fail-closed;
# - the confdeltype -> delete_rule spelling is pinned for every branch
#   (the runtime allowlist compares against the literal 'SET NULL').


def _foreign_schema_name() -> str:
    return "foreign_" + uuid.uuid4().hex


def _create_foreign_users_world(engine, schema: str) -> None:
    """A foreign-schema world that MUST stay invisible to the FK
    inventory: its own users table (one row, serial id=1) and a child
    table with an FK to it."""
    with engine.begin() as conn:
        conn.execute(sa.text(f'CREATE SCHEMA "{schema}"'))
        conn.execute(
            sa.text(
                f'CREATE TABLE "{schema}".users ('
                f'"id" INTEGER PRIMARY KEY GENERATED BY DEFAULT AS IDENTITY,'
                f'"username" TEXT NOT NULL)'
            )
        )
        conn.execute(
            sa.text(f'INSERT INTO "{schema}".users (username) VALUES (:u)'),
            {"u": "foreign_user"},
        )
        conn.execute(
            sa.text(
                f'CREATE TABLE "{schema}".foreign_children ('
                f'"id" INTEGER PRIMARY KEY GENERATED BY DEFAULT AS IDENTITY,'
                f'"user_id" INTEGER NOT NULL REFERENCES "{schema}".users(id))'
            )
        )


def _drop_foreign_schema(engine, schema: str) -> None:
    with engine.begin() as conn:
        conn.execute(sa.text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))


@pytest.mark.integration
@pytest.mark.migration
def test_pg_introspection_ignores_a_foreign_schema_fk(
    retirement_pg_engine,
) -> None:
    """Schema isolation (source side): an FK living entirely inside
    another schema is invisible to the inventory — the catch-all
    enumerates current-schema surfaces only."""
    module = _module()
    engine = retirement_pg_engine
    foreign = _foreign_schema_name()
    _create_foreign_users_world(engine, foreign)
    try:
        with engine.connect() as conn:
            rows = conn.execute(module._SELECT_FK_SURFACES).fetchall()
            conn.rollback()
        seen = {(row.table_name, row.column_name) for row in rows}
        assert ("foreign_children", "user_id") not in seen
        assert all(not row.table_name.startswith("foreign") for row in rows)
    finally:
        _drop_foreign_schema(engine, foreign)


@pytest.mark.integration
@pytest.mark.migration
def test_pg_introspection_does_not_leak_a_cross_schema_reference(
    retirement_pg_engine,
) -> None:
    """Schema isolation (reference side): a current-schema table with an
    FK pointing at ANOTHER schema's users is NOT a surface referencing
    the pairs — the inventory must not report it and the retirement
    must not false-abort on it (the pre-fix query matched the foreign
    users by bare table name)."""
    module = _module()
    engine = retirement_pg_engine
    foreign = _foreign_schema_name()
    _create_foreign_users_world(engine, foreign)
    try:
        with engine.begin() as conn:
            conn.execute(
                sa.text(
                    'CREATE TABLE "cross_probes" ('
                    '"id" INTEGER PRIMARY KEY GENERATED BY DEFAULT AS IDENTITY,'
                    f'"user_id" INTEGER NOT NULL REFERENCES "{foreign}".users(id))'
                )
            )
            conn.execute(sa.text('INSERT INTO "cross_probes" (user_id) VALUES (1)'))

        with engine.connect() as conn:
            rows = conn.execute(module._SELECT_FK_SURFACES).fetchall()
            conn.rollback()
            assert ("cross_probes", "users") not in {
                (row.table_name, row.ref_table) for row in rows
            }

            _seed_all_pairs(conn)
            conn.commit()
            result = module.upgrade_with_conn(conn)
            conn.commit()
            assert result == {"users_deleted": 3, "doctors_deleted": 3}
            assert _usernames_present(conn) == set()
            (probe_rows,) = conn.execute(
                sa.text('SELECT COUNT(*) FROM "cross_probes"')
            ).fetchone()
            assert int(probe_rows) == 1
    finally:
        _drop_foreign_schema(engine, foreign)


@pytest.mark.integration
@pytest.mark.migration
def test_pg_introspection_aborts_on_a_composite_fk_surface(
    retirement_pg_engine,
) -> None:
    """Composite-FK catch-all: a multi-column FK referencing the target
    relation is unsupported surface — the guard discovers it and aborts
    fail-closed (the retirement never guesses)."""
    module = _module()
    engine = retirement_pg_engine
    with engine.begin() as conn:
        conn.execute(
            sa.text(
                "ALTER TABLE users ADD CONSTRAINT uq_users_composite_pin"
                " UNIQUE (id, username)"
            )
        )
        conn.execute(
            sa.text(
                'CREATE TABLE "composite_children" ('
                '"id" INTEGER PRIMARY KEY GENERATED BY DEFAULT AS IDENTITY,'
                '"user_id" INTEGER NOT NULL,'
                '"username" TEXT NOT NULL,'
                "FOREIGN KEY (user_id, username)"
                " REFERENCES users (id, username))"
            )
        )

    with engine.connect() as conn:
        _seed_all_pairs(conn)
        conn.commit()

        rows = conn.execute(module._SELECT_COMPOSITE_FK_CONSTRAINTS).fetchall()
        conn.rollback()
        by_name = {row.constraint_name: int(row.column_count) for row in rows}
        assert by_name.get("composite_children_user_id_username_fkey") == 2

        with pytest.raises(RuntimeError, match="composite"):
            module.upgrade_with_conn(conn)
        conn.rollback()
        # the abort happened BEFORE the deletion — nothing changed
        assert _usernames_present(conn) == set(_PAIR_USERNAMES)
        assert _pair_doctor_count(conn) == 3


@pytest.mark.integration
@pytest.mark.migration
def test_pg_introspection_delete_rule_mapping_pin(
    retirement_pg_engine,
) -> None:
    """The delete_rule spelling is pinned for every confdeltype branch
    (a/r/c/n/d) — the runtime allowlist compares against the literal
    'SET NULL', so a mapping drift would silently break the guard."""
    module = _module()
    engine = retirement_pg_engine
    _pg_scratch_table(engine, "pinned_no_action", "user_id", "users", None)
    _pg_scratch_table(engine, "pinned_restrict", "user_id", "users", "RESTRICT")
    _pg_scratch_table(engine, "pinned_cascade", "user_id", "users", "CASCADE")
    _pg_scratch_table(engine, "pinned_set_default", "user_id", "users", "SET DEFAULT")
    with engine.connect() as conn:
        rows = conn.execute(module._SELECT_FK_SURFACES).fetchall()
        conn.rollback()
    rules = {(row.table_name, row.column_name): row.delete_rule for row in rows}
    assert rules[("pinned_no_action", "user_id")] == "NO ACTION"
    assert rules[("pinned_restrict", "user_id")] == "RESTRICT"
    assert rules[("pinned_cascade", "user_id")] == "CASCADE"
    assert rules[("pinned_set_default", "user_id")] == "SET DEFAULT"
    assert rules[("login_attempts", "user_id")] == "SET NULL"
    assert rules[("services", "doctor_id")] == "SET NULL"
    assert rules[("daily_queues", "specialist_id")] == "NO ACTION"
    assert rules[("doctors", "user_id")] == "SET NULL"
