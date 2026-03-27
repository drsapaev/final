from __future__ import annotations

from datetime import date

import pytest

from app.models.cardio_blood_test import CardioBloodTest


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
