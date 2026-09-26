"""
RQ-09.c — the non-clinic-wide doctor-token join path must re-check the
owner-eligibility contract (E-032 registration).

Defect being pinned: ``join_queue_with_token`` resolves ``daily_queue``
for a non-clinic-wide token from ``(day, token.specialist_id)`` — a
Doctor.id — and NEVER verifies Doctor/owner eligibility. A staff-issued
token for an owner-ghost doctor (Doctor row active after its User was
deactivated, a userless legacy row, or an owner without a doctor-family
role) joins the queue despite the ``appointment_eligibility.py``
contract, which the Path A/B (clinic-wide) branches already enforce
(RQ-09.a #3241, E-028 selection side).

Fix contract:
- a doctor-OWNED resolved surface (queue_resource_id IS NULL) requires
  the same eligibility predicate as Path A/B — refuse otherwise with the
  standard join-path error (QueueValidationError -> 400);
- a RESOURCE-owned resolved surface (QD-2C registry axis) is joined as
  the RESOURCE: the legacy synthetic token owner (role 'Lab'/'Nurse')
  deliberately fails the doctor-role check, so the eligibility gate must
  NOT apply there — resource joins stay working.

Disposable PostgreSQL: the module provisions its own scratch database
(rq09c_check), runs ``alembic upgrade head`` and drops it at the end;
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
SCRATCH_DB_PREFIX = "rq09c_check"
SCRATCH_DB = f"{SCRATCH_DB_PREFIX}_{uuid.uuid4().hex[:12]}"

sys.path.insert(0, str(BACKEND_DIR))


def _candidate_admin_urls() -> list[str]:
    urls: list[str] = []
    explicit = os.getenv("RQ09C_PG_ADMIN_URL", "").strip()
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
            f"disposable PostgreSQL unavailable — RQ-09.c PG acceptance NOT_RUN "
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
        full_name=f"RQ-09.c {username}",
        hashed_password=get_password_hash("rq09c-synthetic-pw"),
        role=role,
        is_active=active,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def _make_doctor(
    session, user_id: int | None, active: bool = True, specialty: str = "cardiology"
):
    from app.models.clinic import Doctor

    doctor = Doctor(
        user_id=user_id,
        specialty=specialty,
        cabinet="301",
        active=active,
    )
    session.add(doctor)
    session.commit()
    session.refresh(doctor)
    return doctor


def _seed_doctor_token(session, suffix: str, doctor_id: int) -> dict:
    """Non-clinic-wide token scoped to the doctor + a live doctor-owned
    queue on the clinic day."""
    from app.models.online_queue import DailyQueue, QueueToken

    day = _clinic_day()
    queue = DailyQueue(
        day=day,
        specialist_id=doctor_id,
        queue_tag="cardiology",
        active=True,
    )
    session.add(queue)
    session.commit()

    local_now = datetime.now(ZoneInfo("Asia/Tashkent")).replace(tzinfo=None)
    token = QueueToken(
        token=f"rq09c-token-{suffix}",
        day=day,
        specialist_id=doctor_id,
        department="cardiology",
        expires_at=local_now + timedelta(hours=2),
        active=True,
    )
    session.add(token)
    session.commit()
    return {"token": token.token, "day": day, "queue_id": queue.id}


def _join(session, token: str) -> dict:
    from app.services.qr_queue import QRQueueService

    svc = QRQueueService(session)
    start = svc.start_join_session(token)
    return svc.complete_join_session(
        start["session_token"], "SYNTHETIC-Token Patient", "+998903000000"
    )


def _entries(session, queue_id: int | None = None) -> list:
    from app.models.online_queue import OnlineQueueEntry

    query = session.query(OnlineQueueEntry)
    if queue_id is not None:
        query = query.filter(OnlineQueueEntry.queue_id == queue_id)
    return query.all()


def test_owner_inactive_ghost_cannot_join_via_doctor_token(pg_session):
    """(a) fail-first: token issued for a doctor whose owner was later
    deactivated — the join must refuse (base joins -> RED)."""
    session = pg_session
    user = _make_user(session, "rq09c_ghost", "Doctor", active=True)
    doctor = _make_doctor(session, user.id)
    user.is_active = False
    session.commit()
    world = _seed_doctor_token(session, "ghost", doctor.id)

    from app.services.queue_svc import QueueValidationError

    with pytest.raises((QueueValidationError, ValueError)):
        _join(session, world["token"])
    assert _entries(session, world["queue_id"]) == []


def test_userless_doctor_cannot_join_via_doctor_token(pg_session):
    """(b) a userless legacy Doctor row (decision #13) must refuse."""
    session = pg_session
    doctor = _make_doctor(session, user_id=None)
    world = _seed_doctor_token(session, "userless", doctor.id)

    from app.services.queue_svc import QueueValidationError

    with pytest.raises((QueueValidationError, ValueError)):
        _join(session, world["token"])
    assert _entries(session, world["queue_id"]) == []


def test_non_doctor_role_owner_cannot_join_via_doctor_token(pg_session):
    """(c) an owner without a doctor-family role must refuse on the
    doctor-owned surface."""
    session = pg_session
    user = _make_user(session, "rq09c_nurserole", "Nurse", active=True)
    doctor = _make_doctor(session, user.id)
    world = _seed_doctor_token(session, "nurse", doctor.id)

    from app.services.queue_svc import QueueValidationError

    with pytest.raises((QueueValidationError, ValueError)):
        _join(session, world["token"])
    assert _entries(session, world["queue_id"]) == []


def test_healthy_doctor_still_joins_via_doctor_token(pg_session):
    """(d) positive control: an eligible doctor's token joins."""
    session = pg_session
    user = _make_user(session, "rq09c_healthy", "Doctor", active=True)
    doctor = _make_doctor(session, user.id)
    world = _seed_doctor_token(session, "healthy", doctor.id)

    result = _join(session, world["token"])
    assert result["success"] is True, result
    entries = _entries(session, world["queue_id"])
    assert len(entries) == 1
    assert entries[0].patient_id is not None


def test_resource_owned_surface_joins_without_doctor_role_gate(pg_session):
    """(e) QD-2C regression guard: when the registry surface is
    resource-owned, the legacy synthetic token owner (role 'Lab') must
    still join — the resource, not the synthetic doctor, owns the queue."""
    session = pg_session
    from app.models.online_queue import DailyQueue, QueueResource, QueueToken

    # The 0055-style synthetic: a Doctor row whose owner has NO
    # doctor-family role — this is the lab-resource mirror. A DEDICATED
    # tag isolates the surface from the other tests' doctor-owned
    # (day, cardiology) queues (tag_routes_to_resource picks the FIRST
    # active (day, tag) queue).
    user = _make_user(session, "rq09c_labsynth", "Lab", active=True)
    synth = _make_doctor(session, user.id, specialty="rq09c-tag")

    resource = QueueResource(
        code=f"rq09c-lab-{synth.id}",
        queue_tag="rq09c-tag",
        display_name="RQ-09.c synthetic lab resource",
        active=True,
        start_number_online=1,
        max_online_per_day=15,
        default_cabinet="L1",
    )
    session.add(resource)
    session.commit()
    session.refresh(resource)

    day = _clinic_day()
    resource_queue = DailyQueue(
        day=day,
        specialist_id=None,
        queue_resource_id=resource.id,
        queue_tag="rq09c-tag",
        active=True,
    )
    session.add(resource_queue)
    session.commit()

    local_now = datetime.now(ZoneInfo("Asia/Tashkent")).replace(tzinfo=None)
    token = QueueToken(
        token="rq09c-token-resource",
        day=day,
        specialist_id=synth.id,
        department="rq09c-tag",
        expires_at=local_now + timedelta(hours=2),
        active=True,
    )
    session.add(token)
    session.commit()

    result = _join(session, token.token)
    assert result["success"] is True, result
    entries = _entries(session, resource_queue.id)
    assert len(entries) == 1
    # The entry landed on the RESOURCE-owned queue, not a doctor queue.
    assert entries[0].queue_id == resource_queue.id
