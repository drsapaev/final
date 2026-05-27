from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import uuid4

from app.core.security import get_password_hash
from app.models.patient import Patient
from app.models.payment import Payment
from app.models.user import User
from app.models.visit import Visit


def _suffix() -> str:
    return uuid4().hex[:10]


def _create_patient_user(db_session, *, label: str) -> tuple[User, Patient]:
    suffix = _suffix()
    user = User(
        username=f"payment_patient_{label}_{suffix}",
        email=f"payment-patient-{label}-{suffix}@test.local",
        hashed_password=get_password_hash("patient123"),
        role="Patient",
        is_active=True,
        is_superuser=False,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    patient = Patient(
        user_id=user.id,
        first_name="Payment",
        last_name=f"Patient{label}{suffix}",
        phone=f"+99893{suffix[:7]}",
        birth_date=date(1990, 1, 1),
    )
    db_session.add(patient)
    db_session.commit()
    db_session.refresh(patient)
    return user, patient


def _create_payment(db_session, *, patient: Patient) -> Payment:
    visit = Visit(
        patient_id=patient.id,
        visit_date=date.today(),
        status="open",
        source="desk",
    )
    db_session.add(visit)
    db_session.commit()
    db_session.refresh(visit)

    payment = Payment(
        visit_id=visit.id,
        amount=Decimal("125000.00"),
        currency="UZS",
        method="online",
        status="paid",
        provider="click",
        provider_payment_id=f"provider-{_suffix()}",
        provider_data={"private": "payload"},
    )
    db_session.add(payment)
    db_session.commit()
    db_session.refresh(payment)
    return payment


def _patient_headers(client, user: User) -> dict[str, str]:
    response = client.post(
        "/api/v1/authentication/login",
        json={"username": user.username, "password": "patient123"},
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_patient_payment_reads_are_limited_to_own_visit(client, db_session) -> None:
    own_user, own_patient = _create_patient_user(db_session, label="own")
    _other_user, other_patient = _create_patient_user(db_session, label="other")
    own_payment = _create_payment(db_session, patient=own_patient)
    other_payment = _create_payment(db_session, patient=other_patient)
    headers = _patient_headers(client, own_user)

    own_response = client.get(f"/api/v1/payments/{own_payment.id}", headers=headers)
    assert own_response.status_code == 200, own_response.text
    assert own_response.json()["payment_id"] == own_payment.id

    status_response = client.get(f"/api/v1/payments/{other_payment.id}", headers=headers)
    assert status_response.status_code == 403

    receipt_response = client.get(
        f"/api/v1/payments/{other_payment.id}/receipt",
        headers=headers,
    )
    assert receipt_response.status_code == 403
