"""Merged-#3340 follow-up (owner P1): the portal booking's FINAL routing
department is re-read with ``populate_existing().with_for_update()`` in the
booking transaction — the ``Department.active`` re-validation is now ATOMIC
with the appointment INSERT.

Two-session PostgreSQL pins (SQLite silently drops FOR UPDATE and cannot
reproduce cross-transaction interleaving — these proofs are NOT_RUN on
SQLite, per the repo's disposable-PostgreSQL doctrine):

1. ``test_lock_revalidation_sees_concurrent_deactivation`` — the exact
   production race the review pinned: session A (booking) resolves the
   department with a PLAIN SELECT; session B (admin) commits
   ``active = False``; session A's lock must then answer the COMMITTED
   state (400 ``department_inactive``), not the stale identity-map snapshot.
2. ``test_lock_revalidation_sees_concurrent_delete`` — session B deletes
   the department and commits between A's resolve and A's lock: controlled
   400 ``department_unknown``, never a persisted appointment with a
   dangling/SET-NULL routing context.
3. ``test_department_row_lock_serializes_deactivation_behind_booking`` —
   the lock is REAL: while the booking transaction holds the department
   row lock (uncommitted), a concurrent admin UPDATE blocks until the
   booking transaction finishes (lock_timeout proof).
"""

from __future__ import annotations

import os
import sys
import uuid
from pathlib import Path

import psycopg
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker

BACKEND_DIR = Path(__file__).resolve().parents[2]
SCRATCH_DB_PREFIX = "portal_dept_lock"
# Review round 3 (owner P2): the scratch name must be RUN-UNIQUE. A fixed
# name with an unconditional pre-drop let two parallel pytest/agent runs on
# the same PostgreSQL server drop each other's database — and would destroy
# any unrelated local database carrying the same name. The name is minted
# once per process (per xdist worker); cleanup drops ONLY the database this
# run created.
SCRATCH_DB = f"{SCRATCH_DB_PREFIX}_{uuid.uuid4().hex[:12]}"

sys.path.insert(0, str(BACKEND_DIR))


def _candidate_admin_urls() -> list[str]:
    """Admin DSNs for scratch provisioning — LOCAL servers only.

    The scratch database must never be created on a remote/production
    server, so DATABASE_URL-derived candidates are accepted only for
    localhost/127.0.0.1 hosts (a pgserver unix-socket DSN passes as-is).
    """
    urls: list[str] = []

    explicit = os.getenv("PORTAL_DEPT_LOCK_PG_ADMIN_URL", "").strip()
    if explicit:
        urls.append(explicit)

    local_pw = os.getenv("LOCAL_PG_SUPERUSER_PASSWORD", "").strip()
    if local_pw:
        urls.append(f"postgresql://postgres:{local_pw}@localhost:5432/postgres")

    env_url = os.getenv("DATABASE_URL", "").strip()
    if env_url:
        u = make_url(env_url)
        if (u.host or "") in {"localhost", "127.0.0.1", "::1"} or u.query.get("host"):
            urls.append(
                env_url
                if u.query.get("host")
                else f"postgresql://{u.username}:{u.password}@{u.host}:{u.port}/postgres"
            )

    return urls


def _dsn_parts(admin_url: str) -> dict:
    """Parse a TCP or unix-socket DSN (pgserver emits ?host=<socket dir>)."""
    from urllib.parse import parse_qs, urlparse

    p = urlparse(admin_url)
    q = parse_qs(p.query)
    return {
        "sockdir": (q.get("host") or [None])[0],
        "user": p.username or "postgres",
        "password": p.password or "",
        "host": p.hostname or "localhost",
        "port": p.port or 5432,
    }


def _scratch_urls(admin_url: str) -> tuple[str, str]:
    """(psycopg DSN, SQLAlchemy URL) for the scratch database."""
    parts = _dsn_parts(admin_url)
    if parts["sockdir"]:
        base_p = f"postgresql://{parts['user']}:{parts['password']}@/"
        base_s = f"postgresql+psycopg://{parts['user']}:{parts['password']}@/"
        return (
            f"{base_p}{SCRATCH_DB}?host={parts['sockdir']}",
            f"{base_s}{SCRATCH_DB}?host={parts['sockdir']}",
        )
    base = f"postgresql://{parts['user']}:{parts['password']}@{parts['host']}:{parts['port']}"
    return (
        f"{base}/{SCRATCH_DB}",
        f"postgresql+psycopg://{parts['user']}:{parts['password']}@{parts['host']}:{parts['port']}/{SCRATCH_DB}",
    )


@pytest.fixture(scope="module")
def pg_engine():
    """Provision a disposable alembic-head PostgreSQL database or skip."""
    last_error: Exception | None = None
    admin_url = None
    for candidate in _candidate_admin_urls():
        try:
            with psycopg.connect(candidate, connect_timeout=5, autocommit=True) as c:
                c.execute("SELECT 1")
            admin_url = candidate
            break
        except Exception as exc:  # noqa: BLE001
            last_error = exc
    if admin_url is None:
        pytest.skip(
            f"disposable PostgreSQL unavailable — portal department-lock "
            f"PG acceptance NOT_RUN (last error: {last_error})"
        )

    psycopg_dsn, sa_url = _scratch_urls(admin_url)
    # No pre-drop: the run-unique name cannot pre-exist (a collision would
    # take 2**48 parallel runs), and dropping a fixed name unconditionally
    # is exactly the cross-run hazard this fixture used to carry.
    with psycopg.connect(admin_url, autocommit=True) as c:
        c.execute(f'CREATE DATABASE "{SCRATCH_DB}"')

    env = dict(os.environ, DATABASE_URL=sa_url, TESTING="1")
    import subprocess  # noqa: E402

    r = subprocess.run(
        [sys.executable, "-m", "alembic", "-c", "alembic.ini", "upgrade", "head"],
        capture_output=True,
        text=True,
        cwd=str(BACKEND_DIR),
        env=env,
    )
    assert r.returncode == 0, r.stderr[-1500:]

    engine = create_engine(sa_url, future=True)
    with engine.connect() as conn:
        version = conn.execute(text("select version_num from alembic_version")).scalar()
    assert version, "alembic_version must be present after upgrade"

    yield engine

    engine.dispose()
    with psycopg.connect(admin_url, autocommit=True) as c:
        # Cleanup touches ONLY the run-unique database this process created;
        # WITH (FORCE) clears lingering connections (PG 13+), falling back
        # to the plain form on older servers.
        try:
            c.execute(f'DROP DATABASE IF EXISTS "{SCRATCH_DB}" WITH (FORCE)')
        except psycopg.errors.SyntaxError:
            c.execute(f'DROP DATABASE IF EXISTS "{SCRATCH_DB}"')


@pytest.fixture
def two_sessions(pg_engine):
    """TWO independent sessions on the scratch database — the booking
    transaction (A) and the admin transaction (B)."""
    Session = sessionmaker(bind=pg_engine, future=True)
    session_a = Session()
    session_b = Session()
    try:
        yield session_a, session_b
    finally:
        session_a.rollback()
        session_a.close()
        session_b.rollback()
        session_b.close()


@pytest.fixture
def seeded_department(two_sessions):
    from app.models.department import Department

    session_a, _ = two_sessions
    # Idempotent seeding: a previous test in this module may have committed
    # the same scratch key (the refusal pins deliberately leave the
    # department world as the race left it).
    session_a.execute(
        text("DELETE FROM departments WHERE key = :k"), {"k": "cardio-lock"}
    )
    session_a.commit()
    row = Department(
        key="cardio-lock",
        name_ru="Кардиология (lock pin)",
        name_uz="Kardiologiya",
        active=True,
    )
    session_a.add(row)
    session_a.commit()
    session_a.refresh(row)
    return int(row.id)


def test_lock_revalidation_sees_concurrent_deactivation(
    two_sessions, seeded_department
):
    """Booking A resolves (plain SELECT) → admin B deactivates + COMMITS →
    booking A's lock re-reads the COMMITTED state and refuses. Without
    ``populate_existing()`` the identity map served A's stale
    ``active=True`` and the re-validation was a no-op — the appointment was
    persisted against an inactive department."""
    from app.models.department import Department
    from app.services.appointment_slot_guard import lock_department_for_booking

    session_a, session_b = two_sessions

    # Booking transaction: the plain resolve (identity map now holds the row).
    resolved = (
        session_a.query(Department).filter(Department.id == seeded_department).first()
    )
    assert resolved.active is True, "harness sanity: seeded active"

    # Admin transaction: deactivate + COMMIT (the concurrent write wins the
    # race because it lands between A's resolve and A's lock).
    session_b.execute(
        text("UPDATE departments SET active = FALSE WHERE id = :i"),
        {"i": seeded_department},
    )
    session_b.commit()

    # The booking lock MUST see the committed state, not the snapshot.
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc:
        lock_department_for_booking(session_a, resolved)
    assert exc.value.status_code == 400
    assert exc.value.detail == {"reason": "department_inactive"}

    # The booking persisted nothing (the refusal happened before any INSERT;
    # A's rollback discards the transaction outright).
    session_a.rollback()
    count = session_b.execute(
        text("select count(*) from appointments where department_id = :i"),
        {"i": seeded_department},
    ).scalar()
    assert count == 0


def test_lock_revalidation_sees_concurrent_delete(two_sessions, seeded_department):
    """Admin B hard-deletes the department + commits between A's resolve
    and A's lock: a controlled 400 ``department_unknown`` — never a
    persisted appointment routed at a vanished department (FK/SET-NULL
    lottery)."""
    from app.models.department import Department
    from app.services.appointment_slot_guard import lock_department_for_booking

    session_a, session_b = two_sessions

    resolved = (
        session_a.query(Department).filter(Department.id == seeded_department).first()
    )
    assert resolved is not None

    session_b.execute(
        text("DELETE FROM departments WHERE id = :i"),
        {"i": seeded_department},
    )
    session_b.commit()

    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc:
        lock_department_for_booking(session_a, resolved)
    assert exc.value.status_code == 400
    assert exc.value.detail == {"reason": "department_unknown"}


def test_department_row_lock_serializes_deactivation_behind_booking(
    two_sessions, seeded_department
):
    """The lock is REAL on PostgreSQL: while the booking transaction holds
    the department row lock (not yet committed), the admin UPDATE must
    BLOCK (lock_timeout proof) and only proceed after the booking
    transaction finishes — deactivate/delete serialize BEHIND the booking
    instead of racing it."""
    from sqlalchemy.exc import OperationalError

    from app.models.department import Department
    from app.services.appointment_slot_guard import lock_department_for_booking

    session_a, session_b = two_sessions

    resolved = (
        session_a.query(Department).filter(Department.id == seeded_department).first()
    )
    locked = lock_department_for_booking(session_a, resolved)
    assert locked.active is True
    # session_a now HOLDS the row lock (uncommitted transaction).

    session_b.execute(text("SET LOCAL lock_timeout = '500ms'"))
    with pytest.raises(OperationalError):
        # Blocks on the booking transaction's row lock until the timeout.
        session_b.execute(
            text("UPDATE departments SET active = FALSE WHERE id = :i"),
            {"i": seeded_department},
        )
    session_b.rollback()

    # The booking transaction finishes (commit — the INSERT would follow;
    # here the empty transaction still releases the lock on commit).
    session_a.commit()

    # Only now the admin write proceeds.
    session_b.execute(
        text("UPDATE departments SET active = FALSE WHERE id = :i"),
        {"i": seeded_department},
    )
    session_b.commit()
    active_now = session_b.execute(
        text("select active from departments where id = :i"),
        {"i": seeded_department},
    ).scalar()
    assert active_now is False
