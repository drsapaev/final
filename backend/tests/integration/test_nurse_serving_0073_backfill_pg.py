"""Owner verdict round-2 P2 (PR #3367) — migration 0073 must protect the
executions that ALREADY exist when the upgrade runs.

The verdict's scenario: migration 0073 added the routing-snapshot columns
additively with NO backfill, so pre-upgrade ``in_progress`` rows (and
rows written by pre-upgrade workers during a rolling deployment) stayed
NULL-snapshot and kept passing the mutable current-catalog D3 — a
catalog re-tag in the window could still block an already-started
execution. The accepted remedy: BACKFILL every ``in_progress`` row
existing at upgrade time from the same chain the runtime resolves
(entry -> queue -> owner resource, else the tag-axis registry row) plus
the visit_service's service line — deliberately corroborated by the
CURRENT catalog so the upgrade never widens authorization (a hand-made
cross-station row or a row a pre-upgrade re-tag already stranded keeps
the legacy refusal; a blanket backfill would have silently legalized
exactly those rows).

Proven on real PostgreSQL: the scratch database is upgraded to 0072,
pre-0073 rows are seeded RAW (the ORM model at HEAD carries the snapshot
columns the 0072 schema does not have), then 0073 runs and the backfill
outcome is pinned:

- R1  in_progress, owner-axis chain, catalog corroborates -> BACKFILLED;
- R2  in_progress, tag-axis chain (queue without an owner resource),
      registry row resolves, catalog corroborates -> BACKFILLED;
- R3  in_progress, chain resolves but the line's CURRENT tag contradicts
      the station (the pre-upgrade re-tag case) -> stays NULL (legacy
      refusal preserved, zero widened authorization);
- R4  in_progress, queue_entry_id NULL (the purged-entry orphan) ->
      chain unresolvable -> stays NULL;
- R5  terminal (completed) row with a resolvable chain -> NOT touched
      (the upgrade rewrites no history).

SQLite is never a substitute here: the alembic chain and the partial
unique index live only on PostgreSQL.

Scratch-database isolation: the scratch name is run-unique (prefix + a
uuid suffix), created WITHOUT a pre-drop and dropped only in teardown,
only if this run actually created it. Two concurrent pytest processes
(or two agents) against one PostgreSQL server therefore never see each
other's scratch database, and a foreign database that happens to carry
the historical fixed name ``n23_0073_backfill`` is never touched.
"""

from __future__ import annotations

import os
import subprocess
import sys
import uuid
from datetime import date, datetime, timezone
from pathlib import Path

import psycopg
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker

from app.models.clinic import Doctor
from app.models.online_queue import DailyQueue, OnlineQueueEntry, QueueResource
from app.models.patient import Patient
from app.models.service import Service
from app.models.user import User
from app.models.visit import Visit, VisitService

pytestmark = pytest.mark.integration

BACKEND_DIR = Path(__file__).resolve().parents[2]
# Run-unique scratch names: the fixed historical name lives on only as
# the prefix, so parallel runs never collide and never pre-drop.
SCRATCH_DB_PREFIX = "n23_0073_backfill_"

sys.path.insert(0, str(BACKEND_DIR))


def _candidate_admin_urls() -> list[str]:
    """Admin DSNs for scratch provisioning (the rq14 harness pattern).

    DATABASE_URL may carry a SQLAlchemy driver suffix
    (``postgresql+psycopg://``) — normalized here so psycopg can dial it
    directly (CI's backend-tests job provides exactly such a URL, and its
    user owns the cluster, so CREATE DATABASE is available).
    """
    urls: list[str] = []
    explicit = os.getenv("N23_PG_ADMIN_URL", "").strip()
    if explicit:
        urls.append(explicit)
    env_url = os.getenv("DATABASE_URL", "").strip()
    if env_url:
        urls.append(env_url)
    return [u.replace("postgresql+psycopg://", "postgresql://", 1) for u in urls]


def _scratch_urls(admin_url: str, scratch_db: str) -> tuple[str, str]:
    """(psycopg DSN, SQLAlchemy URL) for the scratch database.

    Derived from the admin URL by swapping the database name — host,
    port, unix-socket ``?host=`` and credentials all survive.
    """
    url = make_url(admin_url)
    psycopg_scratch = url.set(
        drivername="postgresql", database=scratch_db
    ).render_as_string(hide_password=False)
    sa_scratch = url.set(
        drivername="postgresql+psycopg", database=scratch_db
    ).render_as_string(hide_password=False)
    return psycopg_scratch, sa_scratch


def _drop_scratch_db(admin_url: str, scratch_db: str) -> None:
    """Teardown drop through the same verified admin channel.

    The name is run-unique, so neither the connection termination nor
    the DROP can ever reach a foreign database; the termination is
    belt-and-braces for a pooled connection that outlived the engine's
    ``dispose()``.
    """
    with psycopg.connect(admin_url, connect_timeout=5, autocommit=True) as c:
        c.execute(
            "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
            "WHERE datname = %s AND pid <> pg_backend_pid()",
            (scratch_db,),
        )
        c.execute(f'DROP DATABASE IF EXISTS "{scratch_db}"')


def _run_alembic(sa_url: str, *args: str) -> None:
    env = dict(os.environ, DATABASE_URL=sa_url, TESTING="1")
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "-c", "alembic.ini", "upgrade", *args],
        capture_output=True,
        text=True,
        cwd=str(BACKEND_DIR),
        env=env,
    )
    assert result.returncode == 0, result.stderr[-2000:]


@pytest.fixture(scope="module")
def backfill_world():
    last_error: Exception | None = None
    admin_url = None
    for candidate in _candidate_admin_urls():
        try:
            with psycopg.connect(candidate, connect_timeout=5, autocommit=True) as c:
                c.execute("SELECT 1")
            admin_url = candidate
            break
        except Exception as exc:  # noqa: BLE001 - environmental skip
            last_error = exc
    if admin_url is None:
        pytest.skip(
            f"disposable PostgreSQL unavailable — 0073 backfill proof NOT_RUN "
            f"(last error: {last_error})"
        )

    # Run-unique: never a pre-drop, never a collision with a foreign
    # database or a parallel run (see the module docstring).
    scratch_db = f"{SCRATCH_DB_PREFIX}{uuid.uuid4().hex[:12]}"
    psycopg_dsn, sa_url = _scratch_urls(admin_url, scratch_db)
    created = False
    engine = None
    try:
        with psycopg.connect(admin_url, autocommit=True) as c:
            c.execute(f'CREATE DATABASE "{scratch_db}"')
        created = True

        # The pre-0073 schema: everything up to AND INCLUDING 0072.
        _run_alembic(sa_url, "0072_service_executions")

        engine = create_engine(sa_url, future=True)
        world = _seed_pre_0073_world(engine)

        # The verdict's unit under test: 0073 (columns + the backfill).
        _run_alembic(sa_url, "0073_execution_routing_snapshot")

        yield {"engine": engine, **world}
    finally:
        if engine is not None:
            engine.dispose()
        if created:
            try:
                _drop_scratch_db(admin_url, scratch_db)
            except Exception:  # noqa: BLE001 - a leaked run-unique name
                pass  # is inert and can never collide


def _seed_pre_0073_world(engine) -> dict:
    """The supporting world via ORM (its columns all exist at 0072); the
    execution rows via RAW SQL — the HEAD ORM model carries the 0073
    snapshot columns the 0072 schema does not have."""
    Session = sessionmaker(bind=engine, future=True)
    session = Session()
    nurse = User(
        username="n23_bf_nurse",
        email="n23_bf_nurse@example.com",
        full_name="n23_bf_nurse",
        hashed_password="x",
        role="Nurse",
        is_active=True,
        is_superuser=False,
    )
    patient = Patient(first_name="Backfill", last_name="Test")
    # The bridged surface: a DOCTOR-axis queue (the XOR check forbids an
    # ownerless queue since 0063) that still carries the station's tag —
    # the exact shape whose chain resolves through the runtime's tag
    # axis fallback (``_execution_station_resource``).
    doctor = Doctor(specialty="tag_n23_bf", start_number_online=1, max_online_per_day=15)
    resource = QueueResource(
        code="n23_bf_procedures",
        queue_tag="tag_n23_bf",
        display_name="Resource n23_bf",
        active=True,
        start_number_online=1,
        max_online_per_day=15,
        default_cabinet="c1",
    )
    session.add_all([nurse, patient, resource, doctor])
    session.commit()
    for row in (nurse, patient, resource, doctor):
        session.refresh(row)

    owner_queue = DailyQueue(
        day=date.today(),
        specialist_id=None,
        queue_resource_id=resource.id,
        queue_tag=resource.queue_tag,
        active=True,
        cabinet_number="c1",
        start_number=1,
    )
    tag_axis_queue = DailyQueue(
        day=date.today(),
        specialist_id=doctor.id,  # bridged: doctor axis + the station tag
        queue_resource_id=None,
        queue_tag=resource.queue_tag,
        active=True,
        cabinet_number="c1",
        start_number=1,
    )
    session.add_all([owner_queue, tag_axis_queue])
    session.commit()
    for row in (owner_queue, tag_axis_queue):
        session.refresh(row)

    visit = Visit(
        patient_id=patient.id,
        doctor_id=None,
        visit_date=date.today(),
        department=resource.queue_tag,
        status="in_progress",
    )
    routed = Service(
        code="N23BF_ROUTED",
        name="Service N23BF_ROUTED",
        queue_tag=resource.queue_tag,
        requires_doctor=False,
        active=True,
    )
    retagged = Service(
        code="N23BF_RETAGGED",
        name="Service N23BF_RETAGGED",
        queue_tag="tag_n23_bf_elsewhere",  # contradicts the station NOW
        requires_doctor=False,
        active=True,
    )
    session.add_all([visit, routed, retagged])
    session.commit()
    for row in (visit, routed, retagged):
        session.refresh(row)

    vs_routed = VisitService(
        visit_id=visit.id,
        service_id=routed.id,
        code=routed.code,
        name=routed.name,
        qty=1,
    )
    vs_retagged = VisitService(
        visit_id=visit.id,
        service_id=retagged.id,
        code=retagged.code,
        name=retagged.name,
        qty=1,
    )
    vs_orphan = VisitService(
        visit_id=visit.id,
        service_id=routed.id,
        code=routed.code,
        name=routed.name,
        qty=1,
    )
    # A separate LINE of the same routed service for the tag-axis row —
    # one in_progress attempt per VisitService (the 0072 partial index).
    vs_tag_axis = VisitService(
        visit_id=visit.id,
        service_id=routed.id,
        code=routed.code,
        name=routed.name,
        qty=1,
    )
    session.add_all([vs_routed, vs_retagged, vs_orphan, vs_tag_axis])
    session.commit()
    for row in (vs_routed, vs_retagged, vs_orphan, vs_tag_axis):
        session.refresh(row)

    entry_owner = OnlineQueueEntry(
        queue_id=owner_queue.id,
        number=1,
        patient_id=patient.id,
        patient_name="Backfill",
        status="in_progress",
        priority=0,
        source="desk",
        visit_id=visit.id,
    )
    entry_tag_axis = OnlineQueueEntry(
        queue_id=tag_axis_queue.id,
        number=2,
        patient_id=patient.id,
        patient_name="Backfill",
        status="in_progress",
        priority=0,
        source="desk",
        visit_id=visit.id,
    )
    entry_retagged = OnlineQueueEntry(
        queue_id=owner_queue.id,
        number=3,
        patient_id=patient.id,
        patient_name="Backfill",
        status="in_progress",
        priority=0,
        source="desk",
        visit_id=visit.id,
    )
    session.add_all([entry_owner, entry_tag_axis, entry_retagged])
    session.commit()
    for row in (entry_owner, entry_tag_axis, entry_retagged):
        session.refresh(row)
    # Capture plain ints BEFORE close — ORM instances detach + expire.
    ids = {
        "nurse_id": nurse.id,
        "vs_routed_id": vs_routed.id,
        "vs_retagged_id": vs_retagged.id,
        "vs_orphan_id": vs_orphan.id,
        "vs_tag_axis_id": vs_tag_axis.id,
        "entry_owner_id": entry_owner.id,
        "entry_tag_axis_id": entry_tag_axis.id,
        "entry_retagged_id": entry_retagged.id,
        "resource_id": resource.id,
        "resource_queue_tag": resource.queue_tag,
        "routed_service_id": routed.id,
    }
    session.close()

    started_at = datetime.now(timezone.utc)
    raw_rows = [
        # (visit_service_id, queue_entry_id, attempt_no, status)
        (ids["vs_routed_id"], ids["entry_owner_id"], 1, "in_progress"),
        (ids["vs_tag_axis_id"], ids["entry_tag_axis_id"], 1, "in_progress"),
        (ids["vs_retagged_id"], ids["entry_retagged_id"], 1, "in_progress"),
        (ids["vs_orphan_id"], None, 1, "in_progress"),
        (ids["vs_routed_id"], ids["entry_owner_id"], 2, "completed"),
    ]
    inserted_ids: list[int] = []
    with engine.begin() as conn:
        for visit_service_id, queue_entry_id, attempt_no, status in raw_rows:
            row_id = conn.execute(
                text(
                    "INSERT INTO service_executions "
                    "(visit_service_id, queue_entry_id, attempt_no, status, "
                    " started_by_user_id, started_at) "
                    "VALUES (:visit_service_id, :queue_entry_id, :attempt_no, "
                    ":status, :started_by_user_id, :started_at) "
                    "RETURNING id"
                ),
                {
                    "visit_service_id": visit_service_id,
                    "queue_entry_id": queue_entry_id,
                    "attempt_no": attempt_no,
                    "status": status,
                    "started_by_user_id": ids["nurse_id"],
                    "started_at": started_at,
                },
            ).scalar_one()
            inserted_ids.append(row_id)
    return {
        "r1_owner_axis": inserted_ids[0],
        "r2_tag_axis": inserted_ids[1],
        "r3_contradicted": inserted_ids[2],
        "r4_orphaned": inserted_ids[3],
        "r5_terminal": inserted_ids[4],
        # Plain values captured before the seeding session closed.
        "resource_id": ids["resource_id"],
        "resource_queue_tag": ids["resource_queue_tag"],
        "routed_service_id": ids["routed_service_id"],
    }


def _snapshot_of(engine, execution_id: int) -> tuple:
    with engine.connect() as conn:
        return conn.execute(
            text(
                "SELECT queue_resource_id, routing_queue_tag_snapshot, "
                "routing_service_id FROM service_executions WHERE id = :eid"
            ),
            {"eid": execution_id},
        ).one()


def test_owner_axis_in_progress_row_is_backfilled(backfill_world):
    world = backfill_world
    snapshot = _snapshot_of(world["engine"], world["r1_owner_axis"])
    assert snapshot == (
        world["resource_id"],
        world["resource_queue_tag"],
        world["routed_service_id"],
    )


def test_tag_axis_in_progress_row_is_backfilled(backfill_world):
    world = backfill_world
    snapshot = _snapshot_of(world["engine"], world["r2_tag_axis"])
    assert snapshot == (
        world["resource_id"],
        world["resource_queue_tag"],
        world["routed_service_id"],
    )
    # NOTE: the tag-axis row resolves through the SAME registry resource
    # (its queue is doctor-axis + the station tag), so the snapshot
    # columns equal the owner-axis row's.


def test_catalog_contradicted_row_stays_null(backfill_world):
    """The pre-upgrade re-tag case: the chain resolves but the line's
    CURRENT tag contradicts the station. The legacy D3 refusal is
    preserved — the upgrade writes no snapshot that would widen what the
    legacy path authorizes."""
    world = backfill_world
    snapshot = _snapshot_of(world["engine"], world["r3_contradicted"])
    assert snapshot == (None, None, None)


def test_orphaned_row_stays_null(backfill_world):
    world = backfill_world
    snapshot = _snapshot_of(world["engine"], world["r4_orphaned"])
    assert snapshot == (None, None, None)


def test_terminal_row_is_never_rewritten(backfill_world):
    world = backfill_world
    snapshot = _snapshot_of(world["engine"], world["r5_terminal"])
    assert snapshot == (None, None, None)
