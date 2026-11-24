"""Synthetic cashier requests retain the locked server quote currency."""
from __future__ import annotations

from decimal import Decimal
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.api.v1.endpoints.cashier import _payments, _visits
from app.models.encounter import Encounter
from app.models.payment import Payment
from app.models.visit import Visit, VisitService


def _visit(db, patient, service, currency, *, amount="10.00"):
    encounter = Encounter(patient_id=patient.id, provenance="new")
    db.add(encounter)
    db.flush()
    visit = Visit(patient_id=patient.id, encounter_id=encounter.id,
                  status="open", confirmation_context_epoch=1)
    db.add(visit)
    db.flush()
    db.add(VisitService(visit_id=visit.id, service_id=service.id, name="SYNTHETIC",
                        qty=1, price=Decimal(amount), currency=currency))
    db.commit()
    return visit


@pytest.mark.xfail(strict=True, reason="USD cashier UI, responses, receipts and statistics must carry currency before enabling")
@pytest.mark.parametrize("route", ["single", "mark_paid"])
def test_usd_single_payment_uses_server_currency(client, db_session, admin_auth_headers,
                                                 test_patient, test_service, monkeypatch, route):
    visit = _visit(db_session, test_patient, test_service, "USD")
    monkeypatch.setattr(_visits, "_emit_payment_notification", AsyncMock())
    monkeypatch.setattr(_payments, "_emit_payment_notification", AsyncMock())
    if route == "single":
        response = client.post("/api/v1/cashier/payments", headers=admin_auth_headers,
                               json={"visit_id": visit.id, "amount": "10.00", "method": "cash"})
    else:
        response = client.post(f"/api/v1/cashier/visits/{visit.id}/mark-paid", headers=admin_auth_headers)
    assert response.status_code == 200, response.text
    assert db_session.query(Payment).filter_by(visit_id=visit.id, status="paid").one().currency == "USD"


@pytest.mark.xfail(strict=True, reason="USD cashier UI, responses, receipts and statistics must carry currency before enabling")
def test_usd_grouped_payment_preserves_currency_for_each_leg(client, db_session, admin_auth_headers,
                                                               test_patient, test_service, monkeypatch):
    monkeypatch.setattr(_payments, "_emit_payment_notification", AsyncMock())
    visits = [_visit(db_session, test_patient, test_service, "USD") for _ in range(2)]
    response = client.post("/api/v1/cashier/payments/grouped", headers=admin_auth_headers,
                           json={"visit_ids": [visit.id for visit in visits], "amount": "20.00", "method": "cash"})
    assert response.status_code == 200, response.text
    rows = db_session.query(Payment).filter(Payment.visit_id.in_([visit.id for visit in visits])).all()
    assert len(rows) == 2 and all(row.currency == "USD" for row in rows)


@pytest.mark.parametrize("route", ["single", "grouped", "mark_paid"])
def test_non_uzs_cashier_is_blocked_until_the_ui_displays_currency(
    client, db_session, admin_auth_headers, test_patient, test_service, route,
):
    visit = _visit(db_session, test_patient, test_service, "USD")
    if route == "single":
        response = client.post("/api/v1/cashier/payments", headers=admin_auth_headers,
                               json={"visit_id": visit.id, "amount": "10.00", "method": "cash"})
    elif route == "grouped":
        response = client.post("/api/v1/cashier/payments/grouped", headers=admin_auth_headers,
                               json={"visit_ids": [visit.id], "amount": "10.00", "method": "cash"})
    else:
        response = client.post(f"/api/v1/cashier/visits/{visit.id}/mark-paid", headers=admin_auth_headers)
    assert response.status_code == 409
    assert db_session.query(Payment).filter_by(visit_id=visit.id).count() == 0


@pytest.mark.parametrize("currencies", [("USD", "UZS"), ("USD", None)])
def test_grouped_mixed_or_unknown_currency_cannot_create_payment(client, db_session, admin_auth_headers,
                                                                 test_patient, test_service, currencies):
    visits = [_visit(db_session, test_patient, test_service, value) for value in currencies]
    response = client.post("/api/v1/cashier/payments/grouped", headers=admin_auth_headers,
                           json={"visit_ids": [visit.id for visit in visits], "amount": "20.00", "method": "cash"})
    assert response.status_code == 409, response.text
    assert db_session.query(Payment).filter(Payment.visit_id.in_([visit.id for visit in visits])).count() == 0


@pytest.mark.parametrize("stored, expected", [("USD", "USD"), ("UZS", "UZS"), ("bad", None), ("", None)])
def test_payment_reads_expose_stored_currency_or_unknown(
    client, db_session, admin_auth_headers, test_patient, test_service, stored, expected,
):
    visit = _visit(db_session, test_patient, test_service, "UZS")
    payment = Payment(visit_id=visit.id, amount=Decimal("10.00"), currency=stored,
                      method="cash", status="paid")
    db_session.add(payment)
    db_session.commit()
    detail = client.get(f"/api/v1/cashier/payments/{payment.id}", headers=admin_auth_headers)
    assert detail.status_code == 200, detail.text
    assert detail.json()["currency"] == expected
    history = client.get("/api/v1/cashier/payments", headers=admin_auth_headers)
    assert history.status_code == 200, history.text
    assert next(row for row in history.json()["items"] if row["id"] == payment.id)["currency"] == expected


@pytest.mark.parametrize("route", ["single", "grouped"])
def test_payment_currency_survives_idempotent_replay(
    client, db_session, admin_auth_headers, test_patient, test_service, monkeypatch, route,
):
    monkeypatch.setattr(_payments, "_emit_payment_notification", AsyncMock())
    visit = _visit(db_session, test_patient, test_service, "UZS")
    payload = {"amount": "10.00", "method": "cash", "client_request_id": str(uuid4())}
    if route == "single":
        payload["visit_id"] = visit.id
        path = "/api/v1/cashier/payments"
    else:
        payload["visit_ids"] = [visit.id]
        path = "/api/v1/cashier/payments/grouped"
    first = client.post(path, headers=admin_auth_headers, json=payload)
    assert first.status_code == 200, first.text
    assert first.json()["currency"] == "UZS"
    if route == "grouped":
        assert first.json()["payments"][0]["currency"] == "UZS"
    replay = client.post(path, headers=admin_auth_headers, json=payload)
    assert replay.status_code == 200, replay.text
    assert replay.json() == first.json()


def test_refund_response_uses_original_payment_currency(
    client, db_session, admin_auth_headers, test_patient, test_service, monkeypatch,
):
    monkeypatch.setattr(_payments, "_emit_payment_notification", AsyncMock())
    visit = _visit(db_session, test_patient, test_service, "USD")
    payment = Payment(visit_id=visit.id, amount=Decimal("10.00"), currency="USD",
                      method="cash", status="paid")
    db_session.add(payment)
    db_session.commit()
    response = client.post(f"/api/v1/cashier/payments/{payment.id}/refund",
                           headers=admin_auth_headers,
                           json={"amount": "1.25", "reason": "synthetic refund", "client_request_id": str(uuid4())})
    assert response.status_code == 200, response.text
    assert response.json()["currency"] == "USD"
    assert Decimal(response.json()["refunded_amount"]) == Decimal("1.25")
