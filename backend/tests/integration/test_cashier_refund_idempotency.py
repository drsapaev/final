"""A cashier refund and its retry share one durable database receipt."""

import importlib.util
from decimal import Decimal
from pathlib import Path
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from app.api.v1.endpoints.cashier import _payments
from app.models.payment import Payment, PaymentClientRequest
from app.models.user import User
from app.services import payment_provider_manager_factory
from tests.conftest import mint_access_token
from tests.integration.test_cashier_currency import _visit


def _apply_receipt_guard(conn, schema=None):
    path = Path(__file__).resolve().parents[2] / "alembic/versions/0132_cashier_refund_receipts.py"
    spec = importlib.util.spec_from_file_location("synthetic_refund_receipt_guard", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.op = Operations(MigrationContext.configure(conn, opts={"version_table_schema": schema}))
    module.upgrade()
    return module


@pytest.fixture
def refund_payment(db_session, test_patient, test_service):
    visit = _visit(db_session, test_patient, test_service, "UZS")
    payment = Payment(visit_id=visit.id, amount=Decimal("10.00"), currency="UZS", method="cash", status="paid")
    db_session.add(payment)
    db_session.commit()
    return payment


def _body(amount="1.25"):
    return {"amount": amount, "reason": "SYNTHETIC cashier reason", "client_request_id": str(uuid4())}


def test_replay_after_response_failure_preserves_refund_and_audit_once(
    client, db_session, admin_auth_headers, refund_payment, monkeypatch,
):
    payment_id = refund_payment.id
    route = f"/api/v1/cashier/payments/{payment_id}/refund"
    body = _body()
    sender = AsyncMock(side_effect=RuntimeError("SYNTHETIC response failure after commit"))
    monkeypatch.setattr(_payments, "_emit_payment_notification", sender)

    lost = client.post(route, headers=admin_auth_headers, json=body)
    assert lost.status_code == 500, lost.text
    result = client.post(route, headers=admin_auth_headers, json=body | {"amount": "1.250"})
    assert result.status_code == 200 and result.json()["refunded_amount"] == "1.25", result.text
    assert result.json()["reason"] == body["reason"]
    for mismatch in ({"amount": "1.50"}, {"reason": "SYNTHETIC changed intent"}):
        refused = client.post(route, headers=admin_auth_headers, json=body | mismatch)
        assert refused.status_code == 409, refused.text
    assert client.post(f"/api/v1/cashier/payments/{payment_id + 1}/refund",
                       headers=admin_auth_headers, json=body).status_code == 409
    cashier = User(username="SYNTHETIC-refund-other-cashier", hashed_password="!", role="Cashier", is_active=True)
    db_session.add(cashier)
    db_session.commit()
    other_cashier = {"Authorization": f"Bearer {mint_access_token(cashier)}"}
    assert client.post(route, headers=other_cashier, json=body).status_code == 409
    db_session.expire_all()
    assert db_session.get(Payment, payment_id).refunded_amount == Decimal("1.25")
    anchor = db_session.query(PaymentClientRequest).filter_by(client_request_id=body["client_request_id"]).one()
    assert anchor.endpoint == "refund" and anchor.created_by is not None
    assert anchor.response_payload["currency"] == "UZS" and anchor.response_payload["operation_amount"] == "1.25"
    assert "reason" not in anchor.response_payload
    sender.assert_awaited_once()


def test_invalid_refund_and_unverified_provider_never_change_payment(
    client, db_session, admin_auth_headers, refund_payment, monkeypatch,
):
    payment_id = refund_payment.id
    route = f"/api/v1/cashier/payments/{payment_id}/refund"
    call_provider = Mock()
    monkeypatch.setattr(payment_provider_manager_factory, "get_payment_manager", call_provider)
    body = _body("1.251")
    missing_key = {field: value for field, value in body.items() if field != "client_request_id"}
    assert client.post(route, headers=admin_auth_headers, json=missing_key).status_code == 422
    assert client.post(route, headers=admin_auth_headers, json=body).status_code == 422
    db_session.get(Payment, payment_id).provider = "kaspi"
    db_session.commit()
    assert client.post(route, headers=admin_auth_headers, json=_body()).status_code == 409
    db_session.expire_all()
    assert db_session.get(Payment, payment_id).refunded_amount is None
    assert db_session.query(PaymentClientRequest).filter_by(endpoint="refund").count() == 0
    call_provider.assert_not_called()


def test_cashier_refund_guard_retains_receipt_and_preserves_legacy_purchase(
    client, db_session, admin_auth_headers, refund_payment, monkeypatch,
):
    payment_id = refund_payment.id
    db_session.add(PaymentClientRequest(client_request_id=str(uuid4()), endpoint="single", response_payload={"id": 1}))
    db_session.commit()
    revision = _apply_receipt_guard(db_session.connection())
    revision.downgrade()
    revision.upgrade()
    db_session.commit()
    monkeypatch.setattr(_payments, "_emit_payment_notification", AsyncMock())
    body = _body()
    route = f"/api/v1/cashier/payments/{payment_id}/refund"
    result = client.post(route, headers=admin_auth_headers, json=body)
    assert result.status_code == 200, result.text
    with pytest.raises(DBAPIError, match="immutable cashier refund receipt"), db_session.begin_nested():
        db_session.execute(text("UPDATE payment_client_requests SET request_fingerprint=NULL WHERE endpoint='refund'"))
    with pytest.raises(DBAPIError), db_session.begin_nested():
        revision.downgrade()
    assert db_session.query(PaymentClientRequest).filter_by(endpoint="single").count() == 1
    replay = client.post(route, headers=admin_auth_headers, json=body)
    assert replay.status_code == 200 and replay.json() == result.json()

    # Migration 0132 preserves the receipt when the original account is removed.
    db_session.execute(
        text("UPDATE payment_client_requests SET created_by=NULL WHERE client_request_id=:key"),
        {"key": body["client_request_id"]},
    )
    db_session.commit()
    unverified = client.post(route, headers=admin_auth_headers, json=body)
    assert unverified.status_code == 409, unverified.text
    assert unverified.json()["detail"]["reason"] == "client_request_id_owner_unverified"
    assert db_session.get(Payment, payment_id).refunded_amount == Decimal("1.25")
