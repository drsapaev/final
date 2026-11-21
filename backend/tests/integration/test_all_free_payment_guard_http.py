"""Synthetic HTTP checks: pending all-free must not start a payment."""
from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

from app.api.v1.endpoints import payments
from app.api.v1.endpoints.cashier import _visits
from app.models.all_free_request import AllFreeRequest
from app.models.encounter import Encounter
from app.models.payment import Payment
from app.models.visit import Visit, VisitService
from app.services.payment_invariant_service import PaymentInvariantService


def _visit(db, patient, actor, *, status="pending", amount=Decimal("0.00")):
    encounter = Encounter(patient_id=patient.id, provenance="new")
    db.add(encounter)
    db.flush()
    visit = Visit(patient_id=patient.id, encounter_id=encounter.id, status="pending_confirmation", confirmation_context_epoch=7)
    db.add(visit)
    db.flush()
    db.add(VisitService(visit_id=visit.id, service_id=123, name="Synthetic", price=amount, qty=2, currency="UZS"))
    if status is not None:
        db.add(AllFreeRequest(
            visit_id=visit.id, patient_id=patient.id, encounter_id=encounter.id,
            visit_id_snapshot=visit.id, patient_id_snapshot=patient.id, encounter_id_snapshot=encounter.id,
            visit_context_epoch=7, encounter_generation=encounter.generation, baseline_total=amount * 2,
            status=status, requested_by_user_id=actor.id, requested_by_user_id_snapshot=actor.id,
            requested_by_role_snapshot="Admin", policy_auto_approve=False,
            **({"decision_kind": "admin", "decided_by_user_id": actor.id,
                "decided_by_user_id_snapshot": actor.id, "decided_by_role_snapshot": "Admin",
                "decided_at": datetime.now(UTC)} if status == "rejected" else {}),
        ))
    db.commit()
    return visit


@pytest.mark.parametrize("endpoint", ["mark_paid", "init", "test_init"])
def test_pending_blocks_before_payment_and_external_provider(client, db_session, admin_auth_headers, admin_user, test_patient, monkeypatch, endpoint):
    visit = _visit(db_session, test_patient, admin_user)
    manager = MagicMock()
    manager.get_providers_for_currency.return_value = ["payme"]
    monkeypatch.setattr(payments, "get_payment_manager", lambda: manager)
    monkeypatch.setattr(payments.settings, "ENABLE_TEST_PAYMENT_INIT", True)
    monkeypatch.setattr(_visits, "_emit_payment_notification", AsyncMock())
    if endpoint == "mark_paid":
        response = client.post(f"/api/v1/cashier/visits/{visit.id}/mark-paid", headers=admin_auth_headers)
    else:
        path = "/api/v1/payments/init" if endpoint == "init" else "/api/v1/payments/test-init"
        response = client.post(path, headers=admin_auth_headers,
                               json={"visit_id": visit.id, "provider": "payme", "amount": 1, "currency": "UZS"})
    assert response.status_code == 409, response.text
    assert db_session.query(Payment).filter_by(visit_id=visit.id).count() == 0
    manager.create_payment.assert_not_called()


@pytest.mark.parametrize("endpoint", ["init", "test_init"])
@pytest.mark.parametrize("status", [403, 409, 503])
def test_payment_init_preserves_preflight_http_error_without_provider_call(
    client, db_session, admin_auth_headers, admin_user, test_patient, monkeypatch, endpoint, status
):
    visit = _visit(db_session, test_patient, admin_user, status=None, amount=Decimal("1.00"))
    manager = MagicMock()
    manager.get_providers_for_currency.return_value = ["payme"]
    monkeypatch.setattr(payments, "get_payment_manager", lambda: manager)
    monkeypatch.setattr(payments.settings, "ENABLE_TEST_PAYMENT_INIT", True)
    def fail_preflight(_self, _ids):
        raise HTTPException(status_code=status, detail={"reason": "synthetic_preflight"})
    monkeypatch.setattr(PaymentInvariantService, "preflight_payment_groups", fail_preflight)
    path = "/api/v1/payments/init" if endpoint == "init" else "/api/v1/payments/test-init"
    response = client.post(path, headers=admin_auth_headers,
                           json={"visit_id": visit.id, "provider": "payme", "amount": 1, "currency": "UZS"})
    assert response.status_code == status
    assert response.json()["detail"] == {"reason": "synthetic_preflight"}
    assert db_session.query(Payment).filter_by(visit_id=visit.id).count() == 0
    manager.create_payment.assert_not_called()


@pytest.mark.parametrize("status", [None, "rejected"])
def test_no_pending_request_does_not_block_cashier(client, db_session, admin_auth_headers, admin_user, test_patient, monkeypatch, status):
    visit = _visit(db_session, test_patient, admin_user, status=status, amount=Decimal("1.00"))
    monkeypatch.setattr(_visits, "_emit_payment_notification", AsyncMock())
    response = client.post(f"/api/v1/cashier/visits/{visit.id}/mark-paid", headers=admin_auth_headers)
    assert response.status_code == 200, response.text
    assert db_session.query(Payment).filter_by(visit_id=visit.id).one().amount == Decimal("2.00")


def test_pending_sibling_blocks_zero_total_cashier_until_decided(client, db_session, admin_auth_headers, admin_user, test_patient, monkeypatch):
    first = _visit(db_session, test_patient, admin_user, status=None)
    second = Visit(patient_id=test_patient.id, encounter_id=first.encounter_id,
                   status="pending_confirmation", confirmation_context_epoch=8)
    db_session.add(second)
    db_session.flush()
    db_session.add(VisitService(visit_id=second.id, service_id=123, name="Synthetic", price=Decimal("1.00"), qty=1, currency="UZS"))
    request = AllFreeRequest(
        visit_id=second.id, patient_id=test_patient.id, encounter_id=first.encounter_id,
        visit_id_snapshot=second.id, patient_id_snapshot=test_patient.id, encounter_id_snapshot=first.encounter_id,
        visit_context_epoch=8, encounter_generation=1, baseline_total=Decimal("1.00"), status="pending",
        requested_by_user_id=admin_user.id, requested_by_user_id_snapshot=admin_user.id,
        requested_by_role_snapshot="Admin", policy_auto_approve=False,
    )
    db_session.add(request)
    db_session.commit()
    monkeypatch.setattr(_visits, "_emit_payment_notification", AsyncMock())
    path = f"/api/v1/cashier/visits/{first.id}/mark-paid"
    blocked = client.post(path, headers=admin_auth_headers)
    assert blocked.status_code == 409, blocked.text
    blocked_single = client.post("/api/v1/cashier/payments", headers=admin_auth_headers,
                                 json={"visit_id": first.id, "amount": "1.00", "method": "cash"})
    assert blocked_single.status_code == 409, blocked_single.text
    blocked_group = client.post("/api/v1/cashier/payments/grouped", headers=admin_auth_headers,
                                json={"visit_ids": [first.id], "amount": "1.00", "method": "cash"})
    assert blocked_group.status_code == 409, blocked_group.text
    assert db_session.query(Payment).filter_by(visit_id=first.id).count() == 0
    request.status = "rejected"
    request.decision_kind = "admin"
    request.decided_by_user_id = admin_user.id
    request.decided_by_user_id_snapshot = admin_user.id
    request.decided_by_role_snapshot = "Admin"
    request.decided_at = datetime.now(UTC)
    db_session.commit()
    allowed = client.post(path, headers=admin_auth_headers)
    assert allowed.status_code == 200, allowed.text


@pytest.mark.parametrize("target", ["same", "sibling"])
def test_zero_total_cannot_claim_paid_with_unresolved_provider_intent(
    client, db_session, admin_auth_headers, admin_user, test_patient, target,
):
    first = _visit(db_session, test_patient, admin_user, status=None)
    target_visit = first
    if target == "sibling":
        target_visit = Visit(patient_id=test_patient.id, encounter_id=first.encounter_id,
                             status="pending_confirmation", confirmation_context_epoch=8)
        db_session.add(target_visit)
        db_session.flush()
        db_session.add(VisitService(visit_id=target_visit.id, service_id=123, name="Synthetic",
                                    price=Decimal("1.00"), qty=1, currency="UZS"))
    db_session.add(Payment(visit_id=target_visit.id, amount=Decimal("1.00"), currency="UZS",
                           method="online", status="pending", provider="click"))
    db_session.commit()
    response = client.post(f"/api/v1/cashier/visits/{first.id}/mark-paid", headers=admin_auth_headers)
    assert response.status_code == 409, response.text
    assert db_session.query(Payment).filter_by(status="paid").count() == 0
