from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest

from app.api.v1.endpoints.registrar_integration import _serialize_registrar_datetime
from app.models.appointment import Appointment
from app.models.online_queue import DailyQueue, OnlineQueueEntry
from app.models.payment import Payment


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

        payment = Payment(
            visit_id=test_visit.id,
            amount=Decimal("150000.00"),
            currency="UZS",
            status="paid",
            method="cash",
        )
        db_session.add(payment)
        db_session.commit()

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
        assert appointment_row["visit_type"] == "none"

    def test_today_queues_serializes_queue_time_and_created_at(
        self,
        client,
        db_session,
        auth_headers,
        test_patient,
        test_doctor,
    ):
        queue = DailyQueue(
            day=date.today(),
            specialist_id=test_doctor.id,
            queue_tag="cardiology_common",
            active=True,
        )
        db_session.add(queue)
        db_session.commit()
        db_session.refresh(queue)

        queue_time = datetime(2026, 4, 16, 9, 30, tzinfo=ZoneInfo("Asia/Tashkent"))
        created_at = datetime(2026, 4, 16, 9, 31, tzinfo=ZoneInfo("Asia/Tashkent"))

        entry = OnlineQueueEntry(
            queue_id=queue.id,
            number=1,
            patient_id=test_patient.id,
            patient_name=test_patient.short_name(),
            phone=test_patient.phone,
            visit_id=None,
            source="desk",
            status="waiting",
            queue_time=queue_time,
            created_at=created_at,
        )
        db_session.add(entry)
        db_session.commit()
        db_session.refresh(entry)

        response = client.get(
            f"/api/v1/registrar/queues/today?target_date={date.today().isoformat()}",
            headers=auth_headers,
        )

        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload["date"] == date.today().isoformat()

        found_entry = None
        for queue_payload in payload["queues"]:
            for queue_entry_payload in queue_payload["entries"]:
                if queue_entry_payload.get("id") == entry.id:
                    found_entry = queue_entry_payload
                    break
            if found_entry:
                break

        assert found_entry is not None
        assert found_entry["id"] == entry.id
        assert found_entry["queue_time"] == _serialize_registrar_datetime(entry.queue_time)
        assert found_entry["created_at"] == _serialize_registrar_datetime(entry.created_at)
