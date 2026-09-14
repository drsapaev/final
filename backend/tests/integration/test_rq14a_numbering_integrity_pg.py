"""
RQ-14.a — queue numbering integrity and queue-row identity on real
PostgreSQL (E-033 pin; ACCEPTANCE S-12 integrity half).

Defects being fixed (both live in ``queue_svc/_operations.py``):

1. Numbering race: ``get_next_queue_number`` takes ``FOR UPDATE`` on the
   queue row ONLY when the caller passes a ``queue_id``. Every live
   writer (QR ``join_queue_with_token``, desk wizard assignment, crud
   online-queue writers, batch, visit confirmation) passes an ALREADY
   LOADED ``daily_queue`` — that branch computed the next number with a
   plain ``SELECT MAX`` and NO lock, so two concurrent writers in one
   queue both read the same max and committed the SAME number (pinned by
   the E-033 characterization test). The per-queue uniqueness contract
   ("a number must not duplicate within one queue") was violated.

2. Queue-row fork: the doctor branch of ``get_or_create_daily_queue``
   selected ``(day, specialist_id)`` and INSERTed without any
   serialization; the 0063 partial unique covers only the resource axis
   ``(day, queue_resource_id)``, so two concurrent first arrivals forked
   TWO doctor-owned queue rows for the same key.

Fix (transactional only — NO migration: the 0064 revision slot is
occupied by three OPEN PRs (#3212, #3215, #3208); a revision parented on
0063 would fork the chain into multiple heads. The DB-level unique
indexes are registered as a deferred operator step in PROGRESS):

- the already-loaded branch takes the same ``FOR UPDATE`` row lock, so
  all writers of one queue serialize from the max-read until commit;
- the doctor branch of ``get_or_create_daily_queue`` takes a
  transaction-scoped ``pg_advisory_xact_lock`` keyed by
  (day, specialist_id) before the select (same pattern as the RQ-25.a.1
  patient-identity fix); the resource branch was already serialized by
  ``lock_registry_tag_creation``.

Contract preserved: numbers may repeat ACROSS queues (per-queue scope —
pinned); no renumbering/gap requirements introduced; RQ-14.b owner
identity waits for D-01 and is NOT touched here.

Deterministic race protocol (independent PG sessions + threads): each
writer allocates, signals an event, waits (bounded) for the other
writers' allocation events, and only then commits. On the defective code
every writer reads the same max before any commit -> duplicate numbers /
forked rows. With the fix the lock serializes allocation: latecomers
block INSIDE allocation until the first commit, so the wait times out
for the first writer and every number stays unique.

Disposable PostgreSQL: scratch database rq14a_check, ``alembic upgrade
head``, dropped at the end; skips (NOT_RUN per plan P0) without a local
server. SYNTHETIC data only.
"""

from __future__ import annotations

import os
import sys
import threading
from datetime import datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import psycopg
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker

BACKEND_DIR = Path(__file__).resolve().parents[2]
SCRATCH_DB = "rq14a_check"

sys.path.insert(0, str(BACKEND_DIR))


def _candidate_admin_urls() -> list[str]:
    urls: list[str] = []
    explicit = os.getenv("RQ14A_PG_ADMIN_URL", "").strip()
    if explicit:
        urls.append(explicit)
    local_pw = os.getenv("LOCAL_PG_SUPERUSER_PASSWORD", "").strip()
    if local_pw:
        urls.append(f"postgresql://postgres:{local_pw}@localhost:5432/postgres")
    env_url = os.getenv("DATABASE_URL", "").strip()
    if env_url:
        u = make_url(env_url)
        if (u.host or "") in {"localhost", "127.0.0.1", "::1"}:
            urls.append(
                f"postgresql://{u.username}:{u.password}@{u.host}:{u.port}/postgres"
            )
    return urls


def _scratch_url(admin_url: str) -> tuple[str, str]:
    u = make_url(admin_url)
    base = f"postgresql://{u.username}:{u.password}@{u.host}:{u.port}"
    return (
        f"{base}/{SCRATCH_DB}",
        f"postgresql+psycopg://{u.username}:{u.password}"
        f"@{u.host}:{u.port}/{SCRATCH_DB}",
    )


@pytest.fixture(scope="module")
def pg_engine():
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
            f"disposable PostgreSQL unavailable — RQ-14.a PG acceptance NOT_RUN "
            f"(last error: {last_error})"
        )

    psycopg_dsn, sa_url = _scratch_url(admin_url)
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
def pg_session(pg_engine):
    Session = sessionmaker(bind=pg_engine, future=True)
    session = Session()
    yield session
    session.rollback()
    session.close()


@pytest.fixture(autouse=True)
def _no_time_gate(monkeypatch):
    from app.services.queue_svc import QueueBusinessService
    from app.services.queue_svc._base import QueueBusinessServiceMixinBase

    monkeypatch.setattr(QueueBusinessService, "ONLINE_QUEUE_START_TIME", time(0, 0))
    monkeypatch.setattr(
        QueueBusinessServiceMixinBase, "ONLINE_QUEUE_START_TIME", time(0, 0)
    )


def _clinic_day():
    return datetime.now(ZoneInfo("Asia/Tashkent")).date()


def _make_user(session, username: str, role: str = "Doctor"):
    from app.core.security import get_password_hash
    from app.models.user import User

    user = User(
        username=username,
        email=f"{username}@example.com",
        full_name=f"RQ-14.a {username}",
        hashed_password=get_password_hash("rq14a-synthetic-pw"),
        role=role,
        is_active=True,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def _make_doctor(session, user_id: int):
    from app.models.clinic import Doctor

    doctor = Doctor(user_id=user_id, specialty="cardiology", cabinet="401", active=True)
    session.add(doctor)
    session.commit()
    session.refresh(doctor)
    return doctor


def _seed_world(session, suffix: str) -> dict:
    """Healthy doctor + doctor-owned DailyQueue + a doctor-scoped QR
    token on the clinic day."""
    from app.models.online_queue import DailyQueue, QueueToken

    user = _make_user(session, f"rq14a_doc_{suffix}")
    doctor = _make_doctor(session, user.id)
    day = _clinic_day()
    queue = DailyQueue(
        day=day,
        specialist_id=doctor.id,
        queue_tag="cardiology",
        active=True,
    )
    session.add(queue)
    session.commit()
    session.refresh(queue)

    local_now = datetime.now(ZoneInfo("Asia/Tashkent")).replace(tzinfo=None)
    token = QueueToken(
        token=f"rq14a-token-{suffix}",
        day=day,
        specialist_id=doctor.id,
        department="cardiology",
        expires_at=local_now + timedelta(hours=2),
        active=True,
    )
    session.add(token)
    session.commit()
    return {"doctor_id": doctor.id, "day": day, "queue_id": queue.id, "token": token.token}


def _queue_numbers(pg_engine, queue_id: int) -> list[int]:
    from app.models.online_queue import OnlineQueueEntry

    Session = sessionmaker(bind=pg_engine, future=True)
    session = Session()
    try:
        rows = (
            session.query(OnlineQueueEntry.number)
            .filter(OnlineQueueEntry.queue_id == queue_id)
            .all()
        )
        return sorted(r[0] for r in rows)
    finally:
        session.close()


def _queue_rows(pg_engine, day, specialist_id: int) -> list[int]:
    from app.models.online_queue import DailyQueue

    Session = sessionmaker(bind=pg_engine, future=True)
    session = Session()
    try:
        rows = (
            session.query(DailyQueue.id)
            .filter(
                DailyQueue.day == day,
                DailyQueue.specialist_id == specialist_id,
                DailyQueue.active.is_(True),
            )
            .all()
        )
        return sorted(r[0] for r in rows)
    finally:
        session.close()


def _desk_writer(pg_engine, queue_id: int, tag: str, marker: int, results, events, wait_s):
    """Desk seam: create_queue_entry (the SSOT numbering point) on its own
    session with the deterministic allocate-then-wait protocol."""
    from app.services.queue_svc import QueueBusinessService

    Session = sessionmaker(bind=pg_engine, future=True)
    session = Session()
    try:
        entry = QueueBusinessService().create_queue_entry(
            session,
            queue_id=queue_id,
            patient_name=f"SYNTHETIC-Race Desk {marker}",
            phone=f"+99890410000{marker:02d}",
            source="desk",
            auto_number=True,
        )
        results.append(("desk", entry.number))
    except Exception as exc:  # noqa: BLE001
        session.rollback()
        results.append(("desk-error", f"{type(exc).__name__}: {exc}"))
        return
    # Allocated (lock taken); signal and wait for the co-writers'
    # allocations so that on the defective code every max-read happens
    # before any commit.
    events[marker].set()
    others = [e for i, e in enumerate(events) if i != marker]
    for e in others:
        e.wait(timeout=wait_s)
    session.commit()
    session.close()


def _qr_writer(pg_engine, token: str, marker: int, results, events, wait_s):
    """QR seam: queue_service.join_queue_with_token on its own session."""
    from app.services.queue_service import queue_service

    Session = sessionmaker(bind=pg_engine, future=True)
    session = Session()
    try:
        result = queue_service.join_queue_with_token(
            session,
            token_str=token,
            patient_name=f"SYNTHETIC-Race QR {marker}",
            phone=f"+99890420000{marker:02d}",
            source="online",
        )
        results.append(("qr", result["entry"].number))
    except Exception as exc:  # noqa: BLE001
        session.rollback()
        results.append(("qr-error", f"{type(exc).__name__}: {exc}"))
        return
    events[marker].set()
    others = [e for i, e in enumerate(events) if i != marker]
    for e in others:
        e.wait(timeout=wait_s)
    session.commit()
    session.close()


def test_desk_and_qr_same_queue_get_distinct_numbers(pg_engine, pg_session):
    """(a) fail-first: one queue, a desk writer and a QR writer — the
    per-queue uniqueness contract requires DISTINCT numbers (the E-033
    race committed the same number)."""
    world = _seed_world(pg_session, "dq")

    n = 2
    events = [threading.Event() for _ in range(n)]
    results: list = []

    threads = [
        threading.Thread(
            target=_desk_writer,
            args=(pg_engine, world["queue_id"], "cardiology", 0, results, events, 8.0),
        ),
        threading.Thread(
            target=_qr_writer,
            args=(pg_engine, world["token"], 1, results, events, 8.0),
        ),
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=60)

    errors = [r for r in results if "error" in r[0]]
    assert not errors, errors
    numbers = [num for _, num in results]
    # THE CONTRACT: per-queue numbers must not duplicate.
    assert len(set(numbers)) == len(numbers), (
        f"duplicate numbers in ONE queue: {sorted(numbers)}"
    )
    assert _queue_numbers(pg_engine, world["queue_id"]) == sorted(numbers)


def test_multiple_concurrent_writers_all_unique(pg_engine, pg_session):
    """(b) four concurrent desk writers in ONE queue — all numbers
    distinct (per-queue uniqueness under load)."""
    world = _seed_world(pg_session, "multi")

    n = 4
    events = [threading.Event() for _ in range(n)]
    results: list = []
    threads = [
        threading.Thread(
            target=_desk_writer,
            args=(pg_engine, world["queue_id"], "cardiology", i, results, events, 15.0),
        )
        for i in range(n)
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=120)

    errors = [r for r in results if "error" in r[0]]
    assert not errors, errors
    numbers = [num for _, num in results]
    assert len(set(numbers)) == n, f"duplicates: {sorted(numbers)}"


def test_concurrent_get_or_create_single_queue_row(pg_engine, pg_session):
    """(c) fail-first: two first arrivals race get_or_create_daily_queue
    for the same (day, specialist_id) — exactly ONE doctor-owned row must
    exist (the 0063 partial unique covers only the resource axis)."""
    from app.models.online_queue import DailyQueue
    from app.services.queue_svc import QueueBusinessService

    user = _make_user(pg_session, "rq14a_fork_doc")
    doctor = _make_doctor(pg_session, user.id)
    day = _clinic_day()

    Session = sessionmaker(bind=pg_engine, future=True)
    results: list = []
    barrier = threading.Barrier(2, timeout=20)

    def _forker():
        session = Session()
        try:
            barrier.wait()
            q = QueueBusinessService().get_or_create_daily_queue(
                session, day=day, specialist_id=doctor.id, queue_tag="cardiology"
            )
            results.append(q.id)
            session.commit()
        except Exception as exc:  # noqa: BLE001
            session.rollback()
            results.append(f"error: {type(exc).__name__}: {exc}")
        finally:
            session.close()

    t1 = threading.Thread(target=_forker)
    t2 = threading.Thread(target=_forker)
    t1.start()
    t2.start()
    t1.join(timeout=60)
    t2.join(timeout=60)

    row_ids = [r for r in results if isinstance(r, int)]
    assert len(row_ids) == 2, results
    # THE CONTRACT: one doctor-owned (day, specialist) row.
    assert len(set(row_ids)) == 1, f"forked queue rows: {results}"
    assert _queue_rows(pg_engine, day, doctor.id) == sorted(set(row_ids))


def test_numbers_may_repeat_across_queues(pg_engine, pg_session):
    """(d) per-queue scope pin: two DIFFERENT queues may independently
    start from the same number — no clinic-wide uniqueness is introduced."""
    from app.models.online_queue import DailyQueue
    from app.services.queue_svc import QueueBusinessService

    day = _clinic_day()

    Session = sessionmaker(bind=pg_engine, future=True)
    numbers = []
    for i in range(2):
        # Two DIFFERENT doctors -> two independent queues; per-queue
        # numbering may produce equal numbers (clinic-wide uniqueness
        # would be a NEW requirement and is explicitly not introduced).
        user = _make_user(pg_session, f"rq14a_two_doc_{i}")
        doctor = _make_doctor(pg_session, user.id)
        session = Session()
        q = QueueBusinessService().get_or_create_daily_queue(
            session, day=day, specialist_id=doctor.id, queue_tag="cardiology"
        )
        entry = QueueBusinessService().create_queue_entry(
            session,
            daily_queue=q,
            patient_name="SYNTHETIC-TwoQueues Patient",
            phone="+998904300001",
            source="desk",
            auto_number=True,
        )
        numbers.append(entry.number)
        session.commit()
        session.close()

    assert numbers[0] == numbers[1], (
        f"per-queue numbering must be independent: {numbers}"
    )


def test_failed_writer_does_not_disturb_numbering(pg_engine, pg_session):
    """(e) rollback/retry: a writer that fails mid-transaction (ghost
    refusal) must not consume or corrupt the number sequence; the next
    writer continues the sequence without duplicates."""
    from app.models.online_queue import DailyQueue
    from app.services.queue_svc import QueueBusinessService, QueueValidationError

    user = _make_user(pg_session, "rq14a_seq_doc")
    doctor = _make_doctor(pg_session, user.id)
    day = _clinic_day()

    Session = sessionmaker(bind=pg_engine, future=True)

    # A writer whose queue resolution fails (unknown doctor) — the row
    # lock it takes (if any) must be released by the rollback.
    session = Session()
    try:
        QueueBusinessService().get_or_create_daily_queue(
            session, day=day, specialist_id=999999, queue_tag="cardiology"
        )
        raise AssertionError("unknown doctor must be refused")
    except ValueError:
        session.rollback()
    finally:
        session.close()

    session = Session()
    try:
        q = QueueBusinessService().get_or_create_daily_queue(
            session, day=day, specialist_id=doctor.id, queue_tag="cardiology"
        )
        e1 = QueueBusinessService().create_queue_entry(
            session,
            daily_queue=q,
            patient_name="SYNTHETIC-Seq One",
            phone="+998904400001",
            source="desk",
            auto_number=True,
        )
        e2 = QueueBusinessService().create_queue_entry(
            session,
            daily_queue=q,
            patient_name="SYNTHETIC-Seq Two",
            phone="+998904400002",
            source="desk",
            auto_number=True,
        )
        assert e2.number != e1.number
        session.commit()
    finally:
        session.close()
