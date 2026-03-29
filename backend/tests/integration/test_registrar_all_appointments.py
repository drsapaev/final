from __future__ import annotations

from datetime import date

import pytest

from app.models.appointment import Appointment


@pytest.mark.integration
class TestRegistrarAllAppointments:
    def test_date_filters_accept_iso_strings_for_appointments_and_visits(
        self,
        client,
        db_session,
        auth_headers,
        test_patient,
        test_doctor,
        test_visit,
    ):
        appointment = Appointment(
            patient_id=test_patient.id,
            doctor_id=test_doctor.id,
            appointment_date=date.today(),
            appointment_time="11:00",
            status="scheduled",
            visit_type="paid",
            payment_type="cash",
            services=[],
            notes="SSOT registrar date filter regression",
        )
        db_session.add(appointment)
        db_session.commit()
        db_session.refresh(appointment)

        today = date.today().isoformat()
        response = client.get(
            f"/api/v1/registrar/all-appointments?date_from={today}&date_to={today}&limit=50",
            headers=auth_headers,
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["total"] >= 2

        items = payload["data"]
        appointment_row = next(
            (item for item in items if item.get("appointment_id") == appointment.id),
            None,
        )
        visit_row = next(
            (item for item in items if item.get("visit_id") == test_visit.id),
            None,
        )

        assert appointment_row is not None
        assert appointment_row["patient_id"] == test_patient.id
        assert appointment_row["appointment_date"] == today

        assert visit_row is not None
        assert visit_row["patient_id"] == test_patient.id
        assert visit_row["appointment_date"] == today

    def test_search_uses_patient_name_and_marks_paid_status(
        self,
        client,
        db_session,
        auth_headers,
        test_patient,
        test_doctor,
        test_visit,
    ):
        appointment = Appointment(
            patient_id=test_patient.id,
            doctor_id=test_doctor.id,
            appointment_date=date.today(),
            appointment_time="12:30",
            status="scheduled",
            visit_type="paid",
            payment_type="cash",
            services=[],
            notes="SSOT registrar paid-search regression",
        )
        db_session.add(appointment)
        db_session.commit()
        db_session.refresh(appointment)

        response = client.get(
            "/api/v1/registrar/all-appointments"
            f"?search={test_patient.short_name()}&limit=50&offset=0",
            headers=auth_headers,
        )

        assert response.status_code == 200
        payload = response.json()
        items = payload["data"]
        appointment_row = next(
            (item for item in items if item.get("appointment_id") == appointment.id),
            None,
        )

        assert appointment_row is not None
        assert appointment_row["patient_id"] == test_patient.id
        assert appointment_row["patient_fio"] == test_patient.short_name()
        assert appointment_row["payment_status"] == "paid"
        assert appointment_row["visit_type"] == "paid"
