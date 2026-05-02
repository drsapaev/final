from __future__ import annotations

from datetime import date

import pytest

from app.models.derma_examination import DermaExamination
from app.models.derma_procedure import DermaProcedure


@pytest.mark.integration
class TestDermaApi:
    def test_create_and_list_skin_examinations(
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
            "examination_date": date.today().isoformat(),
            "skin_type": "combination",
            "skin_condition": "Чувствительная кожа",
            "lesions": "Локальная эритема",
            "diagnosis": "Розацеа под вопросом",
            "treatment_plan": "Мягкий уход и повторный контроль",
        }

        create_response = client.post(
            "/api/v1/derma/examinations",
            json=payload,
            headers=auth_headers,
        )

        assert create_response.status_code == 201
        created = create_response.json()
        assert created["patient_id"] == test_patient.id
        assert created["visit_id"] == test_visit.id
        assert created["doctor_id"] == admin_user.id
        assert created["skin_type"] == "combination"

        persisted = (
            db_session.query(DermaExamination)
            .filter(DermaExamination.id == created["id"])
            .first()
        )
        assert persisted is not None
        assert persisted.patient_id == test_patient.id
        assert persisted.visit_id == test_visit.id
        assert persisted.diagnosis == payload["diagnosis"]

        list_response = client.get(
            f"/api/v1/derma/examinations?patient_id={test_patient.id}&limit=10",
            headers=auth_headers,
        )

        assert list_response.status_code == 200
        listed = list_response.json()
        assert len(listed) == 1
        assert listed[0]["id"] == created["id"]
        assert listed[0]["patient_id"] == test_patient.id

    def test_create_and_list_derma_procedures(
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
            "procedure_date": date.today().isoformat(),
            "procedure_type": "laser",
            "area_treated": "Щеки",
            "products_used": "Cooling gel",
            "results": "Покраснение минимальное",
            "follow_up": "Контроль через 14 дней",
            "total_cost": 125000,
        }

        create_response = client.post(
            "/api/v1/derma/procedures",
            json=payload,
            headers=auth_headers,
        )

        assert create_response.status_code == 201
        created = create_response.json()
        assert created["patient_id"] == test_patient.id
        assert created["visit_id"] == test_visit.id
        assert created["doctor_id"] == admin_user.id
        assert created["total_cost"] == 125000

        persisted = (
            db_session.query(DermaProcedure)
            .filter(DermaProcedure.id == created["id"])
            .first()
        )
        assert persisted is not None
        assert persisted.patient_id == test_patient.id
        assert persisted.visit_id == test_visit.id
        assert persisted.procedure_type == payload["procedure_type"]

        list_response = client.get(
            f"/api/v1/derma/procedures?patient_id={test_patient.id}&limit=10",
            headers=auth_headers,
        )

        assert list_response.status_code == 200
        listed = list_response.json()
        assert len(listed) == 1
        assert listed[0]["id"] == created["id"]
        assert listed[0]["patient_id"] == test_patient.id

    def test_create_skin_examination_rejects_missing_patient(
        self,
        client,
        auth_headers,
        test_visit,
    ):
        payload = {
            "patient_id": 999999,
            "visit_id": test_visit.id,
            "examination_date": date.today().isoformat(),
            "skin_type": "dry",
        }

        response = client.post(
            "/api/v1/derma/examinations",
            json=payload,
            headers=auth_headers,
        )

        assert response.status_code == 404
        assert response.json()["detail"] == "Пациент не найден"
