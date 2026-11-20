"""Synthetic cashier HTTP checks for authoritative zero-priced service rows."""
from decimal import Decimal
from unittest.mock import AsyncMock

import pytest

from app.api.v1.endpoints.cashier import _payments, _visits
from app.models.payment import Payment
from app.models.visit import Visit, VisitService


@pytest.fixture
def quiet_notifications(monkeypatch):
    monkeypatch.setattr(_payments, "_emit_payment_notification", AsyncMock())
    monkeypatch.setattr(_visits, "_emit_payment_notification", AsyncMock())


def _visit(db, patient_id, price, qty):
    visit = Visit(patient_id=patient_id, status="open", discount_mode="none", confirmation_context_epoch=1)
    db.add(visit)
    db.flush()
    db.add(VisitService(visit_id=visit.id, service_id=123, name="Synthetic service", qty=qty, price=price, currency="UZS"))
    db.commit()
    return visit


def test_mark_paid_free_and_multiple_units(client, db_session, admin_auth_headers, test_patient, quiet_notifications):
    free = _visit(db_session, test_patient.id, Decimal("0.00"), 3)
    paid = _visit(db_session, test_patient.id, Decimal("0.07"), 3)
    result = client.post(f"/api/v1/cashier/visits/{free.id}/mark-paid", headers=admin_auth_headers)
    assert result.status_code == 200, result.text
    assert Decimal(str(result.json()["amount"])) == Decimal("0.00")
    assert db_session.query(Payment).filter_by(visit_id=free.id).count() == 0
    # The HTTP fixture shares a Session. The real request dependency closes
    # the read-only zero-total transaction before the next request.
    db_session.rollback()
    result = client.post(f"/api/v1/cashier/visits/{paid.id}/mark-paid", headers=admin_auth_headers)
    assert result.status_code == 200, result.text
    assert Decimal(str(result.json()["amount"])) == Decimal("0.21")
    receipt = db_session.query(Payment).filter_by(visit_id=paid.id).one()
    assert receipt.amount == Decimal("0.21")


def test_grouped_payment_does_not_charge_zero_service(client, db_session, admin_auth_headers, test_patient, quiet_notifications):
    free = _visit(db_session, test_patient.id, Decimal("0.00"), 3)
    paid = _visit(db_session, test_patient.id, Decimal("0.07"), 3)
    response = client.post("/api/v1/cashier/payments/grouped", headers=admin_auth_headers,
                           json={"patient_id": test_patient.id, "visit_ids": [free.id, paid.id], "amount": "0.21", "method": "cash"})
    assert response.status_code == 200, response.text
    assert db_session.query(Payment).filter_by(visit_id=free.id).count() == 0
    assert db_session.query(Payment).filter_by(visit_id=paid.id).one().amount == Decimal("0.21")


def test_pending_list_displays_exact_qty_including_free_lines(client, db_session, admin_auth_headers, test_patient):
    free = _visit(db_session, test_patient.id, Decimal("0.00"), 3)
    paid = _visit(db_session, test_patient.id, Decimal("0.07"), 3)
    response = client.get("/api/v1/cashier/pending-payments", headers=admin_auth_headers)
    assert response.status_code == 200, response.text
    item = next(item for item in response.json()["items"] if item["patient_id"] == test_patient.id)
    assert set(item["visit_ids"]) == {free.id, paid.id}
    assert Decimal(str(item["total_amount"])) == Decimal("0.21")
    assert next(s for s in item["services"] if s["visit_id"] == free.id)["quantity"] == 3


@pytest.mark.parametrize("endpoint", ["single", "grouped", "pending"])
def test_invalid_persisted_price_fails_closed_without_receipt(client, db_session, admin_auth_headers, test_patient, endpoint, quiet_notifications):
    bad = _visit(db_session, test_patient.id, None, 2)
    if endpoint == "single":
        response = client.post(f"/api/v1/cashier/visits/{bad.id}/mark-paid", headers=admin_auth_headers)
    elif endpoint == "grouped":
        valid = _visit(db_session, test_patient.id, Decimal("10.00"), 1)
        response = client.post("/api/v1/cashier/payments/grouped", headers=admin_auth_headers,
                               json={"patient_id": test_patient.id, "visit_ids": [bad.id, valid.id], "amount": "1.00", "method": "cash"})
    else:
        response = client.get("/api/v1/cashier/pending-payments", headers=admin_auth_headers)
    assert response.status_code == 409, response.text
    assert db_session.query(Payment).count() == 0


def test_direct_payment_cannot_charge_zero_service(client, db_session, admin_auth_headers, test_patient, quiet_notifications):
    visit = _visit(db_session, test_patient.id, Decimal("0.00"), 3)
    response = client.post("/api/v1/cashier/payments", headers=admin_auth_headers,
                           json={"visit_id": visit.id, "patient_id": test_patient.id, "amount": "0.01", "method": "cash"})
    assert response.status_code == 400, response.text
    assert db_session.query(Payment).filter_by(visit_id=visit.id).count() == 0


@pytest.mark.parametrize("endpoint", ["single", "grouped", "pending"])
def test_invalid_persisted_quantity_fails_closed(client, db_session, admin_auth_headers, test_patient, endpoint, quiet_notifications):
    bad = _visit(db_session, test_patient.id, Decimal("0.07"), 0)
    if endpoint == "single":
        response = client.post(f"/api/v1/cashier/visits/{bad.id}/mark-paid", headers=admin_auth_headers)
    elif endpoint == "grouped":
        valid = _visit(db_session, test_patient.id, Decimal("1.00"), 1)
        response = client.post("/api/v1/cashier/payments/grouped", headers=admin_auth_headers,
                               json={"patient_id": test_patient.id, "visit_ids": [bad.id, valid.id], "amount": "1.00", "method": "cash"})
    else:
        response = client.get("/api/v1/cashier/pending-payments", headers=admin_auth_headers)
    assert response.status_code == 409, response.text
    assert db_session.query(Payment).count() == 0
