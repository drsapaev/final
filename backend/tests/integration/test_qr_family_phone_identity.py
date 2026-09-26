"""
RQ-25.a.1 — QR family-phone identity (ACCEPTANCE S-22 "второй не склеен
с первым только по телефону").

Defect being pinned (E-030 probe: GLUED=True): the QR self-registration
path identified a patient by PHONE DIGITS ONLY at three points:

1. ``qr_queue/_patients.py:_find_or_create_patient`` — the second family
   member sharing a phone silently attached to the first member's card
   (their typed name was discarded, visits/entries landed on someone
   else's medical record — wrong-patient PHI linkage);
2. ``queue_svc/_operations.py:check_uniqueness`` — per-queue dedup by
   ``entry.phone`` returned the FIRST member's ticket for the second;
3. ``queue_svc/_operations.py:_find_clinic_wide_duplicate`` — the
   clinic-wide dedup did the same across all candidate queues.

Contract enforced by these tests (operator decision, RQ-25.a.1):
- a shared phone alone is NOT sufficient to treat two people as one
  patient; family members get their OWN card and their OWN ticket;
- the first patient's existing data is never overwritten by the second's;
- a repeat join (same person, same name+phone) still reuses their entry —
  the existing spam-guard pin ``test_qr_join_duplicate_is_not_recreated``
  must stay green;
- an ambiguous lookup (several patients with the same phone AND name)
  must NOT be resolved by picking the first row — the join refuses loudly;
- no UNIQUE(phone)/UNIQUE(phone, name) index is introduced as an identity
  substitute; phone/Telegram limits are untouched.

Disposable PostgreSQL: the module provisions its own scratch database
(rq25a1_check), runs ``alembic upgrade head`` and drops it at the end;
skips (NOT_RUN per plan P0) when no local disposable PostgreSQL is
reachable. SQLite is never a substitute here. SYNTHETIC data only.
"""

from __future__ import annotations

import os
import sys
import threading
import uuid
from datetime import UTC, datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import psycopg
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker

BACKEND_DIR = Path(__file__).resolve().parents[2]
SCRATCH_DB_PREFIX = "rq25a1_check"
SCRATCH_DB = f"{SCRATCH_DB_PREFIX}_{uuid.uuid4().hex[:12]}"

sys.path.insert(0, str(BACKEND_DIR))


def _candidate_admin_urls() -> list[str]:
    """Admin DSNs for scratch provisioning — LOCAL servers only."""
    urls: list[str] = []
    explicit = os.getenv("RQ25A1_PG_ADMIN_URL", "").strip()
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
        elif not u.host and (u.query.get("host") or "").startswith(
            ("/", "./")
        ):
            # Unix-socket DSN (userspace pgserver holder): the socket dir
            # travels in the query string; still localhost-only by
            # construction, so safe for scratch provisioning.
            urls.append(env_url)
    return urls


def _scratch_url(admin_url: str) -> tuple[str, str]:
    """(psycopg conninfo, sqlalchemy URL) for the scratch database.

    Shape-agnostic: works for TCP (postgres:pw@localhost:5432/postgres)
    and unix-socket (?host=/dir) admin DSNs alike.
    """
    u = make_url(admin_url)
    psycopg_dsn = u.set(drivername="postgresql", database=SCRATCH_DB)
    sa_url = u.set(drivername="postgresql+psycopg", database=SCRATCH_DB)
    return (
        psycopg_dsn.render_as_string(hide_password=False),
        sa_url.render_as_string(hide_password=False),
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
            f"disposable PostgreSQL unavailable — RQ-25.a.1 PG acceptance NOT_RUN "
            f"(last error: {last_error})"
        )

    psycopg_dsn, sa_url = _scratch_url(admin_url)
    with psycopg.connect(admin_url, autocommit=True) as c:
        # No pre-drop: the run-unique name cannot pre-exist (a collision would
        # take 2**48 parallel runs), and dropping a fixed name unconditionally
        # is exactly the cross-run hazard this fixture used to carry.
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
def pg_session(pg_engine):
    Session = sessionmaker(bind=pg_engine, future=True)
    session = Session()
    yield session
    session.rollback()
    session.close()


def _clinic_day():
    return datetime.now(ZoneInfo("Asia/Tashkent")).date()


def _seed_join_world(session, suffix: str) -> dict:
    """Doctor + DailyQueue + a doctor-scoped QueueToken (SYNTHETIC)."""
    from app.core.security import get_password_hash
    from app.models.clinic import Doctor
    from app.models.online_queue import DailyQueue, QueueToken
    from app.models.user import User

    username = f"rq25a1_doc_{suffix}"
    user = session.query(User).filter(User.username == username).first()
    if not user:
        user = User(
            username=username,
            email=f"{username}@example.com",
            full_name="RQ-25.a.1 Synthetic Doctor",
            hashed_password=get_password_hash("rq25a1-synthetic-pw"),
            role="Doctor",
            is_active=True,
        )
        session.add(user)
        session.commit()
        session.refresh(user)

    doctor = Doctor(
        user_id=user.id,
        specialty="cardiology",
        cabinet="101",
        active=True,
    )
    session.add(doctor)
    session.commit()
    session.refresh(doctor)

    day = _clinic_day()
    daily_queue = DailyQueue(
        day=day,
        specialist_id=doctor.id,
        queue_tag="cardiology",
        active=True,
    )
    session.add(daily_queue)
    session.commit()
    session.refresh(daily_queue)

    local_now = datetime.now(ZoneInfo("Asia/Tashkent")).replace(tzinfo=None)
    token = QueueToken(
        token=f"rq25a1-token-{suffix}",
        day=day,
        specialist_id=doctor.id,
        department="cardiology",
        expires_at=local_now + timedelta(hours=2),
        active=True,
    )
    session.add(token)
    session.commit()

    return {
        "doctor_id": doctor.id,
        "queue_id": daily_queue.id,
        "token": token.token,
        "day": day,
    }


def _join(session, token: str, patient_name: str, phone: str) -> dict:
    """Full QR join chain through the service boundary (start → complete).

    Returns the service response; the FINAL queue binding is asserted
    from the database (entry resolved by queue_id + queue_number)."""
    from app.services.qr_queue import QRQueueService

    svc = QRQueueService(session)
    start = svc.start_join_session(token)
    return svc.complete_join_session(
        start["session_token"], patient_name, phone
    )


def _entry_by_number(session, queue_id: int, number: int):
    from app.models.online_queue import OnlineQueueEntry

    return (
        session.query(OnlineQueueEntry)
        .filter(
            OnlineQueueEntry.queue_id == queue_id,
            OnlineQueueEntry.number == number,
        )
        .first()
    )


def _entries_for_queue(session, queue_id: int) -> list:
    from app.models.online_queue import OnlineQueueEntry

    return (
        session.query(OnlineQueueEntry)
        .filter(OnlineQueueEntry.queue_id == queue_id)
        .order_by(OnlineQueueEntry.id)
        .all()
    )


@pytest.fixture(autouse=True)
def _no_time_gate(monkeypatch):
    """Time-window must never block these tests."""
    from app.services.queue_svc import QueueBusinessService

    monkeypatch.setattr(
        QueueBusinessService, "ONLINE_QUEUE_START_TIME", time(0, 0)
    )
    from app.services.queue_svc._base import QueueBusinessServiceMixinBase

    monkeypatch.setattr(
        QueueBusinessServiceMixinBase, "ONLINE_QUEUE_START_TIME", time(0, 0)
    )


def test_family_member_gets_own_card_and_own_ticket(pg_session, pg_engine):
    """(a) full-chain fail-first: same phone + DIFFERENT name → own patient
    and own OnlineQueueEntry (final binding asserted)."""
    world = _seed_join_world(pg_session, "fam")
    from app.models.patient import Patient

    result_a = _join(pg_session, world["token"], "SYNTHETIC-First Famtest", "+998900111222")
    assert result_a["success"] is True, result_a
    entry_a = _entry_by_number(
        pg_session, world["queue_id"], result_a["queue_number"]
    )
    patient_a_id = entry_a.patient_id
    assert patient_a_id is not None

    result_b = _join(pg_session, world["token"], "SYNTHETIC-Second Famtest", "+998900111222")
    assert result_b["success"] is True, result_b
    entry_b = _entry_by_number(
        pg_session, world["queue_id"], result_b["queue_number"]
    )
    patient_b_id = entry_b.patient_id

    # THE defect (base): patient B was glued to A's card and B received
    # A's ticket through the phone-only dedup.
    assert patient_b_id != patient_a_id, (
        "second family member attached to the first member's card"
    )
    assert entry_b.id != entry_a.id, "second family member got the first member's ticket"
    assert result_b["queue_number"] != result_a["queue_number"]

    # The entries are bound to the right cards.
    assert entry_a.patient_id == patient_a_id
    assert entry_b.patient_id == patient_b_id

    # The first patient's card was not overwritten by the second's data.
    patient_a = pg_session.query(Patient).filter(Patient.id == patient_a_id).first()
    assert "SYNTHETIC-First" in patient_a.full_name, patient_a.full_name

    # Both tickets co-exist in the queue.
    entries = _entries_for_queue(pg_session, world["queue_id"])
    assert {e.id for e in entries} == {entry_a.id, entry_b.id}


def test_repeat_join_same_person_reuses_entry(pg_session, pg_engine):
    """(b) the spam-guard contract survives: same person (same name+phone)
    rejoining gets their existing entry, no second entry is created."""
    world = _seed_join_world(pg_session, "rep")

    first = _join(pg_session, world["token"], "SYNTHETIC-Repeat Person", "+998900333444")
    assert first["success"] is True
    second = _join(pg_session, world["token"], "SYNTHETIC-Repeat Person", "+998900333444")
    assert second["success"] is True
    # The rejoin returned the SAME ticket (no new entry, no renumbering).
    assert second["queue_number"] == first["queue_number"], (first, second)

    entries = _entries_for_queue(pg_session, world["queue_id"])
    assert len(entries) == 1


def test_repeat_of_claimed_session_creates_nothing(pg_session, pg_engine):
    """(c) a repeated complete of the SAME session NEVER adds entries —
    round-4 (PR #3362, P1-2): the retry after a lost response re-uses the
    original attempt identity and the joined session REPLAYS its saved
    ticket (``replayed=True``) instead of refusing; either way the atomic
    one-shot claim guarantees no second business action."""
    world = _seed_join_world(pg_session, "claim")
    from app.services.qr_queue import QRQueueService

    svc = QRQueueService(pg_session)
    start = svc.start_join_session(world["token"])
    session_token = start["session_token"]
    first = svc.complete_join_session(
        session_token, "SYNTHETIC-Claim Person", "+998900555666"
    )
    assert first["success"] is True

    replay = svc.complete_join_session(
        session_token, "SYNTHETIC-Claim Person", "+998900555666"
    )
    assert replay["success"] is True
    assert replay["replayed"] is True
    assert replay["queue_number"] == first["queue_number"]
    entries = _entries_for_queue(pg_session, world["queue_id"])
    assert len(entries) == 1


def test_clinic_wide_duplicate_scoped_to_identity(pg_session, pg_engine):
    """(d) the clinic-wide dedup must not hand the first member's ticket to
    the second: same phone + different name → own entry (final binding)."""
    world = _seed_clinic_wide_world(pg_session, "cw")
    from app.services.qr_queue import QRQueueService

    svc = QRQueueService(pg_session)

    start_a = svc.start_join_session(world["token"])
    res_a = svc.complete_join_session_multiple(
        start_a["session_token"],
        [world["profile_id"]],
        "SYNTHETIC-First Cwtest",
        "+998900777888",
        specialist_entity_types=["profile"],  # RQ-09.b (D-01): explicit entity type
    )
    assert res_a["success"] is True, res_a
    entry_a_id = res_a["entries"][0]["queue_entry_id"]

    start_b = svc.start_join_session(world["token"])
    res_b = svc.complete_join_session_multiple(
        start_b["session_token"],
        [world["profile_id"]],
        "SYNTHETIC-Second Cwtest",
        "+998900777888",
        specialist_entity_types=["profile"],  # RQ-09.b (D-01): explicit entity type
    )
    assert res_b["success"] is True, res_b
    entry_b_id = res_b["entries"][0]["queue_entry_id"]
    # Base defect: the clinic-wide phone match returns A's entry as a
    # "duplicate" — B receives A's ticket instead of their own.
    assert res_b["entries"][0]["duplicate"] is False, res_b
    assert entry_b_id != entry_a_id

    from app.models.online_queue import OnlineQueueEntry

    entry_a = (
        pg_session.query(OnlineQueueEntry)
        .filter(OnlineQueueEntry.id == entry_a_id)
        .first()
    )
    entry_b = (
        pg_session.query(OnlineQueueEntry)
        .filter(OnlineQueueEntry.id == entry_b_id)
        .first()
    )
    assert entry_a.patient_id is not None
    assert entry_b.patient_id is not None
    assert entry_b.patient_id != entry_a.patient_id


def _seed_clinic_wide_world(session, suffix: str) -> dict:
    """Clinic-wide token + a QR-visible profile routed to the doctor."""
    from app.core.security import get_password_hash
    from app.models.clinic import Doctor
    from app.models.online_queue import DailyQueue, QueueToken
    from app.models.queue_profile import QueueProfile
    from app.models.user import User

    username = f"rq25a1_cw_{suffix}"
    user = session.query(User).filter(User.username == username).first()
    if not user:
        user = User(
            username=username,
            email=f"{username}@example.com",
            full_name="RQ-25.a.1 CW Doctor",
            hashed_password=get_password_hash("rq25a1-synthetic-pw"),
            role="Doctor",
            is_active=True,
        )
        session.add(user)
        session.commit()
        session.refresh(user)

    doctor = Doctor(user_id=user.id, specialty="cardiology", cabinet="102", active=True)
    session.add(doctor)
    session.commit()
    session.refresh(doctor)

    profile = QueueProfile(
        key=f"rq25a1-{suffix}",
        title=f"RQ-25.a.1 {suffix}",
        queue_tags=["cardiology"],
        department_key="cardiology",
        display_order=1,
        is_active=True,
        show_on_qr_page=True,
    )
    session.add(profile)
    session.commit()
    session.refresh(profile)

    day = _clinic_day()
    daily_queue = DailyQueue(
        day=day,
        specialist_id=doctor.id,
        queue_tag="cardiology",
        active=True,
    )
    session.add(daily_queue)
    session.commit()

    local_now = datetime.now(ZoneInfo("Asia/Tashkent")).replace(tzinfo=None)
    token = QueueToken(
        token=f"rq25a1-cw-token-{suffix}",
        day=day,
        is_clinic_wide=True,
        department="cardiology",
        expires_at=local_now + timedelta(hours=2),
        active=True,
    )
    session.add(token)
    session.commit()

    return {"profile_id": profile.id, "token": token.token}


def test_ambiguous_phone_name_refuses_instead_of_first_row(pg_session, pg_engine):
    """(e) two pre-existing patients with the SAME phone AND name: the join
    must not silently resolve to the first row — it refuses loudly."""
    world = _seed_join_world(pg_session, "amb")
    from app.models.patient import Patient

    for _ in range(2):
        pg_session.add(
            Patient(
                last_name="SYNTHETIC-Ambiguous",
                first_name="Person",
                phone="+998900999000",
            )
        )
    pg_session.commit()

    with pytest.raises(ValueError):
        _join(pg_session, world["token"], "SYNTHETIC-Ambiguous Person", "+998900999000")

    entries = _entries_for_queue(pg_session, world["queue_id"])
    assert entries == []


def test_concurrent_family_members_on_separate_connections(pg_engine):
    """(f) two family members joining SIMULTANEOUSLY on separate
    connections both get their own card and own ticket."""
    Session = sessionmaker(bind=pg_engine, future=True)

    setup = Session()
    world = _seed_join_world(setup, "conc")
    setup.close()

    results: dict[str, dict] = {}
    errors: list[Exception] = []

    def _member(key: str, name: str, phone: str) -> None:
        session = Session()
        try:
            results[key] = _join(session, world["token"], name, phone)
        except Exception as exc:  # noqa: BLE001
            errors.append(exc)
        finally:
            session.close()

    t1 = threading.Thread(
        target=_member,
        args=("a", "SYNTHETIC-Conc First", "+998901222333"),
    )
    t2 = threading.Thread(
        target=_member,
        args=("b", "SYNTHETIC-Conc Second", "+998901222333"),
    )
    t1.start()
    t2.start()
    t1.join(timeout=60)
    t2.join(timeout=60)

    assert not errors, errors
    check = Session()
    entry_a = _entry_by_number(
        check, world["queue_id"], results["a"]["queue_number"]
    )
    entry_b = _entry_by_number(
        check, world["queue_id"], results["b"]["queue_number"]
    )
    assert entry_a is not None and entry_b is not None
    assert entry_a.patient_id != entry_b.patient_id
    assert entry_a.id != entry_b.id

    entries = _entries_for_queue(check, world["queue_id"])
    assert {e.id for e in entries} == {entry_a.id, entry_b.id}
    check.close()


def test_concurrent_same_person_double_submit_single_entry(pg_engine):
    """(g) the same person double-submitting concurrently (two fresh
    sessions, e.g. double tap) must end with ONE entry — the phone-scoped
    serialization makes the second writer see the first patient."""
    Session = sessionmaker(bind=pg_engine, future=True)

    setup = Session()
    world = _seed_join_world(setup, "dbl")
    setup.close()

    results: list[dict] = []
    errors: list[Exception] = []

    def _member(idx: int) -> None:
        session = Session()
        try:
            results.append(
                _join(
                    session,
                    world["token"],
                    "SYNTHETIC-Double Person",
                    "+998901444555",
                )
            )
        except Exception as exc:  # noqa: BLE001
            errors.append(exc)
        finally:
            session.close()

    t1 = threading.Thread(target=_member, args=(1,))
    t2 = threading.Thread(target=_member, args=(2,))
    t1.start()
    t2.start()
    t1.join(timeout=60)
    t2.join(timeout=60)

    assert not errors, errors
    assert len(results) == 2
    # One ticket only: both submits must land on the SAME number - the
    # second writer observes the first join (identity reuse).
    numbers = {r["queue_number"] for r in results}
    assert len(numbers) == 1, [r["queue_number"] for r in results]

    check = Session()
    entries = _entries_for_queue(check, world["queue_id"])
    assert len(entries) == 1
    check.close()
