"""RQ-08 backend slice: the doctor's own today-panel must show every queue
the doctor OWNS, regardless of its queue_tag.

Defect (F-07 / plan RQ-08 result «врач видит положенные ему записи»):
``GET /doctor/{specialty}/queue/today`` scopes DailyQueue by
``specialist_id == doctor.id`` (ownership — D-5 world) but then subtracts
queues whose ``queue_tag`` is not in the hard-coded
``DOCTOR_QUEUE_ALLOWED_TAGS`` allow-list. Queue tags are free strings
chosen per service (``Service.queue_tag`` — e.g. ``cardiology_diagnostics``,
``cardio_echo``) or by profiles, so a doctor's own queue created by the
wizard (``registrar_wizard/_helpers.py`` creates one DailyQueue per unique
``service.queue_tag`` with ``specialist_id = visit.doctor_id``) is
invisible in the owner's panel: the doctor sees ``queue_exists: false``
while patients wait in a queue only they can serve.

Scope of this slice: visibility of OWNED queues in the doctor panel only.
RBAC, D-5 no-substitution 403, same-specialty collaboration and the
general-sentinel path are NOT changed; new-profile tag discovery,
frontend alias lists and ``wizardUtils.filterDoctorsForService`` remain a
separate child slice per the plan.

Disposable PostgreSQL: the module provisions its own scratch database
(rq08_check), runs ``alembic upgrade head`` against it and drops it at the
end. Skips (NOT_RUN, per plan P0) when no disposable PostgreSQL server is
reachable. SQLite is never a substitute here. Only synthetic data is used
(synthetic names/phones), no PHI/PII.
"""

from __future__ import annotations

import os
import sys
from datetime import date
from pathlib import Path

import psycopg
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker

BACKEND_DIR = Path(__file__).resolve().parents[2]
SCRATCH_DB = "rq08_check"

sys.path.insert(0, str(BACKEND_DIR))


def _candidate_admin_urls() -> list[str]:
    """Admin DSNs for scratch provisioning — LOCAL servers only."""
    urls: list[str] = []

    explicit = os.getenv("RQ08_PG_ADMIN_URL", "").strip()
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
            f"disposable PostgreSQL unavailable — RQ-08 PG acceptance NOT_RUN "
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


@pytest.fixture
def pg_client(pg_session):
    """TestClient wired to the disposable PostgreSQL session."""
    from app.api.deps import get_db
    from app.main import app

    def override_get_db():
        try:
            yield pg_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def _headers_for(user) -> dict[str, str]:
    from tests.conftest import mint_access_token

    return {"Authorization": f"Bearer {mint_access_token(user)}"}


def _doctor_with_user(pg_session, *, specialty: str, label: str):
    """Synthetic doctor: own User account + own active Doctor profile."""
    from app.core.security import get_password_hash
    from app.models.clinic import Doctor
    from app.models.user import User

    user = (
        pg_session.query(User).filter(User.username == f"rq08_{label}").first()
    )
    if user is None:
        user = User(
            username=f"rq08_{label}",
            email=f"rq08-{label}@synthetic.test",
            full_name=f"RQ-08 Doctor {label}",
            hashed_password=get_password_hash("rq08-synthetic-pw"),
            role="Doctor",
            is_active=True,
        )
        pg_session.add(user)
        pg_session.flush()
    doctor = (
        pg_session.query(Doctor).filter(Doctor.user_id == user.id).first()
    )
    if doctor is None:
        doctor = Doctor(
            user_id=user.id,
            specialty=specialty,
            cabinet=f"RQ08-{label}",
            active=True,
        )
        pg_session.add(doctor)
        pg_session.commit()
    pg_session.refresh(user)
    pg_session.refresh(doctor)
    return user, doctor


def _patient(pg_session, label: str):
    from app.models.patient import Patient

    patient = Patient(
        first_name="RQ08",
        last_name=f"Synthetic{label}",
        phone=f"+9989000000{label}",
    )
    pg_session.add(patient)
    pg_session.commit()
    pg_session.refresh(patient)
    return patient


def _owned_queue(pg_session, doctor, *, queue_tag: str | None, number: int, label: str):
    """DailyQueue owned by this doctor (specialist_id match) + one entry."""
    from app.models.online_queue import DailyQueue, OnlineQueueEntry

    queue = DailyQueue(
        day=date.today(),
        specialist_id=doctor.id,
        queue_tag=queue_tag,
        active=True,
    )
    pg_session.add(queue)
    pg_session.commit()
    pg_session.refresh(queue)
    patient = _patient(pg_session, label)
    entry = OnlineQueueEntry(
        queue_id=queue.id,
        number=number,
        patient_id=patient.id,
        patient_name=f"{patient.last_name} {patient.first_name}",
        phone=patient.phone,
        source="registrar",
        status="waiting",
    )
    pg_session.add(entry)
    pg_session.commit()
    pg_session.refresh(entry)
    return queue, entry


# ===================== fail-first: owned queues with
# ===================== profile/service tags (RED before the fix)


def test_own_queue_with_profile_tag_visible(pg_client, pg_session):
    """cardiology_diagnostics is the seeded cardiology profile tag
    (characterization pins) yet it is NOT in DOCTOR_QUEUE_ALLOWED_TAGS —
    the doctor must still see their own queue."""
    from app.models.online_queue import DailyQueue

    user, doctor = _doctor_with_user(pg_session, specialty="cardiology", label="proftag")
    queue, entry = _owned_queue(
        pg_session,
        doctor,
        queue_tag="cardiology_diagnostics",
        number=11,
        label="Proftag",
    )

    response = pg_client.get(
        "/api/v1/doctor/cardiology/queue/today",
        headers=_headers_for(user),
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["queue_exists"] is True, (
        "RQ-08 defect: the doctor's own queue is hidden because its "
        f"queue_tag is not in the hardcoded allow-list (tag={queue.queue_tag!r})"
    )
    assert queue.id in (body.get("queue_ids") or [body.get("queue_id")])
    numbers = [e["number"] for e in body["entries"]]
    assert entry.number in numbers


def test_own_queue_with_fully_custom_tag_visible(pg_client, pg_session):
    """An arbitrary custom tag (free string on the service) must not hide
    the queue the doctor owns."""
    user, doctor = _doctor_with_user(pg_session, specialty="cardiology", label="custom")
    queue, entry = _owned_queue(
        pg_session,
        doctor,
        queue_tag="cardio_echo",
        number=12,
        label="Custom",
    )

    response = pg_client.get(
        "/api/v1/doctor/cardiology/queue/today",
        headers=_headers_for(user),
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["queue_exists"] is True, (
        f"RQ-08 defect: owned queue with custom tag {queue.queue_tag!r} hidden"
    )
    numbers = [e["number"] for e in body["entries"]]
    assert entry.number in numbers


def test_new_specialty_own_custom_tag_visible(pg_client, pg_session):
    """A NEW supported specialty (neurology) with a profile tag 'neuro':
    the fallback allow-list is ['neurology'], the profile tag differs —
    the doctor must still see their own queue without code changes."""
    user, doctor = _doctor_with_user(pg_session, specialty="neurology", label="neuro")
    queue, entry = _owned_queue(
        pg_session,
        doctor,
        queue_tag="neuro",
        number=13,
        label="Neuro",
    )

    response = pg_client.get(
        "/api/v1/doctor/neurology/queue/today",
        headers=_headers_for(user),
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["queue_exists"] is True, (
        f"RQ-08 defect: new-specialty owned queue hidden (tag={queue.queue_tag!r})"
    )
    numbers = [e["number"] for e in body["entries"]]
    assert entry.number in numbers


# ===================== regression pins (expected GREEN before AND after)


def test_own_queue_legacy_hardcoded_tag_still_visible(pg_client, pg_session):
    """The legacy allow-listed tag keeps working (no regression)."""
    user, doctor = _doctor_with_user(pg_session, specialty="cardiology", label="legacy")
    queue, entry = _owned_queue(
        pg_session, doctor, queue_tag="cardio", number=14, label="Legacy"
    )

    response = pg_client.get(
        "/api/v1/doctor/cardiology/queue/today",
        headers=_headers_for(user),
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["queue_exists"] is True
    numbers = [e["number"] for e in body["entries"]]
    assert entry.number in numbers


def test_own_queue_null_tag_still_visible(pg_client, pg_session):
    """NULL-tag owned queues were reachable via the legacy fallback — pin it."""
    user, doctor = _doctor_with_user(pg_session, specialty="cardiology", label="nulltag")
    queue, entry = _owned_queue(
        pg_session, doctor, queue_tag=None, number=15, label="Nulltag"
    )

    response = pg_client.get(
        "/api/v1/doctor/cardiology/queue/today",
        headers=_headers_for(user),
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["queue_exists"] is True
    numbers = [e["number"] for e in body["entries"]]
    assert entry.number in numbers


def test_colleague_custom_tag_queue_not_leaked(pg_client, pg_session):
    """Ownership scoping is untouched: a same-specialty colleague's queue
    (custom tag) never appears in the caller's panel — D-5 contract."""
    _doctor_with_user(pg_session, specialty="cardiology", label="leakera")
    user_b, doctor_b = _doctor_with_user(
        pg_session, specialty="cardiology", label="leakerb"
    )
    queue_b, entry_b = _owned_queue(
        pg_session,
        doctor_b,
        queue_tag="cardio_echo",
        number=16,
        label="Leakb",
    )

    response = pg_client.get(
        "/api/v1/doctor/cardiology/queue/today",
        headers=_headers_for(user_b),
    )
    assert response.status_code == 200, response.text
    body = response.json()
    # doctor B DOES see their own custom-tag queue…
    assert body["queue_exists"] is True
    numbers = [e["number"] for e in body["entries"]]
    assert entry_b.number in numbers

    # …and doctor A (own profile, no queues) sees nothing of B's.
    from app.models.user import User

    user_a = pg_session.query(User).filter(User.username == "rq08_leakera").first()
    response_a = pg_client.get(
        "/api/v1/doctor/cardiology/queue/today",
        headers=_headers_for(user_a),
    )
    assert response_a.status_code == 200, response_a.text
    body_a = response_a.json()
    assert body_a["queue_exists"] is False, "colleague queue leaked into A's panel"
    assert body_a["entries"] == []
