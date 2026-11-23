from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.security import get_password_hash
from app.models.patient import Patient
from app.models.payment import Payment
from app.models.payment_webhook import PaymentTransaction
from app.models.user import User
from app.models.visit import Visit
from app.repositories.payment_reconciliation_repository import (
    PaymentReconciliationRepository,
)
from app.services.payment_reconciliation import (
    RECONCILIATION_UNAVAILABLE,
    PaymentReconciliationService,
)
from tests.integration.test_staff_confirmation_guard_pg import guarded_pg  # noqa: F401


def _cashier_headers(client, db_session):
    from tests.conftest import mint_access_token

    cashier = db_session.query(User).filter(User.username == "route_cashier").first()
    if cashier is None:
        cashier = User(
            username="route_cashier",
            email="route.cashier@test.com",
            hashed_password=get_password_hash("cashier123"),
            role="Cashier",
            is_active=True,
            is_superuser=False,
        )
        db_session.add(cashier)
        db_session.commit()
        db_session.refresh(cashier)

    # Cashier is a critical 2FA role: /login would return the two-stage
    # enrollment flow instead of tokens, so mint the access token directly.
    return {"Authorization": f"Bearer {mint_access_token(cashier)}"}


def test_reconcile_all_route_dispatches_to_all_provider_service(
    client, auth_headers, monkeypatch
):
    calls = {"all": 0, "provider": []}

    def fake_reconcile_all(self, *, start_date, end_date):
        calls["all"] += 1
        return {
            "route": "all",
            "providers": {},
            "overall_summary": {"total_discrepancies": 0},
        }

    def fake_reconcile_provider(self, *, provider, start_date, end_date):
        calls["provider"].append(provider)
        return {"route": "provider", "provider": provider}

    monkeypatch.setattr(
        "app.api.v1.endpoints.payment_reconciliation."
        "PaymentReconciliationApiService.reconcile_all_providers",
        fake_reconcile_all,
    )
    monkeypatch.setattr(
        "app.api.v1.endpoints.payment_reconciliation."
        "PaymentReconciliationApiService.reconcile_provider",
        fake_reconcile_provider,
    )

    response = client.post(
        "/api/v1/payments/reconcile/all",
        params={"start_date": "2026-05-01", "end_date": "2026-05-31"},
        headers=auth_headers,
    )

    assert response.status_code == 200
    assert response.json()["route"] == "all"
    assert calls == {"all": 1, "provider": []}


def test_reconcile_all_route_keeps_admin_only_permission(
    client, db_session, monkeypatch
):
    def fake_reconcile_all(self, *, start_date, end_date):
        return {"route": "all"}

    def fake_reconcile_provider(self, *, provider, start_date, end_date):
        return {"route": "provider", "provider": provider}

    monkeypatch.setattr(
        "app.api.v1.endpoints.payment_reconciliation."
        "PaymentReconciliationApiService.reconcile_all_providers",
        fake_reconcile_all,
    )
    monkeypatch.setattr(
        "app.api.v1.endpoints.payment_reconciliation."
        "PaymentReconciliationApiService.reconcile_provider",
        fake_reconcile_provider,
    )

    response = client.post(
        "/api/v1/payments/reconcile/all",
        params={"start_date": "2026-05-01", "end_date": "2026-05-31"},
        headers=_cashier_headers(client, db_session),
    )

    assert response.status_code == 403


REPORT_START = datetime(2025, 2, 3, tzinfo=UTC)
REPORT_END = datetime(2025, 2, 4, 23, 59, 59, 999999, tzinfo=UTC)


def _seed_report_payments(db):
    patient = Patient(first_name="SYNTHETIC", last_name="Reconciliation")
    db.add(patient)
    db.flush()
    visit = Visit(
        patient_id=patient.id, visit_date=REPORT_START.date(), status="open", source="desk",
    )
    db.add(visit)
    db.flush()
    boundaries = [
        REPORT_START - timedelta(microseconds=1),
        REPORT_START,
        REPORT_END,
        REPORT_END + timedelta(microseconds=1),
    ]
    payments = [
        Payment(
            visit_id=visit.id, amount=Decimal("125.00"), currency="UZS", method="online",
            status="pending", provider="click", created_at=timestamp,
        )
        for timestamp in boundaries
    ]
    db.add_all(payments)
    db.add(PaymentTransaction(
        transaction_id="SYNTHETIC-reconciliation-transaction", provider="click",
        amount=12500, currency="UZS", status="processing",
        created_at=REPORT_START.replace(tzinfo=None),
    ))
    db.flush()
    return {payments[1].id, payments[2].id}


def test_reconciliation_report_uses_requested_period_without_provider_statement(
    client, db_session, auth_headers, monkeypatch,
):
    expected = _seed_report_payments(db_session)
    db_session.commit()
    monkeypatch.setattr(
        "app.services.payment_provider_manager_factory.get_payment_manager",
        lambda: SimpleNamespace(get_provider=lambda _: None),
    )

    response = client.get(
        "/api/v1/payments/reconcile/report",
        params={"start_date": "2025-02-03", "end_date": "2025-02-04"},
        headers=auth_headers,
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    click = payload["providers"]["click"]
    assert click["statement_available"] is False
    assert click["summary"]["total_internal"] == 12500
    assert click["summary"]["total_provider"] is None
    assert {item["payment_id"] for item in click["missing_payments"]} == expected
    assert payload["overall_summary"]["has_discrepancies"] is None
    assert len(payload["alerts"]) == 3


def test_missing_payments_read_failure_returns_generic_error(
    client, auth_headers, monkeypatch, caplog,
):
    def unavailable(*args, **kwargs):
        raise SQLAlchemyError("SYNTHETIC database diagnostics")

    monkeypatch.setattr(
        PaymentReconciliationRepository, "list_pending_payments_for_provider", unavailable,
    )
    response = client.get("/api/v1/payments/reconcile/missing/click", headers=auth_headers)

    assert response.status_code == 500
    assert response.json() == {"detail": RECONCILIATION_UNAVAILABLE}
    assert "SYNTHETIC database diagnostics" not in caplog.text


def test_postgres_reconciliation_distinguishes_missing_evidence_from_access_failure(
    guarded_pg, caplog,
):
    admin, runtime, _ = guarded_pg
    quote = admin.dialect.identifier_preparer.quote_identifier
    schema, role = map(quote, (admin.dialect.default_schema_name, runtime.url.username))
    with Session(admin) as seed, seed.begin():
        expected = _seed_report_payments(seed)
        for table in ("payments", "payment_transactions"):
            relation = f"{schema}.{table}"
            seed.connection().exec_driver_sql(f"GRANT SELECT ON {relation} TO {role}")
            seed.connection().exec_driver_sql(
                f"CREATE POLICY synthetic_reconciliation_read ON {relation} "
                f"FOR SELECT TO {role} USING (true)"
            )

    with Session(runtime) as db:
        assert not db.scalar(text("SELECT has_table_privilege('payments', 'UPDATE')"))
        assert not db.scalar(text("SELECT has_table_privilege('payment_visits', 'SELECT')"))
        report = PaymentReconciliationService(db).generate_reconciliation_report(
            date(2025, 2, 3), date(2025, 2, 4),
        )
        click = report["providers"]["click"]
        assert click["summary"]["total_internal"] == 12500
        assert click["summary"]["difference"] is None
        assert {item["payment_id"] for item in click["missing_payments"]} == expected
        assert report["overall_summary"]["comparison_complete"] is False

    with admin.begin() as connection:
        connection.exec_driver_sql(f"REVOKE SELECT ON {schema}.payment_transactions FROM {role}")
    with Session(runtime) as db:
        report = PaymentReconciliationService(db).reconcile_provider(
            "click", date(2025, 2, 3), date(2025, 2, 4),
        )
        assert report["statement_available"] is False
        assert report["error"] == RECONCILIATION_UNAVAILABLE
        assert "permission denied" not in caplog.text
