"""Unapproved legacy benefit modes cannot create or quote zero prices."""
from datetime import date
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from app.models.payment_invoice import PaymentInvoice
from app.models.service import Service
from app.models.visit import Visit
from app.services.registrar_edit_delta_service import RegistrarEditDeltaService


@pytest.mark.parametrize("mode", ["benefit", "BENEFIT", " benefit "])
def test_cart_fails_before_any_creation_even_without_quote(
    client, db_session, admin_auth_headers, test_patient, mode,
):
    before_visits = db_session.query(Visit).count()
    before_invoices = db_session.query(PaymentInvoice).count()
    response = client.post("/api/v1/registrar/cart", headers=admin_auth_headers, json={
        "patient_id": test_patient.id, "discount_mode": mode,
        "visits": [{"visit_date": "2099-01-01", "services": [{"service_id": 999, "quantity": 1}]}],
    })
    assert response.status_code == 409
    assert "подтверждение администратора" in response.json()["detail"]
    assert db_session.query(Visit).count() == before_visits
    assert db_session.query(PaymentInvoice).count() == before_invoices


@pytest.mark.parametrize("pricing_mode", ["cart", "edit_delta", "full_update"])
def test_benefit_quote_is_unavailable_without_admin_approval(client, admin_auth_headers, pricing_mode):
    response = client.post("/api/v1/registrar/cart/quote", headers=admin_auth_headers, json={
        "items": [{"service_id": 999, "quantity": 1}], "discount_mode": "benefit", "pricing_mode": pricing_mode,
    })
    assert response.status_code == 409
    assert "подтверждение администратора" in response.json()["detail"]


def test_edit_delta_no_quote_token_fails_before_patient_mutation(client, db_session, admin_auth_headers, test_patient):
    name_before = test_patient.first_name
    response = client.post("/api/v1/registrar/cart/edit-delta", headers=admin_auth_headers, json={
        "patient_id": test_patient.id, "discount_mode": "benefit", "services": [],
        "patient_data": {"full_name": "SYNTHETIC SHOULD NOT SAVE"},
    })
    assert response.status_code == 409
    db_session.refresh(test_patient)
    assert test_patient.first_name == name_before


def test_direct_edit_delta_cannot_bypass_guard():
    db = MagicMock()
    with pytest.raises(HTTPException) as error:
        RegistrarEditDeltaService(db).apply(patient_id=1, services=[], target_date=date(2099, 1, 1),
                                            payment_method="cash", discount_mode="benefit", all_free=False)
    assert error.value.status_code == 409
    db.query.assert_not_called()


@pytest.mark.parametrize("visit_type,mode", [("benefit", "none"), ("paid", "benefit")])
def test_qr_full_update_no_token_fails_before_entry_read(client, admin_auth_headers, visit_type, mode):
    response = client.put("/api/v1/queue/online-entry/999999/full-update", headers=admin_auth_headers, json={
        "patient_data": {}, "visit_type": visit_type, "discount_mode": mode, "services": [],
    })
    assert response.status_code == 409
    assert "подтверждение администратора" in response.json()["detail"]


def test_all_free_precedence_and_regular_quote_are_preserved(client, db_session, admin_auth_headers):
    service = Service(code="SYNTHETIC-BENEFIT-GUARD", name="SYNTHETIC", price=100,
                      active=True, requires_doctor=False, is_consultation=True)
    db_session.add(service)
    db_session.commit()
    items = [{"service_id": service.id, "quantity": 1}]
    normal = client.post("/api/v1/registrar/cart/quote", headers=admin_auth_headers,
                         json={"items": items, "discount_mode": "none"})
    assert normal.status_code == 200, normal.text
    assert float(normal.json()["total_amount"]) == 100
    all_free = client.post("/api/v1/registrar/cart/quote", headers=admin_auth_headers,
                           json={"items": items, "discount_mode": "benefit", "all_free": True})
    assert all_free.status_code == 200, all_free.text
    assert float(all_free.json()["total_amount"]) == 0
    no_entry = client.put("/api/v1/queue/online-entry/999999/full-update", headers=admin_auth_headers, json={
        "patient_data": {}, "visit_type": "benefit", "discount_mode": "all_free", "services": [],
    })
    assert no_entry.status_code == 404
