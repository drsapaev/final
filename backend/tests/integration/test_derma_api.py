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


EXAMINATION_PAYLOAD = {
    "examination_date": date.today().isoformat(),
    "skin_type": "combination",
    "skin_condition": "Чувствительная кожа",
    "lesions": "Локальная эритема",
    "diagnosis": "Розацеа под вопросом",
    "treatment_plan": "Мягкий уход и повторный контроль",
}

PROCEDURE_PAYLOAD = {
    "procedure_date": date.today().isoformat(),
    "procedure_type": "laser",
    "area_treated": "Щеки",
    "products_used": "Cooling gel",
    "results": "Покраснение минимальное",
    "follow_up": "Контроль через 14 дней",
    "total_cost": 125000,
}


@pytest.mark.integration
class TestDermaApi:
    def test_legacy_examination_writes_are_gone_but_reads_still_list(
        self,
        client,
        db_session,
        auth_headers,
        test_patient,
        test_visit,
        admin_user,
    ):
        """P2-4a: POST /derma/examinations закрыт (410) для всех ролей —
        таблица read-only, новые осмотры живут в specialty_data ЭМК.
        GET-чтение истории не изменилось: заранее засеянные строки
        возвращаются владельцу-админу без изменений."""
        seeded = DermaExamination(
            patient_id=test_patient.id,
            visit_id=test_visit.id,
            doctor_id=admin_user.id,
            examination_date=date.today(),
            skin_type="combination",
            skin_condition="Чувствительная кожа",
            lesions="Локальная эритема",
            diagnosis="Розацеа под вопросом",
            treatment_plan="Мягкий уход и повторный контроль",
        )
        db_session.add(seeded)
        db_session.commit()
        db_session.refresh(seeded)

        write_response = client.post(
            "/api/v1/derma/examinations",
            json={
                **EXAMINATION_PAYLOAD,
                "patient_id": test_patient.id,
                "visit_id": test_visit.id,
            },
            headers=auth_headers,
        )
        assert write_response.status_code == 410
        assert "ЭМК" in write_response.json()["detail"]
        assert (
            db_session.query(DermaExamination)
            .filter(DermaExamination.patient_id == test_patient.id)
            .count()
            == 1
        )

        list_response = client.get(
            f"/api/v1/derma/examinations?patient_id={test_patient.id}&limit=10",
            headers=auth_headers,
        )
        assert list_response.status_code == 200
        listed = list_response.json()
        assert [item["id"] for item in listed] == [seeded.id]
        assert listed[0]["patient_id"] == test_patient.id
        assert listed[0]["diagnosis"] == seeded.diagnosis

    def test_legacy_procedure_writes_are_gone_but_reads_still_list(
        self,
        client,
        db_session,
        auth_headers,
        test_patient,
        test_visit,
        admin_user,
    ):
        """P2-4a: POST /derma/procedures закрыт (410) для всех ролей —
        таблица read-only, новые процедуры живут в specialty_data ЭМК.
        GET-чтение истории не изменилось."""
        seeded = DermaProcedure(
            patient_id=test_patient.id,
            visit_id=test_visit.id,
            doctor_id=admin_user.id,
            procedure_date=date.today(),
            procedure_type="laser",
            area_treated="Щеки",
            products_used="Cooling gel",
            results="Покраснение минимальное",
            follow_up="Контроль через 14 дней",
            total_cost=125000,
        )
        db_session.add(seeded)
        db_session.commit()
        db_session.refresh(seeded)

        write_response = client.post(
            "/api/v1/derma/procedures",
            json={
                **PROCEDURE_PAYLOAD,
                "patient_id": test_patient.id,
                "visit_id": test_visit.id,
            },
            headers=auth_headers,
        )
        assert write_response.status_code == 410
        assert "ЭМК" in write_response.json()["detail"]
        assert (
            db_session.query(DermaProcedure)
            .filter(DermaProcedure.patient_id == test_patient.id)
            .count()
            == 1
        )

        list_response = client.get(
            f"/api/v1/derma/procedures?patient_id={test_patient.id}&limit=10",
            headers=auth_headers,
        )
        assert list_response.status_code == 200
        listed = list_response.json()
        assert [item["id"] for item in listed] == [seeded.id]
        assert listed[0]["patient_id"] == test_patient.id
        assert listed[0]["procedure_type"] == seeded.procedure_type

    def test_legacy_write_endpoints_are_gone_for_doctor_role(
        self,
        client,
        db_session,
    ):
        """P2-4a: fail-closed для врача (Doctor) на своих и чужих пациентах —
        410 возвращается ДО каких-либо ownership-проверок, эндпоинт исчез
        как источник записи; новые данные создаются только в ЭМК."""
        own_user, own_doctor = _create_doctor_user(db_session, label="own")
        _other_user, other_doctor = _create_doctor_user(db_session, label="other")
        own_patient = _create_patient(db_session, label="own")
        other_patient = _create_patient(db_session, label="other")
        own_visit = _create_visit(db_session, patient=own_patient, doctor=own_doctor)
        other_visit = _create_visit(
            db_session, patient=other_patient, doctor=other_doctor
        )
        headers = _doctor_headers(client, own_user)

        own_exam_write = client.post(
            "/api/v1/derma/examinations",
            json={
                **EXAMINATION_PAYLOAD,
                "patient_id": own_patient.id,
                "visit_id": own_visit.id,
            },
            headers=headers,
        )
        assert own_exam_write.status_code == 410

        foreign_exam_write = client.post(
            "/api/v1/derma/examinations",
            json={
                **EXAMINATION_PAYLOAD,
                "patient_id": other_patient.id,
                "visit_id": other_visit.id,
            },
            headers=headers,
        )
        assert foreign_exam_write.status_code == 410

        own_procedure_write = client.post(
            "/api/v1/derma/procedures",
            json={
                **PROCEDURE_PAYLOAD,
                "patient_id": own_patient.id,
                "visit_id": own_visit.id,
            },
            headers=headers,
        )
        assert own_procedure_write.status_code == 410

        foreign_procedure_write = client.post(
            "/api/v1/derma/procedures",
            json={
                **PROCEDURE_PAYLOAD,
                "patient_id": other_patient.id,
                "visit_id": other_visit.id,
            },
            headers=headers,
        )
        assert foreign_procedure_write.status_code == 410

        assert db_session.query(DermaExamination).count() == 0
        assert db_session.query(DermaProcedure).count() == 0

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

    def test_legacy_examination_write_rejects_missing_patient_with_gone(
        self,
        client,
        auth_headers,
        test_visit,
    ):
        """P2-4a: 410 возвращается ДО валидации пациента — эндпоинт записи
        исчез целиком, любых полезных нагрузок, включая некорректные."""
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

        assert response.status_code == 410
