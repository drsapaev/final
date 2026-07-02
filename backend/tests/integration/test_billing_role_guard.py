from __future__ import annotations

from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.billing import Invoice
from app.models.patient import Patient


def _create_invoice(db_session: Session, patient: Patient) -> Invoice:
    invoice = Invoice(
        invoice_number=f"TEST-{uuid4().hex[:12]}",
        patient_id=patient.id,
        subtotal=100000,
        total_amount=100000,
        balance=100000,
        description="role guard invoice",
    )
    db_session.add(invoice)
    db_session.commit()
    db_session.refresh(invoice)
    return invoice


def test_admin_can_list_legacy_billing_invoices(
    client: TestClient,
    auth_headers: dict[str, str],
) -> None:
    response = client.get("/api/v1/billing/invoices", headers=auth_headers)

    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_patient_cannot_read_legacy_billing_invoice(
    client: TestClient,
    db_session: Session,
    patient_token: str,
    test_patient: Patient,
) -> None:
    invoice = _create_invoice(db_session, test_patient)

    response = client.get(
        f"/api/v1/billing/invoices/{invoice.id}",
        headers={"Authorization": f"Bearer {patient_token}"},
    )

    assert response.status_code == 403


def test_patient_cannot_update_or_delete_legacy_billing_invoice(
    client: TestClient,
    db_session: Session,
    patient_token: str,
    test_patient: Patient,
) -> None:
    invoice = _create_invoice(db_session, test_patient)
    headers = {"Authorization": f"Bearer {patient_token}"}

    update_response = client.put(
        f"/api/v1/billing/invoices/{invoice.id}",
        json={"notes": "patient should not mutate billing"},
        headers=headers,
    )
    delete_response = client.delete(
        f"/api/v1/billing/invoices/{invoice.id}",
        headers=headers,
    )

    assert update_response.status_code == 403
    assert delete_response.status_code == 403


def test_patient_cannot_run_legacy_billing_wide_actions(
    client: TestClient,
    patient_token: str,
) -> None:
    headers = {"Authorization": f"Bearer {patient_token}"}

    settings_response = client.get("/api/v1/billing/settings", headers=headers)
    reminders_response = client.post("/api/v1/billing/send-reminders", headers=headers)
    payments_response = client.get("/api/v1/billing/payments", headers=headers)

    assert settings_response.status_code == 403
    assert reminders_response.status_code == 403
    assert payments_response.status_code == 403
