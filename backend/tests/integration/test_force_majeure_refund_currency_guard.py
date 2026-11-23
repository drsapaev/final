"""Force-majeure refund decisions and payment data boundaries."""
import logging
from decimal import Decimal

import pytest
from sqlalchemy.exc import SQLAlchemyError

from app.models.audit import AuditLog
from app.models.payment import Payment
from app.models.refund_deposit import PaymentRefundClaim, RefundRequest
from app.models.visit import Visit
from app.repositories.force_majeure_api_repository import ForceMajeureApiRepository


def _request(db, patient, status, *, snapshot=None):
    visit = Visit(patient_id=patient.id, status="open")
    db.add(visit)
    db.flush()
    payment = Payment(visit_id=visit.id, amount=Decimal("10.25"), currency="UZS", method="cash", status="paid")
    db.add(payment)
    db.flush()
    request = RefundRequest(patient_id=patient.id, payment_id=payment.id, visit_id=visit.id,
                            original_amount=Decimal("10.25"), refund_amount=Decimal("5.25"),
                            commission_amount=Decimal("0"), refund_type="bank_transfer", status=status,
                            is_automatic=True, payment_currency_snapshot=snapshot)
    db.add(request)
    db.flush()
    db.add(PaymentRefundClaim(payment_id=payment.id, channel="refund_request", refund_request_id=request.id))
    db.commit()
    return request, payment


def _audit_events(db, request_id):
    return db.query(AuditLog).filter_by(
        action="refund_request_status_changed", entity_type="refund_request", entity_id=request_id,
    ).all()


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
    assert _audit_events(db_session, request.id) == []


@pytest.mark.parametrize("snapshot", [None, "UZS"], ids=["legacy", "captured"])
def test_pending_reject_releases_and_audits_one_claim(
    client, db_session, test_patient, admin_user, admin_auth_headers, snapshot,
):
    request, payment = _request(db_session, test_patient, "pending", snapshot=snapshot)
    path = f"/api/v1/force-majeure/refund-requests/{request.id}/process"
    body = {
        "action": "reject",
        "rejection_reason": "SYNTHETIC PRIVATE REASON",
        "manager_notes": "SYNTHETIC PRIVATE NOTES",
        "bank_card_number": "0" * 12 + "7654",
    }
    result = client.post(path, headers=admin_auth_headers, json=body)

    assert result.status_code == 200, result.text
    assert result.json()["bank_card_number"] is None
    db_session.expire_all()
    assert request.status == "rejected" and request.rejection_reason == body["rejection_reason"]
    assert request.bank_card_number is None
    assert db_session.query(PaymentRefundClaim).filter_by(payment_id=payment.id).count() == 0
    assert payment.refunded_amount is None and payment.status == "paid"
    [event] = _audit_events(db_session, request.id)
    assert event.event_type == "REFUND_REQUEST_STATUS_CHANGED"
    assert event.actor_user_id == admin_user.id == request.processed_by
    assert event.actor_role == admin_user.role and event.created_at == request.processed_at
    assert event.payload == {
        "payment_id": payment.id,
        "previous_status": "pending",
        "new_status": "rejected",
        "refund_amount": "5.25",
        "currency": snapshot,
    }

    assert client.post(path, headers=admin_auth_headers, json=body).status_code == 400
    assert len(_audit_events(db_session, request.id)) == 1


def test_refund_audit_failure_rolls_back_decision_and_claim(
    client, db_session, test_patient, admin_auth_headers, monkeypatch,
):
    request, payment = _request(db_session, test_patient, "pending")
    request_id, payment_id = request.id, payment.id

    def unavailable(*args, **kwargs):
        raise SQLAlchemyError("SYNTHETIC PRIVATE AUDIT FAILURE")

    monkeypatch.setattr(ForceMajeureApiRepository, "record_refund_request_transition", unavailable)
    response = client.post(
        f"/api/v1/force-majeure/refund-requests/{request_id}/process",
        headers=admin_auth_headers,
        json={"action": "reject", "rejection_reason": "SYNTHETIC"},
    )

    assert response.status_code == 503
    assert "SYNTHETIC PRIVATE AUDIT FAILURE" not in response.text
    db_session.expire_all()
    assert request.status == "pending"
    assert request.processed_by is None and request.processed_at is None and request.rejection_reason is None
    assert db_session.query(PaymentRefundClaim).filter_by(payment_id=payment_id).count() == 1
    assert _audit_events(db_session, request_id) == []


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
