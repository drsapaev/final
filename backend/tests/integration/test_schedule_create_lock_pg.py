"""#3402 review round (owner P2-2): the schedule-create write boundary is
transactional — the doctor (if any) and department rows are re-read with
``populate_existing().with_for_update()`` in the CREATE transaction
(canonical lock order DOCTOR → DEPARTMENT, the booking path's order), the
active/eligibility/consistency checks run on the LOCKED rows, and the
INSERT + COMMIT happen on the same transaction.

Two-session PostgreSQL pins (SQLite silently drops FOR UPDATE and cannot
reproduce cross-transaction interleaving — these proofs are NOT_RUN on
SQLite, per the repo's disposable-PostgreSQL doctrine):

1. ``test_schedule_create_lock_blocks_concurrent_deactivation`` — the
   review's exact race: T1 runs the REAL ``create_template`` endpoint;
   while T1's transaction holds the department row lock (the INSERT is
   flushed but NOT yet committed), T2's admin ``UPDATE departments SET
   active = FALSE`` must BLOCK (lock_timeout proof) and only proceed after
   T1 commits — the deactivation serializes BEHIND the create, so the
   published route was valid when created. Without the lock the
   deactivation committed in between and the template advertised an
   INACTIVE department (the exact outcome this PR closes).
2. ``test_schedule_create_refuses_deactivation_committed_before_lock`` —
   the inverse interleaving: T2's deactivation COMMITS before T1's lock —
   the create must then answer the COMMITTED state (400
   ``department_inactive``) and persist nothing.
3. ``test_schedule_create_doctor_lock_serializes_doctor_deactivation`` —
   the doctor leg of the same boundary: while T1 holds the DOCTOR row
   lock, T2's ``UPDATE doctors SET active = FALSE`` blocks until T1
   commits.

The endpoint is invoked directly (``asyncio.run(create_template(...))``)
with a production-like session per transaction; the blocking probe runs
INSIDE a ``crud.create_schedule`` wrapper — the only point where T1's
transaction provably holds both row locks and has not yet committed.
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path
from types import SimpleNamespace

import psycopg
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import sessionmaker

BACKEND_DIR = Path(__file__).resolve().parents[2]
SCRATCH_DB = "schedule_create_lock"

sys.path.insert(0, str(BACKEND_DIR))


def _candidate_admin_urls() -> list[str]:
    """Admin DSNs for scratch provisioning — LOCAL servers only.

    The scratch database must never be created on a remote/production
    server, so DATABASE_URL-derived candidates are accepted only for
    localhost/127.0.0.1 hosts (a pgserver unix-socket DSN passes as-is).
    """
    urls: list[str] = []

    explicit = os.getenv("SCHEDULE_CREATE_LOCK_PG_ADMIN_URL", "").strip()
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
            f"disposable PostgreSQL unavailable — schedule create-lock "
            f"PG acceptance NOT_RUN (last error: {last_error})"
        )

    psycopg_dsn, sa_url = _scratch_urls(admin_url)
    with psycopg.connect(admin_url, autocommit=True) as c:
        c.execute(f'DROP DATABASE IF EXISTS "{SCRATCH_DB}"')
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
        c.execute(f'DROP DATABASE IF EXISTS "{SCRATCH_DB}"')


@pytest.fixture
def two_sessions(pg_engine):
    """TWO independent sessions on the scratch database — the schedule
    create transaction (A) and the admin transaction (B)."""
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
    # department world as the race left it). ORM inserts carry the model
    # defaults for the NOT NULL columns (display_order, ...).
    session_a.execute(
        text(
            "DELETE FROM schedule_templates WHERE department_id IN "
            "(SELECT id FROM departments WHERE key = :k)"
        ),
        {"k": "sched-lock"},
    )
    session_a.execute(
        text("DELETE FROM departments WHERE key = :k"), {"k": "sched-lock"}
    )
    session_a.commit()
    row = Department(
        key="sched-lock",
        name_ru="Кардиология (sched lock pin)",
        name_uz="Kardiologiya",
        active=True,
    )
    session_a.add(row)
    session_a.commit()
    session_a.refresh(row)
    return int(row.id)


@pytest.fixture
def seeded_doctor(two_sessions):
    """An ELIGIBLE doctor (active, real specialty, active owner with a
    doctor-family role) — the create must survive the eligibility gate and
    hold the DOCTOR row lock."""
    from app.models.clinic import Doctor
    from app.models.user import User

    session_a, _ = two_sessions
    session_a.execute(
        text(
            "DELETE FROM doctors WHERE user_id IN "
            "(SELECT id FROM users WHERE username = :u)"
        ),
        {"u": "sched_lock_owner"},
    )
    session_a.execute(
        text("DELETE FROM users WHERE username = :u"), {"u": "sched_lock_owner"}
    )
    session_a.commit()
    owner = User(
        username="sched_lock_owner",
        email="sched_lock_owner@test.invalid",
        hashed_password="not-a-real-hash",
        role="Doctor",
        is_active=True,
        is_superuser=False,
    )
    session_a.add(owner)
    session_a.flush()
    doctor = Doctor(
        user_id=owner.id,
        specialty="Кардиология",
        active=True,
    )
    session_a.add(doctor)
    session_a.commit()
    session_a.refresh(doctor)
    return int(doctor.id)


def _run_create_template(session_a, **payload_kwargs):
    """Invoke the REAL endpoint on session A (production-like: the request
    owns its session and commits inside the call)."""
    from app.api.v1.endpoints.schedule import create_template
    from app.schemas.schedule import ScheduleCreateIn

    payload = ScheduleCreateIn(**payload_kwargs)

    async def _call():
        return await create_template(
            payload=payload,
            db=session_a,
            user=SimpleNamespace(id=1, username="admin", role="Admin"),
        )

    return asyncio.run(_call())


def test_schedule_create_lock_blocks_concurrent_deactivation(
    two_sessions, seeded_department, monkeypatch
):
    """T1 = the real create endpoint; while its transaction holds the
    department row lock (INSERT flushed, NOT committed), T2's admin
    deactivation must BLOCK until T1 commits (lock_timeout proof) —
    deactivate serializes BEHIND the create."""
    import app.crud.schedule as schedule_crud

    session_a, session_b = two_sessions

    probe: dict = {}
    original = schedule_crud.create_schedule

    def probing_create(db, **kwargs):
        row = original(db, **kwargs)
        # T1 now HOLDS the department row lock (uncommitted transaction).
        session_b.execute(text("SET LOCAL lock_timeout = '500ms'"))
        try:
            session_b.execute(
                text("UPDATE departments SET active = FALSE WHERE id = :i"),
                {"i": seeded_department},
            )
        except OperationalError:
            probe["blocked"] = True
        finally:
            session_b.rollback()
        return row

    monkeypatch.setattr(schedule_crud, "create_schedule", probing_create)

    row = _run_create_template(
        session_a,
        department="sched-lock",
        weekday=1,
        start_time="08:00",
        end_time="10:00",
        active=True,
    )
    assert probe.get("blocked") is True, (
        "the admin deactivation must BLOCK on the create transaction's "
        "department row lock — a plain-SELECT check is not atomic with the INSERT"
    )
    assert row.id is not None

    # The endpoint committed → the template SURVIVED (created while the
    # department was still active — serialization, not corruption).
    persisted = session_b.execute(
        text("SELECT count(*) FROM schedule_templates WHERE id = :i"),
        {"i": int(row.id)},
    ).scalar()
    assert persisted == 1

    # Only now the admin write proceeds (and commits).
    session_b.execute(
        text("UPDATE departments SET active = FALSE WHERE id = :i"),
        {"i": seeded_department},
    )
    session_b.commit()
    active_now = session_b.execute(
        text("SELECT active FROM departments WHERE id = :i"),
        {"i": seeded_department},
    ).scalar()
    assert active_now is False


def test_schedule_create_refuses_deactivation_committed_before_lock(
    two_sessions, seeded_department
):
    """Inverse interleaving: the deactivation COMMITS before T1's lock —
    the locked re-read answers the committed state (400
    ``department_inactive``) and the create persists nothing."""
    session_a, session_b = two_sessions

    session_b.execute(
        text("UPDATE departments SET active = FALSE WHERE id = :i"),
        {"i": seeded_department},
    )
    session_b.commit()

    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc:
        _run_create_template(
            session_a,
            department="sched-lock",
            weekday=2,
            start_time="09:00",
            end_time="11:00",
            active=True,
        )
    assert exc.value.status_code == 400
    assert exc.value.detail == {"reason": "department_inactive"}

    session_a.rollback()
    orphans = session_b.execute(
        text("SELECT count(*) FROM schedule_templates WHERE department_id = :i"),
        {"i": seeded_department},
    ).scalar()
    assert orphans == 0, "a refused create persists nothing"


def test_schedule_create_doctor_lock_serializes_doctor_deactivation(
    two_sessions, seeded_department, seeded_doctor, monkeypatch
):
    """The DOCTOR leg of the boundary: while T1 holds the doctor row lock
    (INSERT flushed, NOT committed), T2's ``UPDATE doctors SET active =
    FALSE`` must BLOCK until T1 commits."""
    import app.crud.schedule as schedule_crud

    session_a, session_b = two_sessions

    probe: dict = {}
    original = schedule_crud.create_schedule

    def probing_create(db, **kwargs):
        row = original(db, **kwargs)
        session_b.execute(text("SET LOCAL lock_timeout = '500ms'"))
        try:
            session_b.execute(
                text("UPDATE doctors SET active = FALSE WHERE id = :i"),
                {"i": seeded_doctor},
            )
        except OperationalError:
            probe["blocked"] = True
        finally:
            session_b.rollback()
        return row

    monkeypatch.setattr(schedule_crud, "create_schedule", probing_create)

    row = _run_create_template(
        session_a,
        department=None,
        doctor_id=seeded_doctor,
        weekday=3,
        start_time="10:00",
        end_time="12:00",
        active=True,
    )
    assert probe.get("blocked") is True, (
        "the doctor deactivation must BLOCK on the create transaction's "
        "doctor row lock"
    )
    persisted = session_b.execute(
        text("SELECT count(*) FROM schedule_templates WHERE id = :i"),
        {"i": int(row.id)},
    ).scalar()
    assert persisted == 1

    session_b.execute(
        text("UPDATE doctors SET active = FALSE WHERE id = :i"),
        {"i": seeded_doctor},
    )
    session_b.commit()
    active_now = session_b.execute(
        text("SELECT active FROM doctors WHERE id = :i"),
        {"i": seeded_doctor},
    ).scalar()
    assert active_now is False
