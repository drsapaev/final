"""Unproven refund currency cannot authorize a financial transition."""
from decimal import Decimal

import pytest

from app.models.payment import Payment
from app.models.refund_deposit import PaymentRefundClaim, RefundRequest
from app.models.visit import Visit


def _request(db, patient, status):
    visit = Visit(patient_id=patient.id, status="open")
    db.add(visit)
    db.flush()
    payment = Payment(visit_id=visit.id, amount=Decimal("10.25"), currency="UZS", method="cash", status="paid")
    db.add(payment)
    db.flush()
    request = RefundRequest(patient_id=patient.id, payment_id=payment.id, visit_id=visit.id,
                            original_amount=Decimal("10.25"), refund_amount=Decimal("5.25"),
                            commission_amount=Decimal("0"), refund_type="bank_transfer", status=status,
                            is_automatic=True)
    db.add(request)
    db.flush()
    db.add(PaymentRefundClaim(payment_id=payment.id, channel="refund_request", refund_request_id=request.id))
    db.commit()
    return request, payment


@pytest.mark.parametrize("status,action", [("pending", "approve"), ("approved", "complete")])
def test_unproven_approval_or_completion_has_no_side_effects(
    client, db_session, test_patient, admin_auth_headers, status, action,
):
    request, payment = _request(db_session, test_patient, status)
    path = f"/api/v1/force-majeure/refund-requests/{request.id}"
    result = client.post(path + "/process", headers=admin_auth_headers,
                         json={"action": action, "bank_card_number": "SYNTHETIC", "manager_notes": "SYNTHETIC"})
    assert result.status_code == 409, result.text
    db_session.expire_all()
    assert request.status == status and request.processed_by is None and request.processed_at is None
    assert request.bank_card_number is None and request.manager_notes is None
    assert payment.refunded_amount is None and payment.status == "paid"
    assert db_session.query(PaymentRefundClaim).filter_by(payment_id=payment.id).count() == 1
    details = client.get(path, headers=admin_auth_headers)
    assert details.status_code == 200, details.text
    assert details.json()["available_actions"] == ["reject"]
    assert not details.json()["can_approve"] and not details.json()["can_complete"]


@pytest.mark.parametrize("status", ["pending", "approved"])
def test_reject_remains_available_and_releases_its_claim(client, db_session, test_patient, admin_auth_headers, status):
    request, payment = _request(db_session, test_patient, status)
    result = client.post(f"/api/v1/force-majeure/refund-requests/{request.id}/process", headers=admin_auth_headers,
                         json={"action": "reject", "rejection_reason": "synthetic"})
    assert result.status_code == 200, result.text
    db_session.expire_all()
    assert request.status == "rejected" and request.rejection_reason == "synthetic"
    assert db_session.query(PaymentRefundClaim).filter_by(payment_id=payment.id).count() == 0
    assert payment.refunded_amount is None and payment.status == "paid"


def test_nonexistent_or_inapplicable_request_is_not_misreported(client, db_session, test_patient, admin_auth_headers):
    path = "/api/v1/force-majeure/refund-requests"
    assert client.post(f"{path}/999999/process", headers=admin_auth_headers, json={"action": "approve"}).status_code == 404
    request, _ = _request(db_session, test_patient, "pending")
    assert client.post(f"{path}/{request.id}/process", headers=admin_auth_headers, json={"action": "complete"}).status_code == 400
