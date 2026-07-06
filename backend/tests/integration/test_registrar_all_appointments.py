from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest

from app.api.v1.endpoints.registrar_integration import _registrar_available_actions
from app.api.v1.endpoints.registrar_integration import _serialize_registrar_datetime
from app.models.appointment import Appointment
from app.models.lab import LabReportInstance
from app.models.online_queue import DailyQueue
from app.models.online_queue import OnlineQueueEntry
from app.models.patient import Patient
from app.models.payment import Payment
from app.models.visit import Visit
from app.models.visit import VisitService


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
            birth_year=1985,
            address="Clinic Street 1",
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
        assert found_entry["canonical_record_id"] == entry.id
        assert found_entry["record_kind"] == "online_queue"
        assert found_entry["queue_entry_id"] == entry.id
        assert found_entry["appointment_id"] is None
        assert found_entry["source_kind"] == "desk"
        assert found_entry["canonical_status"] == "waiting"
        assert found_entry["queue_status"] == "waiting"
        assert found_entry["queue_position"] == entry.number
        assert found_entry["can_mark_paid"] is True
        assert found_entry["can_start_visit"] is False
        assert found_entry["can_cancel"] is True
        assert found_entry["can_print_ticket"] is True
        assert found_entry["can_complete"] is False
        assert set(found_entry["available_actions"]) == {
            "mark_paid",
            "print_ticket",
            "cancel",
        }
        assert found_entry["can_view_emr"] is False
        assert found_entry["can_schedule_next"] is False
        assert found_entry["queue_time"] == _serialize_registrar_datetime(entry.queue_time)
        assert found_entry["created_at"] == _serialize_registrar_datetime(entry.created_at)
        expected_changed_at = _serialize_registrar_datetime(entry.updated_at or entry.created_at)
        assert found_entry["updated_at"] == expected_changed_at
        assert found_entry["last_changed_at"] == expected_changed_at
        assert found_entry["display_time_kind"] == "queue_time"
        assert found_entry["timezone"] == "Asia/Tashkent"
        assert found_entry["patient_name"] == test_patient.short_name()
        assert found_entry["phone"] == test_patient.phone
        assert found_entry["patient_birth_year"] == 1985
        assert found_entry["address"] == "Clinic Street 1"

    def test_today_queues_appointment_does_not_inherit_unrelated_patient_queue_time(
        self,
        client,
        db_session,
        auth_headers,
        test_patient,
        test_doctor,
    ):
        old_queue = DailyQueue(
            day=date.today() - timedelta(days=1),
            specialist_id=test_doctor.id,
            queue_tag="cardiology_common",
            active=True,
        )
        db_session.add(old_queue)
        db_session.flush()

        unrelated_queue_time = datetime(
            2026, 4, 15, 8, 0, tzinfo=ZoneInfo("Asia/Tashkent")
        )
        unrelated_entry = OnlineQueueEntry(
            queue_id=old_queue.id,
            number=77,
            patient_id=test_patient.id,
            patient_name=test_patient.short_name(),
            phone=test_patient.phone,
            visit_id=None,
            source="desk",
            status="waiting",
            queue_time=unrelated_queue_time,
            created_at=datetime(
                2026, 4, 16, 12, 0, tzinfo=ZoneInfo("Asia/Tashkent")
            ),
        )
        appointment_created_at = datetime(
            2026, 4, 16, 10, 0, tzinfo=ZoneInfo("Asia/Tashkent")
        )
        appointment = Appointment(
            patient_id=test_patient.id,
            doctor_id=test_doctor.id,
            appointment_date=date.today(),
            appointment_time="11:00",
            status="scheduled",
            visit_type="paid",
            payment_type="cash",
            services=[],
            notes="same patient but unrelated queue entry from another day",
            created_at=appointment_created_at,
        )
        db_session.add_all([unrelated_entry, appointment])
        db_session.commit()
        db_session.refresh(appointment)

        response = client.get(
            f"/api/v1/registrar/queues/today?target_date={date.today().isoformat()}",
            headers=auth_headers,
        )

        assert response.status_code == 200, response.text
        payload = response.json()
        appointment_row = next(
            entry
            for queue in payload["queues"]
            for entry in queue["entries"]
            if entry["record_kind"] == "appointment" and entry["id"] == appointment.id
        )

        assert appointment_row["number"] != unrelated_entry.number
        assert appointment_row["queue_position"] != unrelated_entry.number
        assert appointment_row["queue_time"] != _serialize_registrar_datetime(
            unrelated_queue_time
        )
        assert appointment_row["queue_time"] == appointment_row["created_at"]

    def test_today_queues_visit_rows_do_not_expose_fuzzy_appointment_id(
        self,
        client,
        db_session,
        auth_headers,
        test_patient,
        test_doctor,
        test_service,
    ):
        visit = Visit(
            patient_id=test_patient.id,
            doctor_id=test_doctor.id,
            visit_date=date.today(),
            visit_time="10:00",
            status="waiting",
            discount_mode="none",
            department="cardiology",
            source="desk",
        )
        unrelated_appointment = Appointment(
            patient_id=test_patient.id,
            doctor_id=test_doctor.id,
            appointment_date=date.today(),
            appointment_time="11:00",
            status="scheduled",
            visit_type="paid",
            payment_type="cash",
            services=[],
            notes="same patient/date/doctor but not linked to the visit",
        )
        db_session.add_all([visit, unrelated_appointment])
        db_session.flush()
        visit_service = VisitService(
            visit_id=visit.id,
            service_id=test_service.id,
            code=test_service.code,
            name=test_service.name,
            qty=1,
            price=test_service.price,
            currency="UZS",
        )
        db_session.add(visit_service)
        db_session.commit()
        db_session.refresh(visit)
        db_session.refresh(unrelated_appointment)

        response = client.get(
            f"/api/v1/registrar/queues/today?target_date={date.today().isoformat()}",
            headers=auth_headers,
        )

        assert response.status_code == 200, response.text
        payload = response.json()
        found_visit = next(
            entry
            for queue_payload in payload["queues"]
            for entry in queue_payload["entries"]
            if entry.get("record_kind") == "visit" and entry.get("id") == visit.id
        )

        assert found_visit["visit_id"] == visit.id
        assert found_visit["appointment_id"] is None

    def test_today_queues_hides_canceled_visit_and_appointment_rows(
        self,
        client,
        db_session,
        auth_headers,
        test_patient,
        test_doctor,
        test_service,
    ):
        canceled_visit = Visit(
            patient_id=test_patient.id,
            doctor_id=test_doctor.id,
            visit_date=date.today(),
            visit_time="10:00",
            status="canceled",
            discount_mode="none",
            department="cardiology",
            source="desk",
        )
        canceled_appointment = Appointment(
            patient_id=test_patient.id,
            doctor_id=test_doctor.id,
            appointment_date=date.today(),
            appointment_time="11:00",
            status="cancelled",
            visit_type="paid",
            payment_type="cash",
            services=[],
        )
        db_session.add_all([canceled_visit, canceled_appointment])
        db_session.flush()
        db_session.add(
            VisitService(
                visit_id=canceled_visit.id,
                service_id=test_service.id,
                code=test_service.code,
                name=test_service.name,
                qty=1,
                price=test_service.price,
                currency="UZS",
            )
        )
        db_session.commit()

        response = client.get(
            f"/api/v1/registrar/queues/today?target_date={date.today().isoformat()}",
            headers=auth_headers,
        )

        assert response.status_code == 200, response.text
        payload = response.json()
        entries = [
            entry for queue_payload in payload["queues"] for entry in queue_payload["entries"]
        ]

        assert all(
            not (
                entry.get("record_kind") == "visit"
                and entry.get("visit_id") == canceled_visit.id
            )
            for entry in entries
        )
        assert all(
            not (
                entry.get("record_kind") == "appointment"
                and entry.get("appointment_id") == canceled_appointment.id
            )
            for entry in entries
        )

    def test_today_queues_visit_ignores_other_patient_queue_entry_with_same_visit_id(
        self,
        client,
        db_session,
        auth_headers,
        test_patient,
        test_doctor,
        test_service,
    ):
        other_patient = Patient(
            first_name="Other",
            last_name="QueueOwner",
            phone="+998901119091",
        )
        queue = DailyQueue(
            day=date.today(),
            specialist_id=test_doctor.id,
            queue_tag="cardiology_common",
            active=True,
        )
        visit = Visit(
            patient_id=test_patient.id,
            doctor_id=test_doctor.id,
            visit_date=date.today(),
            visit_time="10:30",
            status="waiting",
            discount_mode="none",
            department="cardiology",
            source="desk",
        )
        db_session.add_all([other_patient, queue, visit])
        db_session.flush()

        visit_service = VisitService(
            visit_id=visit.id,
            service_id=test_service.id,
            code=test_service.code,
            name=test_service.name,
            qty=1,
            price=test_service.price,
            currency="UZS",
        )
        stale_entry = OnlineQueueEntry(
            queue_id=queue.id,
            number=88,
            patient_id=other_patient.id,
            patient_name=other_patient.short_name(),
            phone=other_patient.phone,
            visit_id=visit.id,
            source="online",
            status="waiting",
            queue_time=datetime(2026, 4, 16, 8, 0, tzinfo=ZoneInfo("Asia/Tashkent")),
        )
        db_session.add_all([visit_service, stale_entry])
        db_session.commit()
        db_session.refresh(visit)
        db_session.refresh(stale_entry)

        response = client.get(
            f"/api/v1/registrar/queues/today?target_date={date.today().isoformat()}",
            headers=auth_headers,
        )

        assert response.status_code == 200, response.text
        payload = response.json()
        entries = [
            entry for queue_payload in payload["queues"] for entry in queue_payload["entries"]
        ]
        found_visit = next(
            (
                entry
                for entry in entries
                if entry.get("record_kind") == "visit"
                and entry.get("visit_id") == visit.id
            ),
            None,
        )

        assert found_visit is not None
        assert found_visit["patient_id"] == test_patient.id
        assert found_visit["queue_entry_id"] is None
        assert found_visit["number"] != stale_entry.number
        assert all(entry.get("queue_entry_id") != stale_entry.id for entry in entries)
        assert all(
            not (
                entry.get("record_kind") == "online_queue"
                and entry.get("id") == stale_entry.id
            )
            for entry in entries
        )

    def test_today_queues_secondary_doctor_actions_are_backend_owned(self):
        user = type("UserStub", (), {"role": "cardio", "roles": []})()

        actions = _registrar_available_actions(
            user=user,
            payment_status="paid",
            queue_status="served",
            visit_id=123,
            patient_id=456,
        )

        assert "view_emr" in actions
        assert "schedule_next" in actions

        waiting_actions = _registrar_available_actions(
            user=user,
            payment_status="paid",
            queue_status="waiting",
            visit_id=123,
            patient_id=456,
        )
        assert "view_emr" not in waiting_actions
        assert "schedule_next" not in waiting_actions

        registrar_actions = _registrar_available_actions(
            user=type("UserStub", (), {"role": "registrar", "roles": []})(),
            payment_status="paid",
            queue_status="served",
            visit_id=123,
            patient_id=456,
        )
        assert "view_emr" not in registrar_actions
        assert "schedule_next" not in registrar_actions

    def test_today_queues_department_filter_limits_lab_rows(
        self,
        client,
        db_session,
        auth_headers,
        test_patient,
        test_doctor,
    ):
        cardio_queue = DailyQueue(
            day=date.today(),
            specialist_id=test_doctor.id,
            queue_tag="cardiology",
            active=True,
        )
        lab_queue = DailyQueue(
            day=date.today(),
            specialist_id=test_doctor.id,
            queue_tag="lab",
            active=True,
        )
        db_session.add_all([cardio_queue, lab_queue])
        db_session.commit()
        db_session.refresh(cardio_queue)
        db_session.refresh(lab_queue)

        cardio_entry = OnlineQueueEntry(
            queue_id=cardio_queue.id,
            number=1,
            patient_id=test_patient.id,
            patient_name=test_patient.short_name(),
            phone=test_patient.phone,
            source="desk",
            status="waiting",
        )
        lab_entry = OnlineQueueEntry(
            queue_id=lab_queue.id,
            number=1,
            patient_id=test_patient.id,
            patient_name=test_patient.short_name(),
            phone=test_patient.phone,
            source="desk",
            status="waiting",
        )
        db_session.add_all([cardio_entry, lab_entry])
        db_session.commit()

        response = client.get(
            "/api/v1/registrar/queues/today?department=lab",
            headers=auth_headers,
        )

        assert response.status_code == 200, response.text
        payload = response.json()
        specialties = {queue["specialty"] for queue in payload["queues"]}
        entry_ids = {
            entry["id"]
            for queue in payload["queues"]
            for entry in queue["entries"]
        }

        assert specialties == {"laboratory"}
        assert lab_entry.id in entry_ids
        assert cardio_entry.id not in entry_ids

    def test_today_queues_lab_rows_include_latest_lab_report_summary(
        self,
        client,
        db_session,
        auth_headers,
        test_patient,
        test_doctor,
        test_visit,
    ):
        lab_queue = DailyQueue(
            day=date.today(),
            specialist_id=test_doctor.id,
            queue_tag="lab",
            active=True,
        )
        db_session.add(lab_queue)
        db_session.commit()
        db_session.refresh(lab_queue)

        lab_entry = OnlineQueueEntry(
            queue_id=lab_queue.id,
            number=1,
            patient_id=test_patient.id,
            patient_name=test_patient.short_name(),
            phone=test_patient.phone,
            visit_id=test_visit.id,
            source="desk",
            status="waiting",
        )
        db_session.add(lab_entry)
        db_session.commit()

        templates_response = client.get("/api/v1/lab/templates", headers=auth_headers)
        assert templates_response.status_code == 200, templates_response.text
        template = next(
            item for item in templates_response.json() if item["code"] == "cbc_oak"
        )

        first_response = client.post(
            "/api/v1/lab/report-instances",
            headers=auth_headers,
            json={
                "patient_id": test_patient.id,
                "visit_id": test_visit.id,
                "template_id": template["id"],
            },
        )
        assert first_response.status_code == 200, first_response.text

        latest_response = client.post(
            "/api/v1/lab/report-instances",
            headers=auth_headers,
            json={
                "patient_id": test_patient.id,
                "visit_id": test_visit.id,
                "template_id": template["id"],
            },
        )
        assert latest_response.status_code == 200, latest_response.text
        latest = latest_response.json()

        # /mark-ready HTTP endpoint was removed (L-2 fix: dead code).
        # Transition the latest instance to READY directly so the registrar
        # today-queues summary surfaces it as the latest lab report.
        lab_instance = (
            db_session.query(LabReportInstance)
            .filter(LabReportInstance.id == latest["id"])
            .first()
        )
        lab_instance.status = "READY"
        db_session.commit()

        response = client.get(
            "/api/v1/registrar/queues/today?department=lab",
            headers=auth_headers,
        )

        assert response.status_code == 200, response.text
        payload = response.json()
        found_entry = next(
            entry
            for queue in payload["queues"]
            for entry in queue["entries"]
            if entry["id"] == lab_entry.id
        )
        latest_lab_report = found_entry["latest_lab_report"]

        assert latest_lab_report["id"] == latest["id"]
        assert latest_lab_report["status"] == "READY"
        assert latest_lab_report["template_id"] == template["id"]
        assert latest_lab_report["template_name"] == template["name"]
        assert latest_lab_report["flagged_findings_count"] == 0
        assert latest_lab_report["critical_findings_count"] == 0
        assert latest_lab_report["can_finalize"] is True
        assert "finalize" in latest_lab_report["available_actions"]

    def test_start_queue_visit_uses_queue_entry_id_when_visit_id_collides(
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

        collision_id = 900001
        unrelated_visit = Visit(
            id=collision_id,
            patient_id=test_patient.id,
            doctor_id=test_doctor.id,
            visit_date=date.today(),
            visit_time="09:00",
            status="pending_confirmation",
            discount_mode="none",
            department="cardiology",
            source="desk",
        )
        entry = OnlineQueueEntry(
            id=collision_id,
            queue_id=queue.id,
            number=1,
            patient_id=test_patient.id,
            patient_name=test_patient.short_name(),
            phone=test_patient.phone,
            visit_id=None,
            source="desk",
            status="waiting",
        )
        db_session.add_all([unrelated_visit, entry])
        db_session.commit()

        response = client.post(
            f"/api/v1/registrar/queue/{entry.id}/start-visit",
            headers=auth_headers,
        )

        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload["entry"]["id"] == entry.id
        assert payload["entry"]["status"] == "in_progress"

        db_session.refresh(entry)
        db_session.refresh(unrelated_visit)
        assert entry.status == "in_progress"
        assert unrelated_visit.status == "pending_confirmation"

    def test_start_queue_visit_rejects_entry_linked_to_other_patient_visit(
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
        other_patient = Patient(
            first_name="Other",
            last_name="Patient",
            phone="+998901119001",
        )
        db_session.add_all([queue, other_patient])
        db_session.flush()

        other_visit = Visit(
            patient_id=other_patient.id,
            doctor_id=test_doctor.id,
            visit_date=date.today(),
            visit_time="10:00",
            status="pending_confirmation",
            discount_mode="none",
            department="cardiology",
            source="desk",
        )
        db_session.add(other_visit)
        db_session.flush()

        entry = OnlineQueueEntry(
            queue_id=queue.id,
            number=1,
            patient_id=test_patient.id,
            patient_name=test_patient.short_name(),
            phone=test_patient.phone,
            visit_id=other_visit.id,
            source="desk",
            status="waiting",
        )
        db_session.add(entry)
        db_session.commit()

        response = client.post(
            f"/api/v1/registrar/queue/{entry.id}/start-visit",
            headers=auth_headers,
        )

        assert response.status_code == 409, response.text
        assert response.json()["detail"] == (
            "Queue entry visit does not belong to the queue patient"
        )

        db_session.refresh(entry)
        db_session.refresh(other_visit)
        assert entry.status == "waiting"
        assert other_visit.status == "pending_confirmation"
