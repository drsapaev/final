from __future__ import annotations

from datetime import date
from types import SimpleNamespace

import pytest

from app.services.patient_appointments_api_service import PatientAppointmentsApiService


@pytest.mark.unit
class TestPatientAppointmentsApiService:
    def test_get_doctor_name_returns_user_full_name(self):
        class Repository:
            def get_doctor(self, doctor_id):
                return SimpleNamespace(user_id=7)

            def get_user(self, user_id):
                return SimpleNamespace(full_name="Dr. Test", username="doctor")

        service = PatientAppointmentsApiService(db=None, repository=Repository())
        assert service.get_doctor_name(doctor_id=10) == "Dr. Test"

    def test_cancel_appointment_marks_status_and_commits(self):
        state = {"committed": False}
        appointment = SimpleNamespace(status="scheduled", updated_at=None)

        class Repository:
            def commit(self):
                state["committed"] = True

        service = PatientAppointmentsApiService(db=None, repository=Repository())
        service.cancel_appointment(appointment)

        assert appointment.status == "cancelled"
        assert appointment.updated_at is not None
        assert state["committed"] is True

    def test_list_available_slots_skips_booked_slot(self):
        start_day = date(2026, 1, 5)

        class Repository:
            def list_active_schedules(self, doctor_id):
                return []

            def list_booked_appointments(self, *, doctor_id, start_date, end_date):
                return [SimpleNamespace(appointment_date=start_day, appointment_time="10:00")]

            def get_doctor(self, doctor_id):
                return None

            def get_user(self, user_id):
                return None

        service = PatientAppointmentsApiService(db=None, repository=Repository())
        slots = service.list_available_slots(
            appointment=SimpleNamespace(doctor_id=5),
            start_date=start_day,
            end_date=start_day,
        )

        times = [item["time"] for item in slots]
        assert "09:00" in times
        assert "10:00" not in times
