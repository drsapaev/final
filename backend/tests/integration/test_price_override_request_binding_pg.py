"""PostgreSQL issuer races with synthetic rows and no notification delivery.

Schema is create_all plus a minimal child -> Visit invalidation trigger, not
proof of the complete Alembic chain; that is tested separately.
"""
from __future__ import annotations

import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session
from sqlalchemy.schema import CreateSchema, DropSchema

from app.db.base_class import Base
from app.models.authentication import TokenBlacklist
from app.models.clinic import Doctor
from app.models.doctor_price_override import DoctorPriceOverride
from app.models.patient import Patient
from app.models.service import Service
from app.models.user import User
from app.models.visit import Visit, VisitService
from app.services.dental_api_service import DentalApiService
from app.services.derma_api_service import DermaApiDomainError, DermaApiService
from app.services.profile_contact_security import ProfileBearerContext


@pytest.fixture
def pg_case():
    url = make_url(os.getenv("DATABASE_URL", "sqlite://"))
    if url.get_backend_name() != "postgresql":
        pytest.skip("requires disposable PostgreSQL")
    if not os.getenv("CI") and not (url.database or "").startswith("clinic_test"):
        pytest.skip("requires explicitly disposable clinic_test database")
    schema = "override_binding_" + uuid4().hex
    admin = create_engine(url)
    with admin.begin() as conn:
        conn.execute(CreateSchema(schema))
    engine = create_engine(url, connect_args={"options": f"-csearch_path={schema} -cstatement_timeout=15000 -clock_timeout=10000"})
    try:
        import app.db.base  # noqa: F401

        Base.metadata.create_all(engine)
        with engine.begin() as conn:
            conn.execute(text("""
                CREATE FUNCTION child_context() RETURNS trigger LANGUAGE plpgsql AS $$
                BEGIN
                  UPDATE visits SET confirmation_context_epoch=confirmation_context_epoch+1
                    WHERE id=COALESCE(NEW.visit_id, OLD.visit_id);
                  RETURN COALESCE(NEW, OLD);
                END $$
            """))
            conn.execute(text("""CREATE TRIGGER child_context_trigger
                AFTER UPDATE OR DELETE ON visit_services FOR EACH ROW EXECUTE FUNCTION child_context()"""))
        with Session(engine, expire_on_commit=False) as db:
            user = User(username="synthetic_issuer", hashed_password="!", role="derma", is_active=True, auth_epoch=0)
            patient = Patient(first_name="Synthetic", last_name="Issuer", birth_date=date(1990, 1, 1), phone="+998900000001")
            service = Service(code="synthetic", name="Synthetic", price=Decimal("10.00"), active=True, allow_doctor_price_override=True, duration_minutes=10)
            db.add_all([user, patient, service])
            db.flush()
            doctor = Doctor(user_id=user.id, specialty="dermatology", active=True, repeat_owner_generation=11)
            db.add(doctor)
            db.flush()
            visit = Visit(patient_id=patient.id, doctor_id=doctor.id, visit_date=date(2099, 1, 1), status="open", source="desk", confirmation_context_epoch=12)
            db.add(visit)
            db.flush()
            line = VisitService(visit_id=visit.id, service_id=service.id, code=service.code, name=service.name, qty=1, price=Decimal("10.00"))
            db.add(line)
            db.flush()
            ids = {"user": user.id, "doctor": doctor.id, "visit": visit.id, "service": service.id, "line": line.id}
            db.commit()
        yield engine, ids
    finally:
        engine.dispose()
        with admin.begin() as conn:
            conn.execute(DropSchema(schema, cascade=True))
        admin.dispose()


def _issue(engine, ids, ready=None, pids=None):
    with Session(engine, expire_on_commit=False) as db:
        if ready is not None:
            pids.append(db.execute(text("SELECT pg_backend_pid()")).scalar_one())
            ready.set()
        ctx = ProfileBearerContext(ids["user"], 0, "synthetic-jti", int(time.time()) + 60, None)
        data = SimpleNamespace(visit_id=ids["visit"], service_id=ids["service"], new_price=Decimal("5.00"), reason="synthetic", details=None, target_visit_service_id=None)
        try:
            row = DermaApiService(db).create_price_override(override_data=data, user_id=ids["user"], bearer=ctx)
            return 200, row.id
        except DermaApiDomainError as exc:
            return exc.status_code, None


def _is_blocked(engine, pid):
    deadline = time.monotonic() + 8
    while time.monotonic() < deadline:
        with engine.connect() as conn:
            if conn.execute(text("SELECT cardinality(pg_blocking_pids(:pid))"), {"pid": pid}).scalar_one():
                return True
        time.sleep(0.02)
    return False


def test_derma_response_is_materialized_before_commit_without_new_sql(pg_case):
    engine, ids = pg_case
    statements_after_commit = []
    committed = []

    def record_statement(_conn, _cursor, statement, _parameters, _context, _many):
        if committed:
            statements_after_commit.append(statement)

    event.listen(engine, "before_cursor_execute", record_statement)
    try:
        with Session(engine, expire_on_commit=True) as db:
            event.listen(db, "after_commit", lambda _session: committed.append(True))
            context = ProfileBearerContext(ids["user"], 0, "synthetic-jti", int(time.time()) + 60, None)
            data = SimpleNamespace(visit_id=ids["visit"], service_id=ids["service"], new_price=Decimal("5.00"),
                                   reason="synthetic", details=None, target_visit_service_id=None)
            result = DermaApiService(db).create_price_override(override_data=data, user_id=ids["user"], bearer=context)
            assert committed and result.id > 0 and result.status == "pending"
            assert result.new_price == Decimal("5.00") and result.created_at is not None
            assert statements_after_commit == []
    finally:
        event.remove(engine, "before_cursor_execute", record_statement)


@pytest.mark.asyncio
async def test_dental_response_is_materialized_before_commit_without_new_sql(pg_case):
    engine, ids = pg_case
    with Session(engine) as setup:
        setup.get(User, ids["user"]).role = "dentist"
        setup.get(Doctor, ids["doctor"]).specialty = "dental"
        setup.commit()
    statements_after_commit = []
    committed = []

    def record_statement(_conn, _cursor, statement, _parameters, _context, _many):
        if committed:
            statements_after_commit.append(statement)

    event.listen(engine, "before_cursor_execute", record_statement)
    try:
        with Session(engine, expire_on_commit=True) as db:
            actor = db.get(User, ids["user"])
            event.listen(db, "after_commit", lambda _session: committed.append(True))
            context = ProfileBearerContext(ids["user"], 0, "synthetic-jti", int(time.time()) + 60, None)
            data = SimpleNamespace(visit_id=ids["visit"], service_id=ids["service"], new_price=Decimal("5.00"),
                                   reason="synthetic", details=None, target_visit_service_id=None)
            service = DentalApiService(db)
            # The separate staff-notification workflow is not exercised here.
            service.send_price_override_notification = AsyncMock()
            result = await service.create_dental_price_override(override_data=data, user=actor, bearer=context)
            assert committed and result.id > 0 and result.status == "pending"
            assert result.new_price == Decimal("5.00") and result.created_at is not None
            assert statements_after_commit == []
    finally:
        event.remove(engine, "before_cursor_execute", record_statement)


@pytest.mark.parametrize("mutation", ["delete", "price"])
def test_child_trigger_race_fails_fast_or_invalidates_snapshot(pg_case, mutation):
    engine, ids = pg_case
    holding_visit, release = threading.Event(), threading.Event()
    issuer_thread = []

    def pause_after_visit(_conn, _cursor, statement, _parameters, _context, _many):
        if threading.get_ident() in issuer_thread and "from services" in statement.lower() and "for update" in statement.lower():
            holding_visit.set()
            if not release.wait(10):
                raise AssertionError("issuer release timeout")

    def issue():
        issuer_thread.append(threading.get_ident())
        return _issue(engine, ids)

    def mutate(pid_ready, pids):
        with Session(engine) as db:
            pids.append(db.execute(text("SELECT pg_backend_pid()")).scalar_one())
            pid_ready.set()
            line = db.get(VisitService, ids["line"])
            if mutation == "delete":
                db.delete(line)
            else:
                line.price = Decimal("9.00")
            db.commit()

    event.listen(engine, "before_cursor_execute", pause_after_visit)
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            issuer = pool.submit(issue)
            assert holding_visit.wait(5)
            ready, pids = threading.Event(), []
            writer = pool.submit(mutate, ready, pids)
            assert ready.wait(5)
            try:
                assert _is_blocked(engine, pids[0])
            finally:
                release.set()
            status, _ = issuer.result(timeout=12)
            writer.result(timeout=12)
    finally:
        release.set()
        event.remove(engine, "before_cursor_execute", pause_after_visit)
    with Session(engine) as db:
        rows = db.query(DoctorPriceOverride).all()
        if mutation == "delete":
            assert status == 409
            assert not rows
        else:
            assert status == 200 and len(rows) == 1
            assert rows[0].visit_price_before == Decimal("10.00")
            assert rows[0].visit_context_epoch == 12
            assert db.get(Visit, ids["visit"]).confirmation_context_epoch == 13
            assert db.get(VisitService, ids["line"]).price == Decimal("9.00")


def test_concurrent_requests_cannot_both_be_pending(pg_case):
    engine, ids = pg_case
    holding, release = threading.Event(), threading.Event()
    issuer_thread = []

    def pause_after_visit(_conn, _cursor, statement, _parameters, _context, _many):
        if threading.get_ident() in issuer_thread and "from services" in statement.lower() and "for update" in statement.lower():
            holding.set()
            if not release.wait(10):
                raise AssertionError("issuer release timeout")

    def first_issue():
        issuer_thread.append(threading.get_ident())
        return _issue(engine, ids)

    event.listen(engine, "before_cursor_execute", pause_after_visit)
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            first = pool.submit(first_issue)
            assert holding.wait(5)
            ready, pids = threading.Event(), []
            second = pool.submit(_issue, engine, ids, ready, pids)
            try:
                assert ready.wait(5)
                assert _is_blocked(engine, pids[0])
            finally:
                release.set()
            assert [first.result(timeout=12)[0], second.result(timeout=12)[0]] == [200, 409]
    finally:
        release.set()
        event.remove(engine, "before_cursor_execute", pause_after_visit)
    with Session(engine) as db:
        assert db.query(DoctorPriceOverride).filter_by(status="pending").count() == 1


@pytest.mark.parametrize("change,expected", [
    ("user_active", 401), ("user_role", 403), ("auth_epoch", 401),
    ("doctor_active", 403), ("doctor_owner", 403),
])
def test_issuer_rechecks_locked_actor_and_doctor(pg_case, change, expected):
    engine, ids = pg_case
    ready, pids = threading.Event(), []
    with Session(engine) as editor:
        if change.startswith("user_") or change == "auth_epoch":
            actor = editor.get(User, ids["user"])
            if change == "user_active":
                actor.is_active = False
            elif change == "user_role":
                actor.role = "Patient"
            else:
                actor.auth_epoch = 1
        else:
            doctor = editor.get(Doctor, ids["doctor"])
            if change == "doctor_active":
                doctor.active = False
            else:
                other = User(username="synthetic_other", hashed_password="!", role="derma", is_active=True)
                editor.add(other)
                editor.flush()
                doctor.user_id = other.id
        editor.flush()
        with ThreadPoolExecutor(max_workers=1) as pool:
            issuer = pool.submit(_issue, engine, ids, ready, pids)
            try:
                assert ready.wait(5)
                assert _is_blocked(engine, pids[0])
            finally:
                editor.commit()
            assert issuer.result(timeout=12)[0] == expected
    with Session(engine) as db:
        assert db.query(DoctorPriceOverride).count() == 0


def test_individual_logout_wins_before_locked_recheck(pg_case):
    engine, ids = pg_case
    ready, pids = threading.Event(), []
    with Session(engine) as logout:
        logout.query(User).filter_by(id=ids["user"]).with_for_update().one()
        logout.add(TokenBlacklist(jti="synthetic-jti", user_id=ids["user"],
                                  expires_at=datetime.now(UTC) + timedelta(hours=1), reason="logout"))
        logout.flush()
        with ThreadPoolExecutor(max_workers=1) as pool:
            issuer = pool.submit(_issue, engine, ids, ready, pids)
            try:
                assert ready.wait(5)
                assert _is_blocked(engine, pids[0])
            finally:
                logout.commit()
            assert issuer.result(timeout=12)[0] == 401
    with Session(engine) as db:
        assert db.query(DoctorPriceOverride).count() == 0
