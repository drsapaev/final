"""Manual confirmation must fence every visit linked to the payment."""

from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import AsyncMock

from app.api.v1.endpoints.cashier import _payments
from app.models.all_free_request import AllFreeRequest
from app.models.payment import Payment, PaymentVisit
from tests.integration.test_all_free_payment_guard_http import _visit


def test_confirm_blocks_other_encounter_pending_and_then_allows_manual_payment(
    client, db_session, admin_auth_headers, admin_user, test_patient, monkeypatch
):
    first = _visit(db_session, test_patient, admin_user, status=None, amount=Decimal("1.00"))
    second = _visit(db_session, test_patient, admin_user, status="pending", amount=Decimal("1.00"))
    payment = Payment(visit_id=first.id, amount=Decimal("1.00"),
                      currency="UZS", method="cash", status="pending")
    db_session.add(payment)
    db_session.flush()
    db_session.add(PaymentVisit(payment_id=payment.id, visit_id=second.id, amount=Decimal("1.00")))
    db_session.commit()
    monkeypatch.setattr(_payments, "_emit_payment_notification", AsyncMock())
    path = f"/api/v1/cashier/payments/{payment.id}/confirm"
    blocked = client.post(path, headers=admin_auth_headers)
    assert blocked.status_code == 409, blocked.text
    db_session.expire_all()
    assert db_session.get(Payment, payment.id).status == "pending"
    request = db_session.query(AllFreeRequest).filter_by(visit_id=second.id).one()
    request.status = "rejected"
    request.decision_kind = "admin"
    request.decided_by_user_id = admin_user.id
    request.decided_by_user_id_snapshot = admin_user.id
    request.decided_by_role_snapshot = "Admin"
    request.decided_at = datetime.now(UTC)
    db_session.commit()
    allowed = client.post(path, headers=admin_auth_headers)
    assert allowed.status_code == 200, allowed.text
    db_session.expire_all()
    assert db_session.get(Payment, payment.id).status == "paid"
