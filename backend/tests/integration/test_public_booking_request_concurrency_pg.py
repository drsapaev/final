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
from app.repositories.services_api_repository import ServicesApiRepository
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


@pytest.fixture
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

            create_calls = 0
            create_calls_lock = threading.Lock()
            second_create_started = threading.Event()

            def pause_first_create(*, db, obj_in, commit=True):
                nonlocal create_calls
                with create_calls_lock:
                    create_calls += 1
                    should_pause = create_calls == 1
                    if create_calls == 2:
                        second_create_started.set()
                if should_pause:
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
            second_service_entered = threading.Event()
            request_service = booking_request_service_module.PublicBookingRequestService
            original_confirm = request_service.confirm_for_staff

            def observe_second_service_entry(
                service, *, request_id, actor_user_id, expected_version
            ):
                if str(request_id) == requests[1]:
                    second_service_entered.set()
                return original_confirm(
                    service,
                    request_id=request_id,
                    actor_user_id=actor_user_id,
                    expected_version=expected_version,
                )

            monkeypatch.setattr(
                booking_request_service_module.PublicBookingRequestService,
                "confirm_for_staff",
                observe_second_service_entry,
            )

            def confirm(label: str, request_id: str):
                if label == "second":
                    second_confirmation_started.set()
                request_client = TestClient(app)
                try:
                    return request_client.post(
                        f"/api/v1/admin/public-booking-requests/{request_id}/confirm",
                        headers={"Authorization": f"Bearer {registrar_token}"},
                        json={"expected_version": 1},
                    )
                finally:
                    request_client.close()

            try:
                with ThreadPoolExecutor(max_workers=2) as executor:
                    first_future = executor.submit(confirm, "first", requests[0])
                    assert first_create_started.wait(timeout=5)
                    second_future = executor.submit(confirm, "second", requests[1])
                    assert second_confirmation_started.wait(timeout=5)
                    second_entered = second_service_entered.wait(timeout=5)
                    deadline = time_module.monotonic() + 5
                    observed_wait = False
                    activity_summary = []
                    with engine.connect() as observer:
                        while time_module.monotonic() < deadline:
                            if second_future.done():
                                break
                            activity = observer.execute(
                                text(
                                    "SELECT state, wait_event_type, wait_event "
                                    "FROM pg_stat_activity "
                                    "WHERE datname = current_database() "
                                    "AND pid <> pg_backend_pid() "
                                    "AND state = 'active' "
                                )
                            ).all()
                            activity_summary = [tuple(row) for row in activity]
                            if any(row[1] == "Lock" for row in activity_summary):
                                observed_wait = True
                                break
                            time_module.sleep(0.02)

                    second_was_pending = not second_future.done()
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
                    Appointment.appointment_time == "09:00",
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
            assert observed_wait, (
                "second confirmation did not wait on a PostgreSQL lock; "
                f"service_entered={second_entered}; "
                f"second_create_started={second_create_started.is_set()}; "
                f"second_pending={second_was_pending}; "
                f"active_activity={activity_summary}"
            )
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


def test_delete_cancels_linked_public_booking_appointment_and_keeps_link(
    booking_request_pg_engine,
):
    engine = booking_request_pg_engine
    unique = uuid.uuid4().hex[:12]
    with Session(engine) as setup:
        doctor_user = User(
            username=f"booking-delete-doctor-{unique}",
            hashed_password="synthetic-test-only",
            role="Doctor",
            is_active=True,
            full_name="Synthetic Doctor",
        )
        patient_user = User(
            username=f"booking-delete-patient-{unique}",
            hashed_password="synthetic-test-only",
            role="Patient",
            is_active=True,
            full_name="Synthetic Patient",
        )
        registrar = User(
            username=f"booking-delete-registrar-{unique}",
            hashed_password="synthetic-test-only",
            role="Registrar",
            is_active=True,
            full_name="Synthetic Registrar",
        )
        setup.add_all([doctor_user, patient_user, registrar])
        setup.flush()
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
            slug=f"booking-delete-doctor-{unique}",
            bio_ru="Synthetic cardiologist.",
            bio_uz="Synthetic cardiologist.",
        )
        service = Service(
            name="Synthetic consultation",
            name_uz="Synthetic consultation",
            slug=f"booking-delete-service-{unique}",
            duration_minutes=20,
            active=True,
            show_on_website=True,
            requires_doctor=True,
        )
        setup.add_all([patient, doctor, service])
        setup.flush()
        appointment_date = datetime.now(PUBLIC_BOOKING_TIMEZONE).date() + timedelta(
            days=2
        )
        linked_appointment = Appointment(
            patient_id=patient.id,
            doctor_id=doctor.id,
            appointment_date=appointment_date,
            appointment_time="09:00",
            status="pending",
        )
        unlinked_appointment = Appointment(
            patient_id=patient.id,
            doctor_id=doctor.id,
            appointment_date=appointment_date,
            appointment_time="09:20",
            status="pending",
        )
        setup.add_all([linked_appointment, unlinked_appointment])
        setup.flush()
        request = PublicBookingRequest(
            patient_id=patient.id,
            service_id=service.id,
            doctor_id=doctor.id,
            appointment_id=linked_appointment.id,
            appointment_date=appointment_date,
            appointment_time=time(9),
            status="confirmed",
            settings_version=1,
        )
        setup.add(request)
        setup.commit()
        linked_appointment_id = int(linked_appointment.id)
        unlinked_appointment_id = int(unlinked_appointment.id)
        request_id = request.id
        registrar_token = mint_access_token(registrar)

    previous_override = app.dependency_overrides.get(deps.get_db)

    def override_get_db():
        with Session(engine) as db:
            yield db

    app.dependency_overrides[deps.get_db] = override_get_db
    try:
        with TestClient(app) as client:
            headers = {"Authorization": f"Bearer {registrar_token}"}
            linked_response = client.delete(
                f"/api/v1/appointments/{linked_appointment_id}", headers=headers
            )
            unlinked_response = client.delete(
                f"/api/v1/appointments/{unlinked_appointment_id}", headers=headers
            )

        assert linked_response.status_code == 200, linked_response.text
        assert unlinked_response.status_code == 200, unlinked_response.text
        with Session(engine) as verify:
            linked = verify.get(Appointment, linked_appointment_id)
            unlinked = verify.get(Appointment, unlinked_appointment_id)
            stored_request = verify.get(PublicBookingRequest, request_id)
            assert linked is not None
            assert linked.status == "cancelled"
            assert unlinked is None
            assert stored_request is not None
            assert stored_request.status == "confirmed"
            assert stored_request.appointment_id == linked_appointment_id
    finally:
        if previous_override is None:
            app.dependency_overrides.pop(deps.get_db, None)
        else:
            app.dependency_overrides[deps.get_db] = previous_override


def test_staff_confirmation_waits_for_service_update_and_uses_new_duration(
    booking_request_pg_engine, monkeypatch
):
    engine = booking_request_pg_engine
    unique = uuid.uuid4().hex[:12]
    with Session(engine) as setup:
        doctor_user = User(
            username=f"booking-duration-doctor-{unique}",
            hashed_password="synthetic-test-only",
            role="Doctor",
            is_active=True,
            full_name="Synthetic Doctor",
        )
        patient_user = User(
            username=f"booking-duration-patient-{unique}",
            hashed_password="synthetic-test-only",
            role="Patient",
            is_active=True,
            full_name="Synthetic Patient",
        )
        registrar = User(
            username=f"booking-duration-registrar-{unique}",
            hashed_password="synthetic-test-only",
            role="Registrar",
            is_active=True,
            full_name="Synthetic Registrar",
        )
        setup.add_all([doctor_user, patient_user, registrar])
        setup.flush()
        department = Department(
            key=f"booking-duration-{unique}",
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
            slug=f"booking-duration-doctor-{unique}",
            bio_ru="Synthetic cardiologist.",
            bio_uz="Synthetic cardiologist.",
        )
        service = Service(
            name="Synthetic consultation",
            name_uz="Synthetic consultation",
            description_ru="Synthetic service description.",
            description_uz="Synthetic service description.",
            slug=f"booking-duration-service-{unique}",
            duration_minutes=20,
            active=True,
            show_on_website=True,
            requires_doctor=True,
        )
        patient = Patient(
            user_id=patient_user.id,
            first_name="Synthetic",
            last_name=f"Patient {unique}",
        )
        setup.add_all([doctor, service, patient])
        setup.flush()
        target_date = datetime.now(PUBLIC_BOOKING_TIMEZONE).date() + timedelta(days=2)
        setup.add_all(
            [
                Schedule(
                    doctor_id=doctor.id,
                    weekday=target_date.weekday(),
                    start_time=time(9),
                    end_time=time(10),
                    breaks=[],
                    active=True,
                ),
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
        service_id = int(service.id)
        doctor_slug = doctor.slug
        service_slug = service.slug
        patient_token = mint_access_token(patient_user)
        registrar_token = mint_access_token(registrar)

    previous_override = app.dependency_overrides.get(deps.get_db)

    def override_get_db():
        with Session(engine) as db:
            yield db

    app.dependency_overrides[deps.get_db] = override_get_db
    release_service_update = threading.Event()
    try:
        with TestClient(app) as client:
            created = client.post(
                PATIENT_REQUESTS,
                headers={
                    "Authorization": f"Bearer {patient_token}",
                    "Idempotency-Key": uuid.uuid4().hex,
                },
                json={
                    "service_slug": service_slug,
                    "doctor_slug": doctor_slug,
                    "appointment_date": target_date.isoformat(),
                    "appointment_time": "09:40",
                    "expected_settings_version": 1,
                },
            )
        assert created.status_code == 201, created.text
        request_id = created.json()["id"]

        service_update_locked = threading.Event()
        confirmation_service_lock_attempted = threading.Event()
        confirmation_pid: list[int] = []
        original_lock_service = ServicesApiRepository.get_service_for_update

        def observe_confirmation_service_lock(repository, locked_service_id):
            if locked_service_id == service_id:
                pid = repository.db.execute(
                    text("SELECT pg_backend_pid()")
                ).scalar_one()
                confirmation_pid.append(int(pid))
                confirmation_service_lock_attempted.set()
            return original_lock_service(repository, locked_service_id)

        monkeypatch.setattr(
            ServicesApiRepository,
            "get_service_for_update",
            observe_confirmation_service_lock,
        )

        def update_service_and_hold_lock():
            with Session(engine) as update_db:
                locked_service = (
                    update_db.query(Service)
                    .filter(Service.id == service_id)
                    .with_for_update()
                    .populate_existing()
                    .one()
                )
                locked_service.duration_minutes = 30
                service_update_locked.set()
                if not release_service_update.wait(timeout=10):
                    raise TimeoutError("test did not release service update lock")
                update_db.commit()

        def confirm_request():
            with TestClient(app) as client:
                return client.post(
                    f"/api/v1/admin/public-booking-requests/{request_id}/confirm",
                    headers={"Authorization": f"Bearer {registrar_token}"},
                    json={"expected_version": 1},
                )

        observed_service_lock_wait = False
        with ThreadPoolExecutor(max_workers=2) as executor:
            update_future = executor.submit(update_service_and_hold_lock)
            confirmation_future = None
            try:
                assert service_update_locked.wait(timeout=5)
                confirmation_future = executor.submit(confirm_request)
                assert confirmation_service_lock_attempted.wait(timeout=5)
                deadline = time_module.monotonic() + 5
                with engine.connect() as observer:
                    while time_module.monotonic() < deadline:
                        wait_type = observer.execute(
                            text(
                                "SELECT wait_event_type FROM pg_stat_activity "
                                "WHERE pid = :pid"
                            ),
                            {"pid": confirmation_pid[0]},
                        ).scalar_one_or_none()
                        if wait_type == "Lock":
                            observed_service_lock_wait = True
                            break
                        if confirmation_future.done():
                            break
                        time_module.sleep(0.05)
            finally:
                release_service_update.set()

            update_future.result(timeout=10)
            assert confirmation_future is not None
            response = confirmation_future.result(timeout=10)

        if not observed_service_lock_wait:
            raise AssertionError("confirmation did not wait on the Service row")
        assert response.status_code == 200, response.text
        assert response.json()["status"] == "needs_new_time"
        with Session(engine) as verify:
            request = verify.get(PublicBookingRequest, uuid.UUID(request_id))
            appointments = verify.query(Appointment).all()
            current_service = verify.get(Service, service_id)
            assert request is not None
            assert request.status == "needs_new_time"
            assert request.appointment_id is None
            assert appointments == []
            assert current_service is not None
            assert current_service.duration_minutes == 30
    finally:
        release_service_update.set()
        if previous_override is None:
            app.dependency_overrides.pop(deps.get_db, None)
        else:
            app.dependency_overrides[deps.get_db] = previous_override
