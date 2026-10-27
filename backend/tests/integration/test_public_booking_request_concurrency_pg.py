"""PostgreSQL concurrency regression for duplicate patient requests."""

from __future__ import annotations

import os
import threading
import time as time_module
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, time, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session
from sqlalchemy.schema import CreateSchema, DropSchema

import app.db.base  # noqa: F401 - register all models before create_all
from app.api import deps
from app.crud.clinic import update_weekly_schedule
from app.db.base_class import Base
from app.main import app
from app.models.appointment import Appointment
from app.models.clinic import ClinicSettings, Doctor, Schedule
from app.models.department import Department
from app.models.patient import Patient
from app.models.public_booking_request import PublicBookingRequest
from app.models.service import Service
from app.models.user import User
from app.services import (
    public_booking_request_service as booking_request_service_module,
)
from app.services.appointment_slot_guard import lock_doctor_for_slot_reservation
from app.services.public_booking_availability import PUBLIC_BOOKING_TIMEZONE
from app.services.telegram_staff_action_adapter_service import (
    TelegramStaffActionAdapterService,
)
from tests.conftest import mint_access_token

pytestmark = pytest.mark.integration

PATIENT_REQUESTS = "/api/v1/patients/booking-requests"


@pytest.fixture(scope="module")
def booking_request_pg_engine():
    raw_url = os.environ.get("DATABASE_URL", "").strip()
    if not raw_url:
        pytest.skip("public booking concurrency proof requires PostgreSQL")
    url = make_url(raw_url)
    if url.get_backend_name() != "postgresql":
        pytest.skip("public booking concurrency proof requires PostgreSQL")
    if os.environ.get("CI", "").lower() != "true" and not (
        url.database or ""
    ).startswith("clinic_test"):
        pytest.skip("use CI or an explicitly disposable clinic_test database")

    schema = "test_booking_request_" + uuid.uuid4().hex
    admin_engine = create_engine(url, pool_pre_ping=True)
    try:
        with admin_engine.begin() as connection:
            connection.execute(CreateSchema(schema))
    except Exception as exc:  # noqa: BLE001 - unavailable disposable PG is skipped
        admin_engine.dispose()
        pytest.skip(f"cannot create isolated PostgreSQL schema: {type(exc).__name__}")

    engine = create_engine(
        url,
        pool_pre_ping=True,
        connect_args={
            "options": (
                f"-csearch_path={schema} -cstatement_timeout=15000 -clock_timeout=15000"
            )
        },
    )
    try:
        Base.metadata.create_all(engine)
        yield engine
    finally:
        engine.dispose()
        with admin_engine.begin() as connection:
            connection.execute(DropSchema(schema, cascade=True))
        admin_engine.dispose()


def test_concurrent_different_keys_create_one_active_request(
    booking_request_pg_engine,
):
    engine = booking_request_pg_engine
    unique = uuid.uuid4().hex[:12]
    with Session(engine) as db:
        doctor_user = User(
            username=f"booking-race-doctor-{unique}",
            hashed_password="synthetic-test-only",
            role="Doctor",
            is_active=True,
            full_name="Synthetic Doctor",
        )
        patient_user = User(
            username=f"booking-race-patient-{unique}",
            hashed_password="synthetic-test-only",
            role="Patient",
            is_active=True,
            full_name="Synthetic Patient",
        )
        db.add_all([doctor_user, patient_user])
        db.flush()
        patient = Patient(
            user_id=patient_user.id,
            first_name="Synthetic",
            last_name=f"Patient {unique}",
        )
        doctor = Doctor(
            user_id=doctor_user.id,
            specialty="cardiology",
            active=True,
            show_on_website=True,
            slug=f"booking-race-doctor-{unique}",
            bio_ru="Synthetic cardiologist.",
            bio_uz="Synthetic cardiologist.",
        )
        service = Service(
            name="Synthetic consultation",
            name_uz="Synthetic consultation",
            description_ru="Synthetic service description.",
            description_uz="Synthetic service description.",
            slug=f"booking-race-service-{unique}",
            duration_minutes=20,
            active=True,
            show_on_website=True,
            requires_doctor=True,
        )
        db.add_all([patient, doctor, service])
        db.flush()

        target_date = datetime.now(PUBLIC_BOOKING_TIMEZONE).date() + timedelta(days=2)
        db.add(
            Schedule(
                doctor_id=doctor.id,
                weekday=target_date.weekday(),
                start_time=time(9),
                end_time=time(11),
                breaks=[],
                active=True,
            )
        )
        db.add_all(
            [
                ClinicSettings(
                    key="public_booking_settings",
                    category="booking_settings",
                    value={
                        "version": 1,
                        "is_enabled": True,
                        "mode": "registrar_request",
                        "booking_horizon_days": 30,
                        "service_ids": [service.id],
                        "doctor_ids": [doctor.id],
                    },
                    updated_by=doctor_user.id,
                ),
                ClinicSettings(
                    key=f"public_booking_calendar_year_{target_date.year:04d}",
                    category="booking_calendar",
                    value={
                        "year": target_date.year,
                        "version": 1,
                        "is_confirmed": True,
                        "holidays": [],
                        "confirmed_at": datetime.now(UTC).isoformat(),
                        "confirmed_by": doctor_user.id,
                    },
                    updated_by=doctor_user.id,
                ),
            ]
        )
        db.commit()
        patient_id = patient.id
        doctor_slug = doctor.slug
        service_slug = service.slug
        token = mint_access_token(patient_user)

    previous_override = app.dependency_overrides.get(deps.get_db)

    def override_get_db():
        with Session(engine) as db:
            yield db

    app.dependency_overrides[deps.get_db] = override_get_db
    barrier = threading.Barrier(2)
    body = {
        "service_slug": service_slug,
        "doctor_slug": doctor_slug,
        "appointment_date": target_date.isoformat(),
        "appointment_time": "09:00",
        "expected_settings_version": 1,
    }
    try:
        with TestClient(app) as client:

            def submit(key: str):
                barrier.wait(timeout=5)
                return client.post(
                    PATIENT_REQUESTS,
                    headers={
                        "Authorization": f"Bearer {token}",
                        "Idempotency-Key": key,
                    },
                    json=body,
                )

            with ThreadPoolExecutor(max_workers=2) as executor:
                responses = list(
                    executor.map(submit, (uuid.uuid4().hex, uuid.uuid4().hex))
                )
    finally:
        if previous_override is None:
            app.dependency_overrides.pop(deps.get_db, None)
        else:
            app.dependency_overrides[deps.get_db] = previous_override

    assert sorted(response.status_code for response in responses) == [201, 409]
    rejected = next(response for response in responses if response.status_code == 409)
    assert rejected.json()["detail"]["code"] == "booking_request_duplicate"

    with Session(engine) as db:
        active = (
            db.query(PublicBookingRequest)
            .filter(
                PublicBookingRequest.patient_id == patient_id,
                PublicBookingRequest.status.in_(("pending", "needs_new_time")),
            )
            .all()
        )
        assert len(active) == 1


def test_concurrent_staff_confirmations_create_one_appointment_for_slot(
    booking_request_pg_engine, monkeypatch
):
    """Two requests for one slot serialize; only one becomes an appointment."""
    engine = booking_request_pg_engine
    unique = uuid.uuid4().hex[:12]
    with Session(engine) as setup:
        doctor_user = User(
            username=f"booking-confirm-doctor-{unique}",
            hashed_password="synthetic-test-only",
            role="Doctor",
            is_active=True,
            full_name="Synthetic Doctor",
        )
        registrar = User(
            username=f"booking-confirm-registrar-{unique}",
            hashed_password="synthetic-test-only",
            role="Registrar",
            is_active=True,
            full_name="Synthetic Registrar",
        )
        patient_users = [
            User(
                username=f"booking-confirm-patient-{index}-{unique}",
                hashed_password="synthetic-test-only",
                role="Patient",
                is_active=True,
                full_name=f"Synthetic Patient {index}",
            )
            for index in (1, 2)
        ]
        setup.add_all([doctor_user, registrar, *patient_users])
        setup.flush()

        department = Department(
            key=f"booking-confirm-{unique}",
            name_ru="Synthetic department",
            name_uz="Synthetic department",
            active=True,
        )
        setup.add(department)
        setup.flush()
        doctor = Doctor(
            user_id=doctor_user.id,
            department_id=department.id,
            specialty="cardiology",
            active=True,
            show_on_website=True,
            slug=f"booking-confirm-doctor-{unique}",
            bio_ru="Synthetic cardiologist.",
            bio_uz="Synthetic cardiologist.",
        )
        service = Service(
            name="Synthetic consultation",
            name_uz="Synthetic consultation",
            description_ru="Synthetic service description.",
            description_uz="Synthetic service description.",
            slug=f"booking-confirm-service-{unique}",
            duration_minutes=20,
            active=True,
            show_on_website=True,
            requires_doctor=True,
        )
        patients = [
            Patient(first_name="Synthetic", last_name=f"Patient {index}-{unique}")
            for index in (1, 2)
        ]
        setup.add_all([doctor, service, *patients])
        setup.flush()
        for patient, patient_user in zip(patients, patient_users, strict=True):
            patient.user_id = patient_user.id

        target_date = datetime.now(PUBLIC_BOOKING_TIMEZONE).date() + timedelta(days=2)
        setup.add(
            Schedule(
                doctor_id=doctor.id,
                weekday=target_date.weekday(),
                start_time=time(9),
                end_time=time(11),
                breaks=[],
                active=True,
            )
        )
        setup.add_all(
            [
                ClinicSettings(
                    key="public_booking_settings",
                    category="booking_settings",
                    value={
                        "version": 1,
                        "is_enabled": True,
                        "mode": "registrar_request",
                        "booking_horizon_days": 30,
                        "service_ids": [service.id],
                        "doctor_ids": [doctor.id],
                    },
                    updated_by=doctor_user.id,
                ),
                ClinicSettings(
                    key=f"public_booking_calendar_year_{target_date.year:04d}",
                    category="booking_calendar",
                    value={
                        "year": target_date.year,
                        "version": 1,
                        "is_confirmed": True,
                        "holidays": [],
                        "confirmed_at": datetime.now(UTC).isoformat(),
                        "confirmed_by": doctor_user.id,
                    },
                    updated_by=doctor_user.id,
                ),
            ]
        )
        setup.commit()
        doctor_id = int(doctor.id)
        doctor_slug = doctor.slug
        service_slug = service.slug
        patient_tokens = [mint_access_token(user) for user in patient_users]
        registrar_token = mint_access_token(registrar)

    previous_override = app.dependency_overrides.get(deps.get_db)

    def override_get_db():
        with Session(engine) as db:
            yield db

    app.dependency_overrides[deps.get_db] = override_get_db
    try:
        with TestClient(app) as client:
            requests = []
            for token in patient_tokens:
                response = client.post(
                    PATIENT_REQUESTS,
                    headers={
                        "Authorization": f"Bearer {token}",
                        "Idempotency-Key": uuid.uuid4().hex,
                    },
                    json={
                        "service_slug": service_slug,
                        "doctor_slug": doctor_slug,
                        "appointment_date": target_date.isoformat(),
                        "appointment_time": "09:00",
                        "expected_settings_version": 1,
                    },
                )
                assert response.status_code == 201, response.text
                requests.append(response.json()["id"])

            first_create_started = threading.Event()
            release_first_create = threading.Event()
            original_create = booking_request_service_module.appointment_crud.create

            def pause_first_create(*, db, obj_in, commit=True):
                first_create_started.set()
                if not release_first_create.wait(timeout=10):
                    raise TimeoutError("test did not release first confirmation")
                return original_create(db=db, obj_in=obj_in, commit=commit)

            monkeypatch.setattr(
                booking_request_service_module.appointment_crud,
                "create",
                pause_first_create,
            )
            second_confirmation_started = threading.Event()

            def confirm(label: str, request_id: str):
                if label == "second":
                    second_confirmation_started.set()
                return client.post(
                    f"/api/v1/admin/public-booking-requests/{request_id}/confirm",
                    headers={"Authorization": f"Bearer {registrar_token}"},
                    json={"expected_version": 1},
                )

            with ThreadPoolExecutor(max_workers=2) as executor:
                first_future = executor.submit(confirm, "first", requests[0])
                assert first_create_started.wait(timeout=5)
                second_future = executor.submit(confirm, "second", requests[1])
                assert second_confirmation_started.wait(timeout=5)
                deadline = time_module.monotonic() + 5
                observed_wait = False
                with engine.connect() as observer:
                    while time_module.monotonic() < deadline:
                        if second_future.done():
                            break
                        lock_waiters = observer.execute(
                            text(
                                "SELECT count(*) FROM pg_stat_activity "
                                "WHERE datname = current_database() "
                                "AND pid <> pg_backend_pid() "
                                "AND state = 'active' "
                                "AND wait_event_type = 'Lock'"
                            )
                        ).scalar_one()
                        if lock_waiters > 0:
                            observed_wait = True
                            break
                        time_module.sleep(0.02)

                assert (
                    observed_wait
                ), "second confirmation did not wait on a PostgreSQL lock"
                assert not second_future.done()
                try:
                    release_first_create.set()
                    first_response = first_future.result(timeout=10)
                    second_response = second_future.result(timeout=10)
                finally:
                    release_first_create.set()

        assert first_response.status_code == 200, first_response.text
        assert second_response.status_code == 200, second_response.text
        assert first_response.json()["status"] == "confirmed"
        assert first_response.json()["appointment_id"] is not None
        assert second_response.json()["status"] == "needs_new_time"
        assert second_response.json()["appointment_id"] is None

        with Session(engine) as verify:
            appointments = (
                verify.query(Appointment)
                .filter(
                    Appointment.doctor_id == doctor_id,
                    Appointment.appointment_date == target_date,
                    Appointment.appointment_time == time(9),
                )
                .all()
            )
            assert len(appointments) == 1
            requests_by_id = {
                str(row.id): row
                for row in verify.query(PublicBookingRequest)
                .filter(
                    PublicBookingRequest.id.in_([uuid.UUID(item) for item in requests])
                )
                .all()
            }
            assert requests_by_id[requests[0]].status == "confirmed"
            assert requests_by_id[requests[0]].appointment_id == appointments[0].id
            assert requests_by_id[requests[1]].status == "needs_new_time"
            assert requests_by_id[requests[1]].appointment_id is None
    finally:
        if "release_first_create" in locals():
            release_first_create.set()
        if previous_override is None:
            app.dependency_overrides.pop(deps.get_db, None)
        else:
            app.dependency_overrides[deps.get_db] = previous_override


def test_doctor_slot_lock_refreshes_preloaded_doctor_after_admin_change(
    booking_request_pg_engine,
):
    engine = booking_request_pg_engine
    unique = uuid.uuid4().hex[:12]
    with Session(engine) as setup:
        doctor_user = User(
            username=f"booking-lock-doctor-{unique}",
            hashed_password="synthetic-test-only",
            role="Doctor",
            is_active=True,
        )
        setup.add(doctor_user)
        setup.flush()
        doctor = Doctor(
            user_id=doctor_user.id,
            specialty="cardiology",
            active=True,
            show_on_website=True,
            slug=f"booking-lock-doctor-{unique}",
            bio_ru="Synthetic doctor.",
            bio_uz="Synthetic doctor.",
        )
        setup.add(doctor)
        setup.commit()
        doctor_id = doctor.id

    with Session(engine) as preloaded_session:
        preloaded = preloaded_session.query(Doctor).filter(Doctor.id == doctor_id).one()
        assert preloaded.active is True

        with Session(engine) as admin_session:
            admin_session.query(Doctor).filter(Doctor.id == doctor_id).update(
                {Doctor.active: False}, synchronize_session=False
            )
            admin_session.commit()

        locked = lock_doctor_for_slot_reservation(preloaded_session, doctor_id)

        assert locked is not None
        assert locked is preloaded
        assert locked.active is False


def test_admin_weekly_schedule_update_waits_for_doctor_booking_lock(
    booking_request_pg_engine,
):
    """Admin schedule edits serialize behind a pending booking confirmation."""
    engine = booking_request_pg_engine
    unique = uuid.uuid4().hex[:12]
    weekday = (
        datetime.now(PUBLIC_BOOKING_TIMEZONE).date() + timedelta(days=2)
    ).weekday()
    with Session(engine) as setup:
        doctor_user = User(
            username=f"booking-schedule-lock-doctor-{unique}",
            hashed_password="synthetic-test-only",
            role="Doctor",
            is_active=True,
        )
        setup.add(doctor_user)
        setup.flush()
        doctor = Doctor(
            user_id=doctor_user.id,
            specialty="cardiology",
            active=True,
            show_on_website=True,
            slug=f"booking-schedule-lock-doctor-{unique}",
            bio_ru="Synthetic doctor.",
            bio_uz="Synthetic doctor.",
        )
        setup.add(doctor)
        setup.flush()
        setup.add(
            Schedule(
                doctor_id=doctor.id,
                weekday=weekday,
                start_time=time(9),
                end_time=time(11),
                breaks=[],
                active=True,
            )
        )
        setup.commit()
        doctor_id = int(doctor.id)

    confirmer = Session(engine)
    locked_doctor = lock_doctor_for_slot_reservation(confirmer, doctor_id)
    assert locked_doctor is not None

    update_started = threading.Event()
    update_pid: dict[str, int] = {}

    def update_schedule():
        with Session(engine) as admin_session:
            update_pid["pid"] = int(
                admin_session.execute(text("SELECT pg_backend_pid()")).scalar_one()
            )
            update_started.set()
            return update_weekly_schedule(
                admin_session,
                doctor_id,
                [
                    {
                        "weekday": weekday,
                        "start_time": time(10),
                        "end_time": time(12),
                        "breaks": [],
                        "active": True,
                    }
                ],
            )

    try:
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(update_schedule)
            assert update_started.wait(timeout=5)
            deadline = time_module.monotonic() + 5
            observed_lock_wait = False
            with engine.connect() as observer:
                while time_module.monotonic() < deadline:
                    if future.done():
                        break
                    wait_type = observer.execute(
                        text(
                            "SELECT wait_event_type FROM pg_stat_activity "
                            "WHERE pid = :pid"
                        ),
                        {"pid": update_pid["pid"]},
                    ).scalar_one_or_none()
                    if wait_type == "Lock":
                        observed_lock_wait = True
                        break
                    time_module.sleep(0.02)

            assert observed_lock_wait, "schedule write did not wait on the doctor lock"
            assert not future.done()
            confirmer.commit()
            updated = future.result(timeout=10)
            assert len(updated) == 1
    finally:
        confirmer.rollback()
        confirmer.close()

    with Session(engine) as verify:
        schedules = (
            verify.query(Schedule)
            .filter(Schedule.doctor_id == doctor_id)
            .order_by(Schedule.id)
            .all()
        )
        assert len(schedules) == 2
        assert schedules[0].active is False
        assert schedules[1].active is True
        assert schedules[1].start_time == time(10)


def test_telegram_schedule_update_waits_for_doctor_booking_lock(
    booking_request_pg_engine,
):
    """Telegram's alternate Schedule writer shares the booking row lock."""
    engine = booking_request_pg_engine
    unique = uuid.uuid4().hex[:12]
    weekday = (
        datetime.now(PUBLIC_BOOKING_TIMEZONE).date() + timedelta(days=2)
    ).weekday()
    with Session(engine) as setup:
        doctor_user = User(
            username=f"booking-telegram-lock-doctor-{unique}",
            hashed_password="synthetic-test-only",
            role="Doctor",
            is_active=True,
        )
        setup.add(doctor_user)
        setup.flush()
        doctor = Doctor(
            user_id=doctor_user.id,
            specialty="cardiology",
            active=True,
            show_on_website=True,
            slug=f"booking-telegram-lock-doctor-{unique}",
            bio_ru="Synthetic doctor.",
            bio_uz="Synthetic doctor.",
        )
        setup.add(doctor)
        setup.flush()
        schedule = Schedule(
            doctor_id=doctor.id,
            weekday=weekday,
            start_time=time(9),
            end_time=time(11),
            breaks=[],
            active=True,
        )
        setup.add(schedule)
        setup.commit()
        doctor_id = int(doctor.id)
        schedule_id = int(schedule.id)

    confirmer = Session(engine)
    locked_doctor = lock_doctor_for_slot_reservation(confirmer, doctor_id)
    assert locked_doctor is not None

    update_started = threading.Event()
    update_pid: dict[str, int] = {}

    def update_schedule():
        with Session(engine) as adapter_session:
            update_pid["pid"] = int(
                adapter_session.execute(text("SELECT pg_backend_pid()")).scalar_one()
            )
            adapter = TelegramStaffActionAdapterService(adapter_session)
            # Exercise the DB/lock boundary without requiring Telegram action
            # confirmation state or creating test audit events.
            adapter._confirmed = lambda **_kwargs: None
            adapter._completed = lambda **_kwargs: None
            update_started.set()
            return adapter.staff_change_doctor_schedule(
                schedule_id=schedule_id,
                actor_user_id=1,
                start_time=time(10),
            )

    try:
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(update_schedule)
            assert update_started.wait(timeout=5)
            deadline = time_module.monotonic() + 5
            observed_lock_wait = False
            with engine.connect() as observer:
                while time_module.monotonic() < deadline:
                    if future.done():
                        break
                    wait_type = observer.execute(
                        text(
                            "SELECT wait_event_type FROM pg_stat_activity "
                            "WHERE pid = :pid"
                        ),
                        {"pid": update_pid["pid"]},
                    ).scalar_one_or_none()
                    if wait_type == "Lock":
                        observed_lock_wait = True
                        break
                    time_module.sleep(0.02)

            assert observed_lock_wait, "Telegram schedule write skipped the doctor lock"
            assert not future.done()
            confirmer.commit()
            result = future.result(timeout=10)
            assert result["success"] is True
    finally:
        confirmer.rollback()
        confirmer.close()

    with Session(engine) as verify:
        updated = verify.query(Schedule).filter(Schedule.id == schedule_id).one()
        assert updated.start_time == time(10)
        assert updated.end_time == time(11)
