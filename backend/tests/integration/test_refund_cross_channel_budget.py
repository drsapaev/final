"""A synthetic payment must not be refunded twice through different channels."""

from decimal import Decimal
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from app.api.v1.endpoints.cashier import _payments
from app.models.payment import Payment, PaymentClientRequest
from app.models.refund_deposit import (
    DepositTransaction,
    PaymentRefundClaim,
    RefundRequest,
    RefundType,
)
from app.models.visit import Visit
from app.services.force_majeure_service import ForceMajeureError, ForceMajeureService
from tests.integration.test_cashier_currency import _visit
from tests.integration.test_cashier_daily_currency import _daily_pg_app
from tests.integration.test_cashier_refund_idempotency import _apply_receipt_guard
from tests.integration.test_staff_confirmation_guard_pg import guarded_pg  # noqa: F401


def test_deposit_credit_consumes_cashier_refund_budget(
    client, db_session, admin_auth_headers, test_patient, test_service, monkeypatch,
):
    monkeypatch.setattr(_payments, "_emit_payment_notification", AsyncMock())
    visit = _visit(db_session, test_patient, test_service, "UZS")
    payment = Payment(visit_id=visit.id, amount=Decimal("10.00"), currency="UZS",
                      method="cash", status="paid")
    db_session.add(payment)
    db_session.commit()

    ForceMajeureService(db_session)._add_to_deposit(
        patient_id=test_patient.id, amount=Decimal("10.00"), reason="SYNTHETIC",
        payment_id=payment.id, visit_id=visit.id, performed_by_id=None,
    )
    db_session.commit()
    assert db_session.query(DepositTransaction).filter_by(payment_id=payment.id).count() == 1

    response = client.post(f"/api/v1/cashier/payments/{payment.id}/refund",
                           headers=admin_auth_headers,
                           json={"amount": "10.00", "reason": "SYNTHETIC", "client_request_id": str(uuid4())})
    assert response.status_code == 409, response.text
    db_session.expire_all()
    assert not db_session.get(Payment, payment.id).refunded_amount


@pytest.mark.parametrize("channel", ["deposit", "bank_transfer"])
def test_cashier_partial_refund_prevents_automatic_full_refund(
    client, db_session, admin_auth_headers, test_patient, test_service, monkeypatch, channel,
):
    monkeypatch.setattr(_payments, "_emit_payment_notification", AsyncMock())
    visit = _visit(db_session, test_patient, test_service, "UZS")
    payment = Payment(visit_id=visit.id, amount=Decimal("10.00"), currency="UZS", method="cash", status="paid")
    db_session.add(payment)
    db_session.commit()

    response = client.post(f"/api/v1/cashier/payments/{payment.id}/refund", headers=admin_auth_headers,
                           json={"amount": "3.00", "reason": "SYNTHETIC", "client_request_id": str(uuid4())})
    assert response.status_code == 200, response.text
    with pytest.raises(ForceMajeureError, match="Доступная сумма возврата"):
        _external_refund(db_session, channel, payment, patient_id=test_patient.id)
    assert db_session.get(Payment, payment.id).refunded_amount == Decimal("3.00")
    for model in (PaymentRefundClaim, DepositTransaction, RefundRequest):
        assert db_session.query(model.id).filter(model.payment_id == payment.id).count() == 0


def _external_refund(db, channel, payment, *, patient_id):
    service = ForceMajeureService(db)
    common = {
        "patient_id": patient_id,
        "amount": payment.amount,
        "reason": "SYNTHETIC",
        "payment_id": payment.id,
        "visit_id": None,
    }
    if channel == "deposit":
        return service._add_to_deposit(**common, performed_by_id=None)
    return service._create_refund_request(**common, refund_type=RefundType.BANK_TRANSFER, is_automatic=True)


@pytest.mark.integration
@pytest.mark.parametrize("channel,evidence_table", [
    ("deposit", "deposit_transactions"), ("bank_transfer", "refund_requests"),
])
def test_postgres_cashier_refund_waits_for_ledger_evidence_and_checks_rls(
    guarded_pg, monkeypatch, channel, evidence_table,
):
    engine, runtime, ids, app, headers, schema, runtime_role, _ = _daily_pg_app(guarded_pg, monkeypatch)
    sql_errors = []

    @event.listens_for(runtime, "handle_error")
    def capture_sql_error(context):
        error = context.original_exception
        sql_errors.append((getattr(error, "sqlstate", None), getattr(getattr(error, "diag", None), "message_primary", None)))

    quote = engine.dialect.identifier_preparer.quote_identifier
    payments = f"{quote(schema)}.payments"
    with engine.begin() as conn:
        _install_cashier_receipt_policy(conn, schema, runtime_role)
        # Existing cashier privileges for this synthetic login. The evidence
        # still uses the application's column-only financial grants.
        conn.execute(text(f"GRANT SELECT, UPDATE (refunded_amount) ON {payments} TO {quote(runtime_role)}"))
        assert not conn.execute(text("SELECT pg_catalog.has_table_privilege(:r,:t,'SELECT')"),
                                {"r": runtime_role, "t": f"{quote(schema)}.{evidence_table}"}).scalar_one()
    sender = AsyncMock()
    monkeypatch.setattr(_payments, "_emit_payment_notification", sender)
    with TestClient(app) as http, Session(engine) as writer:
        payment = writer.query(Payment).filter_by(visit_id=ids["visit"], status="paid").one()
        patient_id = writer.get(Visit, payment.visit_id).patient_id
        payment_id = payment.id
        _external_refund(writer, channel, payment, patient_id=patient_id)
        route = f"/api/v1/cashier/payments/{payment_id}/refund"
        body = {"amount": "4.00", "reason": "SYNTHETIC", "client_request_id": str(uuid4())}
        concurrent = http.post(route, headers=headers, json=body)
        assert concurrent.status_code == 409 and "изменяется" in concurrent.json()["detail"], (concurrent.text, sql_errors)
        writer.commit()
        committed = http.post(route, headers=headers, json=body)
        assert committed.status_code == 409 and "другим способом" in committed.json()["detail"], committed.text

        with engine.begin() as conn:
            conn.execute(text(f"ALTER POLICY financial_backend_select ON {quote(schema)}.{evidence_table} USING (false)"))
        hidden = http.post(route, headers=headers, json=body)
        assert hidden.status_code == 503, hidden.text
        assert writer.get(Payment, payment_id).refunded_amount in (None, Decimal("0"))
        assert writer.query(PaymentRefundClaim.id).filter_by(payment_id=payment_id).count() == 1
        sender.assert_not_awaited()


def _install_cashier_receipt_policy(conn, schema, role):
    quote = conn.dialect.identifier_preparer.quote_identifier
    table, grantee = f"{quote(schema)}.payment_client_requests", quote(role)
    _apply_receipt_guard(conn, schema)
    conn.exec_driver_sql(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
    conn.exec_driver_sql(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
    conn.exec_driver_sql(f"GRANT SELECT, INSERT ON {table} TO {grantee}")
    conn.exec_driver_sql(f"GRANT USAGE ON SEQUENCE {quote(schema)}.payment_client_requests_id_seq TO {grantee}")
    conn.exec_driver_sql(f"CREATE POLICY synthetic_receipt_select ON {table} FOR SELECT TO {grantee} USING (true)")
    conn.exec_driver_sql(f"CREATE POLICY synthetic_receipt_append ON {table} FOR INSERT TO {grantee} WITH CHECK (true)")


@pytest.mark.integration
def test_postgres_cashier_still_records_an_ordinary_partial_refund(guarded_pg, monkeypatch):
    engine, _, ids, app, headers, schema, runtime_role, _ = _daily_pg_app(guarded_pg, monkeypatch)
    quote = engine.dialect.identifier_preparer.quote_identifier
    payments = f"{quote(schema)}.payments"
    with engine.begin() as conn:
        _install_cashier_receipt_policy(conn, schema, runtime_role)
        conn.execute(text(f"GRANT SELECT, UPDATE (refunded_amount,refund_reason,refunded_at,refunded_by) "
                          f"ON {payments} TO {quote(runtime_role)}"))
    sender = AsyncMock()
    monkeypatch.setattr(_payments, "_emit_payment_notification", sender)
    with Session(engine) as db:
        payment_id = db.query(Payment.id).filter_by(visit_id=ids["visit"], status="paid").scalar()
        assert payment_id is not None
    with TestClient(app) as http:
        route = f"/api/v1/cashier/payments/{payment_id}/refund"
        body = {"amount": "1.25", "reason": "SYNTHETIC", "client_request_id": str(uuid4())}
        result = http.post(route, headers=headers, json=body)
        replay = http.post(route, headers=headers, json=body)
        with engine.begin() as conn:
            table = f"{quote(schema)}.payment_client_requests"
            conn.exec_driver_sql(f"ALTER POLICY synthetic_receipt_select ON {table} USING (false)")
        hidden = http.post(route, headers=headers, json=body)
    assert result.status_code == 200, result.text
    assert replay.status_code == 200 and replay.json() == result.json()
    assert hidden.status_code == 503, hidden.text
    assert result.json()["remaining_amount"] == "2.75"
    with Session(engine) as db:
        updated = db.get(Payment, payment_id)
        assert updated.refunded_amount == Decimal("1.25") and updated.refunded_by == ids["stage"]
        assert updated.refund_reason == "SYNTHETIC" and updated.refunded_at is not None
        anchor = db.query(PaymentClientRequest).filter_by(client_request_id=body["client_request_id"]).one()
        assert anchor.response_payload["operation_amount"] == "1.25" and "reason" not in anchor.response_payload
        with pytest.raises(DBAPIError, match="immutable cashier refund receipt"), db.begin_nested():
            db.execute(text("DELETE FROM payment_client_requests WHERE client_request_id=:key"), {"key": body["client_request_id"]})
    sender.assert_awaited_once()
