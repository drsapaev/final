from __future__ import annotations

from datetime import date
from uuid import uuid4

import pytest

from app.core.security import get_password_hash
from app.models.cardio_blood_test import CardioBloodTest
from app.models.clinic import Doctor
from app.models.patient import Patient
from app.models.user import User
from app.models.visit import Visit


def _suffix() -> str:
    return uuid4().hex[:10]


def _create_doctor_user(db_session, *, label: str) -> tuple[User, Doctor]:
    suffix = _suffix()
    user = User(
        username=f"cardio_guard_{label}_{suffix}",
        email=f"cardio-guard-{label}-{suffix}@test.local",
        full_name=f"Cardio Guard {label}",
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
        specialty="cardiology",
        active=True,
    )
    db_session.add(doctor)
    db_session.commit()
    db_session.refresh(doctor)
    return user, doctor


def _create_patient(db_session, *, label: str) -> Patient:
    suffix = _suffix()
    patient = Patient(
        first_name=f"Cardio {label}",
        last_name="OwnerGuard",
        phone=f"+99890{suffix[:7]}",
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
        department="cardiology",
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

    def test_doctor_blood_tests_are_limited_to_owned_patients(
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
        own_test = CardioBloodTest(
            patient_id=own_patient.id,
            visit_id=own_visit.id,
            doctor_id=own_user.id,
            test_date=date.today(),
            cholesterol_total=180,
            interpretation="owned cardio result",
        )
        other_test = CardioBloodTest(
            patient_id=other_patient.id,
            visit_id=other_visit.id,
            doctor_id=None,
            test_date=date.today(),
            cholesterol_total=250,
            interpretation="foreign cardio result",
        )
        db_session.add_all([own_test, other_test])
        db_session.commit()
        db_session.refresh(own_test)
        db_session.refresh(other_test)
        headers = _doctor_headers(client, own_user)

        list_response = client.get(
            "/api/v1/cardio/blood-tests?limit=20",
            headers=headers,
        )
        assert list_response.status_code == 200
        listed_ids = {item["id"] for item in list_response.json()}
        assert own_test.id in listed_ids
        assert other_test.id not in listed_ids

        foreign_read_response = client.get(
            f"/api/v1/cardio/blood-tests?patient_id={other_patient.id}",
            headers=headers,
        )
        assert foreign_read_response.status_code == 403

        foreign_write_response = client.post(
            "/api/v1/cardio/blood-tests",
            json={
                "patient_id": other_patient.id,
                "visit_id": other_visit.id,
                "test_date": date.today().isoformat(),
                "cholesterol_total": 260,
                "interpretation": "must not be written",
            },
            headers=headers,
        )
        assert foreign_write_response.status_code == 403

        own_write_response = client.post(
            "/api/v1/cardio/blood-tests",
            json={
                "patient_id": own_patient.id,
                "visit_id": own_visit.id,
                "test_date": date.today().isoformat(),
                "cholesterol_total": 181,
                "interpretation": "owned write",
            },
            headers=headers,
        )
        assert own_write_response.status_code == 201
        assert own_write_response.json()["patient_id"] == own_patient.id

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
            hashed_password=get_password_hash("cardiologist123"),
            role="cardiologist",
            is_active=True,
            is_superuser=False,
        )
        db_session.add(cardiologist)
        db_session.commit()
        db_session.refresh(cardiologist)
        doctor = Doctor(
            user_id=cardiologist.id,
            specialty="cardiology",
            active=True,
        )
        db_session.add(doctor)
        db_session.commit()
        db_session.refresh(doctor)
        test_visit.doctor_id = doctor.id
        db_session.commit()

        login_response = client.post(
            "/api/v1/authentication/login",
            json={
                "username": cardiologist.username,
                "password": "cardiologist123",
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
