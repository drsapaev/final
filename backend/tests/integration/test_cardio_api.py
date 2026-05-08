from __future__ import annotations

from datetime import date

import pytest

from app.core.security import get_password_hash
from app.models.cardio_blood_test import CardioBloodTest
from app.models.user import User
from tests.auth_test_credentials import CARDIO_PASSWORD


@pytest.mark.integration
class TestCardioApi:
    def test_create_and_list_blood_tests(
        self,
        client,
        db_session,
        auth_headers,
        test_patient,
        test_visit,
        admin_user,
    ):
        payload = {
            "patient_id": test_patient.id,
            "visit_id": test_visit.id,
            "test_date": date.today().isoformat(),
            "cholesterol_total": 190,
            "cholesterol_hdl": 55,
            "cholesterol_ldl": 110,
            "glucose": 96,
            "interpretation": "Пограничный LDL, нужна динамика",
        }

        create_response = client.post(
            "/api/v1/cardio/blood-tests",
            json=payload,
            headers=auth_headers,
        )

        assert create_response.status_code == 201
        created = create_response.json()
        assert created["patient_id"] == test_patient.id
        assert created["visit_id"] == test_visit.id
        assert created["doctor_id"] == admin_user.id
        assert created["cholesterol_total"] == 190

        persisted = (
            db_session.query(CardioBloodTest)
            .filter(CardioBloodTest.id == created["id"])
            .first()
        )
        assert persisted is not None
        assert persisted.patient_id == test_patient.id
        assert persisted.visit_id == test_visit.id
        assert persisted.interpretation == payload["interpretation"]

        list_response = client.get(
            f"/api/v1/cardio/blood-tests?patient_id={test_patient.id}&limit=10",
            headers=auth_headers,
        )

        assert list_response.status_code == 200
        listed = list_response.json()
        assert len(listed) == 1
        assert listed[0]["id"] == created["id"]
        assert listed[0]["patient_id"] == test_patient.id

    def test_create_blood_test_rejects_missing_patient(
        self,
        client,
        auth_headers,
        test_visit,
    ):
        payload = {
            "patient_id": 999999,
            "visit_id": test_visit.id,
            "test_date": date.today().isoformat(),
        }

        response = client.post(
            "/api/v1/cardio/blood-tests",
            json=payload,
            headers=auth_headers,
        )

        assert response.status_code == 404
        assert response.json()["detail"] == "Пациент не найден"

    def test_cardiologist_role_can_access_cardio_endpoints(
        self,
        client,
        db_session,
        test_patient,
        test_visit,
    ):
        cardiologist = User(
            username="test_cardiologist",
            email="cardiologist@test.com",
            full_name="Test Cardiologist",
            hashed_password=get_password_hash(CARDIO_PASSWORD),
            role="cardiologist",
            is_active=True,
            is_superuser=False,
        )
        db_session.add(cardiologist)
        db_session.commit()
        db_session.refresh(cardiologist)

        login_response = client.post(
            "/api/v1/authentication/login",
            json={
                "username": cardiologist.username,
                "password": CARDIO_PASSWORD,
            },
        )
        assert login_response.status_code == 200
        headers = {"Authorization": f"Bearer {login_response.json()['access_token']}"}

        ecg_response = client.get(
            f"/api/v1/cardio/ecg?patient_id={test_patient.id}&limit=10",
            headers=headers,
        )
        assert ecg_response.status_code == 200
        assert ecg_response.json() == []

        blood_test_response = client.post(
            "/api/v1/cardio/blood-tests",
            json={
                "patient_id": test_patient.id,
                "visit_id": test_visit.id,
                "test_date": date.today().isoformat(),
                "cholesterol_total": 180,
                "interpretation": "Проверка доступа для cardiologist",
            },
            headers=headers,
        )

        assert blood_test_response.status_code == 201
        assert blood_test_response.json()["patient_id"] == test_patient.id
