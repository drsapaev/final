"""Synthetic PostgreSQL service races with the real 0102 trigger migration.

The rest of the schema is metadata.create_all in an isolated random schema;
this is not a replacement for a complete Alembic-chain integration test.
"""
from __future__ import annotations

import importlib.util
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session
from sqlalchemy.schema import CreateSchema, DropSchema

from app.db.base_class import Base
from app.models.all_free_request import (
    AllFreeRequest,
    AllFreeRequestEvent,
    AllFreeRequestLine,
)
from app.models.audit import AuditLog
from app.models.authentication import TokenBlacklist
from app.models.encounter import Encounter
from app.models.patient import Patient
from app.models.service import Service
from app.models.user import User
from app.models.visit import Visit, VisitService
from app.services.all_free_request_service import (
    AllFreeRequestError,
    AllFreeRequestService,
)
from app.services.profile_contact_security import (
    ProfileBearerContext,
    ProfileBearerInvalid,
)


@pytest.fixture
def pg_case():
    url = make_url(os.getenv("ALL_FREE_TEST_DATABASE_URL") or os.getenv("DATABASE_URL", "sqlite://"))
    if url.get_backend_name() != "postgresql" or not (url.database or "").startswith("clinic_test"):
        pytest.skip("requires disposable clinic_test PostgreSQL")
    schema = "test_allfree_service_" + uuid4().hex
    admin = sa.create_engine(url)
    with admin.begin() as connection:
        connection.execute(CreateSchema(schema))
    engine = sa.create_engine(url, connect_args={"options": f"-csearch_path={schema} -cstatement_timeout=15000 -clock_timeout=10000"})
    try:
        import app.db.base  # noqa: F401
        Base.metadata.create_all(engine)
        path = Path(__file__).resolve().parents[2] / "alembic/versions/0102_visit_confirmation_context.py"
        spec = importlib.util.spec_from_file_location("synthetic_allfree_real_0102", path)
        assert spec and spec.loader
        migration = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(migration)
        with engine.begin() as connection:
            connection.execute(sa.text("ALTER TABLE visits DROP COLUMN confirmation_context_epoch"))
            with Operations.context(MigrationContext.configure(connection)):
                migration.upgrade()
        with Session(engine, expire_on_commit=False) as db:
            user = User(username="synthetic-admin", hashed_password="!", role="Admin", is_active=True, auth_epoch=0)
            patient = Patient(first_name="Synthetic", last_name="AllFree", birth_date=date(1990, 1, 1))
            service = Service(code="synthetic", name="Synthetic", price=Decimal("0.07"), active=True, duration_minutes=10)
            db.add_all([user, patient, service])
            db.flush()
            encounter = Encounter(patient_id=patient.id, provenance="new")
            db.add(encounter)
            db.flush()
            visit = Visit(patient_id=patient.id, encounter_id=encounter.id,
                          status="pending_confirmation", visit_date=date(2099, 1, 1))
            db.add(visit)
            db.flush()
            line = VisitService(visit_id=visit.id, service_id=service.id, name="Synthetic", qty=3,
                                price=Decimal("0.07"), currency="UZS")
            db.add(line)
            db.flush()
            db.refresh(visit)
            ids = {"user": user.id, "visit": visit.id, "line": line.id, "epoch": visit.confirmation_context_epoch}
            db.commit()
        yield engine, ids
    finally:
        engine.dispose()
        with admin.begin() as connection:
            connection.execute(DropSchema(schema, cascade=True))
        admin.dispose()


def _blocked(engine, pid, future):
    deadline = time.monotonic() + 8
    while time.monotonic() < deadline:
        assert not future.done(), "stage did not wait for competing transaction"
        with engine.connect() as connection:
            if connection.execute(sa.text("SELECT cardinality(pg_blocking_pids(:pid))"), {"pid": pid}).scalar_one():
                return
        time.sleep(0.02)
    pytest.fail("expected PostgreSQL transaction blocking")


def _stage(engine, ids, started, pids):
    with Session(engine) as db:
        pids.append(db.execute(sa.text("SELECT pg_backend_pid()")).scalar_one())
        started.set()
        bearer = ProfileBearerContext(ids["user"], 0, "synthetic-jti", int(time.time()) + 600, None)
        try:
            AllFreeRequestService(db).stage_request(visit_id=ids["visit"], expected_epoch=ids["epoch"], bearer=bearer)
            db.commit()
            return "created"
        except (AllFreeRequestError, ProfileBearerInvalid) as exc:
            db.rollback()
            return type(exc).__name__


def _assert_no_request(engine):
    with Session(engine) as db:
        assert db.query(AllFreeRequest).count() == 0
        assert db.query(AllFreeRequestLine).count() == 0
        assert db.query(AllFreeRequestEvent).count() == 0
        assert db.query(AuditLog).filter_by(action="all_free_requested").count() == 0


def test_line_update_wins_and_invalidates_stage_atomically(pg_case):
    engine, ids = pg_case
    started, pids = threading.Event(), []
    with Session(engine) as editor:
        editor.get(VisitService, ids["line"]).price = Decimal("0.08")
        editor.flush()  # real 0102 trigger has locked the Visit and invalidated its epoch
        with ThreadPoolExecutor(max_workers=1) as pool:
            worker = pool.submit(_stage, engine, ids, started, pids)
            try:
                assert started.wait(5)
                _blocked(engine, pids[0], worker)
            finally:
                editor.commit()
            assert worker.result(timeout=15) == "AllFreeRequestError"
    _assert_no_request(engine)


def test_locked_line_returns_conflict_and_releases_visit_without_deadlock(pg_case):
    engine, ids = pg_case
    started, pids = threading.Event(), []
    with Session(engine) as editor:
        line = (editor.query(VisitService).filter_by(id=ids["line"])
                .with_for_update().one())
        with ThreadPoolExecutor(max_workers=1) as pool:
            worker = pool.submit(_stage, engine, ids, started, pids)
            assert started.wait(5)
            assert worker.result(timeout=5) == "AllFreeRequestError"
            # A full rollback releases the Visit, so the real 0102 trigger can
            # complete in the child-first editor transaction.
            line.price = Decimal("0.08")
            editor.flush()
            editor.commit()
    _assert_no_request(engine)


@pytest.mark.parametrize("revocation", ["jti", "epoch", "deactivate"])
def test_logout_or_revocation_wins_under_user_lock(pg_case, revocation):
    engine, ids = pg_case
    started, pids = threading.Event(), []
    with Session(engine) as logout:
        actor = logout.query(User).filter_by(id=ids["user"]).with_for_update().one()
        if revocation == "jti":
            logout.add(TokenBlacklist(jti="synthetic-jti", user_id=ids["user"],
                                      expires_at=datetime.now(UTC) + timedelta(hours=1), reason="logout"))
        elif revocation == "epoch":
            actor.auth_epoch += 1
        else:
            actor.is_active = False
        logout.flush()
        with ThreadPoolExecutor(max_workers=1) as pool:
            worker = pool.submit(_stage, engine, ids, started, pids)
            try:
                assert started.wait(5)
                _blocked(engine, pids[0], worker)
            finally:
                logout.commit()
            assert worker.result(timeout=15) == "ProfileBearerInvalid"
    _assert_no_request(engine)


def test_real_0102_invalidates_staged_snapshot_after_line_change(pg_case):
    engine, ids = pg_case
    started, pids = threading.Event(), []
    assert _stage(engine, ids, started, pids) == "created"
    with Session(engine) as db:
        request = db.query(AllFreeRequest).one()
        assert request.status == "pending" and request.baseline_total == Decimal("0.21")
        request_id = request.id
        line = db.get(VisitService, ids["line"])
        line.price = Decimal("0.08")
        db.commit()
    with Session(engine) as db:
        visit = db.get(Visit, ids["visit"])
        assert visit.confirmation_context_epoch != ids["epoch"]
        bearer = ProfileBearerContext(ids["user"], 0, "synthetic-jti", int(time.time()) + 600, None)
        with pytest.raises(AllFreeRequestError) as error:
            AllFreeRequestService(db).inspect_decision(request_id=request_id, bearer=bearer)
        assert error.value.status_code == 409
        assert db.get(AllFreeRequest, request_id).status == "pending"


@pytest.mark.parametrize("failure", ["expiry", "audit"])
def test_pg_failed_stage_outer_commit_is_atomic(pg_case, monkeypatch, failure):
    import app.services.all_free_request_service as module
    engine, ids = pg_case
    with Session(engine) as db:
        bearer = ProfileBearerContext(ids["user"], 0, "synthetic-jti", int(time.time()) + 600, None)
        if failure == "expiry":
            def expire_after_flush(_bearer):
                assert db.query(AllFreeRequest).count() == 1
                assert db.query(AllFreeRequestLine).count() == 1
                assert db.query(AllFreeRequestEvent).count() == 1
                assert db.query(AuditLog).filter_by(action="all_free_requested").count() == 1
                raise ProfileBearerInvalid("synthetic expiration after flush")
            monkeypatch.setattr(module, "check_bearer_expiry", expire_after_flush)
        else:
            @sa.event.listens_for(db, "before_flush")
            def fail_audit(session, _context, _instances):
                if any(isinstance(item, AuditLog) for item in session.new):
                    raise RuntimeError("synthetic audit flush failure")
        with pytest.raises(ProfileBearerInvalid if failure == "expiry" else RuntimeError):
            AllFreeRequestService(db).stage_request(visit_id=ids["visit"], expected_epoch=ids["epoch"], bearer=bearer)
        db.commit()
    _assert_no_request(engine)


def test_pg_successful_stage_then_root_rollback_is_atomic(pg_case):
    engine, ids = pg_case
    with Session(engine) as db:
        bearer = ProfileBearerContext(ids["user"], 0, "synthetic-jti", int(time.time()) + 600, None)
        AllFreeRequestService(db).stage_request(visit_id=ids["visit"], expected_epoch=ids["epoch"], bearer=bearer)
        assert db.query(AllFreeRequest).count() == 1
        db.rollback()
    _assert_no_request(engine)
