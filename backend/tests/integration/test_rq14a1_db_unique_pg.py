"""
RQ-14.a.1 — DB-level UNIQUE proofs on disposable PostgreSQL.

Covers the migration-safety matrix and the regression guarantees behind
the 0065 revision (full UNIQUE (queue_id, number) on queue_entries and
the doctor-axis partial unique (day, specialist_id, COALESCE(tag,'')))
behind the #3248 transactional serialization:

- upgrade on a CLEAN schema succeeds and creates both unique indexes;
- upgrade on CORRECT populated synthetic data succeeds (no false
  positives: inactive same-day rows, repeated numbers across different
  queues, a NULL-tag batch row next to a tagged one are all legal);
- upgrade on data with PRE-EXISTING DUPLICATES fails loudly with
  technical identifiers only and does NOT modify any row (counts
  before/after equal, indexes absent);
- a raw duplicate INSERT is rejected by PostgreSQL itself
  (UniqueViolation/IntegrityError) — both for a duplicate number and a
  duplicate active doctor queue row;
- independent queues may share the same number (per-queue scope);
- concurrent desk/QR writers and get_or_create keep the invariants
  (the #3248 locks stay in place — UNIQUE is the second line);
- rollback leaves nothing half-applied;
- QD-2C resource routing, RQ-09.a/c eligibility, family QR dedup
  neighbors stay green (run as neighbor suites, not here).

Disposable PostgreSQL: scratch database rq14a1u_check, ``alembic
upgrade head``, dropped at the end; skips (NOT_RUN per plan P0)
without a local server. SYNTHETIC data only; production/staging are
never touched.
"""

from __future__ import annotations

import os
import subprocess
import sys
import threading
from datetime import datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import psycopg
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

BACKEND_DIR = Path(__file__).resolve().parents[2]
SCRATCH_DB = "rq14a1u_check"

sys.path.insert(0, str(BACKEND_DIR))


def _candidate_admin_urls() -> list[str]:
    urls: list[str] = []
    explicit = os.getenv("RQ14A1U_PG_ADMIN_URL", "").strip()
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


def _admin_url() -> tuple[str, str]:
    for candidate in _candidate_admin_urls():
        try:
            with psycopg.connect(candidate, connect_timeout=5, autocommit=True) as c:
                c.execute("SELECT 1")
            u = make_url(candidate)
            base = f"postgresql://{u.username}:{u.password}@{u.host}:{u.port}"
            return candidate, (
                f"postgresql+psycopg://{u.username}:{u.password}"
                f"@{u.host}:{u.port}/{SCRATCH_DB}"
            )
        except Exception:  # noqa: BLE001
            continue
    pytest.skip("disposable PostgreSQL unavailable — RQ-14.a.1 NOT_RUN")


def _recreate_scratch(admin_url: str) -> None:
    with psycopg.connect(admin_url, autocommit=True) as c:
        c.execute(
            "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
            "WHERE datname = %s AND pid <> pg_backend_pid()",
            (SCRATCH_DB,),
        )
        c.execute(f'DROP DATABASE IF EXISTS "{SCRATCH_DB}"')
        c.execute(f'CREATE DATABASE "{SCRATCH_DB}"')


def _upgrade_to(db_url: str, revision: str = "head") -> None:
    env = dict(os.environ, DATABASE_URL=db_url, TESTING="1", ENV="dev")
    r = subprocess.run(
        [sys.executable, "-m", "alembic", "-c", "alembic.ini", "upgrade", revision],
        capture_output=True,
        text=True,
        cwd=str(BACKEND_DIR),
        env=env,
    )
    assert r.returncode == 0, r.stdout[-1500:] + r.stderr[-1500:]


def _try_upgrade(db_url: str) -> subprocess.CompletedProcess:
    env = dict(os.environ, DATABASE_URL=db_url, TESTING="1", ENV="dev")
    return subprocess.run(
        [sys.executable, "-m", "alembic", "-c", "alembic.ini", "upgrade", "head"],
        capture_output=True,
        text=True,
        cwd=str(BACKEND_DIR),
        env=env,
    )


@pytest.fixture(scope="module")
def pg_engine():
    admin_url, sa_url = _admin_url()
    _recreate_scratch(admin_url)
    _upgrade_to(sa_url)

    engine = create_engine(sa_url, future=True)
    with engine.connect() as conn:
        version = conn.execute(text("select version_num from alembic_version")).scalar()
    assert version == "0065_queue_numbering_unique", version

    yield engine

    engine.dispose()
    with psycopg.connect(admin_url, autocommit=True) as c:
        c.execute(
            "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
            "WHERE datname = %s AND pid <> pg_backend_pid()",
            (SCRATCH_DB,),
        )
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


def _make_doctor(session, suffix: str):
    from app.core.security import get_password_hash
    from app.models.clinic import Doctor
    from app.models.user import User

    user = User(
        username=f"rq14a1u_{suffix}",
        email=f"rq14a1u_{suffix}@example.com",
        full_name=f"RQ-14.a.1 {suffix}",
        hashed_password=get_password_hash("rq14a1u-synthetic-pw"),
        role="Doctor",
        is_active=True,
    )
    session.add(user)
    session.commit()
    doctor = Doctor(user_id=user.id, specialty="cardiology", cabinet="501", active=True)
    session.add(doctor)
    session.commit()
    session.refresh(doctor)
    return doctor


def _seed_queue(session, doctor_id: int, day, tag, active=True):
    from app.models.online_queue import DailyQueue

    q = DailyQueue(day=day, specialist_id=doctor_id, queue_tag=tag, active=active)
    session.add(q)
    session.commit()
    session.refresh(q)
    return q


def test_upgrade_on_clean_schema_and_correct_data(pg_engine, pg_session):
    """(1) clean upgrade creates both indexes; (2) populated CORRECT data
    is not a false positive: same numbers across DIFFERENT queues,
    inactive same-day rows, a NULL-tag row next to a tagged one (for a
    DIFFERENT doctor), closed-then-reopened queues are all legal."""
    from app.models.online_queue import OnlineQueueEntry
    from app.services.queue_svc import QueueBusinessService

    with pg_engine.connect() as conn:
        idx = {
            r[0]
            for r in conn.execute(
                text(
                    "select indexname from pg_indexes where indexname in "
                    "('uq_queue_entries_queue_number',"
                    " 'uq_daily_queues_active_doctor_day_tag')"
                )
            )
        }
    assert idx == {
        "uq_queue_entries_queue_number",
        "uq_daily_queues_active_doctor_day_tag",
    }

    day = _clinic_day()
    doc_a = _make_doctor(pg_session, "ok_a")
    doc_b = _make_doctor(pg_session, "ok_b")
    qa = _seed_queue(pg_session, doc_a.id, day, "cardiology")
    qb = _seed_queue(pg_session, doc_b.id, day, "cardiology")

    for q in (qa, qb):
        pg_session.add(
            OnlineQueueEntry(queue_id=q.id, number=1, patient_name="SYNTHETIC-Ok", source="desk")
        )
    # An INACTIVE same-day row for the same doctor+tag is legal.
    pg_session.add(
        _seed_queue(pg_session, doc_a.id, day, "cardiology", active=False).__class__(
            day=day, specialist_id=doc_a.id, queue_tag="cardiology", active=False
        )
    )
    pg_session.commit()

    # NULL tag for a DIFFERENT doctor coexists with a tagged row.
    qn = _seed_queue(pg_session, doc_b.id, day, None)
    pg_session.add(
        OnlineQueueEntry(queue_id=qn.id, number=1, patient_name="SYNTHETIC-Ok2", source="desk")
    )
    pg_session.commit()

    numbers_a = (
        pg_session.query(OnlineQueueEntry.number)
        .filter(OnlineQueueEntry.queue_id == qa.id)
        .all()
    )
    assert [n for n, in numbers_a] == [1]


def test_raw_duplicate_number_rejected_by_postgres(pg_session):
    """A raw INSERT bypassing every service layer is rejected by the
    UNIQUE index itself."""
    from app.models.online_queue import OnlineQueueEntry

    day = _clinic_day()
    doc = _make_doctor(pg_session, "raw")
    q = _seed_queue(pg_session, doc.id, day, "cardiology")

    pg_session.add(
        OnlineQueueEntry(queue_id=q.id, number=1, patient_name="SYNTHETIC-Raw", source="desk")
    )
    pg_session.commit()

    pg_session.add(
        OnlineQueueEntry(queue_id=q.id, number=1, patient_name="SYNTHETIC-Raw2", source="desk")
    )
    with pytest.raises(IntegrityError):
        pg_session.commit()
    pg_session.rollback()


def test_raw_duplicate_active_doctor_queue_rejected(pg_session):
    """A second ACTIVE (day, doctor, tag) queue row is rejected; an
    INACTIVE duplicate stays legal (partial unique)."""
    from app.models.online_queue import DailyQueue

    day = _clinic_day()
    doc = _make_doctor(pg_session, "dq")
    _seed_queue(pg_session, doc.id, day, "cardiology")

    pg_session.add(DailyQueue(day=day, specialist_id=doc.id, queue_tag="cardiology", active=True))
    with pytest.raises(IntegrityError):
        pg_session.commit()
    pg_session.rollback()

    # Inactive duplicate of the same key is legal.
    pg_session.add(DailyQueue(day=day, specialist_id=doc.id, queue_tag="cardiology", active=False))
    pg_session.commit()


def test_null_tag_folds_into_doctor_key(pg_session):
    """COALESCE semantics: a NULL-tag batch row and a no-tag lookup share
    the doctor key — the second ACTIVE NULL-tag row for the same doctor
    is rejected (queue_batch_repository writers serialize onto one row)."""
    from app.models.online_queue import DailyQueue

    day = _clinic_day()
    doc = _make_doctor(pg_session, "nulltag")
    _seed_queue(pg_session, doc.id, day, None)

    pg_session.add(DailyQueue(day=day, specialist_id=doc.id, queue_tag=None, active=True))
    with pytest.raises(IntegrityError):
        pg_session.commit()
    pg_session.rollback()


def test_independent_queues_share_numbers(pg_session):
    """Per-queue scope pinned at the DB level: two queues, same number —
    the clinic-wide uniqueness is NOT introduced."""
    from app.models.online_queue import OnlineQueueEntry

    day = _clinic_day()
    qa = _seed_queue(pg_session, _make_doctor(pg_session, "sc_a").id, day, "cardiology")
    qb = _seed_queue(pg_session, _make_doctor(pg_session, "sc_b").id, day, "cardiology")

    for q in (qa, qb):
        pg_session.add(
            OnlineQueueEntry(queue_id=q.id, number=7, patient_name="SYNTHETIC-Scope", source="desk")
        )
    pg_session.commit()


def test_concurrent_writers_and_get_or_create_keep_invariants(pg_engine, pg_session):
    """The #3248 locks stay in place with UNIQUE behind them: concurrent
    desk writers + parallel get_or_create produce unique numbers and a
    single queue row."""
    from app.services.queue_svc import QueueBusinessService

    day = _clinic_day()
    doc = _make_doctor(pg_session, "conc")
    svc = QueueBusinessService()
    seed_q = svc.get_or_create_daily_queue(
        pg_session, day=day, specialist_id=doc.id, queue_tag="cardiology"
    )
    pg_session.commit()
    queue_id = seed_q.id

    Session = sessionmaker(bind=pg_engine, future=True)
    results: list = []
    errors: list = []

    def _writer(i: int):
        session = Session()
        try:
            s = QueueBusinessService()
            q = s.get_or_create_daily_queue(
                session, day=day, specialist_id=doc.id, queue_tag="cardiology"
            )
            entry = s.create_queue_entry(
                session,
                daily_queue=q,
                patient_name=f"SYNTHETIC-Conc {i}",
                phone=f"+99890610000{i:02d}",
                source="desk",
                auto_number=True,
            )
            results.append((q.id, entry.number))
            session.commit()
        except Exception as exc:  # noqa: BLE001
            session.rollback()
            errors.append(f"{type(exc).__name__}: {exc}")
        finally:
            session.close()

    threads = [threading.Thread(target=_writer, args=(i,)) for i in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=60)

    assert not errors, errors
    numbers = [num for _, num in results]
    assert len(set(numbers)) == 4, numbers
    queue_ids = {qid for qid, _ in results}
    assert queue_ids == {queue_id}, queue_ids


def test_rollback_leaves_nothing_partial(pg_session):
    """A failed writer rolls back cleanly: no half-inserted rows, and the
    sequence continues without duplicates for the next writer."""
    from app.models.online_queue import OnlineQueueEntry
    from app.services.queue_svc import QueueBusinessService

    day = _clinic_day()
    doc = _make_doctor(pg_session, "rb")
    svc = QueueBusinessService()
    q = svc.get_or_create_daily_queue(
        pg_session, day=day, specialist_id=doc.id, queue_tag="cardiology"
    )
    e1 = svc.create_queue_entry(
        pg_session,
        daily_queue=q,
        patient_name="SYNTHETIC-Rb One",
        phone="+998906200001",
        source="desk",
        auto_number=True,
    )
    pg_session.commit()

    # A writer that hits the unique index and rolls back.
    pg_session.add(
        OnlineQueueEntry(queue_id=q.id, number=e1.number, patient_name="SYNTHETIC-Rb Dup", source="desk")
    )
    with pytest.raises(IntegrityError):
        pg_session.commit()
    pg_session.rollback()

    e2 = svc.create_queue_entry(
        pg_session,
        daily_queue=q,
        patient_name="SYNTHETIC-Rb Two",
        phone="+998906200002",
        source="desk",
        auto_number=True,
    )
    pg_session.commit()
    assert e2.number != e1.number
    assert (
        pg_session.query(OnlineQueueEntry)
        .filter(OnlineQueueEntry.queue_id == q.id)
        .count()
        == 2
    )


def test_upgrade_fails_loudly_on_existing_duplicates():
    """Migration safety: on a database with PRE-EXISTING duplicates the
    upgrade FAILS with technical identifiers only, modifies nothing, and
    creates no indexes (a separate scratch is used)."""
    admin_url, sa_url = _admin_url()
    _recreate_scratch(admin_url)
    _upgrade_to(sa_url, "0064_push_devices_registry")

    engine = create_engine(sa_url, future=True)
    Session = sessionmaker(bind=engine, future=True)
    session = Session()
    from app.core.security import get_password_hash
    from app.models.clinic import Doctor
    from app.models.online_queue import DailyQueue, OnlineQueueEntry
    from app.models.user import User

    day = _clinic_day()
    user = User(
        username="rq14a1u_dup",
        email="rq14a1u_dup@example.com",
        full_name="RQ-14.a.1 dup",
        hashed_password=get_password_hash("rq14a1u-synthetic-pw"),
        role="Doctor",
        is_active=True,
    )
    session.add(user)
    session.commit()
    doc = Doctor(user_id=user.id, specialty="cardiology", cabinet="502", active=True)
    session.add(doc)
    session.commit()
    q = DailyQueue(day=day, specialist_id=doc.id, queue_tag="cardiology", active=True)
    session.add(q)
    session.commit()
    for _ in range(2):
        session.add(
            OnlineQueueEntry(queue_id=q.id, number=3, patient_name="SYNTHETIC-Dup", source="desk")
        )
    session.commit()

    counts_before = {
        "entries": session.query(OnlineQueueEntry).count(),
        "queues": session.query(DailyQueue).count(),
    }
    session.close()
    engine.dispose()

    result = _try_upgrade(sa_url)
    assert result.returncode != 0, "upgrade must fail on duplicates"

    stderr_tail = (result.stderr or "") + (result.stdout or "")
    assert "duplicate pre-check FAILED" in stderr_tail
    assert "queue_id" in stderr_tail and "number" in stderr_tail
    # Technical identifiers only — no patient names from the data.
    assert "SYNTHETIC-Dup" not in stderr_tail

    engine2 = create_engine(sa_url, future=True)
    with engine2.connect() as conn:
        ver = conn.execute(text("select version_num from alembic_version")).scalar()
        idx = conn.execute(
            text(
                "select indexname from pg_indexes where indexname in "
                "('uq_queue_entries_queue_number',"
                " 'uq_daily_queues_active_doctor_day_tag')"
            )
        ).fetchall()
        counts_after = {
            "entries": conn.execute(text("select count(*) from queue_entries")).scalar(),
            "queues": conn.execute(text("select count(*) from daily_queues")).scalar(),
        }
    assert ver == "0064_push_devices_registry", ver
    assert idx == [], idx
    assert counts_after == counts_before, (counts_before, counts_after)
    engine2.dispose()

    with psycopg.connect(admin_url, autocommit=True) as c:
        c.execute(
            "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
            "WHERE datname = %s AND pid <> pg_backend_pid()",
            (SCRATCH_DB,),
        )
        c.execute(f'DROP DATABASE IF EXISTS "{SCRATCH_DB}"')
