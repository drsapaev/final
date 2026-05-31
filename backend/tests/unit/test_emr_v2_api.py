from __future__ import annotations

from datetime import date

import pytest

from app.api.v1.endpoints import emr_v2
from app.core.security import get_password_hash
from app.models.clinic import Doctor
from app.models.emr_v2 import EMRRecord
from app.models.patient import Patient
from app.models.user import User
from app.models.visit import Visit


@pytest.mark.unit
def test_doctor_history_route_is_not_shadowed_by_visit_id(
    client,
    admin_user,
    auth_headers,
    monkeypatch,
):
    def fake_get_history_entries(self, **kwargs):
        return [
            {
                "content": "Chest pain",
                "diagnosis": "I20.0",
                "created_at": "2026-01-01T10:00:00",
            }
        ]

    monkeypatch.setattr(
        emr_v2.EMRDoctorHistoryService,
        "get_history_entries",
        fake_get_history_entries,
    )
    other_doctor_id = admin_user.id + 1000

    response = client.get(
        f"/api/v1/v2/emr/doctor-history?doctor_id={other_doctor_id}&field_name=complaints&specialty=cardiology",
        headers=auth_headers,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["field_name"] == "complaints"
    assert payload["entries"][0]["content"] == "Chest pain"


@pytest.mark.unit
def test_doctor_cannot_save_emr_for_another_doctors_visit(client, db_session):
    attacker_user = User(
        id=9601,
        username="emr_v2_attacker",
        email="emr-v2-attacker@test.com",
        hashed_password=get_password_hash("doctor123"),
        role="Doctor",
        is_active=True,
    )
    victim_user = User(
        id=9603,
        username="emr_v2_victim",
        email="emr-v2-victim@test.com",
        hashed_password=get_password_hash("doctor123"),
        role="Doctor",
        is_active=True,
    )
    attacker_doctor = Doctor(
        id=9602,
        user_id=attacker_user.id,
        specialty="therapy",
        active=True,
    )
    victim_doctor = Doctor(
        id=9604,
        user_id=victim_user.id,
        specialty="therapy",
        active=True,
    )
    patient = Patient(
        first_name="EMR",
        last_name="Owner",
        phone="+998909601000",
        birth_date=date(1990, 1, 1),
    )
    db_session.add_all(
        [attacker_user, victim_user, attacker_doctor, victim_doctor, patient]
    )
    db_session.commit()
    db_session.refresh(patient)

    victim_visit = Visit(
        patient_id=patient.id,
        doctor_id=victim_doctor.id,
        visit_date=date.today(),
        visit_time="13:00",
        status="open",
        department="therapy",
    )
    db_session.add(victim_visit)
    db_session.commit()
    db_session.refresh(victim_visit)

    login_response = client.post(
        "/api/v1/authentication/login",
        json={"username": attacker_user.username, "password": "doctor123"},
    )
    assert login_response.status_code == 200
    headers = {"Authorization": f"Bearer {login_response.json()['access_token']}"}

    response = client.post(
        f"/api/v1/v2/emr/{victim_visit.id}",
        headers=headers,
        json={
            "data": {"complaints": "tampered"},
            "row_version": 0,
            "is_draft": True,
        },
    )

    assert response.status_code == 403, response.text
    assert (
        db_session.query(EMRRecord)
        .filter(EMRRecord.visit_id == victim_visit.id)
        .count()
        == 0
    )


@pytest.mark.unit
@pytest.mark.parametrize(
    ("path_suffix", "payload"),
    [
        ("", {"data": {"complaints": "tampered"}, "row_version": 0, "is_draft": True}),
        ("/sign", {"data": {"complaints": "tampered"}, "row_version": 0}),
        (
            "/amend",
            {
                "data": {"complaints": "tampered"},
                "reason": "Unauthorized lab amendment",
                "row_version": 0,
            },
        ),
        ("/restore", {"target_version": 1, "reason": "Unauthorized lab restore"}),
    ],
)
def test_lab_role_cannot_write_emr_v2_records(
    client,
    db_session,
    path_suffix,
    payload,
):
    label = path_suffix.replace("/", "_") or "_save"
    lab_user = User(
        username=f"emr_v2_lab_writer{label}",
        email=f"emr-v2-lab-writer{label}@test.com",
        hashed_password=get_password_hash("lab123"),
        role="Lab",
        is_active=True,
    )
    doctor_user = User(
        username=f"emr_v2_doctor_owner{label}",
        email=f"emr-v2-doctor-owner{label}@test.com",
        hashed_password=get_password_hash("doctor123"),
        role="Doctor",
        is_active=True,
    )
    doctor = Doctor(
        user_id=doctor_user.id,
        specialty="therapy",
        active=True,
    )
    patient = Patient(
        first_name="EMR",
        last_name="WriteGuard",
        phone=f"+99890965{abs(hash(label)) % 10000:04d}",
        birth_date=date(1990, 1, 1),
    )
    db_session.add_all([lab_user, doctor_user])
    db_session.flush()
    doctor.user_id = doctor_user.id
    db_session.add_all([doctor, patient])
    db_session.commit()
    db_session.refresh(patient)

    visit = Visit(
        patient_id=patient.id,
        doctor_id=doctor.id,
        visit_date=date.today(),
        visit_time="16:00",
        status="open",
        department="therapy",
    )
    db_session.add(visit)
    db_session.commit()
    db_session.refresh(visit)

    login_response = client.post(
        "/api/v1/authentication/login",
        json={"username": lab_user.username, "password": "lab123"},
    )
    assert login_response.status_code == 200
    headers = {"Authorization": f"Bearer {login_response.json()['access_token']}"}

    response = client.post(
        f"/api/v1/v2/emr/{visit.id}{path_suffix}",
        headers=headers,
        json=payload,
    )

    assert response.status_code == 403, response.text
    assert (
        db_session.query(EMRRecord)
        .filter(EMRRecord.visit_id == visit.id)
        .count()
        == 0
    )


@pytest.mark.unit
def test_patient_emr_history_filters_other_doctors_summaries(client, db_session):
    attacker_user = User(
        id=9701,
        username="emr_history_attacker",
        email="emr-history-attacker@test.com",
        hashed_password=get_password_hash("doctor123"),
        role="Doctor",
        is_active=True,
    )
    victim_user = User(
        id=9703,
        username="emr_history_victim",
        email="emr-history-victim@test.com",
        hashed_password=get_password_hash("doctor123"),
        role="Doctor",
        is_active=True,
    )
    attacker_doctor = Doctor(
        id=9702,
        user_id=attacker_user.id,
        specialty="therapy",
        active=True,
    )
    victim_doctor = Doctor(
        id=9704,
        user_id=victim_user.id,
        specialty="therapy",
        active=True,
    )
    patient = Patient(
        first_name="Shared",
        last_name="Patient",
        phone="+998909701000",
        birth_date=date(1990, 1, 1),
    )
    db_session.add_all(
        [attacker_user, victim_user, attacker_doctor, victim_doctor, patient]
    )
    db_session.commit()
    db_session.refresh(patient)

    attacker_visit = Visit(
        patient_id=patient.id,
        doctor_id=attacker_doctor.id,
        visit_date=date.today(),
        visit_time="14:00",
        status="open",
        department="therapy",
    )
    victim_visit = Visit(
        patient_id=patient.id,
        doctor_id=victim_doctor.id,
        visit_date=date.today(),
        visit_time="15:00",
        status="open",
        department="therapy",
    )
    db_session.add_all([attacker_visit, victim_visit])
    db_session.commit()
    db_session.refresh(attacker_visit)
    db_session.refresh(victim_visit)

    attacker_emr = EMRRecord(
        patient_id=patient.id,
        visit_id=attacker_visit.id,
        version=1,
        data={"complaints": "own"},
        status="draft",
        created_by=attacker_user.id,
        row_version=1,
    )
    victim_emr = EMRRecord(
        patient_id=patient.id,
        visit_id=victim_visit.id,
        version=1,
        data={"complaints": "private"},
        status="draft",
        created_by=victim_user.id,
        row_version=1,
    )
    db_session.add_all([attacker_emr, victim_emr])
    db_session.commit()
    db_session.refresh(attacker_emr)
    db_session.refresh(victim_emr)

    login_response = client.post(
        "/api/v1/authentication/login",
        json={"username": attacker_user.username, "password": "doctor123"},
    )
    assert login_response.status_code == 200
    headers = {"Authorization": f"Bearer {login_response.json()['access_token']}"}

    response = client.get(
        f"/api/v1/v2/emr/patient/{patient.id}",
        headers=headers,
    )

    assert response.status_code == 200, response.text
    visit_ids = {item["visit_id"] for item in response.json()}
    assert attacker_visit.id in visit_ids
    assert victim_visit.id not in visit_ids
