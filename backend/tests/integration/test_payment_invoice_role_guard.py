from __future__ import annotations

from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.enums import PaymentStatus
from app.models.payment_invoice import PaymentInvoice


def test_registrar_can_create_and_list_payment_invoices(
    client: TestClient,
    registrar_auth_headers: dict[str, str],
) -> None:
    create_response = client.post(
        "/api/v1/payments/invoice/create",
        headers=registrar_auth_headers,
        json={
            "amount": 100000,
            "currency": "UZS",
            "provider": "click",
            "description": "registrar payment invoice",
        },
    )
    list_response = client.get(
        "/api/v1/payments/invoices/pending",
        headers=registrar_auth_headers,
    )

    assert create_response.status_code == 200
    assert create_response.json()["amount"] == 100000.0
    assert list_response.status_code == 200
    assert any(
        invoice["invoice_id"] == create_response.json()["invoice_id"]
        for invoice in list_response.json()
    )


def test_patient_cannot_create_payment_invoice_for_arbitrary_patient(
    client: TestClient,
    db_session: Session,
    patient_token: str,
) -> None:
    before_count = db_session.query(PaymentInvoice).count()

    response = client.post(
        "/api/v1/payments/invoice/create",
        headers={"Authorization": f"Bearer {patient_token}"},
        json={
            "amount": 250000,
            "currency": "UZS",
            "provider": "click",
            "description": "patient should not create invoice",
            "patient_info": {"patient_id": 999999},
        },
    )

    assert response.status_code == 403
    assert db_session.query(PaymentInvoice).count() == before_count


def test_patient_cannot_list_pending_payment_invoices(
    client: TestClient,
    db_session: Session,
    patient_token: str,
) -> None:
    db_session.add(
        PaymentInvoice(
            patient_id=12345,
            total_amount=Decimal("50000.00"),
            currency="UZS",
            provider="click",
            status=PaymentStatus.PENDING.value,
            payment_method="click",
            notes="pending invoice not visible to patient role",
        )
    )
    db_session.commit()

    response = client.get(
        "/api/v1/payments/invoices/pending",
        headers={"Authorization": f"Bearer {patient_token}"},
    )

    assert response.status_code == 403
