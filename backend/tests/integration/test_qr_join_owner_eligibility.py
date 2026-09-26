"""
RQ-09.a — the clinic-wide join LEGACY doctor-id path (Path B in
``join_queue_with_token``) must re-check the owner-eligibility contract
claimed by ``appointment_eligibility.py`` (E-028 registration).

Defect being pinned: Path B (clinic-wide token + ``specialist_id_override``
that is a Doctor.id, not a QueueProfile.id) verified only
``Doctor.active`` + incomplete-specialty + visible-profile, WITHOUT the
owner checks (owner exists / owner active / doctor-family role) that the
Path A eligible-doctors query applies. An owner-ghost doctor (Doctor row
still active after its User was deactivated, or a userless legacy row, or
an owner without a doctor-family role) submitted DIRECTLY by id joined the
queue despite the contract ("the QR/online queue join ... excludes them").

Fix mirrors Path A's eligibility predicate onto Path B and keeps the
join-path error contract (QueueValidationError -> 400).

Traced, NOT fixed here (registered observation): the non-clinic-wide
doctor-token path resolves the queue from the token without a Doctor
eligibility check either — staff-issued tokens only, separate entry.

Disposable PostgreSQL: the module provisions its own scratch database
(rq09a_check), runs ``alembic upgrade head`` and drops it at the end;
skips (NOT_RUN per plan P0) when no local disposable PostgreSQL is
reachable. SYNTHETIC data only.
"""

from __future__ import annotations

import os
import sys
import uuid
from datetime import datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import psycopg
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker

BACKEND_DIR = Path(__file__).resolve().parents[2]
SCRATCH_DB_PREFIX = "rq09a_check"
SCRATCH_DB = f"{SCRATCH_DB_PREFIX}_{uuid.uuid4().hex[:12]}"

sys.path.insert(0, str(BACKEND_DIR))


def _candidate_admin_urls() -> list[str]:
    urls: list[str] = []
    explicit = os.getenv("RQ09A_PG_ADMIN_URL", "").strip()
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
    return (
        str(u.set(drivername="postgresql", database=SCRATCH_DB)),
        str(u.set(drivername="postgresql+psycopg", database=SCRATCH_DB)),
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
            f"disposable PostgreSQL unavailable — RQ-09.a PG acceptance NOT_RUN "
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


def _make_user(session, username: str, role: str, active: bool = True):
    from app.core.security import get_password_hash
    from app.models.user import User

    user = User(
        username=username,
        email=f"{username}@example.com",
        full_name=f"RQ-09.a {username}",
        hashed_password=get_password_hash("rq09a-synthetic-pw"),
        role=role,
        is_active=active,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def _make_doctor(session, user_id: int | None, active: bool = True):
    from app.models.clinic import Doctor

    doctor = Doctor(
        user_id=user_id,
        specialty="cardiology",
        cabinet="201",
        active=active,
    )
    session.add(doctor)
    session.commit()
    session.refresh(doctor)
    return doctor


def _seed_clinic_wide_token(session, suffix: str) -> dict:
    """Clinic-wide QueueToken for the clinic day (no queues pre-created:
    the join path creates the (day, tag) queue itself)."""
    from app.models.online_queue import QueueToken

    day = _clinic_day()
    local_now = datetime.now(ZoneInfo("Asia/Tashkent")).replace(tzinfo=None)
    token = QueueToken(
        token=f"rq09a-token-{suffix}",
        day=day,
        is_clinic_wide=True,
        department="cardiology",
        expires_at=local_now + timedelta(hours=2),
        active=True,
    )
    session.add(token)
    session.commit()
    return {"token": token.token, "day": day}


def _create_doctor_above_profiles(
    session, user_id: int | None, active: bool = True
):
    """Create a Doctor whose id matches NO QueueProfile.id, so the
    clinic-wide override resolves to Path B (legacy doctor-id) and not to
    the profile branch (RQ-09.b id ambiguity): migrations 0055 seed
    profiles with small ids, so deactivated filler doctors lift the
    Doctor.id counter above every profile id first."""
    from app.models.clinic import Doctor
    from app.models.queue_profile import QueueProfile

    max_profile_id = (
        session.query(QueueProfile.id).order_by(QueueProfile.id.desc()).first()
    )
    guard = 0
    while True:
        row = session.query(Doctor.id).order_by(Doctor.id.desc()).first()
        next_id = (row[0] if row else 0) + 1
        if next_id > (max_profile_id[0] if max_profile_id else 0):
            break
        _make_doctor(session, user_id=None, active=False)
        guard += 1
        if guard > 100:  # pragma: no cover
            break
    return _make_doctor(session, user_id=user_id, active=active)


def _join_by_doctor_id(session, token: str, doctor_id: int) -> dict:
    from app.services.qr_queue import QRQueueService

    svc = QRQueueService(session)
    start = svc.start_join_session(token)
    return svc.complete_join_session_multiple(
        start["session_token"],
        [doctor_id],
        "SYNTHETIC-Elig Patient",
        "+998902000000",
    )


def _queue_entries(session, queue_tag: str) -> list:
    from app.models.online_queue import DailyQueue, OnlineQueueEntry

    return (
        session.query(OnlineQueueEntry)
        .join(DailyQueue, OnlineQueueEntry.queue_id == DailyQueue.id)
        .filter(DailyQueue.queue_tag == queue_tag)
        .all()
    )


def test_owner_inactive_ghost_cannot_join_via_doctor_id(pg_session):
    """(a) fail-first: Doctor.active=True but its owner User deactivated —
    the direct doctor-id join must refuse (base joins -> RED)."""
    session = pg_session
    user = _make_user(session, "rq09a_ghost", "Doctor", active=True)
    # Deactivate the OWNER before creating the doctor row: the legacy
    # ghost-mirror gap leaves the Doctor row active while its owner is not.
    user.is_active = False
    session.commit()
    doctor = _create_doctor_above_profiles(session, user.id)
    world = _seed_clinic_wide_token(session, "ghost")

    from app.services.queue_svc import QueueValidationError

    with pytest.raises((QueueValidationError, ValueError)):
        _join_by_doctor_id(session, world["token"], doctor.id)

    assert _queue_entries(session, "cardiology") == []


def test_userless_active_doctor_cannot_join_via_doctor_id(pg_session):
    """(b) a userless legacy Doctor row (decision #13) must refuse."""
    session = pg_session
    doctor = _create_doctor_above_profiles(session, user_id=None)
    world = _seed_clinic_wide_token(session, "userless")

    from app.services.queue_svc import QueueValidationError

    with pytest.raises((QueueValidationError, ValueError)):
        _join_by_doctor_id(session, world["token"], doctor.id)

    assert _queue_entries(session, "cardiology") == []


def test_non_doctor_role_owner_cannot_join_via_doctor_id(pg_session):
    """(c) an owner without a doctor-family role (e.g. the 0055 resource
    synthetics with 'Lab'/'Nurse' roles) must refuse."""
    session = pg_session
    user = _make_user(session, "rq09a_labrole", "Lab", active=True)
    doctor = _create_doctor_above_profiles(session, user.id)
    world = _seed_clinic_wide_token(session, "labrole")

    from app.services.queue_svc import QueueValidationError

    with pytest.raises((QueueValidationError, ValueError)):
        _join_by_doctor_id(session, world["token"], doctor.id)

    assert _queue_entries(session, "cardiology") == []


def test_healthy_doctor_still_joins_via_doctor_id(pg_session):
    """(d) positive control: an eligible doctor joins through the same
    legacy path — the fix must not break the legitimate flow."""
    session = pg_session
    user = _make_user(session, "rq09a_healthy", "Doctor", active=True)
    doctor = _create_doctor_above_profiles(session, user.id)
    world = _seed_clinic_wide_token(session, "healthy")

    before = len(_queue_entries(session, "cardiology"))
    result = _join_by_doctor_id(session, world["token"], doctor.id)
    assert result["success"] is True, result
    entries = _queue_entries(session, "cardiology")
    assert len(entries) == before + 1
    assert entries[-1].patient_id is not None


def test_inactive_doctor_row_cannot_join_via_doctor_id(pg_session):
    """(e) Doctor.active=False keeps refusing (pre-existing behavior)."""
    session = pg_session
    user = _make_user(session, "rq09a_inactive", "Doctor", active=True)
    doctor = _create_doctor_above_profiles(session, user.id, active=False)
    world = _seed_clinic_wide_token(session, "inact")

    from app.services.queue_svc import QueueValidationError

    with pytest.raises((QueueValidationError, ValueError)):
        _join_by_doctor_id(session, world["token"], doctor.id)
