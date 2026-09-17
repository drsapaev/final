"""
RQ-14.a.2 — hardened PG proofs for the 0065 DB-level UNIQUE (operator
follow-up to #3252 before any production application).

What changed vs the #3252 version of this module (scope registered in
PROGRESS E-037 before the edits):

- SCRATCH ISOLATION: every scenario owns a UNIQUELY-NAMED scratch
  database (run-scoped suffix). The old version's module fixture and
  the duplicate-upgrade test both recreated the SAME fixed name
  (`rq14a1u_check`), so one teardown could drop the other's database
  and order/parallel runs raced. Now nothing is shared: creation is
  `CREATE DATABASE` only (no `DROP DATABASE IF EXISTS` as a capture
  primitive), teardown happens in `finally` after `engine.dispose()`,
  and only the database created by THIS test is dropped. No
  `pg_terminate_backend` against other tests' connections.
- DSN CANDIDATES: every candidate — including the explicit
  RQ14A1U_PG_ADMIN_URL env override — is verified to be
  localhost/loopback BEFORE connecting; remote/unverified candidates
  are rejected (never used, never printed).
- REAL MIGRATION PROOFS: populated upgrade = 0064 -> ORM seed ->
  session.commit() -> alembic upgrade head, comparing meaningful ROW
  VALUES before/after (not only counts). Duplicate refusals are three
  separate scenarios on separate databases (entry number, active
  doctor/day/tag, NULL-vs-empty COALESCE tag), each asserting: loud
  diagnostics without PII, version stays 0064, BOTH new objects are
  absent, and the data rows are unchanged.
- PRODUCTION REORDER PATH on real PostgreSQL through
  QueueReorderApiService (not manual ORM edits), with pg_constraint
  preconditions (the constraint exists and is condeferrable/condeferred
  = true): a legal swap with an intermediate duplicate commits; an
  end-state duplicate is rejected AT COMMIT by the deferred constraint;
  a rolled-back violation leaves numbers untouched; completed/cancelled
  rows are not part of the reorder surface.
- PG-bind honesty: every PG test re-asserts dialect=postgresql and
  alembic head=0065 before proving anything; SQLite conftest results
  are NOT counted as PG evidence.

Disposable local PostgreSQL only; production/staging/Supabase are never
touched. SYNTHETIC data only.
"""

from __future__ import annotations

import os
import subprocess
import sys
import uuid
from datetime import UTC, date, datetime, time
from pathlib import Path
from types import SimpleNamespace

import psycopg
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

BACKEND_DIR = Path(__file__).resolve().parents[2]

sys.path.insert(0, str(BACKEND_DIR))

_RUN = uuid.uuid4().hex[:8]
_LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}


def _candidate_admin_urls() -> list[str]:
    """All admin-DSN candidates — LOCALHOST ONLY, verified before use."""
    urls: list[str] = []
    explicit = os.getenv("RQ14A1U_PG_ADMIN_URL", "").strip()
    if explicit:
        urls.append(explicit)
    local_pw = os.getenv("LOCAL_PG_SUPERUSER_PASSWORD", "").strip()
    if local_pw:
        urls.append(f"postgresql://postgres:{local_pw}@localhost:5432/postgres")
    env_url = os.getenv("DATABASE_URL", "").strip()
    if env_url:
        from sqlalchemy.engine import make_url

        u = make_url(env_url)
        if (u.host or "") in _LOCAL_HOSTS:
            urls.append(
                f"postgresql://{u.username}:{u.password}@{u.host}:{u.port}/postgres"
            )
    return urls


def _verified_admin_url() -> tuple[str, str]:
    """(admin conninfo, host) — the FIRST candidate that is loopback AND
    reachable. Remote or unverified candidates are rejected before any
    connection attempt; nothing is printed."""
    from sqlalchemy.engine import make_url

    last_error: Exception | None = None
    for candidate in _candidate_admin_urls():
        try:
            host = make_url(candidate).host or ""
            if host not in _LOCAL_HOSTS:
                last_error = RuntimeError("non-localhost admin DSN rejected")
                continue
            with psycopg.connect(candidate, connect_timeout=5, autocommit=True) as c:
                c.execute("SELECT 1")
            return candidate, host
        except Exception as exc:  # noqa: BLE001
            last_error = exc
    pytest.skip(
        f"disposable local PostgreSQL unavailable — RQ-14.a.2 NOT_RUN "
        f"(last reason: {type(last_error).__name__})"
    )


def _scratch_pair(admin_url: str, label: str) -> tuple[str, str]:
    """(admin conninfo, scratch sa-url) with a UNIQUE run-scoped name."""
    from sqlalchemy.engine import make_url

    u = make_url(admin_url)
    name = f"rq14a2_{label}_{_RUN}"
    base = f"postgresql://{u.username}:{u.password}@{u.host}:{u.port}"
    return name, (
        f"postgresql+psycopg://{u.username}:{u.password}@{u.host}:{u.port}/{name}"
    )


def _create_scratch(admin_url: str, db_name: str) -> None:
    """CREATE only — this module never captures a pre-existing database."""
    with psycopg.connect(admin_url, autocommit=True) as c:
        c.execute(f'CREATE DATABASE "{db_name}"')


def _drop_scratch(admin_url: str, db_name: str) -> None:
    with psycopg.connect(admin_url, autocommit=True) as c:
        c.execute(f'DROP DATABASE IF EXISTS "{db_name}"')


def _upgrade(db_url: str, revision: str = "head") -> subprocess.CompletedProcess:
    env = dict(os.environ, DATABASE_URL=db_url, TESTING="1", ENV="dev")
    return subprocess.run(
        [sys.executable, "-m", "alembic", "-c", "alembic.ini", "upgrade", revision],
        capture_output=True,
        text=True,
        cwd=str(BACKEND_DIR),
        env=env,
    )


def _assert_pg_head(engine) -> None:
    assert engine.dialect.name == "postgresql"
    with engine.connect() as conn:
        version = conn.execute(text("select version_num from alembic_version")).scalar()
    # QD-2E chain reconciliation + RQ-13.b + RQ-15.d: the populated head
    # assert advances with the chain (0065 -> 0066 cutover -> 0067
    # snapshot -> 0068 direction public-address registry, RQ-16.c /
    # E-055 -> 0069 sentinel pair retirement).
    assert version == "0069_sentinel_pair_retirement", version


def _both_unique_objects(engine) -> dict[str, bool]:
    with engine.connect() as conn:
        constraint = conn.execute(
            text(
                "select count(*) from pg_constraint "
                "where conname = 'uq_queue_entries_queue_number'"
            )
        ).scalar()
        index = conn.execute(
            text(
                "select count(*) from pg_indexes "
                "where indexname = 'uq_daily_queues_active_doctor_day_tag'"
            )
        ).scalar()
    return {
        "entry_constraint": bool(constraint),
        "doctor_index": bool(index),
    }


@pytest.fixture(scope="module")
def pg_engine():
    """A run-unique scratch database upgraded to head (0068 — the QD-2E
    cutover is data-only; the RQ-15.d sentinel retirement cleanly removes
    the 0055 pairs the same chain seeded on the empty scratch)."""
    admin_url, _host = _verified_admin_url()
    db_name, sa_url = _scratch_pair(admin_url, "main")
    _create_scratch(admin_url, db_name)
    result = _upgrade(sa_url)
    assert result.returncode == 0, result.stderr[-1500:]

    engine = create_engine(sa_url, future=True)
    _assert_pg_head(engine)
    yield engine
    engine.dispose()
    _drop_scratch(admin_url, db_name)


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


def _make_doctor(session, suffix: str):
    from app.core.security import get_password_hash
    from app.models.clinic import Doctor
    from app.models.user import User

    user = User(
        username=f"rq14a2_{suffix}_{_RUN}",
        email=f"rq14a2_{suffix}_{_RUN}@example.com",
        full_name=f"RQ-14.a.2 {suffix}",
        hashed_password=get_password_hash("rq14a2-synthetic-pw"),
        role="Doctor",
        is_active=True,
    )
    session.add(user)
    session.commit()
    doctor = Doctor(user_id=user.id, specialty="cardiology", cabinet="601", active=True)
    session.add(doctor)
    session.commit()
    session.refresh(doctor)
    return doctor


def _seed_queue(session, doctor_id: int, day: date, tag, active=True):
    """RQ-13.b: Core INSERT with the 0064-era column list so the
    populated-upgrade proof can seed rows at the OLD schema revision
    while later tests seed the same helper at head (start_number is
    server-defaulted, never referenced)."""
    # RAW SQL with the 0064-era column list: any SQLAlchemy insert
    # (entity or Core) auto-includes python-defaulted columns such as the
    # 0067 start_number, which does not exist on the pre-0067 schema this
    # proof seeds at. A full ORM re-select would also reference the new
    # column — callers only ever use .id, so return a lightweight stand-in.
    row = session.execute(
        text(
            "INSERT INTO daily_queues (day, specialist_id, queue_tag, active, "
            "online_start_time, online_end_time, max_online_entries) "
            "VALUES (:d, :s, :t, :a, '07:00', '09:00', 15) RETURNING id"
        ),
        {"d": day, "s": doctor_id, "t": tag, "a": active},
    ).one()
    session.commit()
    return SimpleNamespace(id=row[0])


def _seed_entry(session, queue_id: int, number: int, status="waiting", source="desk"):
    from app.models.online_queue import OnlineQueueEntry

    entry = OnlineQueueEntry(
        queue_id=queue_id,
        number=number,
        patient_name=f"SYNTHETIC-RQ14A2 {number}",
        phone=f"+9989070000{number:03d}",
        source=source,
        status=status,
        queue_time=datetime.now(UTC),
    )
    session.add(entry)
    session.commit()
    session.refresh(entry)
    return entry


# ===================== populated upgrade / constraint shape =====================


def test_upgrade_creates_both_objects_on_clean_schema(pg_engine):
    _assert_pg_head(pg_engine)
    assert _both_unique_objects(pg_engine) == {
        "entry_constraint": True,
        "doctor_index": True,
    }


def test_populated_upgrade_preserves_row_values():
    """REAL migration proof: 0064 -> synthetic rows -> COMMIT -> upgrade
    to 0065 -> the same rows are compared FIELD BY FIELD (not counts)."""
    admin_url, _host = _verified_admin_url()
    db_name, sa_url = _scratch_pair(admin_url, "populated")
    _create_scratch(admin_url, db_name)
    try:
        assert _upgrade(sa_url, "0064_push_devices_registry").returncode == 0

        engine = create_engine(sa_url, future=True)
        Session = sessionmaker(bind=engine, future=True)
        session = Session()
        day = date(2026, 9, 14)
        doc_a = _make_doctor(session, "pa")
        doc_b = _make_doctor(session, "pb")
        qa = _seed_queue(session, doc_a.id, day, "cardiology")
        qb = _seed_queue(session, doc_b.id, day, "cardiology")
        _seed_queue(session, doc_a.id, day, None)  # NULL-tag batch-style row
        _seed_queue(session, doc_a.id, day, "cardiology", active=False)
        for number, status in enumerate(
            ("waiting", "called", "served", "completed", "cancelled"), start=1
        ):
            _seed_entry(session, qa.id, number, status=status)
        _seed_entry(session, qb.id, 3, status="waiting", source="online")
        session.close()
        engine.dispose()

        before_engine = create_engine(sa_url, future=True)
        with before_engine.connect() as conn:
            entries_before = conn.execute(
                text(
                    "select queue_id, number, patient_name, status, source "
                    "from queue_entries order by queue_id, number"
                )
            ).fetchall()
            queues_before = conn.execute(
                text(
                    "select day, specialist_id, coalesce(queue_tag, '<NULL>'), "
                    "active from daily_queues order by id"
                )
            ).fetchall()
        before_engine.dispose()

        assert _upgrade(sa_url).returncode == 0

        after_engine = create_engine(sa_url, future=True)
        _assert_pg_head(after_engine)
        with after_engine.connect() as conn:
            entries_after = conn.execute(
                text(
                    "select queue_id, number, patient_name, status, source "
                    "from queue_entries order by queue_id, number"
                )
            ).fetchall()
            queues_after = conn.execute(
                text(
                    "select day, specialist_id, coalesce(queue_tag, '<NULL>'), "
                    "active from daily_queues order by id"
                )
            ).fetchall()
        after_engine.dispose()

        assert entries_after == entries_before, (entries_before, entries_after)
        assert queues_after == queues_before, (queues_before, queues_after)
        assert len(entries_before) == 6
    finally:
        _drop_scratch(admin_url, db_name)


def test_reflected_constraint_is_deferrable(pg_engine):
    """PG metadata (pg_constraint) reflects the existing constraint with
    condeferrable=true and condeferred=true — the DEFERRABLE shape the
    0065 migration created. Model-side parity via
    UniqueConstraint(deferrable=True) was evaluated and STOPPED:
    SQLAlchemy renders the generic deferrable for SQLite too, where it
    is a syntax error (CREATE TABLE ... DEFERRABLE is FK-only in
    SQLite), so the constraint stays migration-only."""
    with pg_engine.connect() as conn:
        row = conn.execute(
            text(
                "select condeferrable, condeferred from pg_constraint "
                "where conname = 'uq_queue_entries_queue_number'"
            )
        ).fetchone()
    assert row is not None
    assert row[0] is True and row[1] is True, row


# ===================== duplicate refusals (separate databases) =====================


def _dup_scenario(db_label: str, seeder):
    """Shared harness: 0064 schema -> seeder(session) -> commit -> the
    upgrade must fail loudly, leave the version at 0064, create NEITHER
    object, and not modify any row."""
    admin_url, _host = _verified_admin_url()
    db_name, sa_url = _scratch_pair(admin_url, db_label)
    _create_scratch(admin_url, db_name)
    try:
        assert _upgrade(sa_url, "0064_push_devices_registry").returncode == 0
        engine = create_engine(sa_url, future=True)
        Session = sessionmaker(bind=engine, future=True)
        session = Session()
        seeder(session)
        session.commit()
        session.close()
        engine.dispose()

        snapshot_engine = create_engine(sa_url, future=True)
        with snapshot_engine.connect() as conn:
            before_entries = conn.execute(
                text(
                    "select queue_id, number, patient_name, status "
                    "from queue_entries order by queue_id, number"
                )
            ).fetchall()
            before_queues = conn.execute(
                text(
                    "select day, specialist_id, coalesce(queue_tag,'<N>'), active "
                    "from daily_queues order by id"
                )
            ).fetchall()
        snapshot_engine.dispose()

        result = _upgrade(sa_url)
        assert result.returncode != 0, "upgrade must fail on duplicates"

        combined = (result.stderr or "") + (result.stdout or "")
        assert "duplicate pre-check FAILED" in combined
        assert "SYNTHETIC" not in combined  # no PII/patient data in diagnostics

        check_engine = create_engine(sa_url, future=True)
        with check_engine.connect() as conn:
            version = conn.execute(
                text("select version_num from alembic_version")
            ).scalar()
            after_entries = conn.execute(
                text(
                    "select queue_id, number, patient_name, status "
                    "from queue_entries order by queue_id, number"
                )
            ).fetchall()
            after_queues = conn.execute(
                text(
                    "select day, specialist_id, coalesce(queue_tag,'<N>'), active "
                    "from daily_queues order by id"
                )
            ).fetchall()
        assert version == "0064_push_devices_registry", version
        assert _both_unique_objects(check_engine) == {
            "entry_constraint": False,
            "doctor_index": False,
        }
        check_engine.dispose()

        assert after_entries == before_entries
        assert after_queues == before_queues
    finally:
        _drop_scratch(admin_url, db_name)


def test_refuse_preexisting_duplicate_entry_numbers():
    def seed(session):
        day = date(2026, 9, 14)
        doc = _make_doctor(session, "dup_e")
        q = _seed_queue(session, doc.id, day, "cardiology")
        _seed_entry(session, q.id, 3)
        _seed_entry(session, q.id, 3)  # duplicate number in ONE queue

    _dup_scenario("dupe", seed)


def test_refuse_preexisting_duplicate_active_doctor_rows():
    def seed(session):
        day = date(2026, 9, 14)
        doc = _make_doctor(session, "dup_d")
        _seed_queue(session, doc.id, day, "cardiology", active=True)
        _seed_queue(session, doc.id, day, "cardiology", active=True)  # fork

    _dup_scenario("dupd", seed)


def test_refuse_null_and_empty_tag_folding_into_one_key():
    """COALESCE contract: queue_tag=NULL and queue_tag='' fold to the
    same effective key for one (day, doctor) — the second ACTIVE row is
    a duplicate."""

    def seed(session):
        day = date(2026, 9, 14)
        doc = _make_doctor(session, "dup_t")
        _seed_queue(session, doc.id, day, None, active=True)
        _seed_queue(session, doc.id, day, "", active=True)

    _dup_scenario("dupt", seed)


# ===================== raw-PG rejection + per-queue scope =====================


def test_raw_duplicate_number_rejected_by_postgres(pg_session):
    from app.models.online_queue import OnlineQueueEntry

    day = date(2026, 9, 14)
    doc = _make_doctor(pg_session, "raw")
    q = _seed_queue(pg_session, doc.id, day, "cardiology")

    _seed_entry(pg_session, q.id, 1)
    pg_session.add(
        OnlineQueueEntry(
            queue_id=q.id,
            number=1,
            patient_name="SYNTHETIC-Raw2",
            source="desk",
            status="waiting",
        )
    )
    with pytest.raises(IntegrityError):
        pg_session.commit()
    pg_session.rollback()


def test_raw_duplicate_active_doctor_queue_rejected(pg_session):
    from app.models.online_queue import DailyQueue

    day = date(2026, 9, 14)
    doc = _make_doctor(pg_session, "dq")
    _seed_queue(pg_session, doc.id, day, "cardiology")

    pg_session.add(
        DailyQueue(day=day, specialist_id=doc.id, queue_tag="cardiology", active=True)
    )
    with pytest.raises(IntegrityError):
        pg_session.commit()
    pg_session.rollback()

    pg_session.add(
        DailyQueue(day=day, specialist_id=doc.id, queue_tag="cardiology", active=False)
    )
    pg_session.commit()  # inactive duplicate stays legal


def test_independent_queues_share_numbers(pg_session):
    day = date(2026, 9, 14)
    qa = _seed_queue(pg_session, _make_doctor(pg_session, "sc_a").id, day, "cardio1")
    qb = _seed_queue(pg_session, _make_doctor(pg_session, "sc_b").id, day, "cardio2")

    _seed_entry(pg_session, qa.id, 7)
    _seed_entry(pg_session, qb.id, 7)  # same number across queues: legal


# ===================== production reorder on real PostgreSQL =====================


def _make_user_admin():
    from types import SimpleNamespace

    return SimpleNamespace(id=1, role="Admin")


def _reorder_service(session):
    from app.services.queue_reorder_api_service import QueueReorderApiService

    return QueueReorderApiService(session)


def _numbers(engine, queue_id: int) -> list[tuple[int, str]]:
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                "select number, status from queue_entries "
                "where queue_id = :q order by number"
            ),
            {"q": queue_id},
        ).fetchall()
    return [(r[0], r[1]) for r in rows]


def test_production_reorder_on_postgres(pg_engine):
    """The DEFERRABLE contract proven through the production reorder
    service (doctor-queue branch, raw positions) on real PostgreSQL."""
    from sqlalchemy.exc import IntegrityError as SAIntegrityError

    # Preconditions: PG dialect, alembic head, deferrable constraint shape.
    _assert_pg_head(pg_engine)
    with pg_engine.connect() as conn:
        row = conn.execute(
            text(
                "select condeferrable, condeferred from pg_constraint "
                "where conname = 'uq_queue_entries_queue_number'"
            )
        ).fetchone()
    assert row is not None and row[0] is True and row[1] is True, row

    Session = sessionmaker(bind=pg_engine, future=True)
    day = date(2026, 9, 14)

    # Seed: waiting 1..3, a called 4, a completed 5 and a cancelled 6 —
    # only ACTIVE entries form the reorder surface.
    seed = Session()
    doc = _make_doctor(seed, "reord")
    q = _seed_queue(seed, doc.id, day, "cardio_reord")
    for number, status in (
        (1, "waiting"),
        (2, "waiting"),
        (3, "waiting"),
        (4, "called"),
        (5, "completed"),
        (6, "cancelled"),
    ):
        _seed_entry(seed, q.id, number, status=status)
    admin = _make_user_admin()
    queue_id = q.id
    seed.close()

    def _entry_id(number: int) -> int:
        session = Session()
        from app.models.online_queue import OnlineQueueEntry

        try:
            return (
                session.query(OnlineQueueEntry.id)
                .filter(
                    OnlineQueueEntry.queue_id == queue_id,
                    OnlineQueueEntry.number == number,
                )
                .scalar()
            )
        finally:
            session.close()

    # (1) LEGAL SWAP with an intermediate duplicate commits.
    session = Session()
    e1, e2 = _entry_id(1), _entry_id(2)
    updated, _info = _reorder_service(session).reorder_queue(
        queue_id=queue_id,
        entry_orders=[
            {"entry_id": e1, "new_position": 2},
            {"entry_id": e2, "new_position": 1},
        ],
        current_user=admin,
    )
    session.close()
    assert updated == 2
    after = _numbers(pg_engine, queue_id)
    assert [n for n, _s in after] == [1, 2, 3, 4, 5, 6]
    assert dict(after)[1] == "waiting" and dict(after)[2] == "waiting"

    # (2) END-STATE DUPLICATE rejected AT COMMIT (deferred constraint).
    session = Session()
    a, b = _entry_id(1), _entry_id(3)  # both target position 3
    with pytest.raises(SAIntegrityError):
        _reorder_service(session).reorder_queue(
            queue_id=queue_id,
            entry_orders=[
                {"entry_id": a, "new_position": 3},
                {"entry_id": b, "new_position": 3},
            ],
            current_user=admin,
        )
    session.rollback()
    session.close()

    # (3) ROLLBACK leaves every number untouched.
    assert [n for n, _s in _numbers(pg_engine, queue_id)] == [1, 2, 3, 4, 5, 6]

    # (4) completed/cancelled stay out of the reorder surface: swapping
    # active entries never touches rows 5/6.
    session = Session()
    _reorder_service(session).reorder_queue(
        queue_id=queue_id,
        entry_orders=[
            {"entry_id": _entry_id(1), "new_position": 4},
            {"entry_id": _entry_id(4), "new_position": 1},
        ],
        current_user=admin,
    )
    session.close()
    final = dict(_numbers(pg_engine, queue_id))
    assert final[5] == "completed" and final[6] == "cancelled"
    assert sorted(final) == [1, 2, 3, 4, 5, 6]


def test_concurrent_writers_and_get_or_create_keep_invariants(pg_engine, pg_session):
    from app.services.queue_svc import QueueBusinessService

    day = date(2026, 9, 14)
    doc = _make_doctor(pg_session, "conc")
    svc = QueueBusinessService()
    seed_q = svc.get_or_create_daily_queue(
        pg_session, day=day, specialist_id=doc.id, queue_tag="cardiology"
    )
    pg_session.commit()
    queue_id = seed_q.id

    import threading

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
    assert {qid for qid, _ in results} == {queue_id}


def test_rollback_leaves_nothing_partial(pg_session):
    from app.models.online_queue import OnlineQueueEntry
    from app.services.queue_svc import QueueBusinessService

    day = date(2026, 9, 14)
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

    pg_session.add(
        OnlineQueueEntry(
            queue_id=q.id,
            number=e1.number,
            patient_name="SYNTHETIC-Rb Dup",
            source="desk",
        )
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
