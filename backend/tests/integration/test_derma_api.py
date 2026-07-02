from __future__ import annotations

from datetime import date
from uuid import uuid4

import pytest

from app.core.security import get_password_hash
from app.models.clinic import Doctor
from app.models.derma_examination import DermaExamination
from app.models.derma_procedure import DermaProcedure
from app.models.patient import Patient
from app.models.user import User
from app.models.visit import Visit


def _suffix() -> str:
    return uuid4().hex[:10]


def _create_doctor_user(db_session, *, label: str) -> tuple[User, Doctor]:
    suffix = _suffix()
    user = User(
        username=f"derma_guard_{label}_{suffix}",
        email=f"derma-guard-{label}-{suffix}@test.local",
        full_name=f"Derma Guard {label}",
        hashed_password=get_password_hash("doctor123"),
        role="Doctor",
        is_active=True,
        is_superuser=False,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    doctor = Doctor(
        user_id=user.id,
        specialty="dermatology",
        active=True,
    )
    db_session.add(doctor)
    db_session.commit()
    db_session.refresh(doctor)
    return user, doctor


def _create_patient(db_session, *, label: str) -> Patient:
    suffix = _suffix()
    patient = Patient(
        first_name=f"Derma {label}",
        last_name="OwnerGuard",
        phone=f"+99891{suffix[:7]}",
        birth_date=date(1990, 1, 1),
    )
    db_session.add(patient)
    db_session.commit()
    db_session.refresh(patient)
    return patient


def _create_visit(db_session, *, patient: Patient, doctor: Doctor) -> Visit:
    visit = Visit(
        patient_id=patient.id,
        doctor_id=doctor.id,
        visit_date=date.today(),
        status="open",
        source="desk",
        department="dermatology",
    )
    db_session.add(visit)
    db_session.commit()
    db_session.refresh(visit)
    return visit


def _doctor_headers(client, user: User) -> dict[str, str]:
    response = client.post(
        "/api/v1/authentication/login",
        json={"username": user.username, "password": "doctor123"},
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


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

    def test_doctor_derma_records_are_limited_to_owned_patients(
        self,
        client,
        db_session,
    ):
        own_user, own_doctor = _create_doctor_user(db_session, label="own")
        _other_user, other_doctor = _create_doctor_user(db_session, label="other")
        own_patient = _create_patient(db_session, label="own")
        other_patient = _create_patient(db_session, label="other")
        own_visit = _create_visit(db_session, patient=own_patient, doctor=own_doctor)
        other_visit = _create_visit(db_session, patient=other_patient, doctor=other_doctor)
        own_exam = DermaExamination(
            patient_id=own_patient.id,
            visit_id=own_visit.id,
            doctor_id=own_user.id,
            examination_date=date.today(),
            skin_type="combination",
            diagnosis="owned diagnosis",
        )
        other_exam = DermaExamination(
            patient_id=other_patient.id,
            visit_id=other_visit.id,
            doctor_id=None,
            examination_date=date.today(),
            skin_type="dry",
            diagnosis="foreign diagnosis",
        )
        own_procedure = DermaProcedure(
            patient_id=own_patient.id,
            visit_id=own_visit.id,
            doctor_id=own_user.id,
            procedure_date=date.today(),
            procedure_type="laser",
            total_cost=100000,
        )
        other_procedure = DermaProcedure(
            patient_id=other_patient.id,
            visit_id=other_visit.id,
            doctor_id=None,
            procedure_date=date.today(),
            procedure_type="peel",
            total_cost=200000,
        )
        db_session.add_all([own_exam, other_exam, own_procedure, other_procedure])
        db_session.commit()
        db_session.refresh(own_exam)
        db_session.refresh(other_exam)
        db_session.refresh(own_procedure)
        db_session.refresh(other_procedure)
        headers = _doctor_headers(client, own_user)

        exams_response = client.get("/api/v1/derma/examinations?limit=20", headers=headers)
        assert exams_response.status_code == 200
        exam_ids = {item["id"] for item in exams_response.json()}
        assert own_exam.id in exam_ids
        assert other_exam.id not in exam_ids

        procedures_response = client.get("/api/v1/derma/procedures?limit=20", headers=headers)
        assert procedures_response.status_code == 200
        procedure_ids = {item["id"] for item in procedures_response.json()}
        assert own_procedure.id in procedure_ids
        assert other_procedure.id not in procedure_ids

        foreign_exam_read_response = client.get(
            f"/api/v1/derma/examinations?patient_id={other_patient.id}",
            headers=headers,
        )
        assert foreign_exam_read_response.status_code == 403

        foreign_procedure_read_response = client.get(
            f"/api/v1/derma/procedures?patient_id={other_patient.id}",
            headers=headers,
        )
        assert foreign_procedure_read_response.status_code == 403

        foreign_exam_write_response = client.post(
            "/api/v1/derma/examinations",
            json={
                "patient_id": other_patient.id,
                "visit_id": other_visit.id,
                "examination_date": date.today().isoformat(),
                "skin_type": "dry",
                "diagnosis": "must not be written",
            },
            headers=headers,
        )
        assert foreign_exam_write_response.status_code == 403

        foreign_procedure_write_response = client.post(
            "/api/v1/derma/procedures",
            json={
                "patient_id": other_patient.id,
                "visit_id": other_visit.id,
                "procedure_date": date.today().isoformat(),
                "procedure_type": "laser",
                "total_cost": 300000,
            },
            headers=headers,
        )
        assert foreign_procedure_write_response.status_code == 403

        own_exam_write_response = client.post(
            "/api/v1/derma/examinations",
            json={
                "patient_id": own_patient.id,
                "visit_id": own_visit.id,
                "examination_date": date.today().isoformat(),
                "skin_type": "combination",
                "diagnosis": "owned write",
            },
            headers=headers,
        )
        assert own_exam_write_response.status_code == 201
        assert own_exam_write_response.json()["patient_id"] == own_patient.id

        own_procedure_write_response = client.post(
            "/api/v1/derma/procedures",
            json={
                "patient_id": own_patient.id,
                "visit_id": own_visit.id,
                "procedure_date": date.today().isoformat(),
                "procedure_type": "laser",
                "total_cost": 110000,
            },
            headers=headers,
        )
        assert own_procedure_write_response.status_code == 201
        assert own_procedure_write_response.json()["patient_id"] == own_patient.id

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
