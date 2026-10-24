from __future__ import annotations

from datetime import date, time

from app.models.appointment import Appointment
from app.models.clinic import Doctor, Schedule
from app.models.user import User
from app.repositories.public_booking_availability_repository import (
    PublicBookingAvailabilityRepository,
)


def test_repository_reads_only_active_profile_shift_and_minimal_day_occupancy(
    db_session, test_doctor, test_doctor_user, test_patient
):
    test_doctor.show_on_website = True
    db_session.flush()
    target_date = date(2026, 10, 26)
    other_doctor = Doctor(user_id=test_doctor_user.id, specialty="Тест")
    db_session.add(other_doctor)
    db_session.flush()

    db_session.add_all(
        [
            Schedule(
                doctor_id=test_doctor.id,
                weekday=target_date.weekday(),
                start_time=time(9, 10),
                end_time=time(17),
                breaks=[{"start": "12:00", "end": "13:00"}],
                active=True,
            ),
            Schedule(
                doctor_id=test_doctor.id,
                weekday=target_date.weekday(),
                start_time=time(10),
                end_time=time(11),
                active=False,
            ),
            Schedule(
                doctor_id=other_doctor.id,
                weekday=target_date.weekday(),
                start_time=time(8),
                end_time=time(9),
                active=True,
            ),
            Appointment(
                patient_id=test_patient.id,
                doctor_id=test_doctor.id,
                appointment_date=target_date,
                appointment_time="09:30",
                duration_minutes_snapshot=40,
                status="scheduled",
                notes="must not be selected by the availability query",
            ),
            Appointment(
                patient_id=test_patient.id,
                doctor_id=test_doctor.id,
                appointment_date=date(2026, 10, 27),
                appointment_time="09:30",
                duration_minutes_snapshot=20,
                status="scheduled",
            ),
            Appointment(
                patient_id=test_patient.id,
                doctor_id=other_doctor.id,
                appointment_date=target_date,
                appointment_time="09:30",
                duration_minutes_snapshot=20,
                status="scheduled",
            ),
        ]
    )
    db_session.flush()

    repository = PublicBookingAvailabilityRepository(db_session)

    schedules = repository.list_active_schedules_for_weekday(
        doctor_id=test_doctor.id,
        weekday=target_date.weekday(),
    )
    appointments = repository.list_appointment_occupancy_for_day(
        doctor_id=test_doctor.id,
        target_date=target_date,
    )

    assert schedules == [(time(9, 10), time(17), [{"start": "12:00", "end": "13:00"}])]
    assert appointments == [(target_date, "09:30", 40, "scheduled")]


def test_repository_hides_shifts_for_ineligible_public_doctor(db_session, test_doctor):
    target_date = date(2026, 10, 26)
    weekday = target_date.weekday()
    test_doctor.show_on_website = True
    db_session.add(
        Schedule(
            doctor_id=test_doctor.id,
            weekday=weekday,
            start_time=time(9),
            end_time=time(12),
            active=True,
        )
    )
    db_session.flush()

    repository = PublicBookingAvailabilityRepository(db_session)
    assert repository.list_active_schedules_for_weekday(
        doctor_id=test_doctor.id, weekday=weekday
    ) == [(time(9), time(12), None)]

    test_doctor.active = False
    db_session.flush()
    assert (
        repository.list_active_schedules_for_weekday(
            doctor_id=test_doctor.id, weekday=weekday
        )
        == []
    )

    test_doctor.active = True
    test_doctor.show_on_website = False
    db_session.flush()
    assert (
        repository.list_active_schedules_for_weekday(
            doctor_id=test_doctor.id, weekday=weekday
        )
        == []
    )

    test_doctor.show_on_website = True
    doctor_user = db_session.get(User, test_doctor.user_id)
    assert doctor_user is not None
    doctor_user.is_active = False
    db_session.flush()
    assert (
        repository.list_active_schedules_for_weekday(
            doctor_id=test_doctor.id, weekday=weekday
        )
        == []
    )

    test_doctor.user_id = None
    db_session.flush()
    assert (
        repository.list_active_schedules_for_weekday(
            doctor_id=test_doctor.id, weekday=weekday
        )
        == []
    )
