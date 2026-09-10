"""Reminder pipeline — PostgreSQL atomic-claim race semantics (Codex P2).

``test_reminder_pipeline.py`` runs on SQLite — the sequential idempotency
contract is covered there, but the CONCURRENT claim race (two overlapping
deliveries for the same visit) can only be proven against real PostgreSQL
row locking.

This module is self-contained: it sets its own environment defaults
BEFORE importing app modules (same pattern as ``test_gate_d.py``), builds
its own engine, and never touches the repo conftest. It is marked
``gate_d`` — excluded from the default suite by pytest.ini addopts and
executed in CI by a dedicated backend-tests step whose DATABASE_URL
points at the job's postgres service.

Run locally:
    cd backend && DATABASE_URL=postgresql+psycopg://clinic:pw@localhost:5432/clinicdb \
        pytest tests/integration/test_reminder_pipeline_pg.py -m gate_d --noconftest

NOTE: this module is collected by the main suite too — there the repo
conftest puts ``backend/`` on sys.path and pytest.ini's ``-m "not gate_d"``
deselects everything here; the sys.path insert above keeps the dedicated
``--noconftest`` CI step working without the conftest.
"""

from __future__ import annotations

import asyncio
import os
import sys
import threading
import uuid
from datetime import date, timedelta

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))  # backend/

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+psycopg://clinic:clinic_ci_only_password@localhost:5432/clinicdb",
)
# Environment contract for the isolated (--noconftest) CI step: ENV=dev keeps
# the production-only config gates (ENCRYPTION_KEY / SMS provider) from
# firing, and TESTING=1 is deliberately NOT set — the config validator
# forbids it outside explicit dev values. The schema/behavior under test is
# env-independent.
os.environ.setdefault("ENV", "dev")
os.environ.setdefault(
    "SECRET_KEY", "test-secret-key-for-reminder-pg-concurrency-32-chars"
)
os.environ.setdefault("ALLOW_SQLITE_DATABASE_URL", "0")

from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

import app.db.base  # noqa: F401,E402 - registers every model on Base

pytestmark = pytest.mark.gate_d


@pytest.fixture(scope="module")
def pg_engine():
    """Real PostgreSQL engine — the fixture ASSERTS the expected schema and
    never creates it (Codex round 14, P2: ``Base.metadata.create_all()``
    could silently create missing tables outside Alembic — and without the
    migrations' RLS setup — if the documented command was ever pointed at a
    shared/staging/production database; that is exactly the schema drift
    the repository guardrail forbids). The database MUST be provisioned by
    ``alembic upgrade head`` first (the CI gate_d job runs it on its
    disposable postgres service before this step)."""
    url = os.environ["DATABASE_URL"]
    if "postgres" not in url:
        pytest.skip("reminder PG-concurrency proof requires PostgreSQL")
    from sqlalchemy import inspect

    engine = create_engine(url)
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())
    missing_tables = {"visits", "patients", "doctors", "users"} - tables
    if missing_tables:
        pytest.fail(
            f"tables {sorted(missing_tables)} do not exist — run "
            "`alembic upgrade head` against the gate_d database first; "
            "this fixture must not create schema outside Alembic "
            "(schema-drift guardrail)"
        )
    visit_columns = {c["name"] for c in inspector.get_columns("visits")}
    missing_columns = {
        "reminder_sent_at",
        "reminder_claimed_at",
        "reminder_generation",
    } - visit_columns
    if missing_columns:
        pytest.fail(
            f"visits is missing reminder-pipeline columns {sorted(missing_columns)} "
            "— the gate_d database is behind alembic head; upgrade it instead "
            "of letting the fixture mutate the schema"
        )
    yield engine
    engine.dispose()


@pytest.fixture
def cleanup_rows(pg_engine):
    """Collect created row ids and delete them FK-safe on teardown, so the
    shared CI postgres service stays clean across runs."""
    created: list[tuple[int, int, int, int]] = []
    yield created
    from app.models.clinic import Doctor
    from app.models.patient import Patient
    from app.models.user import User
    from app.models.visit import Visit

    s = sessionmaker(bind=pg_engine)()
    try:
        for visit_id, patient_id, doctor_id, user_id in created:
            s.query(Visit).filter(Visit.id == visit_id).delete()
            s.query(Patient).filter(Patient.id == patient_id).delete()
            s.query(Doctor).filter(Doctor.id == doctor_id).delete()
            s.query(User).filter(User.id == user_id).delete()
        s.commit()
    finally:
        s.close()


def test_concurrent_reminder_jobs_send_exactly_once(
    pg_engine, cleanup_rows, monkeypatch: pytest.MonkeyPatch
):
    """Two overlapping deliveries for the same visit race the lease claim.
    The atomic conditional-UPDATE claim in ``send_visit_reminder``
    (``UPDATE ... SET reminder_claimed_at = :lease WHERE id = X AND
    reminder_sent_at IS NULL AND no live lease``) must serialize them: the
    loser blocks on the winner's row lock until the claim commits, then
    re-evaluates the predicate, matches 0 rows, and skips the send —
    exactly one notification dispatch per visit, no matter how the jobs
    overlap. Without the conditional predicate both writers would claim
    and both would dispatch (calls == 2)."""
    from app.models.clinic import Doctor
    from app.models.patient import Patient
    from app.models.user import User
    from app.models.visit import Visit
    from app.services.notifications_pkg._reminders import RemindersMixin
    from app.tasks.worker import send_visit_reminder

    suffix = uuid.uuid4().hex[:8]
    s = sessionmaker(bind=pg_engine)()
    try:
        user = User(
            username=f"rempg_{suffix}",
            email=f"rempg_{suffix}@test.invalid",
            full_name="Reminder PG Doctor",
            hashed_password="test-not-a-login-hash",
            role="Doctor",
            is_active=True,
            is_superuser=False,
        )
        s.add(user)
        s.flush()
        doctor = Doctor(user_id=user.id, specialty="Кардиология", active=True)
        s.add(doctor)
        s.flush()
        # Synthetic-data policy (AGENTS.md): operator prefix 00 does not
        # exist in the +998 numbering plan; address is marked SYNTHETIC.
        patient = Patient(
            first_name="Синтетик",
            last_name=f"ПГ_{suffix}",
            middle_name="Синтетикович",
            phone=f"+998000{int(uuid.uuid4().int % 10**6):06d}",
            birth_date=date(1990, 1, 1),
            address="SYNTHETIC-REMINDER-PG-FIXTURE",
        )
        s.add(patient)
        s.flush()
        visit = Visit(
            patient_id=patient.id,
            doctor_id=doctor.id,
            # Round 17, P1: the appointment must be reliably in the FUTURE —
            # the worker's post-claim start check aborts started appointments,
            # so a "today 10:00" fixture would fail for most of every day
            # (10:00 clinic time = 05:00 UTC).
            visit_date=date.today() + timedelta(days=2),
            visit_time="10:00",
            status="pending_confirmation",
            discount_mode="none",
            department="cardiology",
            confirmation_token=f"rempg-{suffix}",
            confirmation_channel="pwa",
        )
        s.add(visit)
        s.commit()
        cleanup_rows.append((visit.id, patient.id, doctor.id, user.id))
        visit_id = visit.id
    finally:
        s.close()

    calls: list[dict] = []
    started = threading.Barrier(2)

    async def _spy(self, db, vid, hours_before=24, channel=None):
        calls.append({"visit_id": vid, "hours_before": hours_before})
        # Simulate slow provider I/O AFTER the claim committed — the window
        # an unguarded second reader would exploit to double-send.
        await asyncio.sleep(0.2)
        return {"success": True, "channel": "telegram"}

    monkeypatch.setattr(RemindersMixin, "send_confirmation_reminder", _spy)

    # Codex round 7: every delivery carries the schedule version (the
    # fixture visit has date=today, time="10:00", generation=0).
    from app.tasks.scheduler import build_reminder_schedule_version

    _vs = sessionmaker(bind=pg_engine)()
    _fresh = _vs.query(Visit).filter(Visit.id == visit_id).first()
    fixture_version = build_reminder_schedule_version(_fresh)
    _vs.close()

    def _run_job() -> None:
        started.wait(30)
        asyncio.run(
            send_visit_reminder(
                {},
                visit_id=visit_id,
                channel="telegram",
                schedule_version=fixture_version,
            )
        )

    t1 = threading.Thread(target=_run_job, name="reminder-job-1")
    t2 = threading.Thread(target=_run_job, name="reminder-job-2")
    t1.start()
    t2.start()
    t1.join(120)
    t2.join(120)
    assert not t1.is_alive() and not t2.is_alive(), "worker jobs deadlocked"

    assert len(calls) == 1, (
        f"exactly one dispatch expected under the atomic claim, "
        f"got {len(calls)}: {calls}"
    )
    assert calls[0]["visit_id"] == visit_id
    assert calls[0]["hours_before"] == 24

    from app.models.visit import Visit as VisitModel

    fresh = sessionmaker(bind=pg_engine)()
    try:
        row = fresh.query(VisitModel).filter(VisitModel.id == visit_id).first()
        assert row is not None and row.reminder_sent_at is not None
    finally:
        fresh.close()
