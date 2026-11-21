from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.v1.endpoints.billing import InvoiceResponse
from app.models.billing import (
    BillingSettings,
    Invoice,
    InvoiceItem,
    InvoiceStatus,
    PaymentReminder,
    RecurrenceType,
)
from app.models.patient import Patient
from app.models.payment import Payment


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


def test_invoice_and_recurrence_roll_back_when_reminder_staging_fails(
    client, db_session, admin_auth_headers, test_patient,
):
    settings = BillingSettings(next_invoice_number=17, reminder_days_before="7", reminder_days_after="invalid")
    db_session.add(settings)
    db_session.commit()
    url = "/api/v1/billing/invoices"
    payload = {
        "patient_id": test_patient.id,
        "items": [{"description": "Synthetic consultation", "quantity": 1, "unit_price": 25}],
        "is_recurring": True,
        "recurrence_type": "weekly",
        "recurrence_interval": 2,
        "send_reminders": True,
    }

    rejected = client.post(url, headers=admin_auth_headers, json=payload)
    assert rejected.status_code == 400, rejected.text
    assert db_session.query(Invoice).count() == 0
    assert db_session.query(InvoiceItem).count() == 0
    assert db_session.query(PaymentReminder).count() == 0
    assert db_session.query(BillingSettings.next_invoice_number).scalar() == 17

    settings.reminder_days_after = "1"
    db_session.commit()
    created = client.post(url, headers=admin_auth_headers, json=payload)
    assert created.status_code == 200, created.text
    db_session.expire_all()
    invoice = db_session.query(Invoice).one()
    assert created.json()["id"] == invoice.id
    assert invoice.is_recurring and invoice.next_invoice_date == invoice.issue_date + timedelta(days=14)
    assert invoice.invoice_number.endswith("-000017") and invoice.total_amount == 25
    assert db_session.query(InvoiceItem).one().invoice_id == invoice.id
    assert len(db_session.query(PaymentReminder).filter_by(invoice_id=invoice.id).all()) == 2
    assert db_session.query(BillingSettings.next_invoice_number).scalar() == 18


def test_invoice_response_error_rolls_back_first_time_settings(
    client, db_session, admin_auth_headers, test_patient, monkeypatch,
):
    validate = InvoiceResponse.model_validate

    def invalid_invoice_response(_invoice):
        return validate({})

    monkeypatch.setattr(InvoiceResponse, "model_validate", invalid_invoice_response)
    response = client.post(
        "/api/v1/billing/invoices",
        headers=admin_auth_headers,
        json={
            "patient_id": test_patient.id,
            "items": [{"description": "Synthetic consultation", "quantity": 1, "unit_price": 25}],
        },
    )
    assert response.status_code == 500, response.text
    assert db_session.query(Invoice).count() == 0
    assert db_session.query(InvoiceItem).count() == 0
    assert db_session.query(PaymentReminder).count() == 0
    assert db_session.query(BillingSettings).count() == 0


def test_recurring_processing_advances_existing_counter_and_skips_invalid_parent(
    client, db_session, admin_auth_headers, test_patient,
):
    due = datetime.now(UTC).replace(tzinfo=None) - timedelta(hours=12)
    settings = BillingSettings(invoice_number_format="SYN-{number:06d}", next_invoice_number=17)
    invalid = Invoice(
        invoice_number="SYN-INVALID-PARENT", patient_id=test_patient.id,
        is_recurring=True, recurrence_type=RecurrenceType.DAILY,
        recurrence_interval=0, next_invoice_date=due,
    )
    parents = [
        Invoice(
            invoice_number=f"SYN-PARENT-{i}", patient_id=test_patient.id, total_amount=10,
            is_recurring=True, recurrence_type=RecurrenceType.WEEKLY,
            recurrence_interval=1, next_invoice_date=due,
        )
        for i in range(2)
    ]
    db_session.add_all([settings, invalid, *parents])
    db_session.flush()
    db_session.add(Invoice(
        invoice_number="SYN-000017", patient_id=test_patient.id, parent_invoice_id=parents[0].id,
    ))
    db_session.commit()

    for _ in range(2):
        response = client.post("/api/v1/billing/process-recurring", headers=admin_auth_headers)
        assert response.status_code == 200, response.text

    db_session.expire_all()
    children = db_session.query(Invoice).filter(Invoice.parent_invoice_id.is_not(None)).order_by(Invoice.id).all()
    assert [child.invoice_number for child in children] == ["SYN-000017", "SYN-000018", "SYN-000019"]
    assert [child.parent_invoice_id for child in children[1:]] == [parent.id for parent in parents]
    assert all(parent.next_invoice_date == due + timedelta(weeks=1) for parent in parents)
    assert invalid.next_invoice_date == due and settings.next_invoice_number == 20


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


def test_billing_analytics_includes_the_end_date_and_filters_the_breakdown(
    client, db_session, admin_auth_headers, test_patient, test_visit,
):
    inside = _create_invoice(db_session, test_patient)
    outside = _create_invoice(db_session, test_patient)
    day = date(2031, 3, 4)
    midday = datetime(2031, 3, 4, 12, 30)
    inside.issue_date = midday
    inside.status = InvoiceStatus.PENDING
    outside.issue_date = midday + timedelta(days=1)
    outside.status = InvoiceStatus.OVERDUE
    db_session.add_all([
        Payment(visit_id=test_visit.id, amount=Decimal("15.25"), currency="USD",
                status="refunded", created_at=midday.replace(tzinfo=UTC)),
        Payment(visit_id=test_visit.id, amount=Decimal("90.50"),
                created_at=(midday + timedelta(days=1)).replace(tzinfo=UTC)),
    ])
    db_session.commit()
    response = client.get(
        "/api/v1/billing/analytics", headers=admin_auth_headers,
        params={"date_from": day.isoformat(), "date_to": day.isoformat()},
    )
    assert response.status_code == 200, response.text
    report = response.json()
    assert report["summary"]["total_invoices"] == 1
    assert report["summary"]["total_payments"] == 1
    assert report["summary"]["payments_amount"] == "15.25"
    assert [entry["status"] for entry in report["status_breakdown"]] == ["pending"]

    period = {"date_from": day.isoformat(), "date_to": day.isoformat()}
    invoices = client.get("/api/v1/billing/invoices", headers=admin_auth_headers, params=period)
    assert invoices.status_code == 200, invoices.text
    assert [row["id"] for row in invoices.json()] == [inside.id]
    payments = client.get("/api/v1/billing/payments", headers=admin_auth_headers, params=period)
    assert payments.status_code == 200, payments.text
    [payment] = payments.json()
    assert payment["visit_id"] == test_visit.id and payment["paid_at"] is None
    assert payment["amount"] == 15.25 and payment["currency"] == "USD" and payment["status"] == "refunded"


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
