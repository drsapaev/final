"""
RQ-13.b — D-06 (APPROVED, E-039): snapshot of the day's APPLIED parameters,
including the START NUMBER (ACCEPTANCE S-11 server part).

Owner decision (DECISION_PROPOSALS.md, «Решение владельца продукта»):
«Для действующей дневной очереди сохраняется снимок применённых
параметров, включая стартовый номер, время и лимит. Не обещать "без
миграции": при нехватке сохраняемых полей потребуется отдельный
Alembic-срез по правилам плана. Новые настройки не меняют выданные
номера и историю текущего дня.»

Verified pre-slice (f6d9128, merged #3250): ``DailyQueue`` snapshots only
``online_start_time``/``online_end_time``/``max_online_entries``; the
``start_number`` column DOES NOT EXIST and ``calculate_next_number`` falls
back to LIVE sources at numbering time (``QueueResource.start_number_online``
for the resource axis, clinic ``start_numbers``/``SPECIALTY_START_NUMBERS``
for the doctor axis) — so a mid-day change of those live settings shifts the
numbering baseline of the ACTIVE day (the D-06 defect). The GraphQL join
path additionally floors doctor queues at the LIVE ``doctor.start_number_online``.

This slice (contract pinned RED-first by this module):

1. Day creation FREEZES ``DailyQueue.start_number`` to the effective
   applied value of that day at creation time:
   - resource day: ``QueueResource.start_number_online`` (QD-2C registry
     SSOT — unchanged priority);
   - doctor day: ``doctor.start_number_online`` when explicitly configured
     (>1 — the column default is treated as "unconfigured"), otherwise the
     clinic level (``settings.start_numbers[tag]`` →
     ``SPECIALTY_START_NUMBERS[tag]`` → default 1). This is the D-06 chain
     «клиника → отделение → владелец» (owner wins when configured); the
     department level arrives with RQ-23.
2. Numbering engines consume the SNAPSHOT first:
   ``calculate_next_number`` (the column now exists, so its existing
   snapshot-first chain becomes live), ``get_next_queue_number`` (the
   snapshot check moves ABOVE the live registry re-read) and the GraphQL
   joinQueue floor (snapshot before ``resource_start_number`` /
   ``doctor.start_number_online``).
   Intended flips vs pre-slice behavior (all D-06-directed, documented):
   - a mid-day change of live settings no longer shifts the active day's
     floor (T2/T5);
   - a doctor day with a configured owner start (>1) numbers from the
     OWNER value on the REST path too (pre-slice REST ignored it and used
     the clinic tag default; GQL already used the owner value — the two
     engines converge on the frozen snapshot, T3/T5).
3. Alembic 0067 adds the NOT NULL DEFAULT 1 column and backfills existing
   rows from their owner's ``start_number_online`` (resource join /
   doctor join), so in-flight days keep their pre-migration baseline.

Disposable PostgreSQL: the acceptance tests provision a scratch database at
the current head. The historical migration test provisions a separate database
at 0066. Both scratch databases are dropped at teardown. Skips (NOT_RUN, per
plan P0) when no disposable PostgreSQL server is reachable. SYNTHETIC data only.
"""

from __future__ import annotations

import asyncio
import os
import subprocess
import sys
import uuid
from contextlib import contextmanager
from datetime import date, datetime
from pathlib import Path
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import psycopg
import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import URL, make_url
from sqlalchemy.orm import sessionmaker

BACKEND_DIR = Path(__file__).resolve().parents[2]
SCRATCH_DB_PREFIX = "rq13b_check"
SNAPSHOT_PREDECESSOR = "0066_general_retirement_cutover"
SNAPSHOT_REVISION = "0067_daily_queue_start_number"

sys.path.insert(0, str(BACKEND_DIR))

from tests._pg_admin_guard import is_local_admin_dsn  # noqa: E402

pytestmark = pytest.mark.integration


def _candidate_admin_urls() -> list[str]:
    """Admin DSNs for scratch provisioning — LOCAL servers only."""
    urls: list[str] = []
    explicit = os.getenv("RQ13B_PG_ADMIN_URL", "").strip()
    if is_local_admin_dsn(explicit):
        urls.append(explicit)
    local_pw = os.getenv("LOCAL_PG_SUPERUSER_PASSWORD", "").strip()
    if local_pw:
        local_url = URL.create(
            "postgresql",
            username="postgres",
            password=local_pw,
            host="localhost",
            port=5432,
            database="postgres",
        ).render_as_string(hide_password=False)
        if is_local_admin_dsn(local_url):
            urls.append(local_url)
    env_url = os.getenv("DATABASE_URL", "").strip()
    if env_url:
        # PR #3468 audit P1: DATABASE_URL is usable for scratch
        # provisioning only when EVERY endpoint it can reach (netloc host,
        # ?host= / ?hostaddr= failover lists) is local — a remote DSN must
        # never receive CREATE/DROP DATABASE.
        if is_local_admin_dsn(env_url):
            urls.append(env_url)
    return urls


def _run_alembic(url: URL, operation: str, revision: str) -> None:
    # SQLAlchemy masks the password in str(url). Pass it only in the child environment.
    database_url = url.render_as_string(hide_password=False)
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "-c", "alembic.ini", operation, revision],
        capture_output=True,
        text=True,
        cwd=BACKEND_DIR,
        env=dict(os.environ, DATABASE_URL=database_url, TESTING="1"),
    )
    stderr = result.stderr.replace(database_url, str(url))
    assert result.returncode == 0, stderr[-1500:]


@contextmanager
def _scratch_pg_engine(revision: str):
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
            f"disposable PostgreSQL unavailable — RQ-13.b PG acceptance NOT_RUN "
            f"(last error: {last_error})"
        )

    database = f"{SCRATCH_DB_PREFIX}_{uuid.uuid4().hex[:12]}"
    admin = make_url(admin_url)
    # Preserve the validated endpoints and use only the generated database.
    url = admin.set(
        drivername="postgresql+psycopg",
        database=database,
        query={
            key: value
            for key, value in admin.query.items()
            if key in {"host", "hostaddr", "port"}
        },
    )
    with psycopg.connect(admin_url, autocommit=True) as c:
        # No pre-drop: the run-unique name cannot pre-exist (a collision would
        # take 2**48 parallel runs), and dropping a fixed name unconditionally
        # is exactly the cross-run hazard this fixture used to carry.
        c.execute(f'CREATE DATABASE "{database}"')

    # PR #3468 audit P2: from this point on a scratch database EXISTS on the
    # admin server. Run-unique names mean the next run can no longer sweep a
    # leaked database (the old fixed-name pre-drop used to), so every
    # provisioning step between CREATE DATABASE and the yield is
    # failure-safe: teardown runs on ALL exit paths — a pre-yield setup
    # failure included — instead of only after a successful yield.
    engine = None
    try:
        _run_alembic(url, "upgrade", revision)
        engine = create_engine(url, future=True)
        with engine.connect() as conn:
            version = conn.execute(
                text("select version_num from alembic_version")
            ).scalar()
            dialect = conn.execute(text("select version()")).scalar()
        if revision == "head":
            assert version, "alembic_version must be present after upgrade"
        else:
            assert version == revision
        assert "PostgreSQL" in (dialect or ""), "RQ-13.b proof requires real PostgreSQL"
        yield engine
    finally:
        if engine is not None:
            engine.dispose()
        with psycopg.connect(admin_url, autocommit=True) as c:
            # Cleanup touches ONLY the run-unique database this process created;
            # WITH (FORCE) clears lingering connections (PG 13+), falling back
            # to the plain form on older servers.
            try:
                c.execute(f'DROP DATABASE IF EXISTS "{database}" WITH (FORCE)')
            except psycopg.errors.SyntaxError:
                c.execute(f'DROP DATABASE IF EXISTS "{database}"')


@pytest.fixture(scope="module")
def pg_engine():
    with _scratch_pg_engine("head") as engine:
        yield engine


@pytest.fixture
def historical_pg_engine():
    with _scratch_pg_engine(SNAPSHOT_PREDECESSOR) as engine:
        yield engine


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


def _seed_patient(session, suffix: str):
    from app.models.patient import Patient

    patient = Patient(
        last_name=f"RQ13B{suffix[-4:]}",
        first_name="Synthetic",
        phone=f"+99890130{suffix[-4:]}",
    )
    session.add(patient)
    session.commit()
    session.refresh(patient)
    return patient


def _seed_doctor(session, suffix: str, *, start_number_online: int):
    """SYNTHETIC active doctor with a configured online start number."""
    from app.core.security import get_password_hash
    from app.models.clinic import Doctor
    from app.models.user import User

    username = f"rq13b_doc_{suffix}"
    user = session.query(User).filter(User.username == username).first()
    if not user:
        user = User(
            username=username,
            email=f"{username}@example.com",
            full_name="RQ-13.b Synthetic Doctor",
            hashed_password=get_password_hash("rq13b-synthetic-pw"),
            role="Doctor",
            is_active=True,
        )
        session.add(user)
        session.commit()
        session.refresh(user)
    doctor = Doctor(
        user_id=user.id,
        specialty="rq13b_filler",
        cabinet="101",
        active=True,
        start_number_online=start_number_online,
        max_online_per_day=50,
    )
    session.add(doctor)
    session.commit()
    session.refresh(doctor)
    return doctor


def _seed_resource(session, suffix: str, *, start_number_online: int):
    """SYNTHETIC active registry row owning a unique tag."""
    from app.models.online_queue import QueueResource

    resource = QueueResource(
        code=f"rq13b_{suffix}",
        queue_tag=f"rq13b_lab_{suffix}",
        display_name="RQ-13.b Synthetic Resource",
        active=True,
        start_number_online=start_number_online,
        max_online_per_day=50,
    )
    session.add(resource)
    session.commit()
    session.refresh(resource)
    return resource


def _set_clinic_start_number(session, key: str, value) -> None:
    """ClinicSettings row (category='queue') — the SSOT get_queue_settings
    reads (app/crud/clinic.py: get_settings_by_category → ClinicSettings)."""
    from app.models.clinic import ClinicSettings

    row = session.query(ClinicSettings).filter(ClinicSettings.key == key).first()
    if row is None:
        row = ClinicSettings(key=key, value=value, category="queue")
        session.add(row)
    else:
        row.value = value
    session.commit()


def _issue_entry(session, daily_queue, number: int, patient_id: int):
    from app.models.online_queue import OnlineQueueEntry

    entry = OnlineQueueEntry(
        queue_id=daily_queue.id,
        number=number,
        patient_id=patient_id,
        status="waiting",
        source="desk",
        queue_time=datetime.now(ZoneInfo("Asia/Tashkent")).replace(tzinfo=None),
    )
    session.add(entry)
    session.commit()
    session.refresh(entry)
    return entry


# ---------------------------------------------------------------------------
# T1/T2 — resource axis: the day freezes the registry start number and a
# mid-day registry change no longer shifts the active day.
# ---------------------------------------------------------------------------

def test_resource_day_freezes_registry_start_number(pg_session):
    from app.services.queue_service import QueueBusinessService, queue_service

    suffix = "r01"
    resource = _seed_resource(pg_session, suffix, start_number_online=10)
    patient = _seed_patient(pg_session, suffix)
    day = _clinic_day(pg_session)

    dq = queue_service.get_or_create_daily_queue(
        pg_session,
        day=day,
        specialist_id=None,
        queue_tag=resource.queue_tag,
    )
    pg_session.refresh(dq)

    # 1) the day's APPLIED start number is FROZEN on the row at creation
    assert dq.start_number == 10
    # 2) the first ticket floors at the frozen value
    first = QueueBusinessService.calculate_next_number(pg_session, dq)
    assert first == 10
    _issue_entry(pg_session, dq, first, patient.id)


def test_resource_midday_change_does_not_shift_active_day(pg_session):
    from app.services.queue_service import QueueBusinessService, queue_service

    suffix = "r02"
    resource = _seed_resource(pg_session, suffix, start_number_online=10)
    patient = _seed_patient(pg_session, suffix)
    day = _clinic_day(pg_session)

    dq = queue_service.get_or_create_daily_queue(
        pg_session,
        day=day,
        specialist_id=None,
        queue_tag=resource.queue_tag,
    )
    pg_session.refresh(dq)
    assert dq.start_number == 10
    _issue_entry(pg_session, dq, 10, patient.id)

    # Mid-day admin change of the LIVE registry value must not rewrite the
    # issued numbering of the active day (D-06: «Новые настройки не меняют
    # выданные номера и историю текущего дня»).
    resource.start_number_online = 25
    pg_session.commit()

    nxt = QueueBusinessService.calculate_next_number(pg_session, dq)
    assert nxt == 11, (
        "mid-day registry change shifted the active day's baseline — "
        "D-06 snapshot violated"
    )


# ---------------------------------------------------------------------------
# T3/T4 — doctor axis: owner-first snapshot (D-06 chain), clinic level
# applies when the owner is unconfigured.
# ---------------------------------------------------------------------------

def test_doctor_day_owner_first_snapshot(pg_session):
    from app.services.queue_service import QueueBusinessService, queue_service

    suffix = "d01"
    doctor = _seed_doctor(pg_session, suffix, start_number_online=5)
    patient = _seed_patient(pg_session, suffix)
    day = _clinic_day(pg_session)

    dq = queue_service.get_or_create_daily_queue(
        pg_session,
        day=day,
        specialist_id=doctor.id,
        queue_tag="general",
    )
    pg_session.refresh(dq)

    # D-06: the owner level applies when configured (>1) — the day freezes
    # the owner value and BOTH engines (REST + GQL) number from it.
    assert dq.start_number == 5
    first = QueueBusinessService.calculate_next_number(pg_session, dq)
    assert first == 5
    _issue_entry(pg_session, dq, first, patient.id)


def test_doctor_owner_unconfigured_falls_to_clinic_level(pg_session):
    from app.services.queue_service import QueueBusinessService, queue_service

    suffix = "d02"
    tag = f"rq13b_sp_{suffix}"
    # owner column left at its DEFAULT (1) == unconfigured
    doctor = _seed_doctor(pg_session, suffix, start_number_online=1)
    _set_clinic_start_number(pg_session, f"start_number_{tag}", 15)
    day = _clinic_day(pg_session)

    dq = queue_service.get_or_create_daily_queue(
        pg_session,
        day=day,
        specialist_id=doctor.id,
        queue_tag=tag,
    )
    pg_session.refresh(dq)

    # Clinic level still applies when the owner is unconfigured — the
    # legacy per-specialty offset (derma/dental style) is preserved.
    assert dq.start_number == 15
    first = QueueBusinessService.calculate_next_number(pg_session, dq)
    assert first == 15


# ---------------------------------------------------------------------------
# T5 — GraphQL joinQueue consumes the snapshot: a mid-day owner change does
# not make the live floor jump over issued numbers.
# ---------------------------------------------------------------------------

def test_gql_joinqueue_consumes_snapshot(pg_session, pg_engine, monkeypatch):
    from app.db import session as db_session_module
    from app.graphql.schema import GraphQLContext, schema
    from app.models.user import User

    suffix = "g01"
    doctor = _seed_doctor(pg_session, suffix, start_number_online=5)
    seeded_patient = _seed_patient(pg_session, suffix + "a")
    join_patient = _seed_patient(pg_session, suffix + "b")
    day = _clinic_day(pg_session)

    from app.services.queue_service import queue_service

    dq = queue_service.get_or_create_daily_queue(
        pg_session,
        day=day,
        specialist_id=doctor.id,
        queue_tag="general",
    )
    pg_session.refresh(dq)
    assert dq.start_number == 5
    _issue_entry(pg_session, dq, 5, seeded_patient.id)

    # Mid-day change of the LIVE doctor setting — the GQL floor must keep
    # reading the FROZEN snapshot (5 → next issued 6), not jump to 9.
    doctor.start_number_online = 9
    pg_session.commit()

    factory = sessionmaker(bind=pg_engine, future=True)
    monkeypatch.setattr(db_session_module, "SessionLocal", factory)
    from app.graphql import mutations as gql_mutations

    monkeypatch.setattr(
        gql_mutations,
        "get_queue_settings",
        lambda db: {"queue_start_hour": 0, "timezone": "Asia/Tashkent"},
    )

    admin = pg_session.query(User).filter(User.role == "Admin").first()
    if admin is None:
        admin = User(
            username="rq13b_admin",
            email="rq13b_admin@example.com",
            full_name="RQ-13.b Admin",
            hashed_password="x",
            role="Admin",
            is_active=True,
        )
        pg_session.add(admin)
        pg_session.commit()
        pg_session.refresh(admin)

    context = GraphQLContext(
        user=SimpleNamespace(
            id=admin.id,
            username=admin.username,
            full_name=admin.full_name,
            role="Admin",
            is_active=True,
        )
    )

    async def _run():
        return await schema.execute(
            """
            mutation($input: QueueEntryInput!) {
              joinQueue(input: $input) {
                success message
                queueEntry { id number status }
              }
            }
            """,
            variable_values={
                "input": {
                    "patientId": join_patient.id,
                    "doctorId": doctor.id,
                    "queueTag": "general",
                }
            },
            context_value=context,
        )

    result = asyncio.run(_run())
    assert result.errors is None, f"GraphQL errors: {result.errors}"
    join = result.data["joinQueue"]
    assert join["success"] is True, join
    assert join["queueEntry"]["number"] == 6, (
        "joinQueue floored at the LIVE doctor.start_number_online instead of "
        "the day's frozen snapshot — D-06 violated"
    )


# ---------------------------------------------------------------------------
# T6 — get_next_queue_number prefers the day snapshot over the LIVE
# registry value (priority reorder; the snapshot check used to sit below
# the live re-read and was unreachable).
# ---------------------------------------------------------------------------

def test_get_next_queue_number_prefers_snapshot_over_live_resource(pg_session):
    from app.models.online_queue import DailyQueue
    from app.services.queue_service import queue_service

    suffix = "r03"
    resource = _seed_resource(pg_session, suffix, start_number_online=50)
    day = _clinic_day(pg_session)

    # Raw row with an explicitly set snapshot (pre-existing day whose owner
    # value changed after the day was created).
    dq = DailyQueue(
        day=day,
        specialist_id=None,
        queue_resource_id=resource.id,
        queue_tag=resource.queue_tag + "_raw",
        active=True,
        online_start_time="07:00",
        online_end_time="09:00",
        start_number=3,
    )
    pg_session.add(dq)
    pg_session.commit()
    pg_session.refresh(dq)

    got = queue_service.get_next_queue_number(
        pg_session, daily_queue=dq, queue_tag=dq.queue_tag
    )
    assert got == 3, (
        "live registry value overrode the day's frozen snapshot — the "
        "snapshot-first priority is not in effect"
    )


# ---------------------------------------------------------------------------
# T7: 0067 backfills its predecessor's rows and preserves them on rollback.
# ---------------------------------------------------------------------------

def test_0067_backfills_owner_values_and_reversible(historical_pg_engine):
    engine = historical_pg_engine
    assert "start_number" not in {
        c["name"] for c in inspect(engine).get_columns("daily_queues")
    }

    # Use the 0066 table shape, so the rows exist before the snapshot column.
    with engine.begin() as conn:
        resource_id = conn.execute(
            text("""
            INSERT INTO queue_resources
                (code, queue_tag, display_name, start_number_online, max_online_per_day)
            VALUES ('rq13b_snapshot', 'rq13b_snapshot', 'Synthetic resource', 12, 20)
            RETURNING id
        """)
        ).scalar_one()
        doctor_id = conn.execute(
            text("""
            INSERT INTO doctors (specialty, start_number_online, max_online_per_day, active)
            VALUES ('cardiology', 7, 20, true)
            RETURNING id
        """)
        ).scalar_one()
        add_queue = text("""
            INSERT INTO daily_queues
                (day, queue_resource_id, specialist_id, queue_tag, active,
                 online_start_time, online_end_time, max_online_entries)
            VALUES (:day, :resource_id, :doctor_id, :tag, true, '07:00', '22:00', 20)
            RETURNING id
        """)
        day = date(2026, 1, 1)
        resource_queue = conn.execute(
            add_queue,
            {
                "day": day,
                "resource_id": resource_id,
                "doctor_id": None,
                "tag": "rq13b_snapshot",
            },
        ).scalar_one()
        doctor_queue = conn.execute(
            add_queue,
            {
                "day": day,
                "resource_id": None,
                "doctor_id": doctor_id,
                "tag": "cardiology",
            },
        ).scalar_one()

    queue_ids = {"resource_queue": resource_queue, "doctor_queue": doctor_queue}

    def assert_backfill() -> None:
        columns = {c["name"]: c for c in inspect(engine).get_columns("daily_queues")}
        assert columns["start_number"]["nullable"] is False
        assert columns["start_number"]["default"] == "1"
        with engine.connect() as conn:
            assert (
                conn.execute(
                    text("SELECT version_num FROM alembic_version")
                ).scalar_one()
                == SNAPSHOT_REVISION
            )
            rows = conn.execute(
                text("""
                SELECT id, start_number FROM daily_queues
                WHERE id IN (:resource_queue, :doctor_queue)
            """),
                queue_ids,
            )
            assert {row.id: row.start_number for row in rows} == {
                resource_queue: 12,
                doctor_queue: 7,
            }

    _run_alembic(engine.url, "upgrade", SNAPSHOT_REVISION)
    assert_backfill()

    _run_alembic(engine.url, "downgrade", SNAPSHOT_PREDECESSOR)
    assert "start_number" not in {
        c["name"] for c in inspect(engine).get_columns("daily_queues")
    }
    with engine.connect() as conn:
        assert (
            conn.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
            == SNAPSHOT_PREDECESSOR
        )
        rows = conn.execute(
            text("""
            SELECT id, queue_resource_id, specialist_id FROM daily_queues
            WHERE id IN (:resource_queue, :doctor_queue)
        """),
            queue_ids,
        )
        assert {row.id: (row.queue_resource_id, row.specialist_id) for row in rows} == {
            resource_queue: (resource_id, None),
            doctor_queue: (None, doctor_id),
        }

    _run_alembic(engine.url, "upgrade", SNAPSHOT_REVISION)
    assert_backfill()
