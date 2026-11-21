"""Force-majeure refund decisions and payment data boundaries."""
import logging
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


@pytest.mark.parametrize("status,action", [("pending", "approve"), ("approved", "complete"), ("approved", "reject")])
def test_unproven_bank_refund_transition_has_no_side_effects(
    client, db_session, test_patient, admin_auth_headers, status, action,
):
    request, payment = _request(db_session, test_patient, status)
    path = f"/api/v1/force-majeure/refund-requests/{request.id}"
    result = client.post(path + "/process", headers=admin_auth_headers,
                         json={"action": action, "bank_card_number": "SYNTHETIC", "manager_notes": "SYNTHETIC",
                               "rejection_reason": "SYNTHETIC"})
    assert result.status_code == 409, result.text
    db_session.expire_all()
    assert request.status == status and request.processed_by is None and request.processed_at is None
    assert request.bank_card_number is None and request.manager_notes is None and request.rejection_reason is None
    assert payment.refunded_amount is None and payment.status == "paid"
    assert db_session.query(PaymentRefundClaim).filter_by(payment_id=payment.id).count() == 1
    details = client.get(path, headers=admin_auth_headers)
    assert details.status_code == 200, details.text
    assert details.json()["available_actions"] == (["reject"] if status == "pending" else [])
    assert not details.json()["can_approve"] and not details.json()["can_complete"]


def test_pending_reject_remains_available_and_releases_its_claim(client, db_session, test_patient, admin_auth_headers):
    request, payment = _request(db_session, test_patient, "pending")
    result = client.post(f"/api/v1/force-majeure/refund-requests/{request.id}/process", headers=admin_auth_headers,
                         json={"action": "reject", "rejection_reason": "synthetic",
                               "bank_card_number": "0" * 12 + "7654"})
    assert result.status_code == 200, result.text
    assert result.json()["bank_card_number"] is None
    db_session.expire_all()
    assert request.status == "rejected" and request.rejection_reason == "synthetic"
    assert request.bank_card_number is None
    assert db_session.query(PaymentRefundClaim).filter_by(payment_id=payment.id).count() == 0
    assert payment.refunded_amount is None and payment.status == "paid"


@pytest.mark.parametrize(
    "stored_card,display_card",
    [("0000 0000 0000 7654", "****7654"), ("****7654", "****7654"), ("SYNTHETIC", None)],
)
def test_historical_refund_card_is_masked_in_reads_and_processing(
    client, db_session, test_patient, admin_auth_headers, stored_card, display_card,
):
    request, _ = _request(db_session, test_patient, "pending")
    request.bank_card_number = stored_card
    db_session.commit()
    path = "/api/v1/force-majeure/refund-requests"
    listing = client.get(path, headers=admin_auth_headers, params={"patient_id": test_patient.id})
    assert listing.status_code == 200
    assert listing.json()[0]["bank_card_number"] == display_card
    detail = client.get(f"{path}/{request.id}", headers=admin_auth_headers)
    assert detail.status_code == 200
    assert detail.json()["bank_card_number"] == display_card
    rejected = client.post(f"{path}/{request.id}/process", headers=admin_auth_headers,
                           json={"action": "reject", "rejection_reason": "synthetic",
                                 "bank_card_number": "0" * 12 + "5678"})
    assert rejected.status_code == 200
    assert rejected.json()["bank_card_number"] == display_card
    db_session.refresh(request)
    assert request.bank_card_number == stored_card


@pytest.mark.parametrize("request_id", ["1", "invalid-id"])
def test_refund_validation_hides_submitted_card_data(client, admin_auth_headers, caplog, request_id):
    card_marker = "SYNTHETIC-REFUND-CARD"
    with caplog.at_level(logging.INFO, logger="app.middleware.audit_middleware"):
        result = client.post(f"/api/v1/force-majeure/refund-requests/{request_id}/process",
                             headers=admin_auth_headers, params={"bank_card_number": card_marker},
                             json={"bank_card_number": card_marker})
    assert result.status_code == 422
    assert result.headers["Cache-Control"] == "no-store"
    assert card_marker not in result.text
    app_logs = "\n".join(record.getMessage() for record in caplog.records if record.name.startswith("app."))
    assert card_marker not in app_logs
    assert "?[REDACTED]" in app_logs


def test_nonexistent_or_inapplicable_request_is_not_misreported(client, db_session, test_patient, admin_auth_headers):
    path = "/api/v1/force-majeure/refund-requests"
    assert client.post(f"{path}/999999/process", headers=admin_auth_headers, json={"action": "approve"}).status_code == 404
    request, _ = _request(db_session, test_patient, "pending")
    assert client.post(f"{path}/{request.id}/process", headers=admin_auth_headers, json={"action": "complete"}).status_code == 400
