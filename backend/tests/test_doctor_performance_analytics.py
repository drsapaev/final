"""
Regression (Sentry PYTHON-FASTAPI-12): get_doctor_performance queried
non-existent User.fio / User.specialty and joined users.id to
appointments.doctor_id even though that FK points to doctors.id — the
endpoint always returned {"error": "type object 'User' has no attribute
'fio'"}. The fix joins Doctor (specialty) -> User (full_name) through the
real FKs; this test pins the payload.
"""

from datetime import UTC, datetime, timedelta

from app.models.appointment import Appointment
from app.models.clinic import Doctor
from app.models.patient import Patient
from app.models.user import User
from app.services.advanced_analytics import AdvancedAnalyticsService


def test_get_doctor_performance_uses_doctor_join(db_session):
    user = User(
        username="perf_doc_user",
        email="perf_doc@test.com",
        full_name="Perf Doctor",
        hashed_password="not-verified-here",
        role="Doctor",
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    doctor = Doctor(
        user_id=user.id,
        specialty="cardiology",
        start_number_online=1,
        max_online_per_day=15,
    )
    db_session.add(doctor)
    db_session.commit()
    db_session.refresh(doctor)

    patient = Patient(last_name="Testova", first_name="Testa")
    db_session.add(patient)
    db_session.commit()
    db_session.refresh(patient)

    today = datetime.now(UTC).date()
    db_session.add(
        Appointment(
            patient_id=patient.id,
            doctor_id=doctor.id,
            appointment_date=today,
            status="completed",
        )
    )
    db_session.add(
        Appointment(
            patient_id=patient.id,
            doctor_id=doctor.id,
            appointment_date=today,
            status="cancelled",
        )
    )
    db_session.commit()

    now = datetime.now(UTC)
    result = AdvancedAnalyticsService().get_doctor_performance(
        db_session, now - timedelta(days=1), now + timedelta(days=1)
    )

    # Pre-fix the service returned {"error": "type object 'User' has no attribute 'fio'"}
    assert "error" not in result, result.get("error")
    rows = result["doctor_performance"]
    assert len(rows) == 1

    row = rows[0]
    assert row["doctor_id"] == doctor.id
    assert row["doctor_name"] == "Perf Doctor"
    assert row["specialty"] == "cardiology"
    assert row["total_appointments"] == 2
    assert row["completed_appointments"] == 1
    assert row["cancelled_appointments"] == 1
