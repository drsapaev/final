from __future__ import annotations

from datetime import date

import pytest

from app.models.clinic import Doctor
from app.models.online_queue import DailyQueue, OnlineQueueEntry
from app.models.patient import Patient
from app.models.visit import Visit
from app.core.security import get_password_hash
from app.models.user import User


from tests.auth_test_credentials import (
    DOCTOR_PASSWORD,
)

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
            json={"username": test_doctor_user.username, "password": DOCTOR_PASSWORD},
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

    def test_general_queue_returns_empty_payload_without_configuration(
        self,
        client,
        test_doctor_user,
    ):
        login_response = client.post(
            "/api/v1/authentication/login",
            json={"username": test_doctor_user.username, "password": DOCTOR_PASSWORD},
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
        assert payload["doctor"]["id"] == test_doctor_user.id
        assert payload["doctor"]["name"] == (
            test_doctor_user.full_name or test_doctor_user.username
        )
        assert payload["doctor"]["specialty"] == "general"

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
            json={"username": test_doctor_user.username, "password": DOCTOR_PASSWORD},
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
            status="waiting",
        )
        db_session.add(entry)
        db_session.commit()
        db_session.refresh(entry)

        login_response = client.post(
            "/api/v1/auth/minimal-login",
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
            json={"username": test_doctor_user.username, "password": DOCTOR_PASSWORD},
        )
        assert login_response.status_code == 200
        headers = {"Authorization": f"Bearer {login_response.json()['access_token']}"}

        response = client.get("/api/v1/doctor/stats", headers=headers)

        assert response.status_code == 200
        payload = response.json()
        assert payload["doctor"]["cabinet"] == "101"
        assert payload["stats"]["total_patients"] >= 1
