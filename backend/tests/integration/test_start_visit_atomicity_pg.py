"""Start-atomicity follow-up (PR after #3367) — PostgreSQL twin of the
core scenarios.

The SQLite-file fresh-session proofs live in
``tests/integration/test_queue_resource_runtime_switch.py`` (the
d5ac9441e discipline). The owner's follow-up spec asks for a real
transaction boundary with PostgreSQL PREFERRED in CI: this module runs
the same controlled-failure scenarios against a run-unique PostgreSQL
schema — real commits, real rollbacks, fresh-session durability
verification — inside the CI Gate D backend job (skipped anywhere a
disposable PostgreSQL is not configured).

Scenario matrix (mirrors the SQLite twins):

- EXISTING visit: the entry flip + the open→in_progress transition must NOT be durable when the endpoint's boundary commit
  fails after the lifecycle call;
- CREATED visit (doctor branch): no durable visit row / link / flip;
- CREATED visit (resource branch): the same through the doctorless
  surface;
- SUCCESS (resource branch): the single boundary commit persists the
  whole unit (created visit + link + flip + annotations).

The failure injection is the frame-name one: ONLY the ``db.commit()``
called directly from ``start_patient_visit``'s body fails; the
lifecycle service's internal commit (the defect under test on the
broken head) runs for real.

Scratch-schema isolation: the schema name is run-unique (prefix + a
uuid suffix), created WITHOUT a pre-drop and dropped only in teardown
by the run that created it — two concurrent pytest processes never see
each other's schema.
"""

from __future__ import annotations

import os
import sys
import uuid
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.schema import CreateSchema, DropSchema

from app.db import base  # noqa: F401 — registers all models
from app.db.base_class import Base
from app.models.clinic import Doctor
from app.models.online_queue import OnlineQueueEntry
from app.models.patient import Patient
from app.models.user import User
from app.models.visit import Visit
from app.services.medical_specialty_seed import seed_medical_specialties
from app.services.queue_service import queue_service

pytestmark = pytest.mark.integration

_DISABLED_HASH = "!disabled:start-atomicity-pg"


def _now_tashkent_day():
    return datetime.now(ZoneInfo("Asia/Tashkent")).date()


@pytest.fixture(scope="module")
def sa_pg_engine():
    raw_url = os.environ.get("DATABASE_URL", "").strip()
    if not raw_url:
        pytest.skip("start-atomicity PG proof requires DATABASE_URL for PostgreSQL")
    url = make_url(raw_url)
    if url.get_backend_name() != "postgresql":
        pytest.skip("start-atomicity PG proof requires PostgreSQL")
    if os.environ.get("CI", "").lower() != "true" and not (
        url.database or ""
    ).startswith("clinic_test"):
        pytest.skip("use CI or an explicitly disposable clinic_test database")

    schema = "test_start_atomicity_" + uuid.uuid4().hex
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
        with engine.connect() as catalog_conn:
            seed_medical_specialties(catalog_conn)
            catalog_conn.commit()
        yield engine
    finally:
        engine.dispose()
        with admin.begin() as connection:
            connection.execute(DropSchema(schema, cascade=True))
        admin.dispose()


def _mk_user(db: Session, username: str, role: str) -> User:
    user = User(
        username=username,
        email=f"{username}@example.com",
        full_name=username,
        hashed_password=_DISABLED_HASH,
        role=role,
        is_active=True,
        is_superuser=False,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _mk_doctor(db: Session, user_id: int, specialty: str) -> Doctor:
    doctor = Doctor(user_id=user_id, specialty=specialty, active=True)
    db.add(doctor)
    db.commit()
    db.refresh(doctor)
    return doctor


def _inject_start_boundary_commit_failure(db):
    """Fail ONLY ``db.commit()`` called directly from the endpoint body.

    The lifecycle service's internal commit (``transition_status`` with
    the default ``commit=True`` — the defect under test on the broken
    head) runs for real; only the endpoint's own boundary commit fails.

    Returns ``(real_commit, fired)``: ``fired`` is a mutable flag set
    when the injected failure actually fired — the non-vacuousity guard
    proving the flow REACHED the endpoint's boundary commit (RBAC
    passed, the resolution and the lifecycle call ran) rather than
    dying earlier inside the endpoint's broad ``except``.
    """
    real_commit = db.commit
    fired = [False]

    def _failing_commit() -> None:
        if sys._getframe(1).f_code.co_name == "start_patient_visit":
            fired[0] = True
            raise RuntimeError("simulated boundary-commit failure")
        real_commit()

    db.commit = _failing_commit
    return real_commit, fired


def _seed_called_entry(engine, *, resource: bool):
    """Seed patient + queue + `called` entry; return ids + caller user."""
    token = uuid.uuid4().hex[:8]
    with Session(engine) as db:
        patient = Patient(
            last_name=f"Стартов{token[:4]}",
            first_name="Пациент",
            phone=f"+9989012345{token[:5]}",
            is_deleted=False,
        )
        db.add(patient)
        db.commit()

        queue_day = _now_tashkent_day()
        if resource:
            from app.models.online_queue import QueueResource

            db.add(
                QueueResource(
                    code=f"prcstart_{token}",
                    queue_tag=f"prcstart_{token}",
                    display_name=f"PG start-atomicity {token}",
                    active=True,
                    start_number_online=1,
                    max_online_per_day=15,
                )
            )
            db.commit()
            queue = queue_service.get_or_create_daily_queue(
                db, day=queue_day, specialist_id=None, queue_tag=f"prcstart_{token}"
            )
            caller = _mk_user(db, f"adm_sa_{token}", "Admin")
        else:
            doc_user = _mk_user(db, f"doc_sa_{token}", "Doctor")
            therapist = _mk_doctor(db, doc_user.id, "therapy")
            queue = queue_service.get_or_create_daily_queue(
                db, day=queue_day, specialist_id=therapist.id
            )
            caller = doc_user

        entry = OnlineQueueEntry(
            queue_id=queue.id, number=1, status="called", source="desk"
        )
        entry.patient_id = patient.id
        db.add(entry)
        db.commit()
        db.refresh(entry)
        # caller_id, NOT the User instance: the trailing ``db.commit()``
        # expires every instance of the seeding session, so a returned
        # User would be detached-with-expired-attributes — the endpoint's
        # ``current_user.role`` access would then raise
        # DetachedInstanceError (a VACUOUS 500 before any lifecycle
        # work). Each test re-fetches the caller inside its RUN session.
        return entry.id, patient.id, caller.id


def _run_failing_start(engine, entry_id, caller_id):
    from fastapi import HTTPException

    from app.api.v1.endpoints.doctor_integration._queue_ops import (
        start_patient_visit,
    )

    maker = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    db = maker()
    try:
        caller = db.get(User, caller_id)  # bound to the RUN session
        real_commit, fired = _inject_start_boundary_commit_failure(db)
        try:
            with pytest.raises(HTTPException) as exc:
                start_patient_visit(entry_id=entry_id, db=db, current_user=caller)
            assert exc.value.status_code == 500
        finally:
            db.commit = real_commit
        assert fired[0], (
            "non-vacuousity guard: the 500 must come from the injected "
            "BOUNDARY-commit failure — the flow reached the endpoint's "
            "own db.commit() (RBAC passed, resolution + lifecycle ran)"
        )
        db.rollback()
    finally:
        db.close()


def test_pg_existing_visit_start_not_durable_when_boundary_commit_fails(
    sa_pg_engine,
) -> None:
    entry_id, patient_id, caller = _seed_called_entry(sa_pg_engine, resource=False)
    with Session(sa_pg_engine) as db:
        entry = db.get(OnlineQueueEntry, entry_id)
        queue_day = entry.queue.day
        visit = Visit(
            patient_id=patient_id,
            doctor_id=None,
            visit_date=queue_day,
            visit_time="09:00",
            status="open",
            department="general",
        )
        db.add(visit)
        db.commit()
        db.refresh(visit)
        entry.visit_id = visit.id
        db.commit()
        visit_id = visit.id

    _run_failing_start(sa_pg_engine, entry_id, caller_id)

    with Session(sa_pg_engine) as check:
        row = check.get(OnlineQueueEntry, entry_id)
        assert row.status == "called"  # NOT in_progress
        fresh_visit = check.get(Visit, visit_id)
        assert fresh_visit.status == "open"  # NOT in_progress
        assert fresh_visit.visit_time == "09:00"  # annotation not durable
        assert fresh_visit.notes is None


def test_pg_created_visit_start_not_durable_when_boundary_commit_fails(
    sa_pg_engine,
) -> None:
    entry_id, patient_id, caller = _seed_called_entry(sa_pg_engine, resource=False)

    _run_failing_start(sa_pg_engine, entry_id, caller_id)

    with Session(sa_pg_engine) as check:
        row = check.get(OnlineQueueEntry, entry_id)
        assert row.status == "called"  # NOT in_progress
        assert row.visit_id is None  # the link never persisted
        assert (
            check.query(Visit).filter(Visit.patient_id == patient_id).count() == 0
        )  # the created visit did not survive


def test_pg_resource_branch_created_visit_start_not_durable_when_boundary_commit_fails(
    sa_pg_engine,
) -> None:
    entry_id, patient_id, caller = _seed_called_entry(sa_pg_engine, resource=True)

    _run_failing_start(sa_pg_engine, entry_id, caller_id)

    with Session(sa_pg_engine) as check:
        row = check.get(OnlineQueueEntry, entry_id)
        assert row.status == "called"  # NOT in_progress
        assert row.visit_id is None
        assert check.query(Visit).filter(Visit.patient_id == patient_id).count() == 0


def test_pg_resource_branch_start_success_persists_created_visit_unit(
    sa_pg_engine,
) -> None:
    from app.api.v1.endpoints.doctor_integration._queue_ops import (
        start_patient_visit,
    )

    entry_id, _patient_id, caller_id = _seed_called_entry(sa_pg_engine, resource=True)

    with Session(sa_pg_engine) as run_db:
        caller = run_db.get(User, caller_id)  # bound to the RUN session
        result = start_patient_visit(entry_id=entry_id, db=run_db, current_user=caller)
        assert result["success"] is True

    with Session(sa_pg_engine) as check:
        row = check.get(OnlineQueueEntry, entry_id)
        assert row.status == "in_progress"
        assert row.visit_id is not None
        fresh_visit = check.get(Visit, row.visit_id)
        assert fresh_visit is not None
        assert fresh_visit.status == "in_progress"
        assert fresh_visit.doctor_id is None  # resource surface
        assert fresh_visit.visit_time is not None
        assert fresh_visit.notes is not None
