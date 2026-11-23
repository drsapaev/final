"""Real PostgreSQL revision and lifecycle serialization for Telegram RSVP."""
from __future__ import annotations

import io
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from fastapi import HTTPException
from sqlalchemy import create_engine, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session
from sqlalchemy.schema import CreateSchema, DropSchema

from app.crud.appointment import appointment as crud_appointment
from app.db.base_class import Base
from app.models.appointment import Appointment
from app.models.patient import Patient
from app.models.telegram_config import TelegramUser
from app.services.appointment_rsvp import apply_appointment_decision, make_appointment_callback, preview_appointment_decision

def load_migration(filename="0100_appointment_rsvp_occurrence.py"):
    import importlib.util
    from pathlib import Path
    path = Path(__file__).resolve().parents[2] / "alembic/versions" / filename
    spec = importlib.util.spec_from_file_location("appointment_rsvp_0100", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def pg_engine():
    raw = os.getenv("DATABASE_URL", "").strip()
    ci = os.getenv("CI", "").lower() == "true"
    if not raw or make_url(raw).get_backend_name() != "postgresql":
        if ci:
            pytest.fail("CI requires PostgreSQL DATABASE_URL")
        pytest.skip("requires disposable PostgreSQL DATABASE_URL")
    url = make_url(raw)
    if not ci and not (url.database or "").startswith("clinic_test"):
        pytest.skip("requires explicitly disposable clinic_test database")
    schema = "test_rsvp_" + uuid4().hex
    admin = create_engine(url)
    with admin.begin() as connection:
        connection.execute(CreateSchema(schema))
    engine = create_engine(url, pool_size=6, connect_args={"options": f"-csearch_path={schema} -cstatement_timeout=15000 -clock_timeout=10000"})
    try:
        import app.db.base  # noqa: F401
        Base.metadata.create_all(engine)
        # Construct the pre-migration shape, then exercise the actual revision.
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE appointments DROP COLUMN patient_rsvp_revision, DROP COLUMN patient_rsvp_at, DROP COLUMN occurrence_revision"))
            conn.execute(text("ALTER TABLE telegram_users DROP COLUMN patient_link_epoch CASCADE"))
            with Operations.context(MigrationContext.configure(conn)):
                load_migration().upgrade()
                load_migration("0101_telegram_patient_link_epoch.py").upgrade()
        yield engine
    finally:
        engine.dispose()
        with admin.begin() as conn:
            conn.execute(DropSchema(schema, cascade=True))
        admin.dispose()


def seed(engine, *, status="pending"):
    with Session(engine, expire_on_commit=False) as db:
        patient = Patient(first_name="SYNTHETIC", last_name="TEST")
        db.add(patient)
        db.flush()
        appointment = Appointment(patient_id=patient.id, appointment_date=(datetime.now(UTC) + timedelta(days=4)).date(),
                                  appointment_time="12:00", status=status)
        db.add_all([appointment, TelegramUser(patient_id=patient.id, chat_id=413371, active=True,
                                             blocked=False, notifications_enabled=True, appointment_reminders=True)])
        db.commit()
        return appointment.id


def signed(engine, action, appointment_id, revision=0):
    with Session(engine) as db:
        link = db.query(TelegramUser).filter_by(chat_id=413371).one()
        return make_appointment_callback(action, appointment_id, revision, 413371, link.id, link.patient_link_epoch)


def wait_until_blocked(engine, pid):
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        with engine.connect() as conn:
            if conn.execute(text("SELECT cardinality(pg_blocking_pids(:pid))"), {"pid": pid}).scalar_one():
                return
        time.sleep(0.02)
    pytest.fail("contending transaction did not wait on row lock")


def test_online_upgrade_downgrade_and_offline_sql(pg_engine):
    module = load_migration()
    with pg_engine.begin() as conn:
        with Operations.context(MigrationContext.configure(conn)):
            module.downgrade()
            module.upgrade()
        assert conn.execute(text("SELECT count(*) FROM pg_trigger WHERE tgname='appointments_occurrence_revision' AND tgrelid='appointments'::regclass AND NOT tgisinternal")).scalar_one() == 1
    output = io.StringIO()
    context = MigrationContext.configure(dialect_name="postgresql", opts={"as_sql": True, "output_buffer": output})
    with Operations.context(context):
        module.upgrade()
    sql = output.getvalue()
    assert "CREATE TRIGGER appointments_occurrence_revision" in sql
    assert "CREATE FUNCTION bump_appointment_occurrence_revision" in sql


def test_trigger_invalidates_aba_terminal_and_rolls_back(pg_engine):
    appointment_id = seed(pg_engine)
    with Session(pg_engine) as db:
        assert apply_appointment_decision(db, callback_data=signed(pg_engine, "c", appointment_id), chat_id=413371) == "confirmed"
    with pg_engine.begin() as conn:
        conn.execute(text("UPDATE appointments SET appointment_time = '13:00' WHERE id=:id"), {"id": appointment_id})
        conn.execute(text("UPDATE appointments SET appointment_time = '12:00' WHERE id=:id"), {"id": appointment_id})
    with Session(pg_engine) as db:
        row = db.get(Appointment, appointment_id)
        assert row.occurrence_revision == 2
        assert row.patient_rsvp_at is not None
        assert row.patient_confirmed_at is None
        assert apply_appointment_decision(db, callback_data=signed(pg_engine, "c", appointment_id), chat_id=413371) == "stale"
    with pg_engine.connect() as conn:
        trans = conn.begin()
        conn.execute(text("UPDATE appointments SET status='cancelled' WHERE id=:id"), {"id": appointment_id})
        assert conn.execute(text("SELECT occurrence_revision FROM appointments WHERE id=:id"), {"id": appointment_id}).scalar_one() == 3
        trans.rollback()
    with pg_engine.begin() as conn:
        assert conn.execute(text("SELECT occurrence_revision FROM appointments WHERE id=:id"), {"id": appointment_id}).scalar_one() == 2
        conn.execute(text("UPDATE appointments SET status='paid' WHERE id=:id"), {"id": appointment_id})
        assert conn.execute(text("SELECT occurrence_revision FROM appointments WHERE id=:id"), {"id": appointment_id}).scalar_one() == 2
        conn.execute(text("UPDATE appointments SET status='no_show' WHERE id=:id"), {"id": appointment_id})
        conn.execute(text("UPDATE appointments SET status='paid' WHERE id=:id"), {"id": appointment_id})
        assert conn.execute(text("SELECT occurrence_revision FROM appointments WHERE id=:id"), {"id": appointment_id}).scalar_one() == 4


def test_callback_waits_for_registrar_terminal_change(pg_engine):
    appointment_id = seed(pg_engine, status="paid")
    callback_data = signed(pg_engine, "x", appointment_id)
    started = threading.Event()
    pids = []
    def callback():
        with Session(pg_engine) as db:
            pids.append(db.execute(text("SELECT pg_backend_pid()")).scalar_one())
            started.set()
            return apply_appointment_decision(db, callback_data=callback_data, chat_id=413371)
    with Session(pg_engine) as registrar:
        row = registrar.execute(select(Appointment).where(Appointment.id == appointment_id).with_for_update()).scalar_one()
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(callback)
            assert started.wait(5)
            wait_until_blocked(pg_engine, pids[0])
            row.status = "no_show"
            registrar.commit()
            assert future.result(timeout=5) in {"stale", "unavailable"}
    with Session(pg_engine) as db:
        assert db.get(Appointment, appointment_id).status == "no_show"


def test_registrar_waits_and_rechecks_after_patient_cancel(pg_engine):
    appointment_id = seed(pg_engine, status="paid")
    started = threading.Event()
    pids = []
    def registrar():
        with Session(pg_engine) as db:
            pids.append(db.execute(text("SELECT pg_backend_pid()")).scalar_one())
            started.set()
            try:
                crud_appointment.update_status(db, appointment_id=appointment_id, new_status="no_show")
            except HTTPException as exc:
                return exc.status_code
            return 200
    with Session(pg_engine) as patient:
        row = patient.execute(select(Appointment).where(Appointment.id == appointment_id).with_for_update()).scalar_one()
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(registrar)
            assert started.wait(5)
            wait_until_blocked(pg_engine, pids[0])
            row.status = "cancelled"
            patient.commit()
            assert future.result(timeout=5) == 400
    with Session(pg_engine) as db:
        assert db.get(Appointment, appointment_id).status == "cancelled"


def test_revocation_wins_over_waiting_callback(pg_engine):
    appointment_id = seed(pg_engine)
    callback_data = signed(pg_engine, "c", appointment_id)
    started = threading.Event()
    pids = []
    def callback():
        with Session(pg_engine) as db:
            pids.append(db.execute(text("SELECT pg_backend_pid()")).scalar_one())
            started.set()
            return apply_appointment_decision(db, callback_data=callback_data, chat_id=413371)
    with Session(pg_engine) as admin:
        link = admin.execute(select(TelegramUser).where(TelegramUser.chat_id == 413371).with_for_update()).scalar_one()
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(callback)
            assert started.wait(5)
            wait_until_blocked(pg_engine, pids[0])
            link.active = False
            admin.commit()
            assert future.result(timeout=5) == "unavailable"
    with Session(pg_engine) as db:
        assert db.get(Appointment, appointment_id).patient_rsvp_at is None


def test_revocation_wins_over_waiting_preview(pg_engine):
    appointment_id = seed(pg_engine)
    data = signed(pg_engine, "v", appointment_id)
    started = threading.Event()
    pids = []

    def preview():
        with Session(pg_engine) as db:
            pids.append(db.execute(text("SELECT pg_backend_pid()")).scalar_one())
            started.set()
            return preview_appointment_decision(db, callback_data=data, chat_id=413371)

    with Session(pg_engine) as admin:
        link = admin.execute(select(TelegramUser).where(TelegramUser.chat_id == 413371).with_for_update()).scalar_one()
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(preview)
            assert started.wait(5)
            wait_until_blocked(pg_engine, pids[0])
            link.active = False
            admin.commit()
            assert future.result(timeout=5) is None


def test_old_button_never_revives_after_bulk_revoke_and_relink(pg_engine):
    appointment_id = seed(pg_engine)
    old_data = signed(pg_engine, "c", appointment_id)
    with pg_engine.begin() as conn:
        original = conn.execute(text("SELECT patient_link_epoch FROM telegram_users WHERE chat_id=413371")).scalar_one()
        conn.execute(text("UPDATE telegram_users SET notifications_enabled=false WHERE chat_id=413371"))
        conn.execute(text("UPDATE telegram_users SET notifications_enabled=true WHERE chat_id=413371"))
        assert conn.execute(text("SELECT patient_link_epoch FROM telegram_users WHERE chat_id=413371")).scalar_one() != original
    with Session(pg_engine) as db:
        assert apply_appointment_decision(db, callback_data=old_data, chat_id=413371) == "stale"
        assert db.get(Appointment, appointment_id).patient_rsvp_at is None


def test_patient_cancel_rechecks_terminal_state_under_lock(pg_engine):
    from app.services.patient_appointments_api_service import PatientAppointmentsApiService

    appointment_id = seed(pg_engine, status="paid")
    started = threading.Event()
    pids = []

    def patient_cancel():
        with Session(pg_engine) as db:
            stale = db.get(Appointment, appointment_id)
            pids.append(db.execute(text("SELECT pg_backend_pid()")).scalar_one())
            started.set()
            try:
                PatientAppointmentsApiService(db).cancel_appointment(stale)
            except HTTPException as exc:
                return exc.status_code
            return 200

    with Session(pg_engine) as registrar:
        row = registrar.execute(select(Appointment).where(Appointment.id == appointment_id).with_for_update()).scalar_one()
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(patient_cancel)
            assert started.wait(5)
            wait_until_blocked(pg_engine, pids[0])
            row.status = "no_show"
            registrar.commit()
            assert future.result(timeout=5) == 409
    with Session(pg_engine) as db:
        assert db.get(Appointment, appointment_id).status == "no_show"


def test_emr_promotion_rechecks_cancelled_state_under_lock(pg_engine):
    from app.services.appointment_flow_api_service import AppointmentFlowApiService

    appointment_id = seed(pg_engine, status="paid")
    started = threading.Event()
    pids = []

    def promote():
        with Session(pg_engine) as db:
            stale = db.get(Appointment, appointment_id)
            pids.append(db.execute(text("SELECT pg_backend_pid()")).scalar_one())
            started.set()
            try:
                AppointmentFlowApiService(db).promote_appointment_to_in_visit(appointment=stale)
            except HTTPException as exc:
                return exc.status_code
            return 200

    with Session(pg_engine) as patient:
        row = patient.execute(select(Appointment).where(Appointment.id == appointment_id).with_for_update()).scalar_one()
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(promote)
            assert started.wait(5)
            wait_until_blocked(pg_engine, pids[0])
            row.status = "cancelled"
            patient.commit()
            assert future.result(timeout=5) == 409
    with Session(pg_engine) as db:
        assert db.get(Appointment, appointment_id).status == "cancelled"


def test_doctor_completion_rechecks_cancelled_state_under_lock(pg_engine):
    from types import SimpleNamespace
    from app.api.v1.endpoints.doctor_integration._queue_ops import complete_patient_visit

    appointment_id = seed(pg_engine, status="paid")
    started = threading.Event()
    pids = []

    def complete():
        with Session(pg_engine) as db:
            # Load stale object before the competing commit, as a real caller can.
            db.get(Appointment, appointment_id)
            pids.append(db.execute(text("SELECT pg_backend_pid()")).scalar_one())
            started.set()
            try:
                complete_patient_visit(entry_id=appointment_id, visit_data=None, db=db,
                                       current_user=SimpleNamespace(id=1, role="Admin"))
            except HTTPException as exc:
                return exc.status_code
            return 200

    with Session(pg_engine) as patient:
        row = patient.execute(select(Appointment).where(Appointment.id == appointment_id).with_for_update()).scalar_one()
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(complete)
            assert started.wait(5)
            wait_until_blocked(pg_engine, pids[0])
            row.status = "cancelled"
            patient.commit()
            assert future.result(timeout=5) == 409
    with Session(pg_engine) as db:
        assert db.get(Appointment, appointment_id).status == "cancelled"


def test_queue_completion_rolls_back_when_callback_wins(pg_engine):
    from types import SimpleNamespace

    from app.api.v1.endpoints.doctor_integration._queue_ops import complete_patient_visit
    from app.models.clinic import Doctor
    from app.models.online_queue import DailyQueue, OnlineQueueEntry
    from app.models.visit import Visit

    appointment_id = seed(pg_engine, status="paid")
    with Session(pg_engine, expire_on_commit=False) as db:
        appointment = db.get(Appointment, appointment_id)
        doctor = Doctor(specialty="general", active=True)
        db.add(doctor)
        db.flush()
        appointment.doctor_id = doctor.id
        queue = DailyQueue(day=appointment.appointment_date, specialist_id=doctor.id,
                           queue_tag="general", active=True)
        visit = Visit(patient_id=appointment.patient_id, doctor_id=doctor.id,
                      visit_date=appointment.appointment_date, visit_time="12:00",
                      department="general", status="in_progress")
        db.add_all([queue, visit])
        db.flush()
        entry = OnlineQueueEntry(queue_id=queue.id, number=1, patient_id=appointment.patient_id,
                                 visit_id=visit.id, status="in_progress", source="registrar")
        db.add(entry)
        db.commit()
        db.refresh(appointment)
        entry_id, visit_id, revision = entry.id, visit.id, appointment.occurrence_revision
    callback_data = signed(pg_engine, "x", appointment_id, revision)
    started = threading.Event()
    pids = []

    def complete():
        with Session(pg_engine) as db:
            pids.append(db.execute(text("SELECT pg_backend_pid()")).scalar_one())
            started.set()
            try:
                complete_patient_visit(entry_id=entry_id, visit_data=None, db=db,
                                       current_user=SimpleNamespace(id=1, role="Admin"))
            except HTTPException as exc:
                return exc.status_code
            return 200

    with Session(pg_engine) as patient:
        patient.execute(select(Appointment).where(Appointment.id == appointment_id).with_for_update()).scalar_one()
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(complete)
            assert started.wait(5)
            wait_until_blocked(pg_engine, pids[0])
            assert apply_appointment_decision(patient, callback_data=callback_data, chat_id=413371) == "cancelled"
            assert future.result(timeout=5) == 409
    with Session(pg_engine) as db:
        assert db.get(Appointment, appointment_id).status == "cancelled"
        assert db.get(OnlineQueueEntry, entry_id).status == "in_progress"
        assert db.get(Visit, visit_id).status == "in_progress"
