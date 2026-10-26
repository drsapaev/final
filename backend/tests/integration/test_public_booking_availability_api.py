"""Public read-only booking availability contract and fail-closed behavior."""

from datetime import UTC, datetime, time, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.appointment import Appointment
from app.models.clinic import ClinicSettings, Doctor, Schedule
from app.models.online_queue import DailyQueue, QueueResource
from app.models.service import Service
from app.models.user import User
from app.services.public_booking_availability import PUBLIC_BOOKING_TIMEZONE

BASE = "/api/v1/public-site/availability"


def _configured_public_booking(
    db_session: Session, *, target_date, enabled: bool = True, confirmed: bool = True
):
    doctor_user = User(
        username="public_availability_doctor",
        hashed_password="not-used-in-this-test",
        role="Doctor",
        is_active=True,
        full_name="Test Doctor",
    )
    db_session.add(doctor_user)
    db_session.flush()
    doctor = Doctor(
        user_id=doctor_user.id,
        specialty="cardiology",
        active=True,
        show_on_website=True,
        slug="test-doctor",
        bio_ru="Врач-кардиолог",
        bio_uz="Kardiolog shifokor",
    )
    service = Service(
        name="Cardiology consultation",
        name_uz="Kardiolog maslahati",
        description_ru="Приём врача-кардиолога.",
        description_uz="Kardiolog shifokor qabuli.",
        slug="cardiology-consultation",
        duration_minutes=20,
        active=True,
        show_on_website=True,
        requires_doctor=True,
    )
    db_session.add_all([doctor, service])
    db_session.flush()
    db_session.add(
        Schedule(
            doctor_id=doctor.id,
            weekday=target_date.weekday(),
            start_time=time(9),
            end_time=time(11),
            breaks=[{"start": "09:40", "end": "10:00"}],
            active=True,
        )
    )
    db_session.add_all(
        [
            ClinicSettings(
                key="public_booking_settings",
                category="booking_settings",
                value={
                    "version": 1,
                    "is_enabled": enabled,
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
                    "is_confirmed": confirmed,
                    "holidays": [],
                    "confirmed_at": (
                        datetime.now(UTC).isoformat() if confirmed else None
                    ),
                    "confirmed_by": doctor_user.id if confirmed else None,
                },
                updated_by=doctor_user.id,
            ),
        ]
    )
    db_session.flush()
    return service, doctor, doctor_user


def _availability_url(service_slug: str, doctor_slug: str, target_date) -> str:
    return (
        f"{BASE}?service_slug={service_slug}&doctor_slug={doctor_slug}"
        f"&date={target_date.isoformat()}"
    )


@pytest.mark.integration
def test_public_availability_returns_local_candidate_times_without_reserving(
    client: TestClient, db_session: Session, test_patient
) -> None:
    target_date = datetime.now(PUBLIC_BOOKING_TIMEZONE).date() + timedelta(days=2)
    _, doctor, _ = _configured_public_booking(db_session, target_date=target_date)

    response = client.get(
        _availability_url("cardiology-consultation", doctor.slug, target_date)
    )

    assert response.status_code == 200, response.text
    assert response.headers["cache-control"] == "no-store"
    assert response.json() == {
        "date": target_date.isoformat(),
        "timezone": "Asia/Tashkent",
        "settings_version": 1,
        "slots": ["09:00:00", "09:20:00", "10:00:00", "10:20:00", "10:40:00"],
    }
    assert set(response.json()) == {
        "date",
        "timezone",
        "settings_version",
        "slots",
    }

    # An existing non-cancelled appointment with unknown duration closes that
    # doctor/date; the read endpoint neither creates nor reserves appointments.
    db_session.add(
        Appointment(
            patient_id=test_patient.id,
            doctor_id=doctor.id,
            appointment_date=target_date,
            appointment_time="09:00",
            duration_minutes_snapshot=None,
            status="scheduled",
        )
    )
    db_session.flush()
    blocked = client.get(
        _availability_url("cardiology-consultation", doctor.slug, target_date)
    )
    assert blocked.status_code == 200
    assert blocked.json()["slots"] == []
    assert blocked.headers["cache-control"] == "no-store"
    assert db_session.query(Appointment).count() == 1


@pytest.mark.integration
@pytest.mark.parametrize(
    ("enabled", "confirmed"),
    [(False, True), (True, False)],
)
def test_public_availability_returns_no_slots_when_booking_is_off_or_calendar_unconfirmed(
    client: TestClient,
    db_session: Session,
    enabled: bool,
    confirmed: bool,
) -> None:
    target_date = datetime.now(PUBLIC_BOOKING_TIMEZONE).date() + timedelta(days=2)
    _, doctor, _ = _configured_public_booking(
        db_session,
        target_date=target_date,
        enabled=enabled,
        confirmed=confirmed,
    )

    response = client.get(
        _availability_url("cardiology-consultation", doctor.slug, target_date)
    )

    assert response.status_code == 200, response.text
    assert response.json()["slots"] == []
    assert response.headers["cache-control"] == "no-store"


@pytest.mark.integration
def test_public_availability_hides_unknown_pair_with_no_store(
    client: TestClient, db_session: Session
) -> None:
    target_date = datetime.now(PUBLIC_BOOKING_TIMEZONE).date() + timedelta(days=2)
    _configured_public_booking(db_session, target_date=target_date)

    response = client.get(
        _availability_url("cardiology-consultation", "unknown-doctor", target_date)
    )

    assert response.status_code == 404
    assert response.json() == {"detail": {"code": "public_content_not_found"}}
    assert response.headers["cache-control"] == "no-store"


@pytest.mark.integration
def test_public_availability_hides_doctor_pair_when_day_is_resource_routed(
    client: TestClient, db_session: Session
) -> None:
    target_date = datetime.now(PUBLIC_BOOKING_TIMEZONE).date() + timedelta(days=2)
    service, doctor, _ = _configured_public_booking(db_session, target_date=target_date)
    resource = QueueResource(
        code="public_booking_resource_test",
        queue_tag="public_booking_resource_test",
        display_name="Public booking test resource",
        active=False,
    )
    db_session.add(resource)
    db_session.flush()
    service.queue_tag = resource.queue_tag
    db_session.add(
        DailyQueue(
            day=target_date,
            specialist_id=None,
            queue_resource_id=resource.id,
            queue_tag=resource.queue_tag,
            active=True,
        )
    )
    db_session.flush()

    response = client.get(
        _availability_url("cardiology-consultation", doctor.slug, target_date)
    )

    assert response.status_code == 404
    assert response.json() == {"detail": {"code": "public_content_not_found"}}
    assert response.headers["cache-control"] == "no-store"


@pytest.mark.integration
def test_public_availability_returns_safe_no_store_error_for_invalid_settings(
    client: TestClient, db_session: Session
) -> None:
    target_date = datetime.now(PUBLIC_BOOKING_TIMEZONE).date() + timedelta(days=2)
    _configured_public_booking(db_session, target_date=target_date)
    settings = (
        db_session.query(ClinicSettings)
        .filter(ClinicSettings.key == "public_booking_settings")
        .one()
    )
    settings.value = {"version": 1, "is_enabled": True}
    db_session.flush()

    response = client.get(
        _availability_url("cardiology-consultation", "test-doctor", target_date)
    )

    assert response.status_code == 503
    assert response.json() == {"detail": {"code": "public_booking_unavailable"}}
    assert response.headers["cache-control"] == "no-store"
