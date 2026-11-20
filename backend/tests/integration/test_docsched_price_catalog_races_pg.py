"""Serialize doctor service assignment with catalog changes on PostgreSQL.

Both lock orderings are exercised: a committed catalog edit must be observed
by a waiting assignment, and an edit started after assignment's locked read
must wait for the assignment to commit.  Everything uses synthetic rows and
the confirmation transport is mocked.
"""

from __future__ import annotations

import asyncio
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session
from sqlalchemy.schema import CreateSchema, DropSchema

from app.api.v1.endpoints.doctor_integration import _visits as endpoint
from app.db.base_class import Base
from app.models.patient import Patient
from app.models.service import Service
from app.models.user import User
from app.models.visit import Visit, VisitService
from app.services.notification_service import NotificationService

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def catalog_pg_engine():
    ci = os.environ.get("CI", "").lower() == "true"
    raw_url = os.environ.get("DATABASE_URL", "").strip()
    if not raw_url or make_url(raw_url).get_backend_name() != "postgresql":
        if ci:
            pytest.fail("CI requires a PostgreSQL DATABASE_URL")
        pytest.skip("requires disposable PostgreSQL DATABASE_URL")
    url = make_url(raw_url)
    if not ci and not (url.database or "").startswith("clinic_test"):
        pytest.skip("use an explicitly disposable clinic_test database")
    schema = "test_docsched_catalog_" + uuid4().hex
    admin = create_engine(url, pool_pre_ping=True)
    with admin.begin() as conn:
        conn.execute(CreateSchema(schema))
    engine = create_engine(
        url,
        pool_pre_ping=True,
        pool_size=8,
        connect_args={"options": f"-csearch_path={schema} -cstatement_timeout=15000 -clock_timeout=10000"},
    )
    try:
        import app.db.base  # noqa: F401 — register the complete metadata

        Base.metadata.create_all(engine)
        yield engine
    finally:
        engine.dispose()
        with admin.begin() as conn:
            conn.execute(DropSchema(schema, cascade=True))
        admin.dispose()


@pytest.fixture
def catalog_case(catalog_pg_engine, monkeypatch):
    deliveries = []

    async def no_delivery(*_args, **_kwargs):
        deliveries.append(True)
        return {"success": False, "channel": "phone"}

    monkeypatch.setattr(NotificationService, "send_visit_confirmation_invitation", no_delivery)
    suffix = uuid4().hex[:10]
    with Session(catalog_pg_engine, expire_on_commit=False) as db:
        actor = User(username=f"synthetic_catalog_{suffix}", hashed_password="!synthetic",
                     role="Admin", is_active=True, is_superuser=False)
        patient = Patient(first_name="Synthetic", last_name=f"Catalog{suffix}",
                          phone="+998900000001", birth_date=date(1990, 1, 1))
        service = Service(code=f"C{suffix}", service_code=f"C{suffix[:9]}",
                          name="Synthetic catalog service", price=Decimal("100.00"),
                          active=True, duration_minutes=30,
                          allow_doctor_price_override=False)
        db.add_all([actor, patient, service])
        db.flush()
        visit = Visit(patient_id=patient.id, status="open", visit_date=date(2099, 1, 1),
                      discount_mode="none", source="desk")
        db.add(visit)
        db.flush()
        ids = {"actor": actor.id, "patient": patient.id, "service": service.id,
               "visit": visit.id, "deliveries": deliveries}
        db.commit()
    return ids


def _wait_until_blocked(engine, pid: int, future) -> None:
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        if future.done():
            pytest.fail("operation completed instead of waiting for the competing row lock")
        with engine.connect() as conn:
            if conn.execute(text("SELECT cardinality(pg_blocking_pids(:pid))"), {"pid": pid}).scalar_one():
                return
        time.sleep(0.02)
    pytest.fail("operation did not block on the competing PostgreSQL row lock")


def _assign(engine, ids, route, started, pids):
    with Session(engine, expire_on_commit=False) as db:
        pids.append(db.execute(text("SELECT pg_backend_pid()" )).scalar_one())
        actor = db.get(User, ids["actor"])
        started.set()
        try:
            if route == "schedule":
                request = endpoint.ScheduleNextVisitRequest(
                    patient_id=ids["patient"],
                    services=[endpoint.ScheduleNextVisitService(service_id=ids["service"], quantity=1)],
                    visit_date=date(2099, 1, 2), visit_time="10:00",
                    discount_mode="none", confirmation_channel="phone",
                )
                result = asyncio.run(endpoint.schedule_next_visit(request, db=db, current_user=actor))
                return 200, result.visit_id, result.idempotent_replay
            result = endpoint.add_service_to_visit(
                visit_id=ids["visit"], service_id=ids["service"], quantity=1,
                custom_price=None, db=db, current_user=actor,
            )
            return 200, ids["visit"] if result["success"] else None, result["idempotent_replay"]
        except HTTPException as exc:
            db.rollback()
            return exc.status_code, None, False


@pytest.mark.parametrize("route", ["schedule", "add"])
@pytest.mark.parametrize("change", ["deactivate", "price"])
def test_assignment_rechecks_catalog_after_prior_update_commits(
    catalog_pg_engine, catalog_case, route, change
):
    """A pending admin edit wins the row lock; assignment sees its commit."""
    engine, ids = catalog_pg_engine, catalog_case
    started, pids = threading.Event(), []
    with Session(engine, expire_on_commit=False) as editor:
        service = editor.get(Service, ids["service"])
        if change == "deactivate":
            service.active = False
        else:
            service.price = Decimal("240.00")
        editor.flush()  # UPDATE holds the service row lock until commit.
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(_assign, engine, ids, route, started, pids)
            try:
                assert started.wait(5)
                _wait_until_blocked(engine, pids[0], future)
            finally:
                editor.commit()  # release even if a regression is detected
            status, assigned_visit_id, _ = future.result(timeout=15)

    with Session(engine) as db:
        if change == "deactivate":
            assert status == 400
            assert db.query(VisitService).filter_by(service_id=ids["service"]).count() == 0
            assert db.query(Visit).filter_by(patient_id=ids["patient"], status="pending_confirmation").count() == 0
            assert not ids["deliveries"]
        else:
            assert status == 200
            line = db.query(VisitService).filter_by(visit_id=assigned_visit_id, service_id=ids["service"]).one()
            assert line.price == Decimal("240.00")


@pytest.mark.parametrize("route", ["schedule", "add"])
@pytest.mark.parametrize("change", ["deactivate", "price"])
def test_catalog_update_waits_for_assignment_locked_snapshot(
    catalog_pg_engine, catalog_case, route, change
):
    """Once assignment owns the catalog lock, a writer waits for its commit."""
    engine, ids = catalog_pg_engine, catalog_case
    assignment_started, locked, release = threading.Event(), threading.Event(), threading.Event()
    assignment_pids, editor_pids, editor_started = [], [], threading.Event()
    assignment_thread = []

    def pause_locked_read(_conn, _cursor, statement, _parameters, _context, _many):
        sql = statement.lower()
        if (threading.get_ident() in assignment_thread and "from services" in sql
            and ("for update" in sql or "for share" in sql) and not locked.is_set()):
            locked.set()
            if not release.wait(12):
                raise AssertionError("test did not release the service lock")

    def assign_with_marker():
        assignment_thread.append(threading.get_ident())
        return _assign(engine, ids, route, assignment_started, assignment_pids)

    def edit_catalog():
        with Session(engine) as db:
            editor_pids.append(db.execute(text("SELECT pg_backend_pid()" )).scalar_one())
            editor_started.set()
            values = {"active": False} if change == "deactivate" else {"price": Decimal("240.00")}
            db.query(Service).filter(Service.id == ids["service"]).update(values)
            db.commit()

    event.listen(engine, "after_cursor_execute", pause_locked_read)
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            assignment = pool.submit(assign_with_marker)
            try:
                assert assignment_started.wait(5)
                assert locked.wait(10), "assignment never acquired the service row lock"
                editor = pool.submit(edit_catalog)
                assert editor_started.wait(5)
                _wait_until_blocked(engine, editor_pids[0], editor)
            finally:
                release.set()
            status, assigned_visit_id, _ = assignment.result(timeout=15)
            editor.result(timeout=15)
    finally:
        release.set()
        event.remove(engine, "after_cursor_execute", pause_locked_read)

    assert status == 200
    with Session(engine) as db:
        line = db.query(VisitService).filter_by(visit_id=assigned_visit_id, service_id=ids["service"]).one()
        assert line.price == Decimal("100.00")
        service = db.get(Service, ids["service"])
        if change == "deactivate":
            assert service.active is False
        else:
            assert service.price == Decimal("240.00")


@pytest.mark.parametrize("route", ["schedule", "add"])
@pytest.mark.parametrize("change", ["deactivate", "price", "both"])
def test_replay_after_catalog_change_never_creates_a_second_assignment(
    catalog_pg_engine, catalog_case, route, change
):
    """Retry inside the 10s window must not turn into a new visit or line."""
    engine, ids = catalog_pg_engine, catalog_case
    first_status, first_visit, first_replay = _assign(engine, ids, route, threading.Event(), [])
    assert first_status == 200 and first_replay is False
    with Session(engine) as editor:
        service = editor.get(Service, ids["service"])
        if change in ("deactivate", "both"):
            service.active = False
        if change in ("price", "both"):
            service.price = Decimal("240.00")
        editor.commit()

    retry_status, retry_visit, retry_replay = _assign(engine, ids, route, threading.Event(), [])
    if change == "deactivate":
        assert (retry_status, retry_visit, retry_replay) == (200, first_visit, True)
    else:
        assert retry_status == 409

    with Session(engine) as db:
        lines = db.query(VisitService).filter_by(service_id=ids["service"]).all()
        assert len(lines) == 1
        assert lines[0].visit_id == first_visit and lines[0].price == Decimal("100.00")
        assert db.query(Visit).filter_by(patient_id=ids["patient"], status="pending_confirmation").count() == (1 if route == "schedule" else 0)
    assert len(ids["deliveries"]) == (1 if route == "schedule" else 0)
