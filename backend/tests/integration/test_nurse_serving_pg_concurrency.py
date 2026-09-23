"""NURSE-V2 N2-3 — the mandatory §6 PostgreSQL concurrency proofs.

Owner scenario (``nurse-v2-clinical-serving.md`` §6, verbatim contract):
two Nurses, ONE QueueResource procedures station, two cabinets,
SIMULTANEOUS call-next. Proven here:

1. one QueueEntry is never issued to two Nurses (the queue-row FOR
   UPDATE serialization + the canonical-order entry claim);
2. each Nurse gets a separate patient;
3. the same Nurse's repeated request is idempotent (the held claim,
   including the concurrent double-tap);
4. ``called_by_user_id``/``served_by_user_id`` attribute the actual
   Nurse;
5. reconnect/reload does not lose the active serving (the held claim
   is refetchable through the station board);
6. concurrent execution creates on one VisitService leave exactly ONE
   in_progress attempt (the loser answers 409);
7. the last-completer race flips the entry exactly once with the
   flipping Nurse's attribution.

Gating follows the repo pattern (test_lab_draft_pg_concurrency): a
PostgreSQL ``DATABASE_URL`` (CI or an explicitly disposable
clinic_test* database); SQLite runs skip. Schema is disposable
(uuid-suffixed), built via ``create_all`` (the same ORM shape the
migration acceptance suite verifies against 0071/0072 DDL).
"""

from __future__ import annotations

import os
import threading
import uuid

import pytest
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session
from sqlalchemy.schema import CreateSchema, DropSchema

from app.crud.clinic import clinic_today
from app.db.base_class import Base
from app.models.nurse_workplace import NurseWorkplaceAssignment
from app.models.online_queue import DailyQueue, OnlineQueueEntry, QueueResource
from app.models.patient import Patient
from app.models.service import Service
from app.models.service_execution import ServiceExecution
from app.models.user import User
from app.models.visit import Visit, VisitService
from app.services.nurse_serving_api_service import (
    NurseServingApiDomainError,
    NurseServingApiService,
)

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def n23_pg_engine():
    raw_url = os.environ.get("DATABASE_URL", "").strip()
    if not raw_url:
        pytest.skip(
            "nurse serving concurrency proof requires DATABASE_URL for PostgreSQL"
        )
    url = make_url(raw_url)
    if url.get_backend_name() != "postgresql":
        pytest.skip("nurse serving concurrency proof requires PostgreSQL")
    if os.environ.get("CI", "").lower() != "true" and not (
        url.database or ""
    ).startswith("clinic_test"):
        pytest.skip("use CI or an explicitly disposable clinic_test database")

    schema = "test_n23_serving_" + uuid.uuid4().hex
    admin = create_engine(url, pool_pre_ping=True)
    try:
        with admin.begin() as connection:
            connection.execute(CreateSchema(schema))
    except Exception as exc:  # noqa: BLE001 - environmental skip, not product logic
        admin.dispose()
        pytest.skip(f"disposable PostgreSQL unavailable: {exc}")

    engine = create_engine(
        url,
        pool_pre_ping=True,
        connect_args={
            "options": (
                f"-csearch_path={schema} "
                "-cstatement_timeout=15000 -clock_timeout=15000"
            )
        },
    )
    try:
        Base.metadata.create_all(engine)
        yield engine
    finally:
        engine.dispose()
        with admin.begin() as connection:
            connection.execute(DropSchema(schema, cascade=True))
        admin.dispose()


def _mk_user(db: Session, username: str, role: str = "Nurse") -> User:
    user = User(
        username=username,
        email=f"{username}@example.com",
        full_name=username,
        hashed_password="x",
        role=role,
        is_active=True,
        is_superuser=False,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _mk_world(engine, *, waiting: int = 2, station_services: int = 1):
    """A §6 station: one resource, two nurses/cabinets, waiting patients."""
    token = uuid.uuid4().hex[:8]
    with Session(engine) as db:
        nurse_a = _mk_user(db, f"n23pg_a_{token}")
        nurse_b = _mk_user(db, f"n23pg_b_{token}")
        resource = QueueResource(
            code=f"proc_{token}",
            queue_tag=f"tag_{token}",
            display_name=f"PG station {token}",
            active=True,
            start_number_online=1,
            max_online_per_day=50,
            default_cabinet="c1",
        )
        db.add(resource)
        db.flush()
        db.add_all(
            [
                NurseWorkplaceAssignment(
                    user_id=nurse_a.id,
                    queue_resource_id=resource.id,
                    cabinet_override="pg-cab-A",
                    is_active=True,
                ),
                NurseWorkplaceAssignment(
                    user_id=nurse_b.id,
                    queue_resource_id=resource.id,
                    cabinet_override="pg-cab-B",
                    is_active=True,
                ),
            ]
        )
        queue = DailyQueue(
            day=clinic_today(db),
            specialist_id=None,
            queue_resource_id=resource.id,
            queue_tag=resource.queue_tag,
            active=True,
            start_number=1,
        )
        db.add(queue)
        db.flush()
        entries = []
        patients = []
        for i in range(waiting):
            patient = Patient(first_name=f"PG{i}_{token}", last_name="Conc")
            db.add(patient)
            db.flush()
            patients.append(patient)
            entry = OnlineQueueEntry(
                queue_id=queue.id,
                number=i + 1,
                patient_id=patient.id,
                patient_name=patient.first_name,
                status="waiting",
                source="desk",
            )
            db.add(entry)
            db.flush()
            entries.append(entry)
        services = []
        for i in range(station_services):
            service = Service(
                code=f"PGSVC{i}_{token}",
                name=f"PG service {i}",
                queue_tag=resource.queue_tag,
                requires_doctor=False,
                active=True,
            )
            db.add(service)
            db.flush()
            services.append(service)
        db.commit()
        return {
            "nurse_a": nurse_a.id,
            "nurse_b": nurse_b.id,
            "resource": resource.id,
            "queue": queue.id,
            "entries": [e.id for e in entries],
            "patients": [p.id for p in patients],
            "services": [s.id for s in services],
        }


def _barrier_run(fn_a, fn_b):
    """Run two closures concurrently, released by a shared barrier."""
    barrier = threading.Barrier(2)
    outcomes: dict[str, object] = {}

    def _wrap(key, fn):
        def runner():
            barrier.wait()
            try:
                outcomes[key] = ("ok", fn())
            except Exception as exc:  # noqa: BLE001 — the assertion inspects it
                outcomes[key] = ("err", exc)

        return runner

    threads = [
        threading.Thread(target=_wrap("a", fn_a)),
        threading.Thread(target=_wrap("b", fn_b)),
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=60)
    return outcomes


# ----------------------------------------------------------------------------
# §6 proofs
# ----------------------------------------------------------------------------


def test_simultaneous_call_next_issues_distinct_patients(n23_pg_engine):
    world = _mk_world(n23_pg_engine, waiting=2)

    def claim(engine, nurse_id):
        with Session(engine) as db:
            return NurseServingApiService(db).call_next(nurse_id, world["resource"])

    outcomes = _barrier_run(
        lambda: claim(n23_pg_engine, world["nurse_a"]),
        lambda: claim(n23_pg_engine, world["nurse_b"]),
    )
    assert outcomes["a"][0] == "ok", outcomes["a"]
    assert outcomes["b"][0] == "ok", outcomes["b"]
    entry_a = outcomes["a"][1]["entry"]["id"]
    entry_b = outcomes["b"][1]["entry"]["id"]

    # (1)+(2): different patients, no double issue.
    assert entry_a != entry_b
    assert {entry_a, entry_b} == set(world["entries"])

    with Session(n23_pg_engine) as db:
        rows = (
            db.query(OnlineQueueEntry)
            .filter(OnlineQueueEntry.id.in_([entry_a, entry_b]))
            .all()
        )
        by_id = {r.id: r for r in rows}
        # (4): attribution of the ACTUAL nurse.
        assert by_id[entry_a].called_by_user_id == world["nurse_a"]
        assert by_id[entry_b].called_by_user_id == world["nurse_b"]
        assert all(r.status == "called" for r in rows)
        waiting = (
            db.query(OnlineQueueEntry)
            .filter(
                OnlineQueueEntry.queue_id == world["queue"],
                OnlineQueueEntry.status == "waiting",
            )
            .count()
        )
        assert waiting == 0


def test_same_nurse_concurrent_double_tap_is_idempotent(n23_pg_engine):
    world = _mk_world(n23_pg_engine, waiting=2)

    def claim(engine, nurse_id):
        with Session(engine) as db:
            return NurseServingApiService(db).call_next(nurse_id, world["resource"])

    outcomes = _barrier_run(
        lambda: claim(n23_pg_engine, world["nurse_a"]),
        lambda: claim(n23_pg_engine, world["nurse_a"]),
    )
    assert outcomes["a"][0] == "ok", outcomes["a"]
    assert outcomes["b"][0] == "ok", outcomes["b"]
    # (3): the SAME entry twice — one claim, not two patients.
    assert outcomes["a"][1]["entry"]["id"] == outcomes["b"][1]["entry"]["id"]
    with Session(n23_pg_engine) as db:
        called = (
            db.query(OnlineQueueEntry)
            .filter(
                OnlineQueueEntry.queue_id == world["queue"],
                OnlineQueueEntry.status == "called",
            )
            .count()
        )
        assert called == 1

    # (5): reconnect — a fresh session still surfaces the held claim.
    with Session(n23_pg_engine) as db:
        state = NurseServingApiService(db).get_station_state(
            world["nurse_a"], world["resource"]
        )
    assert state["my_entry"] is not None
    assert state["my_entry"]["is_my_claim"] is True


def test_concurrent_execution_creates_leave_one_active(n23_pg_engine):
    world = _mk_world(n23_pg_engine, waiting=1, station_services=1)

    with Session(n23_pg_engine) as db:
        service_api = NurseServingApiService(db)
        service_api.call_next(world["nurse_a"], world["resource"])
        service_api.start_entry(
            world["nurse_a"], world["resource"], world["entries"][0]
        )
        entry = db.get(OnlineQueueEntry, world["entries"][0])
        visit = db.get(Visit, entry.visit_id)
        visit_service = VisitService(
            visit_id=visit.id,
            service_id=world["services"][0],
            code="PGS",
            name="PG station service",
            qty=1,
        )
        db.add(visit_service)
        db.commit()
        db.refresh(visit_service)
        visit_service_id = visit_service.id
        entry_id = entry.id

    def create_attempt(engine, nurse_id):
        with Session(engine) as db:
            return NurseServingApiService(db).create_execution(
                nurse_id,
                world["resource"],
                queue_entry_id=entry_id,
                visit_service_id=visit_service_id,
            )

    outcomes = _barrier_run(
        lambda: create_attempt(n23_pg_engine, world["nurse_a"]),
        lambda: create_attempt(n23_pg_engine, world["nurse_b"]),
    )
    results = [outcomes[k] for k in ("a", "b")]
    ok = [r for r in results if r[0] == "ok"]
    err = [r for r in results if r[0] == "err"]
    # Exactly one creator wins; the loser answers the deterministic 409.
    assert len(ok) == 1, outcomes
    assert len(err) == 1 and isinstance(err[0][1], NurseServingApiDomainError)
    assert err[0][1].status_code == 409

    with Session(n23_pg_engine) as db:
        active = (
            db.query(ServiceExecution)
            .filter(
                ServiceExecution.visit_service_id == visit_service_id,
                ServiceExecution.status == "in_progress",
            )
            .count()
        )
        assert active == 1


def test_last_completer_race_flips_the_entry_exactly_once(n23_pg_engine):
    world = _mk_world(n23_pg_engine, waiting=1, station_services=2)

    with Session(n23_pg_engine) as db:
        service_api = NurseServingApiService(db)
        service_api.call_next(world["nurse_a"], world["resource"])
        service_api.start_entry(
            world["nurse_a"], world["resource"], world["entries"][0]
        )
        entry = db.get(OnlineQueueEntry, world["entries"][0])
        visit = db.get(Visit, entry.visit_id)
        visit_services = []
        for i, service_id in enumerate(world["services"]):
            vs = VisitService(
                visit_id=visit.id,
                service_id=service_id,
                code=f"PGS{i}",
                name=f"PG station service {i}",
                qty=1,
            )
            db.add(vs)
            db.flush()
            visit_services.append(vs)
        db.commit()
        vs_ids = [vs.id for vs in visit_services]
        entry_id = entry.id

    # Each nurse starts her own service attempt (the two cabinets).
    with Session(n23_pg_engine) as db:
        service_api = NurseServingApiService(db)
        exec_a = service_api.create_execution(
            world["nurse_a"],
            world["resource"],
            queue_entry_id=entry_id,
            visit_service_id=vs_ids[0],
        )
        exec_b = service_api.create_execution(
            world["nurse_b"],
            world["resource"],
            queue_entry_id=entry_id,
            visit_service_id=vs_ids[1],
        )
        exec_a_id, exec_b_id = exec_a["id"], exec_b["id"]

    def complete(engine, nurse_id, execution_id):
        with Session(engine) as db:
            return NurseServingApiService(db).complete_execution(nurse_id, execution_id)

    outcomes = _barrier_run(
        lambda: complete(n23_pg_engine, world["nurse_a"], exec_a_id),
        lambda: complete(n23_pg_engine, world["nurse_b"], exec_b_id),
    )
    assert outcomes["a"][0] == "ok", outcomes["a"]
    assert outcomes["b"][0] == "ok", outcomes["b"]

    with Session(n23_pg_engine) as db:
        entry = db.get(OnlineQueueEntry, entry_id)
        # (7): exactly ONE flip happened, attributed to the flipping nurse.
        assert entry.status == "served"
        assert entry.served_at is not None
        assert entry.served_by_user_id in (world["nurse_a"], world["nurse_b"])
        # Both attempts completed regardless of who flipped the entry.
        statuses = {
            e.visit_service_id: e.status
            for e in db.query(ServiceExecution).filter(
                ServiceExecution.queue_entry_id == entry_id
            )
        }
        assert set(statuses.values()) == {"completed"}
        # The audit ledger holds exactly one entry-flip row.
        from app.models.user_profile import UserAuditLog

        flip_rows = (
            db.query(UserAuditLog)
            .filter(
                UserAuditLog.resource_type == "online_queue_entries",
                UserAuditLog.resource_id == entry_id,
                UserAuditLog.action == "UPDATE",
            )
            .count()
        )
        assert flip_rows == 1
