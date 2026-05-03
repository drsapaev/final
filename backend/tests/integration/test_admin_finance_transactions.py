from __future__ import annotations

import pytest

from app.models.clinic import Doctor
from app.models.patient import Patient


from tests.auth_test_credentials import (
    ADMIN_PASSWORD,
    REGISTRAR_PASSWORD,
)

def _login_admin(client, admin_user):
    response = client.post(
        "/api/v1/authentication/login",
        json={"username": admin_user.username, "password": ADMIN_PASSWORD},
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _login_registrar(client, registrar_user):
    response = client.post(
        "/api/v1/auth/minimal-login",
        json={"username": registrar_user.username, "password": REGISTRAR_PASSWORD},
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest.mark.integration
def test_admin_finance_transactions_crud_roundtrip(
    client,
    db_session,
    admin_user,
    test_doctor_user,
):
    patient = Patient(
        first_name="Тест",
        last_name="Финансов",
        middle_name="Пациент",
        phone="+998901234567",
        email="finance.patient@test.com",
        birth_date=None,
    )
    doctor = Doctor(
        user_id=test_doctor_user.id,
        specialty="cardiology",
        cabinet="101",
        active=True,
    )
    db_session.add(patient)
    db_session.add(doctor)
    db_session.commit()
    db_session.refresh(patient)
    db_session.refresh(doctor)

    headers = _login_admin(client, admin_user)

    create_response = client.post(
        "/api/v1/admin/finance/transactions",
        json={
            "type": "income",
            "category": "Консультация врача",
            "amount": 150000,
            "description": "Плановая консультация",
            "patient_id": patient.id,
            "doctor_id": doctor.id,
            "payment_method": "cash",
            "status": "pending",
            "transaction_date": "2026-03-27",
            "notes": "QA smoke",
            "reference": "FIN-001",
        },
        headers=headers,
    )

    assert create_response.status_code == 200, create_response.text
    created = create_response.json()
    assert created["type"] == "income"
    assert created["category"] == "Консультация врача"
    assert created["amount"] == 150000
    assert created["patient_id"] == patient.id
    assert created["doctor_id"] == doctor.id
    assert created["patient_name"] == patient.short_name()
    assert created["doctor_name"] == test_doctor_user.full_name
    assert created["status"] == "pending"

    transaction_id = created["id"]

    update_response = client.put(
        f"/api/v1/admin/finance/transactions/{transaction_id}",
        json={
            "status": "completed",
            "notes": "updated",
            "reference": "FIN-001-UPD",
        },
        headers=headers,
    )

    assert update_response.status_code == 200, update_response.text
    updated = update_response.json()
    assert updated["status"] == "completed"
    assert updated["notes"] == "updated"
    assert updated["reference"] == "FIN-001-UPD"

    list_response = client.get(
        "/api/v1/admin/finance/transactions",
        headers=headers,
    )
    assert list_response.status_code == 200, list_response.text
    rows = list_response.json()
    assert len(rows) == 1
    assert rows[0]["id"] == transaction_id

    delete_response = client.delete(
        f"/api/v1/admin/finance/transactions/{transaction_id}",
        headers=headers,
    )
    assert delete_response.status_code == 200, delete_response.text

    final_list_response = client.get(
        "/api/v1/admin/finance/transactions",
        headers=headers,
    )
    assert final_list_response.status_code == 200, final_list_response.text
    assert final_list_response.json() == []


@pytest.mark.integration
def test_admin_finance_transactions_reject_non_admin_access(
    client,
    registrar_user,
):
    headers = _login_registrar(client, registrar_user)
    response = client.get("/api/v1/admin/finance/transactions", headers=headers)
    assert response.status_code == 403, response.text
