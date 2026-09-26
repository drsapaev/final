"""
RQ-14 verification — QR join vs registrar wizard desk assignment:
day/owner/tag consistency and the number source (ACCEPTANCE S-12).

Characterization module (documents CURRENT behavior on a disposable
PostgreSQL; SYNTHETIC data only; no runtime code is changed by this
slice — defects pinned here are registered as plan children):

1. ``test_desk_then_qr_aligned_tags_share_queue_row`` — positive control:
   with service.queue_tag == doctor.specialty == profile key the desk
   wizard assignment and the QR join land in the SAME DailyQueue row and
   numbering continues (1, 2) with preserved queue_time/status/source.

2. ``test_concurrent_desk_and_qr_numbering_can_duplicate_within_one_queue``
   — pins the numbering gap (plan child RQ-14.a): both writers resolve
   the next number with a plain ``SELECT MAX(number)`` over the same
   queue row — ``get_next_queue_number`` takes ``with_for_update()`` only
   when it re-fetches the queue by id, while both live paths
   (``RegistrarWizardQueueAssignmentService`` create-branch and
   ``join_queue_with_token``) pass an ALREADY LOADED queue, and
   ``queue_entries`` has NO unique constraint on ``(queue_id, number)``.
   A deterministic barrier inside ``calculate_next_number`` shows two
   concurrent writers committing the same number. When the integrity fix
   lands, this test must be rewritten to assert uniqueness.

3. ``test_qr_override_and_desk_share_row_for_registered_direction`` —
   RQ-14.b FIXED (was the E-033 owner-fork pin, flipped per D-01
   APPROVED): a doctor whose stored specialty spelling drifted from the
   direction registry + a service registered under the direction's
   canonical key — desk and the clinic-wide QR doctor-override join
   land on the SAME ``(day, doctor, canonical tag)`` row.

4. ``test_distinct_direction_tags_keep_separate_rows_without_raw_specialty``
   — the no-collapse half of D-01: a service tag OUTSIDE the doctor's
   direction vocabulary keeps a separate desk row (service tag
   verbatim); no queue row is tagged with the RAW specialty spelling
   anymore (the per-surface fallback source is gone, nothing is
   merged or renumbered).

Disposable PostgreSQL: the module provisions its own scratch database
(rq14_check), runs ``alembic upgrade head`` and drops it at the end;
skips (NOT_RUN per plan P0) when no local disposable PostgreSQL is
reachable. SQLite is never a substitute here.
"""

from __future__ import annotations

import os
import sys
import threading
import uuid
from datetime import datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import psycopg
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

BACKEND_DIR = Path(__file__).resolve().parents[2]
SCRATCH_DB_PREFIX = "rq14_check"
SCRATCH_DB = f"{SCRATCH_DB_PREFIX}_{uuid.uuid4().hex[:12]}"

sys.path.insert(0, str(BACKEND_DIR))


def _candidate_admin_urls() -> list[str]:
    """Admin DSNs for scratch provisioning — LOCAL servers only."""
    urls: list[str] = []
    explicit = os.getenv("RQ14_PG_ADMIN_URL", "").strip()
    if explicit:
        urls.append(explicit)
    local_pw = os.getenv("LOCAL_PG_SUPERUSER_PASSWORD", "").strip()
    if local_pw:
        urls.append(f"postgresql://postgres:{local_pw}@localhost:5432/postgres")
    env_url = os.getenv("DATABASE_URL", "").strip()
    if env_url:
        urls.append(env_url)
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
            f"disposable PostgreSQL unavailable — RQ-14 PG acceptance NOT_RUN "
            f"(last error: {last_error})"
        )

    psycopg_dsn, sa_url = _scratch_urls(admin_url)
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
        dialect = conn.execute(text("select version()")).scalar()
    assert version, "alembic_version must be present after upgrade"
    assert "PostgreSQL" in (dialect or ""), "RQ-14 proof requires real PostgreSQL"

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


def _clinic_day(session) -> object:
    from app.crud.clinic import clinic_today

    return clinic_today(session)


def _seed_join_world(
    session,
    *,
    suffix: str,
    service_tag: str,
    doctor_specialty: str | None = None,
    profile_queue_tags: list[str] | None = None,
) -> dict:
    """SYNTHETIC world: active doctor, visible cardiology profile, service,
    clinic-wide QR token, two patients, one confirmed visit (desk side).

    ``doctor_specialty`` seeds a DRIFTED stored specialty spelling (the
    documented live case: the dental family where the canonical stored
    value diverged from the profile registry key — D-1 vocabulary).
    ``profile_queue_tags`` widens the profile's tag vocabulary so the
    drifted spelling still resolves to the SAME QR-visible direction
    (mirroring the stomatology profile carrying ["dental", "stomatology",
    "dentist"]). Default ``None`` keeps the pre-RQ-14.b aligned shape."""
    from app.core.security import get_password_hash
    from app.models.clinic import Doctor
    from app.models.online_queue import QueueToken
    from app.models.patient import Patient
    from app.models.queue_profile import QueueProfile
    from app.models.service import Service
    from app.models.user import User
    from app.models.visit import Visit, VisitService

    username = f"rq14_doc_{suffix}"
    user = session.query(User).filter(User.username == username).first()
    if not user:
        user = User(
            username=username,
            email=f"{username}@example.com",
            full_name="RQ-14 Synthetic Doctor",
            hashed_password=get_password_hash("rq14-synthetic-pw"),
            role="Doctor",
            is_active=True,
        )
        session.add(user)
        session.commit()
        session.refresh(user)

    # RQ-09.b note: the live QR join matches specialist_id_override against
    # QueueProfile.id FIRST — a small Doctor.id colliding with a seeded
    # profile (baseline seeds profiles ids 1..7) silently reroutes the join.
    # This module pins RQ-14 behavior, so the synthetic Doctor is forced to
    # an id ABOVE every QueueProfile.id (filler doctors with an inert
    # specialty keep the collision out of the scenario).
    from sqlalchemy import func as sa_func

    max_profile_id = (
        session.query(sa_func.max(QueueProfile.id)).scalar() or 0
    )

    profile_key = f"cardiology_{suffix}"
    profile = QueueProfile(
        key=profile_key,
        title=f"Cardiology {suffix}",
        title_ru=f"Кардиология {suffix}",
        queue_tags=(
            profile_queue_tags
            if profile_queue_tags is not None
            else [profile_key]
        ),
        is_active=True,
        show_on_qr_page=True,
    )
    session.add(profile)
    session.commit()
    session.refresh(profile)
    max_profile_id = max(max_profile_id, profile.id)

    doctor = Doctor(
        user_id=user.id,
        specialty="rq14_filler",
        cabinet="101",
        active=True,
    )
    session.add(doctor)
    session.commit()
    session.refresh(doctor)
    filler_no = 0
    while doctor.id <= max_profile_id:
        filler_no += 1
        filler_user = User(
            username=f"{username}_filler_{filler_no}",
            email=f"{username}_filler_{filler_no}@example.com",
            full_name=f"RQ-14 Filler {filler_no}",
            hashed_password=get_password_hash("rq14-synthetic-pw"),
            role="Doctor",
            is_active=True,
        )
        session.add(filler_user)
        session.commit()
        session.refresh(filler_user)
        filler_doctor = Doctor(
            user_id=filler_user.id,
            specialty="rq14_filler",
            cabinet="199",
            active=True,
        )
        session.add(filler_doctor)
        session.commit()
        session.refresh(filler_doctor)
        if filler_doctor.id > max_profile_id:
            doctor = filler_doctor
    doctor.specialty = (
        doctor_specialty if doctor_specialty is not None else profile_key
    )
    session.add(doctor)
    session.commit()
    session.refresh(doctor)

    service = Service(
        code=f"RQ14{suffix[-4:]}",
        name="RQ-14 Synthetic Consultation",
        price=100000.00,
        duration_minutes=30,
        active=True,
        requires_doctor=True,
        queue_tag=service_tag,
        is_consultation=True,
    )
    session.add(service)
    session.commit()
    session.refresh(service)

    desk_patient = Patient(
        last_name=f"RQ14Desk{suffix[-4:]}",
        first_name="Desk",
        phone="+998901000001",
    )
    qr_patient = Patient(
        last_name=f"RQ14QR{suffix[-4:]}",
        first_name="QR",
        phone="+998901000002",
    )
    session.add_all([desk_patient, qr_patient])
    session.commit()
    session.refresh(desk_patient)
    session.refresh(qr_patient)

    day = _clinic_day(session)
    visit = Visit(
        patient_id=desk_patient.id,
        doctor_id=doctor.id,
        status="confirmed",
        visit_date=day,
    )
    session.add(visit)
    session.commit()
    session.refresh(visit)

    visit_service = VisitService(
        visit_id=visit.id,
        service_id=service.id,
        name=service.name,
        qty=1,
        price=100000.00,
    )
    session.add(visit_service)
    session.commit()

    local_now = datetime.now(ZoneInfo("Asia/Tashkent")).replace(
        tzinfo=None, microsecond=0
    ) + timedelta(hours=2)
    token = QueueToken(
        token=f"rq14-token-{suffix}",
        day=day,
        specialist_id=None,
        department="cardiology",
        is_clinic_wide=True,
        expires_at=local_now,
        active=True,
    )
    session.add(token)
    session.commit()

    return {
        "doctor": doctor,
        "user": user,
        "profile": profile,
        "service": service,
        "desk_patient": desk_patient,
        "qr_patient": qr_patient,
        "visit": visit,
        "token": token,
        "day": day,
    }


def _patch_online_window() -> None:
    """Open the online window for the whole test day (00:00)."""
    from app.services.queue_service import QueueBusinessService

    QueueBusinessService.ONLINE_QUEUE_START_TIME = time(0, 0)


def _desk_assignment(pg_engine, visit_id: int, day) -> dict:
    """Desk seam: RegistrarWizardQueueAssignmentService on its own session."""
    from app.models.visit import Visit
    from app.services.registrar_wizard_queue_assignment_service import (
        RegistrarWizardQueueAssignmentService,
    )

    Session = sessionmaker(bind=pg_engine, future=True)
    session = Session()
    try:
        visit = session.query(Visit).filter(Visit.id == visit_id).one()
        service = RegistrarWizardQueueAssignmentService(session)
        assignments = service.assign_same_day_queue_numbers(
            [visit],
            target_day=day,
            source="desk",
        )
        session.commit()
        return {"assignments": assignments, "error": None}
    except Exception as exc:  # noqa: BLE001
        session.rollback()
        return {"assignments": None, "error": f"{type(exc).__name__}: {exc}"}
    finally:
        session.close()


def _qr_join(pg_engine, token_str: str, doctor_id: int, patient_name: str, phone: str) -> dict:
    """QR seam: queue_service.join_queue_with_token on its own session."""
    from app.services.queue_service import queue_service

    Session = sessionmaker(bind=pg_engine, future=True)
    session = Session()
    try:
        result = queue_service.join_queue_with_token(
            session,
            token_str=token_str,
            patient_name=patient_name,
            phone=phone,
            specialist_id_override=doctor_id,
            source="online",
        )
        return {
            "entry_id": result["entry"].id,
            "queue_id": result["daily_queue"].id,
            "number": result["entry"].number,
            "duplicate": result["duplicate"],
            "error": None,
        }
    except Exception as exc:  # noqa: BLE001
        session.rollback()
        return {"entry_id": None, "error": f"{type(exc).__name__}: {exc}"}
    finally:
        session.close()


def _entries(pg_engine, queue_id: int | None = None) -> list[dict]:
    from app.models.online_queue import OnlineQueueEntry

    Session = sessionmaker(bind=pg_engine, future=True)
    session = Session()
    try:
        q = session.query(OnlineQueueEntry)
        if queue_id is not None:
            q = q.filter(OnlineQueueEntry.queue_id == queue_id)
        return [
            {
                "id": e.id,
                "queue_id": e.queue_id,
                "number": e.number,
                "source": e.source,
                "status": e.status,
                "queue_time": e.queue_time,
            }
            for e in q.all()
        ]
    finally:
        session.close()


def _queues_for_doctor(pg_engine, day) -> list[dict]:
    from app.models.online_queue import DailyQueue

    Session = sessionmaker(bind=pg_engine, future=True)
    session = Session()
    try:
        rows = (
            session.query(DailyQueue)
            .filter(DailyQueue.day == day, DailyQueue.specialist_id.isnot(None))
            .all()
        )
        return [
            {
                "id": q.id,
                "specialist_id": q.specialist_id,
                "queue_tag": q.queue_tag,
                "active": q.active,
            }
            for q in rows
        ]
    finally:
        session.close()


@pytest.mark.integration
@pytest.mark.queue
def test_desk_then_qr_aligned_tags_share_queue_row(pg_engine, pg_session):
    """S-12 positive control: aligned tags → one queue row, numbering continues."""
    _patch_online_window()
    world = _seed_join_world(
        pg_session, suffix="align", service_tag="cardiology_align"
    )

    desk = _desk_assignment(pg_engine, world["visit"].id, world["day"])
    assert desk["error"] is None, desk
    assert desk["assignments"], "desk assignment must produce queue numbers"
    desk_visit_id = world["visit"].id
    assert len(desk["assignments"][desk_visit_id]) == 1
    desk_number = desk["assignments"][desk_visit_id][0]["number"]

    qr = _qr_join(
        pg_engine,
        world["token"].token,
        world["doctor"].id,
        "RQ-14 QR Patient",
        "+998901000002",
    )
    assert qr["error"] is None, qr
    assert qr["duplicate"] is False

    queues = [
        q
        for q in _queues_for_doctor(pg_engine, world["day"])
        if q["specialist_id"] == world["doctor"].id
    ]
    assert len(queues) == 1, f"expected ONE shared queue row, got {queues}"
    assert queues[0]["queue_tag"] == world["doctor"].specialty

    entries = _entries(pg_engine, queues[0]["id"])
    assert len(entries) == 2
    by_source = {e["source"]: e for e in entries}
    assert set(by_source) == {"desk", "online"}
    assert by_source["desk"]["number"] == desk_number
    assert by_source["online"]["number"] == qr["number"]
    assert qr["number"] == max(e["number"] for e in entries)
    for e in entries:
        assert e["status"] == "waiting"
        assert e["queue_time"] is not None


@pytest.mark.integration
@pytest.mark.queue
def test_concurrent_desk_and_qr_numbering_stay_unique_within_one_queue(
    pg_engine, pg_session
):
    """RQ-14.a FIXED (was the E-033 duplicate pin, flipped on the fix):
    same queue row, two concurrent writers — DISTINCT numbers.

    The E-033 pin proved the numbering race: both writers computed the
    next number via an unlocked ``SELECT MAX`` on an already-loaded
    queue (no row lock, no (queue_id, number) unique) and committed the
    SAME number behind a barrier. RQ-14.a serializes every writer of a
    queue on the queue row (FOR UPDATE in ``get_next_queue_number`` for
    the already-loaded branch), so the second writer reads a fresh
    snapshot after the first one's number landed. Per-queue uniqueness
    is asserted here; numbers repeating ACROSS queues is a different
    (preserved) contract."""

    _patch_online_window()
    world = _seed_join_world(pg_session, suffix="race", service_tag="cardiology_race")

    from app.models.online_queue import DailyQueue

    # Pre-create the shared queue row so both writers RESOLVE it instead of
    # racing in get_or_create (that separate race is covered by the RQ-14.a
    # integration suite).
    Session = sessionmaker(bind=pg_engine, future=True)
    seed_session = Session()
    queue_row = DailyQueue(
        day=world["day"],
        specialist_id=world["doctor"].id,
        queue_tag=world["doctor"].specialty,
        active=True,
    )
    seed_session.add(queue_row)
    seed_session.commit()
    queue_id = queue_row.id
    seed_session.close()

    results: dict[str, dict] = {}

    def desk_worker():
        results["desk"] = _desk_assignment(pg_engine, world["visit"].id, world["day"])

    def qr_worker():
        results["qr"] = _qr_join(
            pg_engine,
            world["token"].token,
            world["doctor"].id,
            "RQ-14 QR Patient Race",
            "+998901000002",
        )

    threads = [
        threading.Thread(target=desk_worker),
        threading.Thread(target=qr_worker),
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=60)

    assert "desk" in results and "qr" in results
    assert results["desk"]["error"] is None, results["desk"]
    assert results["qr"]["error"] is None, results["qr"]

    entries = _entries(pg_engine, queue_id)
    assert len(entries) == 2, f"both writers must land on the shared row: {entries}"
    numbers = sorted(e["number"] for e in entries)
    # THE CONTRACT (RQ-14.a): per-queue numbers must not duplicate.
    assert len(set(numbers)) == 2, (
        f"per-queue uniqueness violated: {numbers}"
    )


@pytest.mark.integration
@pytest.mark.queue
def test_qr_override_and_desk_share_row_for_registered_direction(
    pg_engine, pg_session
):
    """RQ-14.b FIXED (was the E-033 owner-fork pin, flipped per D-01):
    desk and the QR doctor-override join resolve ONE row for the same
    registered direction.

    Pre-fix behavior (the E-033 pin): the clinic-wide doctor-override
    branch derived ``queue_tag`` from the RAW ``doctor.specialty``
    string — a per-surface fallback source. With the stored specialty
    spelling drifted from the profile registry key (the documented
    dental-family case) the same (day, doctor) got TWO rows numbered
    independently — the desk patient and the QR patient of the SAME
    direction landed in different queues.

    D-01 (APPROVED 2026-09-15): one server-side resolution method for
    desk and QR, no per-surface fallbacks, no name guessing. The QR
    override branch now resolves the tag through the SAME direction
    registry source as the profile-pick branch — the QR-visible
    profile's canonical key. The desk keeps the approved source
    (``service.queue_tag``); when the service is registered under the
    direction's canonical key, both surfaces share the row and
    numbering continues (1, 2) with sources desk/online preserved."""
    _patch_online_window()
    drifted = "cardio_legacy_flip"
    world = _seed_join_world(
        pg_session,
        suffix="flip",
        service_tag="cardiology_flip",
        doctor_specialty=drifted,
        profile_queue_tags=["cardiology_flip", drifted],
    )

    desk = _desk_assignment(pg_engine, world["visit"].id, world["day"])
    assert desk["error"] is None, desk
    assert desk["assignments"], "desk assignment must produce queue numbers"
    desk_visit_id = world["visit"].id
    desk_number = desk["assignments"][desk_visit_id][0]["number"]

    qr = _qr_join(
        pg_engine,
        world["token"].token,
        world["doctor"].id,
        "RQ-14 QR Patient Flip",
        "+998901000002",
    )
    assert qr["error"] is None, qr
    assert qr["duplicate"] is False

    queues = [
        q
        for q in _queues_for_doctor(pg_engine, world["day"])
        if q["specialist_id"] == world["doctor"].id
    ]
    # THE CONTRACT (D-01/RQ-14.b): ONE canonical row for the registered
    # direction — the profile registry key — shared by both surfaces.
    assert len(queues) == 1, f"expected ONE shared queue row, got {queues}"
    assert queues[0]["queue_tag"] == "cardiology_flip"

    entries = _entries(pg_engine, queues[0]["id"])
    assert len(entries) == 2
    by_source = {e["source"]: e for e in entries}
    assert set(by_source) == {"desk", "online"}
    assert by_source["desk"]["number"] == desk_number
    assert qr["number"] == max(e["number"] for e in entries)
    for e in entries:
        assert e["status"] == "waiting"
        assert e["queue_time"] is not None


@pytest.mark.integration
@pytest.mark.queue
def test_distinct_direction_tags_keep_separate_rows_without_raw_specialty(
    pg_engine, pg_session
):
    """RQ-14.b no-collapse half (D-01): separate tags stay separate rows;
    no queue row carries the RAW specialty spelling anymore.

    A service tag OUTSIDE the doctor's direction vocabulary is a
    different direction: the desk row keeps the service tag verbatim,
    the QR override join lands on the doctor's registry direction
    (profile key). D-01 forbids auto-collapsing different tags of one
    doctor and forbids merging/renumbering existing queues — so TWO
    rows is the correct outcome here; the flipped part is the tag
    SOURCE: the QR row must be the registry key, not the raw
    ``doctor.specialty`` string the legacy branch used before."""
    _patch_online_window()
    drifted = "cardio_legacy_noc"
    outside_tag = "cardiology_outside_noc"
    world = _seed_join_world(
        pg_session,
        suffix="noc",
        service_tag=outside_tag,
        doctor_specialty=drifted,
        profile_queue_tags=["cardiology_noc", drifted],
    )

    desk = _desk_assignment(pg_engine, world["visit"].id, world["day"])
    assert desk["error"] is None, desk
    assert desk["assignments"], "desk assignment must produce queue numbers"

    qr = _qr_join(
        pg_engine,
        world["token"].token,
        world["doctor"].id,
        "RQ-14 QR Patient NoCollapse",
        "+998901000002",
    )
    assert qr["error"] is None, qr
    assert qr["duplicate"] is False

    queues = [
        q
        for q in _queues_for_doctor(pg_engine, world["day"])
        if q["specialist_id"] == world["doctor"].id
    ]
    tags = {q["queue_tag"] for q in queues}
    # Distinct directions stay distinct (no silent collapse)…
    assert len(queues) == 2, f"expected separate direction rows, got {queues}"
    # …both tags are CANONICAL sources: the service tag verbatim (desk)
    # and the direction registry key (QR).
    assert tags == {outside_tag, "cardiology_noc"}, (
        f"expected canonical tags only, got {tags}"
    )
    # The per-surface raw-specialty fallback is gone.
    assert drifted not in tags, (
        f"raw specialty spelling must not own a queue row: {tags}"
    )
