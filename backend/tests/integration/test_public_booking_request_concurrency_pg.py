"""PostgreSQL concurrency regression for duplicate patient requests."""

from __future__ import annotations

import os
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, time, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session
from sqlalchemy.schema import CreateSchema, DropSchema

import app.db.base  # noqa: F401 - register all models before create_all
from app.db.base_class import Base
from app.api import deps
from app.main import app
from app.models.clinic import ClinicSettings, Doctor, Schedule
from app.models.patient import Patient
from app.models.public_booking_request import PublicBookingRequest
from app.models.service import Service
from app.models.user import User
from app.services.public_booking_availability import PUBLIC_BOOKING_TIMEZONE
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
