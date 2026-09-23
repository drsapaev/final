"""Corrective follow-up (owner verdict on the merged #3355 + #3358 runtime):
the immutable execution-to-station routing regression, on real PostgreSQL.

The owner's mandated PG scenario:

    start execution on station A
    -> validly re-tag the Service A->B mid-flight
    -> the starter can still complete AND incomplete the original attempt
    -> drain discovery keeps the execution visible for the starter

Before the fix the terminal endpoint re-read the CURRENT catalog (403
after the re-tag), the draining surface skipped the chain entirely
(``continue``), and the 0072 partial unique one-active index blocked
every retry — a clinical operation stuck with no штатный recovery. The
attempt now persists its routing snapshot (migration 0073) and the
terminal/drain paths prove routing from THAT, not from the mutable
catalog.

PostgreSQL is not a substitute-able surface here: the one-active partial
index, the FOR UPDATE locks and the snapshot persistence under real
constraints are the point (the SQLite unit suite pins the same flows at
the logic level).
"""

from __future__ import annotations

import os
import uuid
from datetime import date

import pytest
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session
from sqlalchemy.schema import CreateSchema, DropSchema

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
def rt_pg_engine():
    raw_url = os.environ.get("DATABASE_URL", "").strip()
    if not raw_url:
        pytest.skip("routing snapshot proof requires DATABASE_URL for PostgreSQL")
    url = make_url(raw_url)
    if url.get_backend_name() != "postgresql":
        pytest.skip("routing snapshot proof requires PostgreSQL")
    if os.environ.get("CI", "").lower() != "true" and not (
        url.database or ""
    ).startswith("clinic_test"):
        pytest.skip("use CI or an explicitly disposable clinic_test database")

    schema = "test_n23_retag_" + uuid.uuid4().hex
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


def _mk_user(db: Session, username: str) -> User:
    user = User(
        username=username,
        email=f"{username}@example.com",
        full_name=username,
        hashed_password="x",
        role="Nurse",
        is_active=True,
        is_superuser=False,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _started_attempt(engine, *, with_assignment_deactivation: bool):
    """A full §6 start on station A, then the admin's valid mid-flight
    re-tag of the Service to station B's tag."""
    token = uuid.uuid4().hex[:8]
    with Session(engine) as db:
        nurse = _mk_user(db, f"rt_a_{token}")
        resource_a = QueueResource(
            code=f"proc_a_{token}",
            queue_tag=f"tag_a_{token}",
            display_name=f"PG station A {token}",
            active=True,
            start_number_online=1,
            max_online_per_day=50,
            default_cabinet="cab-a",
        )
        resource_b = QueueResource(
            code=f"proc_b_{token}",
            queue_tag=f"tag_b_{token}",
            display_name=f"PG station B {token}",
            active=True,
            start_number_online=1,
            max_online_per_day=50,
            default_cabinet="cab-b",
        )
        db.add_all([resource_a, resource_b])
        db.flush()
        assignment = NurseWorkplaceAssignment(
            user_id=nurse.id,
            queue_resource_id=resource_a.id,
            cabinet_override="pg-rt-A",
            is_active=True,
        )
        db.add(assignment)
        queue = DailyQueue(
            day=date.today(),
            specialist_id=None,
            queue_resource_id=resource_a.id,
            queue_tag=resource_a.queue_tag,
            active=True,
            start_number=1,
        )
        db.add(queue)
        db.flush()
        patient = Patient(first_name="Retag", last_name="PG")
        db.add(patient)
        db.flush()
        entry = OnlineQueueEntry(
            queue_id=queue.id,
            number=1,
            patient_id=patient.id,
            patient_name="Retag PG",
            status="waiting",
            source="desk",
        )
        db.add(entry)
        db.commit()

        service = NurseServingApiService(db)
        service.call_next(nurse.id, resource_a.id)
        service.start_entry(nurse.id, resource_a.id, entry.id)
        visit = db.get(Visit, entry.visit_id)
        svc = Service(
            code=f"rt_{token}",
            name=f"Retag service {token}",
            queue_tag=resource_a.queue_tag,
            requires_doctor=False,
            active=True,
        )
        db.add(svc)
        db.commit()
        vs = VisitService(
            visit_id=visit.id, service_id=svc.id, code=svc.code, name=svc.name, qty=1
        )
        db.add(vs)
        db.commit()
        execution = service.create_execution(
            nurse.id, resource_a.id, queue_entry_id=entry.id, visit_service_id=vs.id
        )
        execution_id = execution["id"]

        # The snapshot is persisted BEFORE any catalog move.
        row = db.get(ServiceExecution, execution_id)
        assert row.queue_resource_id == resource_a.id
        assert row.routing_queue_tag_snapshot == resource_a.queue_tag
        assert row.routing_service_id == svc.id

        # The admin's VALID mid-flight action: canonical re-tag A -> B.
        svc.queue_tag = resource_b.queue_tag
        if with_assignment_deactivation:
            # The §8 drain scenario: the deactivation lands MID-FLIGHT
            # (after the start) — the drained nurse keeps only the
            # bounded terminal/drain surface.
            assignment.is_active = False
        db.commit()

        return nurse.id, resource_a.id, entry.id, vs.id, execution_id, svc.id


def test_starter_completes_the_retagged_attempt(rt_pg_engine):
    nurse_id, resource_a_id, entry_id, _vs_id, execution_id, _svc_id = _started_attempt(
        rt_pg_engine, with_assignment_deactivation=False
    )
    with Session(rt_pg_engine) as db:
        service = NurseServingApiService(db)
        result = service.complete_execution(nurse_id, execution_id)
        assert result["status"] == "completed"
        entry = db.get(OnlineQueueEntry, entry_id)
        assert entry.status == "served"  # the last-completer flip still works


def test_starter_incompletes_the_retagged_attempt(rt_pg_engine):
    nurse_id, resource_a_id, entry_id, vs_id, execution_id, _svc_id = _started_attempt(
        rt_pg_engine, with_assignment_deactivation=False
    )
    with Session(rt_pg_engine) as db:
        service = NurseServingApiService(db)
        result = service.incomplete_execution(
            nurse_id, execution_id, reason="пациент ожидает переноса"
        )
        assert result["status"] == "incomplete"
        entry = db.get(OnlineQueueEntry, entry_id)
        assert entry.status == "in_progress"  # incomplete never flips
        # The retry stays CURRENT-catalog gated: the re-tagged service no
        # longer routes to A, so a NEW attempt on A is a 400 — while the
        # already-started attempt above remained finishable.
        with pytest.raises(NurseServingApiDomainError) as exc:
            service.create_execution(
                nurse_id,
                resource_a_id,
                queue_entry_id=entry_id,
                visit_service_id=vs_id,
            )
        assert exc.value.status_code == 400


def test_drain_discovery_preserves_the_retagged_execution(rt_pg_engine):
    nurse_id, resource_a_id, entry_id, _vs_id, execution_id, _svc_id = _started_attempt(
        rt_pg_engine, with_assignment_deactivation=True
    )
    with Session(rt_pg_engine) as db:
        service = NurseServingApiService(db)
        payload = service.list_draining_executions(nurse_id)
        assert payload["total"] == 1
        item = payload["items"][0]
        assert item["execution"]["id"] == execution_id
        assert item["station"]["queue_resource_id"] == resource_a_id
        # ...and the discovered attempt is still finishable through it.
        result = service.complete_execution(nurse_id, execution_id)
        assert result["status"] == "completed"
        entry = db.get(OnlineQueueEntry, entry_id)
        assert entry.status == "served"
