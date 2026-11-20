from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.billing import Invoice, InvoiceStatus
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


@pytest.mark.parametrize("status", ["paid", "partially_paid", "refunded", None])
def test_admin_cannot_assign_a_financial_invoice_status(client, db_session, admin_auth_headers, test_patient, status):
    invoice = _create_invoice(db_session, test_patient)
    response = client.put(
        f"/api/v1/billing/invoices/{invoice.id}",
        headers=admin_auth_headers,
        json={"status": status, "notes": "Synthetic unchanged on conflict"},
    )
    assert response.status_code == 409, response.text
    db_session.expire_all()
    assert invoice.status == InvoiceStatus.DRAFT
    assert invoice.notes is None and invoice.paid_amount == 0


def test_admin_can_edit_unpaid_invoice_metadata_and_workflow_status(client, db_session, admin_auth_headers, test_patient):
    invoice = _create_invoice(db_session, test_patient)
    response = client.put(
        f"/api/v1/billing/invoices/{invoice.id}",
        headers=admin_auth_headers,
        json={"status": "pending", "notes": "Synthetic updated note"},
    )
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "pending" and response.json()["paid_amount"] == 0
    assert response.json()["notes"] == "Synthetic updated note"


def test_admin_cannot_delete_legacy_draft_with_recorded_money(client, db_session, admin_auth_headers, test_patient):
    invoice = _create_invoice(db_session, test_patient)
    invoice.paid_amount = 1
    db_session.commit()
    invoice_id = invoice.id
    response = client.delete(f"/api/v1/billing/invoices/{invoice_id}", headers=admin_auth_headers)
    assert response.status_code == 400, response.text
    assert db_session.get(Invoice, invoice_id).paid_amount == 1


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
