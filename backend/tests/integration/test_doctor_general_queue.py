from __future__ import annotations

from datetime import date

import pytest

from app.models.clinic import Doctor
from app.models.appointment import Appointment
from app.models.online_queue import DailyQueue, OnlineQueueEntry
from app.models.patient import Patient
from app.models.visit import Visit
from app.core.security import get_password_hash
from app.models.user import User


@pytest.mark.integration
class TestDoctorGeneralQueue:
    def test_general_queue_uses_current_user_when_doctor_row_is_missing(
        self,
        client,
        db_session,
        test_doctor_user,
        test_patient,
    ):
        queue = DailyQueue(
            day=date.today(),
            specialist_id=test_doctor_user.id,
            queue_tag="general",
            active=True,
        )
        db_session.add(queue)
        db_session.commit()
        db_session.refresh(queue)

        entry = OnlineQueueEntry(
            queue_id=queue.id,
            number=1,
            patient_id=test_patient.id,
            patient_name=test_patient.short_name(),
            phone=test_patient.phone,
            source="registrar",
            status="waiting",
        )
        db_session.add(entry)
        db_session.commit()
        db_session.refresh(entry)

        login_response = client.post(
            "/api/v1/authentication/login",
            json={"username": test_doctor_user.username, "password": "doctor123"},
        )
        assert login_response.status_code == 200
        headers = {"Authorization": f"Bearer {login_response.json()['access_token']}"}

        response = client.get("/api/v1/doctor/general/queue/today", headers=headers)

        assert response.status_code == 200
        payload = response.json()
        assert payload["queue_exists"] is True
        assert payload["doctor"]["id"] == test_doctor_user.id
        assert payload["doctor"]["name"] == (
            test_doctor_user.full_name or test_doctor_user.username
        )
        assert payload["doctor"]["specialty"] == "general"
        assert payload["stats"]["waiting"] == 1
        assert len(payload["entries"]) == 1
        assert payload["entries"][0]["id"] == entry.id
        assert payload["entries"][0]["patient_name"] == test_patient.short_name()
        assert payload["can_call_next"] is True
        assert payload["next_call_entry_id"] == entry.id
        assert set(payload["entries"][0]["available_actions"]) == {"call", "no_show"}
        assert payload["entries"][0]["can_call"] is True
        assert payload["entries"][0]["can_no_show"] is True
        assert payload["entries"][0]["can_start_visit"] is False
        assert payload["entries"][0]["can_complete"] is False

    def test_general_queue_exposes_backend_owned_start_and_complete_actions(
        self,
        client,
        db_session,
        test_doctor_user,
        test_patient,
    ):
        doctor = Doctor(
            user_id=test_doctor_user.id,
            specialty="general",
            active=True,
            cabinet="101",
        )
        db_session.add(doctor)
        db_session.commit()
        db_session.refresh(doctor)

        queue = DailyQueue(
            day=date.today(),
            specialist_id=doctor.id,
            queue_tag="general",
            active=True,
        )
        db_session.add(queue)
        db_session.commit()
        db_session.refresh(queue)

        called_entry = OnlineQueueEntry(
            queue_id=queue.id,
            number=1,
            patient_id=test_patient.id,
            patient_name=test_patient.short_name(),
            phone=test_patient.phone,
            source="registrar",
            status="called",
        )
        in_progress_entry = OnlineQueueEntry(
            queue_id=queue.id,
            number=2,
            patient_id=test_patient.id,
            patient_name=test_patient.short_name(),
            phone=test_patient.phone,
            source="registrar",
            status="in_progress",
        )
        db_session.add_all([called_entry, in_progress_entry])
        db_session.commit()

        login_response = client.post(
            "/api/v1/authentication/login",
            json={"username": test_doctor_user.username, "password": "doctor123"},
        )
        assert login_response.status_code == 200
        headers = {"Authorization": f"Bearer {login_response.json()['access_token']}"}

        response = client.get("/api/v1/doctor/general/queue/today", headers=headers)

        assert response.status_code == 200
        entries = response.json()["entries"]
        called_payload = entries[0]
        in_progress_payload = entries[1]

        assert called_payload["status"] == "called"
        assert "start_visit" in called_payload["available_actions"]
        assert "complete" not in called_payload["available_actions"]
        assert called_payload["can_start_visit"] is True
        assert called_payload["can_complete"] is False

        assert in_progress_payload["status"] == "in_progress"
        assert set(in_progress_payload["available_actions"]) == {"complete"}
        assert in_progress_payload["can_start_visit"] is False
        assert in_progress_payload["can_complete"] is True

    def test_queue_commands_reject_statuses_without_backend_action(
        self,
        client,
        db_session,
        test_doctor_user,
        test_patient,
    ):
        doctor = Doctor(
            user_id=test_doctor_user.id,
            specialty="general",
            active=True,
            cabinet="101",
        )
        db_session.add(doctor)
        db_session.commit()
        db_session.refresh(doctor)

        queue = DailyQueue(
            day=date.today(),
            specialist_id=doctor.id,
            queue_tag="general",
            active=True,
        )
        db_session.add(queue)
        db_session.commit()
        db_session.refresh(queue)

        waiting_entry = OnlineQueueEntry(
            queue_id=queue.id,
            number=1,
            patient_id=test_patient.id,
            patient_name=test_patient.short_name(),
            phone=test_patient.phone,
            source="registrar",
            status="waiting",
        )
        called_entry = OnlineQueueEntry(
            queue_id=queue.id,
            number=2,
            patient_id=test_patient.id,
            patient_name=test_patient.short_name(),
            phone=test_patient.phone,
            source="registrar",
            status="called",
        )
        db_session.add_all([waiting_entry, called_entry])
        db_session.commit()
        db_session.refresh(waiting_entry)
        db_session.refresh(called_entry)

        login_response = client.post(
            "/api/v1/authentication/login",
            json={"username": test_doctor_user.username, "password": "doctor123"},
        )
        assert login_response.status_code == 200
        headers = {"Authorization": f"Bearer {login_response.json()['access_token']}"}

        start_response = client.post(
            f"/api/v1/doctor/queue/{waiting_entry.id}/start-visit",
            headers=headers,
        )
        complete_response = client.post(
            f"/api/v1/doctor/queue/{called_entry.id}/complete",
            headers=headers,
        )

        assert start_response.status_code == 400
        assert complete_response.status_code == 400
        db_session.refresh(waiting_entry)
        db_session.refresh(called_entry)
        assert waiting_entry.status == "waiting"
        assert called_entry.status == "called"

    def test_start_visit_does_not_reuse_another_doctors_open_visit(
        self,
        client,
        db_session,
        test_doctor_user,
        test_patient,
    ):
        doctor = Doctor(
            user_id=test_doctor_user.id,
            specialty="general",
            active=True,
            cabinet="101",
        )
        other_doctor = Doctor(
            user_id=None,
            specialty="dermatology",
            active=True,
            cabinet="202",
        )
        db_session.add_all([doctor, other_doctor])
        db_session.commit()
        db_session.refresh(doctor)
        db_session.refresh(other_doctor)

        unrelated_visit = Visit(
            patient_id=test_patient.id,
            doctor_id=other_doctor.id,
            visit_date=date.today(),
            visit_time="08:00",
            status="open",
            notes="do not touch",
            discount_mode="none",
            source="desk",
        )
        queue = DailyQueue(
            day=date.today(),
            specialist_id=doctor.id,
            queue_tag="general",
            active=True,
        )
        db_session.add_all([unrelated_visit, queue])
        db_session.commit()
        db_session.refresh(unrelated_visit)
        db_session.refresh(queue)

        entry = OnlineQueueEntry(
            queue_id=queue.id,
            number=1,
            patient_id=test_patient.id,
            patient_name=test_patient.short_name(),
            phone=test_patient.phone,
            source="registrar",
            status="called",
        )
        db_session.add(entry)
        db_session.commit()
        db_session.refresh(entry)

        login_response = client.post(
            "/api/v1/authentication/login",
            json={"username": test_doctor_user.username, "password": "doctor123"},
        )
        assert login_response.status_code == 200
        headers = {"Authorization": f"Bearer {login_response.json()['access_token']}"}

        response = client.post(
            f"/api/v1/doctor/queue/{entry.id}/start-visit",
            headers=headers,
        )

        assert response.status_code == 200, response.text
        db_session.refresh(entry)
        db_session.refresh(unrelated_visit)
        created_visit = (
            db_session.query(Visit)
            .filter(
                Visit.patient_id == test_patient.id,
                Visit.visit_date == date.today(),
                Visit.doctor_id == doctor.id,
            )
            .one()
        )

        assert entry.status == "in_progress"
        assert created_visit.id != unrelated_visit.id
        assert created_visit.notes is not None
        assert unrelated_visit.status == "open"
        assert unrelated_visit.visit_time == "08:00"
        assert unrelated_visit.notes == "do not touch"

    def test_general_queue_returns_empty_payload_without_configuration(
        self,
        client,
        test_doctor_user,
    ):
        login_response = client.post(
            "/api/v1/authentication/login",
            json={"username": test_doctor_user.username, "password": "doctor123"},
        )
        assert login_response.status_code == 200
        headers = {"Authorization": f"Bearer {login_response.json()['access_token']}"}

        response = client.get("/api/v1/doctor/general/queue/today", headers=headers)

        assert response.status_code == 200
        payload = response.json()
        assert payload["queue_exists"] is False
        assert payload["entries"] == []
        assert payload["stats"] == {
            "total": 0,
            "waiting": 0,
            "called": 0,
            "served": 0,
        }
        assert payload["can_call_next"] is False
        assert payload["next_call_entry_id"] is None
        assert payload["doctor"]["id"] == test_doctor_user.id
        assert payload["doctor"]["name"] == (
            test_doctor_user.full_name or test_doctor_user.username
        )
        assert payload["doctor"]["specialty"] == "general"

    def test_call_patient_rejects_non_callable_queue_status(
        self,
        client,
        db_session,
        test_doctor_user,
        test_patient,
    ):
        doctor = Doctor(
            user_id=test_doctor_user.id,
            specialty="general",
            active=True,
            cabinet="101",
        )
        db_session.add(doctor)
        db_session.commit()
        db_session.refresh(doctor)

        queue = DailyQueue(
            day=date.today(),
            specialist_id=doctor.id,
            queue_tag="general",
            active=True,
        )
        db_session.add(queue)
        db_session.commit()
        db_session.refresh(queue)

        entry = OnlineQueueEntry(
            queue_id=queue.id,
            number=1,
            patient_id=test_patient.id,
            patient_name=test_patient.short_name(),
            phone=test_patient.phone,
            source="registrar",
            status="served",
        )
        db_session.add(entry)
        db_session.commit()
        db_session.refresh(entry)

        login_response = client.post(
            "/api/v1/authentication/login",
            json={"username": test_doctor_user.username, "password": "doctor123"},
        )
        assert login_response.status_code == 200
        headers = {"Authorization": f"Bearer {login_response.json()['access_token']}"}

        response = client.post(
            f"/api/v1/doctor/queue/{entry.id}/call",
            headers=headers,
        )

        assert response.status_code == 400
        db_session.refresh(entry)
        assert entry.status == "served"

    def test_complete_queue_entry_prefers_queue_entry_over_id_collision_with_visit(
        self,
        client,
        db_session,
        test_doctor_user,
        test_patient,
    ):
        doctor = Doctor(
            user_id=test_doctor_user.id,
            specialty="general",
            active=True,
            cabinet="101",
        )
        db_session.add(doctor)
        db_session.commit()
        db_session.refresh(doctor)

        queue = DailyQueue(
            day=date.today(),
            specialist_id=doctor.id,
            queue_tag="general",
            active=True,
        )
        db_session.add(queue)
        db_session.commit()
        db_session.refresh(queue)

        other_patient = Patient(
            first_name="Петр",
            last_name="Смирнов",
            middle_name="Тестовый",
            phone="+998909999999",
            birth_date=date(1988, 5, 5),
            address="Тестовый адрес 2",
        )
        db_session.add(other_patient)
        db_session.commit()
        db_session.refresh(other_patient)

        collision_id = 9001
        unrelated_visit = Visit(
            id=collision_id,
            patient_id=other_patient.id,
            doctor_id=None,
            visit_date=date.today(),
            status="open",
            discount_mode="none",
            source="desk",
        )
        db_session.add(unrelated_visit)

        entry = OnlineQueueEntry(
            id=collision_id,
            queue_id=queue.id,
            number=1,
            patient_id=test_patient.id,
            patient_name=test_patient.short_name(),
            phone=test_patient.phone,
            source="registrar",
            status="diagnostics",
        )
        db_session.add(entry)
        db_session.commit()
        db_session.refresh(entry)

        login_response = client.post(
            "/api/v1/authentication/login",
            json={"username": test_doctor_user.username, "password": "doctor123"},
        )
        assert login_response.status_code == 200
        headers = {"Authorization": f"Bearer {login_response.json()['access_token']}"}

        response = client.post(
            f"/api/v1/doctor/queue/{collision_id}/complete",
            headers=headers,
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["success"] is True
        assert payload["entry_id"] == collision_id
        assert payload["status"] == "completed"

        db_session.refresh(entry)
        db_session.refresh(unrelated_visit)
        assert entry.status == "served"
        assert unrelated_visit.status == "open"

    def test_complete_does_not_mutate_unrelated_queue_entry_on_appointment_collision(
        self,
        client,
        db_session,
        test_doctor_user,
        test_patient,
    ):
        doctor = Doctor(
            user_id=test_doctor_user.id,
            specialty="general",
            active=True,
            cabinet="101",
        )
        db_session.add(doctor)
        db_session.commit()
        db_session.refresh(doctor)

        queue = DailyQueue(
            day=date.today(),
            specialist_id=doctor.id,
            queue_tag="general",
            active=True,
        )
        db_session.add(queue)
        db_session.commit()
        db_session.refresh(queue)

        other_patient = Patient(
            first_name="Collision",
            last_name="Queue",
            middle_name="Patient",
            phone="+998901111111",
            birth_date=date(1985, 4, 4),
            address="Queue patient address",
        )
        db_session.add(other_patient)
        db_session.commit()
        db_session.refresh(other_patient)

        collision_id = 9002
        appointment = Appointment(
            id=collision_id,
            patient_id=test_patient.id,
            doctor_id=doctor.id,
            appointment_date=date.today(),
            appointment_time="12:00",
            status="paid",
            visit_type="paid",
            payment_type="cash",
            services=["consultation"],
        )
        entry = OnlineQueueEntry(
            id=collision_id,
            queue_id=queue.id,
            number=2,
            patient_id=other_patient.id,
            patient_name=other_patient.short_name(),
            phone=other_patient.phone,
            source="registrar",
            status="diagnostics",
        )
        db_session.add_all([appointment, entry])
        db_session.commit()

        login_response = client.post(
            "/api/v1/authentication/login",
            json={"username": test_doctor_user.username, "password": "doctor123"},
        )
        assert login_response.status_code == 200
        headers = {"Authorization": f"Bearer {login_response.json()['access_token']}"}

        response = client.post(
            f"/api/v1/doctor/queue/{collision_id}/complete",
            json={"patient_id": test_patient.id, "notes": "appointment complete"},
            headers=headers,
        )

        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload["success"] is True
        assert payload["status"] == "completed"

        db_session.refresh(appointment)
        db_session.refresh(entry)
        assert appointment.status == "completed"
        assert entry.status == "diagnostics"

    def test_complete_skips_unrelated_visit_when_appointment_id_collides(
        self,
        client,
        db_session,
        test_doctor_user,
        test_patient,
        test_doctor,
    ):
        other_patient = Patient(
            first_name="Unrelated",
            last_name="Visit",
            middle_name="Collision",
            phone="+998901222222",
            birth_date=date(1982, 6, 6),
            address="Unrelated visit address",
        )
        db_session.add(other_patient)
        db_session.commit()
        db_session.refresh(other_patient)

        collision_id = 9003
        unrelated_visit = Visit(
            id=collision_id,
            patient_id=other_patient.id,
            doctor_id=None,
            visit_date=date.today(),
            status="open",
            discount_mode="none",
            source="desk",
        )
        appointment = Appointment(
            id=collision_id,
            patient_id=test_patient.id,
            doctor_id=test_doctor.id,
            appointment_date=date.today(),
            appointment_time="12:30",
            status="paid",
            visit_type="paid",
            payment_type="cash",
            services=["consultation"],
        )
        db_session.add_all([unrelated_visit, appointment])
        db_session.commit()

        login_response = client.post(
            "/api/v1/authentication/login",
            json={"username": test_doctor_user.username, "password": "doctor123"},
        )
        assert login_response.status_code == 200
        headers = {"Authorization": f"Bearer {login_response.json()['access_token']}"}

        response = client.post(
            f"/api/v1/doctor/queue/{collision_id}/complete",
            json={"patient_id": test_patient.id, "notes": "appointment complete"},
            headers=headers,
        )

        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload["success"] is True
        assert payload["entry_id"] == collision_id
        assert payload["status"] == "completed"

        db_session.refresh(unrelated_visit)
        db_session.refresh(appointment)
        assert unrelated_visit.status == "open"
        assert appointment.status == "completed"

    def test_complete_queue_entry_with_matching_appointment_persists_visit_and_appointment(
        self,
        client,
        db_session,
        test_doctor_user,
        test_patient,
    ):
        doctor = Doctor(
            user_id=test_doctor_user.id,
            specialty="general",
            active=True,
            cabinet="101",
        )
        db_session.add(doctor)
        db_session.commit()
        db_session.refresh(doctor)

        queue = DailyQueue(
            day=date.today(),
            specialist_id=doctor.id,
            queue_tag="general",
            active=True,
        )
        db_session.add(queue)
        db_session.commit()
        db_session.refresh(queue)

        entry = OnlineQueueEntry(
            id=9004,
            queue_id=queue.id,
            number=4,
            patient_id=test_patient.id,
            patient_name=test_patient.short_name(),
            phone=test_patient.phone,
            source="registrar",
            status="diagnostics",
        )
        appointment = Appointment(
            id=9104,
            patient_id=test_patient.id,
            doctor_id=doctor.id,
            appointment_date=date.today(),
            appointment_time="13:00",
            status="paid",
            visit_type="paid",
            payment_type="cash",
            services=["consultation"],
        )
        db_session.add_all([entry, appointment])
        db_session.commit()

        login_response = client.post(
            "/api/v1/authentication/login",
            json={"username": test_doctor_user.username, "password": "doctor123"},
        )
        assert login_response.status_code == 200
        headers = {"Authorization": f"Bearer {login_response.json()['access_token']}"}

        response = client.post(
            f"/api/v1/doctor/queue/{entry.id}/complete",
            headers=headers,
        )

        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload["success"] is True
        assert payload["entry_id"] == entry.id
        assert payload["status"] == "completed"

        db_session.refresh(entry)
        db_session.refresh(appointment)
        visit = (
            db_session.query(Visit)
            .filter(
                Visit.patient_id == test_patient.id,
                Visit.doctor_id == doctor.id,
                Visit.visit_date == date.today(),
            )
            .one()
        )

        assert entry.status == "served"
        assert visit.status == "completed"
        assert appointment.status == "completed"

    def test_cardiologist_role_can_complete_queue_entry(
        self,
        client,
        db_session,
        test_patient,
    ):
        cardiologist_user = User(
            username="test_cardiologist",
            email="cardiologist@test.com",
            full_name="Test Cardiologist",
            hashed_password=get_password_hash("cardiologist123"),
            role="Cardiologist",
            is_active=True,
            is_superuser=False,
        )
        db_session.add(cardiologist_user)
        db_session.commit()
        db_session.refresh(cardiologist_user)

        doctor = Doctor(
            user_id=cardiologist_user.id,
            specialty="cardiology",
            active=True,
            cabinet="202",
        )
        db_session.add(doctor)
        db_session.commit()
        db_session.refresh(doctor)

        queue = DailyQueue(
            day=date.today(),
            specialist_id=doctor.id,
            queue_tag="cardiology",
            active=True,
        )
        db_session.add(queue)
        db_session.commit()
        db_session.refresh(queue)

        entry = OnlineQueueEntry(
            queue_id=queue.id,
            number=11,
            patient_id=test_patient.id,
            patient_name=test_patient.short_name(),
            phone=test_patient.phone,
            source="registrar",
            status="in_progress",
        )
        db_session.add(entry)
        db_session.commit()
        db_session.refresh(entry)

        login_response = client.post(
            "/api/v1/authentication/login",
            json={"username": cardiologist_user.username, "password": "cardiologist123"},
        )
        assert login_response.status_code == 200
        headers = {"Authorization": f"Bearer {login_response.json()['access_token']}"}

        response = client.post(
            f"/api/v1/doctor/queue/{entry.id}/complete",
            json={"notes": "done"},
            headers=headers,
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["success"] is True
        assert payload["entry_id"] == entry.id
        assert payload["status"] == "completed"

    def test_doctor_stats_reads_daily_queue_by_doctor_id(
        self,
        client,
        db_session,
        test_doctor_user,
        test_patient,
    ):
        doctor = Doctor(
            user_id=test_doctor_user.id,
            specialty="general",
            active=True,
            cabinet="101",
        )
        db_session.add(doctor)
        db_session.commit()
        db_session.refresh(doctor)

        queue = DailyQueue(
            day=date.today(),
            specialist_id=doctor.id,
            queue_tag="general",
            active=True,
        )
        db_session.add(queue)
        db_session.commit()
        db_session.refresh(queue)

        entry = OnlineQueueEntry(
            queue_id=queue.id,
            number=5,
            patient_id=test_patient.id,
            patient_name=test_patient.short_name(),
            phone=test_patient.phone,
            source="registrar",
            status="served",
        )
        db_session.add(entry)
        db_session.commit()

        login_response = client.post(
            "/api/v1/authentication/login",
            json={"username": test_doctor_user.username, "password": "doctor123"},
        )
        assert login_response.status_code == 200
        headers = {"Authorization": f"Bearer {login_response.json()['access_token']}"}

        response = client.get("/api/v1/doctor/stats", headers=headers)

        assert response.status_code == 200
        payload = response.json()
        assert payload["doctor"]["cabinet"] == "101"
        assert payload["stats"]["total_patients"] >= 1
