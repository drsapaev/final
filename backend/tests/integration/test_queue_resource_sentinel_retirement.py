"""RQ-15.d (ADR-001 stage E): the 0055 synthetic pair retirement pins.

Migration ``0068_sentinel_pair_retirement`` completes the QD-2 staged
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
  invention, no sequence games;
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
MIGRATION_0068 = (
    BACKEND_ROOT / "alembic" / "versions" / "0068_sentinel_pair_retirement.py"
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
    assert MIGRATION_0068.exists(), (
        "0068_sentinel_pair_retirement.py is missing from the alembic "
        "chain — the RQ-15.d retirement is not implemented"
    )
    spec = importlib.util.spec_from_file_location(
        "migration_0068_sentinel_pair_retirement", MIGRATION_0068
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
def test_alembic_chain_single_head_0068() -> None:
    """The chain stays single-headed with the retirement as the head
    (the sentinel-suite graph pattern)."""
    module = _module()
    versions = MIGRATION_0068.parent
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
    assert module.revision == "0068_sentinel_pair_retirement"
    assert module.down_revision == "0067_daily_queue_start_number"
    assert graph["0068_sentinel_pair_retirement"] == ("0067_daily_queue_start_number",)
    assert len(module.revision) <= 32
    referenced = {parent for parents in graph.values() for parent in parents}
    heads = sorted(revision for revision in graph if revision not in referenced)
    assert heads == ["0068_sentinel_pair_retirement"]


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
    provisions the pairs somewhere mid-chain, 0068 retires them at the
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
