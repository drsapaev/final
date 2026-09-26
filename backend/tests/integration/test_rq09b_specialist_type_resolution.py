"""
RQ-09.b — explicit specialist TYPE resolution for the clinic-wide QR join.

D-01 APPROVED 2026-09-15 (verbatim): «Doctor.id, QueueResource.id и
QueueProfile.id — разные пространства. Тип выбора передаётся явно.
... Не определять тип сущности по совпадению числового ID».

Defect being pinned (registered at E-028 as RQ-09.b): the clinic-wide
branch of ``join_queue_with_token`` probed
``QueueProfile.id == specialist_id_override`` FIRST. The public selection
SSOT emits DOCTOR ids (``selectable_specialists[].id`` = Doctor.id), so
whenever a small QueueProfile.id collided with the submitted Doctor.id,
the join silently re-routed the patient onto the PROFILE route
(least-loaded across the specialty / resource surface) instead of the
chosen doctor.

Contract under D-01 (this slice):
- ``specialist_type`` is passed EXPLICITLY by the caller through the
  session-join API (``specialist_entity_types`` aligned with
  ``specialist_ids``);
- ``None``/``"doctor"`` (the legacy untyped form — the only ids the
  current selection emits) resolves DIRECTLY to the doctor branch; the
  numeric ``QueueProfile.id`` probe is removed;
- ``"profile"`` keeps the profile route reachable — profile ids are
  honored only when typed explicitly;
- unknown types and misaligned type lists are rejected.

Collision mechanics: seeded migrations occupy both id spaces, so the
colliding QueueProfile row is inserted with an EXPLICIT id equal to the
already-created doctor's id (the queue_profiles sequence is re-synced via
setval afterwards). Disposable PostgreSQL: the module provisions its own
scratch database (rq09b_check), runs ``alembic upgrade head`` and drops
it at the end; skips (NOT_RUN per plan P0) when no local disposable
PostgreSQL is reachable. SYNTHETIC data only.
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
SCRATCH_DB_PREFIX = "rq09b_check"
SCRATCH_DB = f"{SCRATCH_DB_PREFIX}_{uuid.uuid4().hex[:12]}"

sys.path.insert(0, str(BACKEND_DIR))


def _candidate_admin_urls() -> list[str]:
    urls: list[str] = []
    explicit = os.getenv("RQ09B_PG_ADMIN_URL", "").strip()
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
            f"disposable PostgreSQL unavailable — RQ-09.b PG acceptance NOT_RUN "
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
        full_name=f"RQ-09.b {username}",
        hashed_password=get_password_hash("rq09b-synthetic-pw"),
        role=role,
        is_active=active,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def _make_doctor(session, user_id: int | None, specialty: str, active: bool = True):
    from app.models.clinic import Doctor

    doctor = Doctor(
        user_id=user_id,
        specialty=specialty,
        cabinet="209",
        active=active,
    )
    session.add(doctor)
    session.commit()
    session.refresh(doctor)
    return doctor


def _make_eligible_doctor(session, username: str, specialty: str):
    user = _make_user(session, username, "Doctor")
    return _make_doctor(session, user.id, specialty)


def _max_table_id(session, table: str) -> int:
    return int(
        session.execute(text(f"SELECT COALESCE(MAX(id), 0) FROM {table}")).scalar() or 0
    )


def _make_eligible_doctor_above_profiles(session, username: str, specialty: str):
    """An eligible doctor whose id is guaranteed ABOVE every seeded
    QueueProfile id (migrations seed both id spaces low — RQ-09.a's lift
    pattern), so an explicit-id profile can be placed exactly on this
    doctor's id without touching the seeded pkeys."""
    target = _max_table_id(session, "queue_profiles") + 1
    while True:
        next_id = _max_table_id(session, "doctors") + 1
        if next_id >= target:
            break
        _make_doctor(session, user_id=None, specialty="filler", active=False)
    return _make_eligible_doctor(session, username, specialty)


def _make_visible_profile_at(session, explicit_id: int, key: str):
    """Insert a QR-visible profile with an EXPLICIT id (the collision
    under test) and re-sync the id sequence so later auto-inserts stay
    consistent."""
    from app.models.queue_profile import QueueProfile

    profile = QueueProfile(
        id=explicit_id,
        key=key,
        title=f"RQ09b {key}",
        title_ru=f"RQ09b {key}",
        queue_tags=[key],
        department_key=key,
        display_order=90,
        is_active=True,
        show_on_qr_page=True,
    )
    session.add(profile)
    session.commit()
    session.refresh(profile)
    session.execute(
        text(
            "SELECT setval(pg_get_serial_sequence('queue_profiles', 'id'), "
            "GREATEST((SELECT MAX(id) FROM queue_profiles), 1))"
        )
    )
    session.commit()
    return profile


def _seed_clinic_wide_token(session, suffix: str) -> dict:
    from app.models.online_queue import QueueToken

    day = _clinic_day()
    local_now = datetime.now(ZoneInfo("Asia/Tashkent")).replace(tzinfo=None)
    token = QueueToken(
        token=f"rq09b-token-{suffix}",
        day=day,
        is_clinic_wide=True,
        department="rq09b",
        expires_at=local_now + timedelta(hours=2),
        active=True,
    )
    session.add(token)
    session.commit()
    return {"token": token.token, "day": day}


def _join(session, token: str, specialist_ids, entity_types=None) -> dict:
    from app.services.qr_queue import QRQueueService

    svc = QRQueueService(session)
    start = svc.start_join_session(token)
    kwargs: dict = {}
    if entity_types is not None:
        kwargs["specialist_entity_types"] = entity_types
    return svc.complete_join_session_multiple(
        start["session_token"],
        list(specialist_ids),
        "SYNTHETIC RQ-09.b Patient",
        "+998902010101",
        **kwargs,
    )


def _entries_for_tag(session, queue_tag: str) -> list:
    from app.models.online_queue import DailyQueue, OnlineQueueEntry

    return (
        session.query(OnlineQueueEntry)
        .join(DailyQueue, OnlineQueueEntry.queue_id == DailyQueue.id)
        .filter(DailyQueue.queue_tag == queue_tag)
        .all()
    )


def _entry_queue(session, join_result: dict):
    from app.models.online_queue import OnlineQueueEntry

    entry_id = join_result["entries"][0]["queue_entry_id"]
    entry = session.query(OnlineQueueEntry).filter(OnlineQueueEntry.id == entry_id).first()
    return entry.queue


def _preload_waiting(session, doctor, day, tag: str, waiting: int = 1):
    """Desk-shaped (day, doctor, tag) queue with waiting entries — gives
    the least-loaded profile routing a reason to pick a DIFFERENT owner
    than the doctor the patient explicitly chose."""
    from app.models.online_queue import DailyQueue, OnlineQueueEntry

    queue = DailyQueue(day=day, specialist_id=doctor.id, queue_tag=tag, active=True)
    session.add(queue)
    session.flush()
    for number in range(1, waiting + 1):
        session.add(
            OnlineQueueEntry(
                queue_id=queue.id,
                number=number,
                patient_name=f"RQ09b preload {number}",
                status="waiting",
                source="desk",
            )
        )
    session.commit()
    return queue


def test_untyped_doctor_id_with_colliding_profile_id_keeps_selected_doctor(pg_session):
    """(a) THE misroute pin: the patient picks doctor D1 whose id collides
    with a visible QueueProfile id; an idle eligible sibling D2 exists.
    The untyped join must land on D1's (day, D1, tag) row — never on the
    profile route's least-loaded pick (D2)."""
    session = pg_session
    d1 = _make_eligible_doctor_above_profiles(session, "rq09b_collision_d1", "rq09bcard")
    profile = _make_visible_profile_at(session, d1.id, "rq09bcard")
    assert profile.id == d1.id
    d2 = _make_eligible_doctor(session, "rq09b_collision_d2", "rq09bcard")
    assert d2.id != d1.id
    world = _seed_clinic_wide_token(session, "misroute")
    _preload_waiting(session, d1, world["day"], "rq09bcard", waiting=1)

    result = _join(session, world["token"], [d1.id])

    assert result["success"] is True, result
    routed = _entry_queue(session, result)
    assert routed.specialist_id == d1.id, (
        f"join silently re-routed to specialist {routed.specialist_id} "
        f"(profile route least-loaded pick) instead of chosen doctor {d1.id}"
    )
    assert routed.queue_resource_id is None


def test_untyped_profile_id_without_doctor_match_is_refused(pg_session):
    """(b) an untyped id that matches NO doctor but matches a visible
    profile must be REFUSED (D-01: no numeric-id guessing) — the base
    behavior silently joined the profile route."""
    session = pg_session
    d3 = _make_eligible_doctor_above_profiles(session, "rq09b_derma_doc", "rq09bderma")
    profile = _make_visible_profile_at(session, d3.id + 7, "rq09bderma")
    world = _seed_clinic_wide_token(session, "refuse")

    from app.services.queue_svc import QueueValidationError

    with pytest.raises((QueueValidationError, ValueError)):
        _join(session, world["token"], [profile.id])

    assert _entries_for_tag(session, "rq09bderma") == []


def test_explicit_doctor_type_joins_chosen_doctor_under_collision(pg_session):
    """(c) explicit ``specialist_entity_types=['doctor']`` resolves the
    chosen doctor directly even under the id collision."""
    session = pg_session
    d1 = _make_eligible_doctor_above_profiles(session, "rq09b_explicit_doc", "rq09bcard2")
    _make_visible_profile_at(session, d1.id, "rq09bcard2")
    _make_eligible_doctor(session, "rq09b_explicit_doc2", "rq09bcard2")
    world = _seed_clinic_wide_token(session, "explicitdoc")

    result = _join(session, world["token"], [d1.id], entity_types=["doctor"])

    assert result["success"] is True, result
    routed = _entry_queue(session, result)
    assert routed.specialist_id == d1.id
    assert routed.queue_tag == "rq09bcard2"


def test_explicit_profile_type_resolves_profile_route(pg_session):
    """(d) explicit ``specialist_entity_types=['profile']`` keeps the
    profile route reachable (D-01: профильный выбор разрешается сервером
    в конкретного допустимого исполнителя) — least-loaded routing among
    the profile's eligible doctors."""
    session = pg_session
    d1 = _make_eligible_doctor_above_profiles(session, "rq09b_explicit_prof", "rq09bcard3")
    profile = _make_visible_profile_at(session, d1.id + 3, "rq09bcard3")
    world = _seed_clinic_wide_token(session, "explicitprof")

    result = _join(session, world["token"], [profile.id], entity_types=["profile"])

    assert result["success"] is True, result
    routed = _entry_queue(session, result)
    assert routed.queue_tag == "rq09bcard3"
    assert routed.specialist_id == d1.id


def test_unknown_entity_type_rejected(pg_session):
    """(e) an unknown explicit type is rejected, not guessed."""
    session = pg_session
    d1 = _make_eligible_doctor_above_profiles(session, "rq09b_unknown_type", "rq09bcard4")
    _make_visible_profile_at(session, d1.id, "rq09bcard4")
    world = _seed_clinic_wide_token(session, "unknown")

    with pytest.raises(ValueError):
        _join(session, world["token"], [d1.id], entity_types=["nurse"])

    assert _entries_for_tag(session, "rq09bcard4") == []


def test_entity_types_length_mismatch_rejected(pg_session):
    """(f) ``specialist_entity_types`` must align with ``specialist_ids``."""
    session = pg_session
    d1 = _make_eligible_doctor_above_profiles(session, "rq09b_misalign", "rq09bcard5")
    _make_visible_profile_at(session, d1.id, "rq09bcard5")
    d2 = _make_eligible_doctor(session, "rq09b_misalign2", "rq09bcard5")
    world = _seed_clinic_wide_token(session, "misalign")

    with pytest.raises(ValueError):
        _join(session, world["token"], [d1.id, d2.id], entity_types=["doctor"])

    assert _entries_for_tag(session, "rq09bcard5") == []


def test_untyped_id_above_profiles_still_joins_doctor_positive_control(pg_session):
    """(g) positive control (green before AND after): a legacy untyped
    doctor id above every profile id keeps joining its own row — the
    doctor-default for untyped payloads must not break the live flow."""
    session = pg_session
    d1 = _make_eligible_doctor_above_profiles(session, "rq09b_above", "rq09bcard6")
    _make_visible_profile_at(session, d1.id + 11, "rq09bcard6")
    world = _seed_clinic_wide_token(session, "above")

    result = _join(session, world["token"], [d1.id])

    assert result["success"] is True, result
    routed = _entry_queue(session, result)
    assert routed.specialist_id == d1.id
