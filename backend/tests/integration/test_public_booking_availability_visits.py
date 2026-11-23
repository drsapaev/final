from __future__ import annotations

from datetime import date, time

from app.models.clinic import Schedule
from app.models.service import Service
from app.models.visit import Visit, VisitService
from app.repositories.public_booking_availability_repository import (
    PublicBookingAvailabilityRepository,
)
from app.services.public_booking_availability import BookingCalendar
from app.services.public_booking_availability_service import (
    PublicBookingAvailabilityService,
)

TARGET_DATE = date(2026, 10, 26)


class StubRepository:
    def __init__(self, visit_rows):
        self.visit_rows = visit_rows

    def list_active_schedules_for_weekday(self, *, doctor_id: int, weekday: int):
        return [(time(9), time(10), None)]

    def list_appointment_occupancy_for_day(self, *, doctor_id: int, target_date: date):
        return []

    def list_visit_occupancy_for_day(self, *, doctor_id: int, target_date: date):
        return self.visit_rows


def test_exact_visit_snapshot_blocks_only_overlapping_starts():
    service = PublicBookingAvailabilityService(
        StubRepository([(1, TARGET_DATE, "09:20", 1, 20)])  # type: ignore[arg-type]
    )

    starts = service.available_starts_for_day(
        doctor_id=1,
        target_date=TARGET_DATE,
        service_duration_minutes=20,
        calendar=BookingCalendar(confirmed_years=frozenset({TARGET_DATE.year})),
    )

    assert [value.strftime("%H:%M") for value in starts] == ["09:00", "09:40"]


def test_unknown_or_multiple_visit_services_close_the_day():
    calendar = BookingCalendar(confirmed_years=frozenset({TARGET_DATE.year}))
    unknown_service = PublicBookingAvailabilityService(
        StubRepository([(1, TARGET_DATE, "09:20", 1, None)])  # type: ignore[arg-type]
    )
    multiple_services = PublicBookingAvailabilityService(
        StubRepository(
            [
                (1, TARGET_DATE, "09:20", 1, 20),
                (1, TARGET_DATE, "09:20", 1, 30),
            ]
        )  # type: ignore[arg-type]
    )

    for service in (unknown_service, multiple_services):
        assert (
            service.available_starts_for_day(
                doctor_id=1,
                target_date=TARGET_DATE,
                service_duration_minutes=20,
                calendar=calendar,
            )
            == []
        )


def test_qr_live_visit_without_assigned_time_does_not_close_public_day(
    db_session, test_patient, test_doctor
):
    """QR queue presence is not a reservation of a scheduled clock hour."""
    from app.services.qr_queue import QRQueueService

    test_doctor.active = True
    test_doctor.show_on_website = True
    service = Service(
        name="Synthetic QR consultation",
        price=100000,
        duration_minutes=20,
        active=True,
    )
    db_session.add_all(
        [
            service,
            Schedule(
                doctor_id=test_doctor.id,
                weekday=TARGET_DATE.weekday(),
                start_time=time(9),
                end_time=time(10),
                active=True,
            ),
        ]
    )
    db_session.flush()

    visit = QRQueueService(db_session)._create_visit_for_qr(
        patient_id=test_patient.id,
        visit_date=TARGET_DATE,
        services=[
            {
                "service_id": service.id,
                "name": service.name,
                "quantity": 1,
                "price": 100000,
            }
        ],
        doctor_id=test_doctor.id,
    )
    db_session.flush()
    assert visit.visit_time is None

    repository = PublicBookingAvailabilityRepository(db_session)
    assert (
        repository.list_visit_occupancy_for_day(
            doctor_id=test_doctor.id,
            target_date=TARGET_DATE,
        )
        == []
    )

    starts = PublicBookingAvailabilityService(repository).available_starts_for_day(
        doctor_id=test_doctor.id,
        target_date=TARGET_DATE,
        service_duration_minutes=20,
        calendar=BookingCalendar(confirmed_years=frozenset({TARGET_DATE.year})),
    )
    assert [value.strftime("%H:%M") for value in starts] == [
        "09:00",
        "09:20",
        "09:40",
    ]


def test_repository_excludes_both_spellings_of_cancelled_visits(
    db_session, test_patient, test_doctor
):
    for status, minute in (
        ("open", "09:00"),
        ("canceled", "09:20"),
        ("cancelled", "09:40"),
    ):
        visit = Visit(
            patient_id=test_patient.id,
            doctor_id=test_doctor.id,
            visit_date=TARGET_DATE,
            visit_time=minute,
            status=status,
        )
        db_session.add(visit)
        db_session.flush()
        if status == "open":
            db_session.add(
                VisitService(
                    visit_id=visit.id,
                    service_id=77,
                    name="synthetic service",
                    qty=1,
                    duration_minutes_snapshot=20,
                )
            )
    db_session.flush()

    rows = PublicBookingAvailabilityRepository(db_session).list_visit_occupancy_for_day(
        doctor_id=test_doctor.id,
        target_date=TARGET_DATE,
    )

    assert len(rows) == 1
    assert rows[0][1:] == (TARGET_DATE, "09:00", 1, 20)
