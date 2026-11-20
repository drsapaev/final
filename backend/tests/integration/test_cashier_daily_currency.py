"""Daily cashier totals are exact, currency-scoped and evidence-backed."""
from datetime import datetime
from decimal import Decimal
from uuid import uuid4

import pytest

from app.models.payment import Payment, PaymentVisit
from app.models.refund_deposit import DepositTransaction, PatientDeposit, RefundRequest
from app.models.visit import Visit, VisitService
from tests.integration.test_staff_confirmation_guard_pg import guarded_pg  # noqa: F401


def _visit(db, patient, amount, currency, *, status="open"):
    visit = Visit(patient_id=patient.id, status=status, confirmation_context_epoch=1)
    db.add(visit)
    db.flush()
    db.add(VisitService(visit_id=visit.id, service_id=1, name="SYNTHETIC", qty=1,
                        price=Decimal(amount), currency=currency))
    db.commit()
    return visit


def _payment(db, visit, amount, currency, *, refund="0"):
    payment = Payment(visit_id=visit.id, amount=Decimal(amount), currency=currency, method="cash",
                      status="paid", refunded_amount=Decimal(refund))
    db.add(payment)
    db.commit()
    return payment


def test_proven_uzs_gross_net_and_pending_keep_legacy_contract(client, db_session, test_patient, admin_auth_headers):
    visit = _visit(db_session, test_patient, "100.00", "UZS")
    _payment(db_session, visit, "80.00", "UZS", refund="10.00")
    legacy = client.get("/api/v1/cashier/stats", headers=admin_auth_headers)
    assert legacy.status_code == 200, legacy.text
    data = legacy.json()
    assert Decimal(str(data["total_amount"])) == Decimal("80.00")
    assert Decimal(str(data["refunded_amount"])) == Decimal("10.00")
    assert Decimal(str(data["net_total_amount"])) == Decimal("70.00")
    assert Decimal(str(data["pending_amount"])) == Decimal("30.00")
    assert data["paid_count"] == 1 and data["pending_count"] == 1


def test_manual_topup_preserves_daily_totals(client, db_session, test_patient, admin_auth_headers):
    visit = _visit(db_session, test_patient, "10.00", "UZS")
    _payment(db_session, visit, "4.00", "UZS")
    path = "/api/v1/cashier/stats/by-currency"
    before = client.get(path, headers=admin_auth_headers)
    assert before.status_code == 200, before.text

    credit = client.post("/api/v1/force-majeure/deposits/add", headers=admin_auth_headers, json={
        "patient_id": test_patient.id, "amount": "2.00", "client_request_id": str(uuid4()),
    })
    assert credit.status_code == 200 and credit.json()["balance"] == 2, credit.text
    after = client.get(path, headers=admin_auth_headers)
    assert after.status_code == 200 and after.json() == before.json(), after.text
    assert client.get("/api/v1/cashier/stats", headers=admin_auth_headers).status_code == 200


def test_currency_buckets_do_not_sum_unknown_or_foreign(client, db_session, test_patient, admin_auth_headers):
    for amount, currency in (("10.25", "UZS"), ("2.10", "USD"), ("3.05", ""), ("999.99", "bad")):
        visit = _visit(db_session, test_patient, amount, currency, status="completed")
        _payment(db_session, visit, amount, currency)
    assert client.get("/api/v1/cashier/stats", headers=admin_auth_headers).status_code == 409
    response = client.get("/api/v1/cashier/stats/by-currency", headers=admin_auth_headers)
    assert response.status_code == 200, response.text
    unknown, usd, uzs = response.json()
    assert unknown["currency"] is None and unknown["paid_count"] == 2
    assert unknown["total_amount"] is None and unknown["net_total_amount"] is None
    assert unknown["requires_reconciliation"] is True
    assert usd["currency"] == "USD" and usd["total_amount"] is None and usd["paid_count"] is None
    assert uzs["currency"] == "UZS" and uzs["total_amount"] is None and uzs["paid_count"] is None


def test_known_currencies_have_separate_exact_gross(client, db_session, test_patient, admin_auth_headers):
    for amount, currency in (("10.25", "UZS"), ("2.10", "USD")):
        visit = _visit(db_session, test_patient, amount, currency, status="completed")
        _payment(db_session, visit, amount, currency)
    response = client.get("/api/v1/cashier/stats/by-currency", headers=admin_auth_headers)
    assert response.status_code == 200, response.text
    usd, uzs = response.json()
    assert usd["currency"] == "USD" and usd["total_amount"] == "2.10" and usd["paid_count"] == 1
    assert uzs["currency"] == "UZS" and uzs["total_amount"] == "10.25" and uzs["paid_count"] == 1
    assert client.get("/api/v1/cashier/stats", headers=admin_auth_headers).status_code == 409


def test_daily_date_bounds_and_empty_json_contract(client, db_session, test_patient, admin_auth_headers):
    visit = _visit(db_session, test_patient, "10.00", "UZS", status="completed")
    for created, amount in ((datetime(2025, 1, 1, 23, 59, 59), "1.00"),
                            (datetime(2025, 1, 2, 0, 0, 0), "2.00"),
                            (datetime(2025, 1, 2, 23, 59, 59, 999999), "3.00"),
                            (datetime(2025, 1, 3, 0, 0, 0), "4.00")):
        payment = _payment(db_session, visit, amount, "UZS")
        payment.created_at = created
        db_session.commit()
    path = "/api/v1/cashier/stats/by-currency"
    response = client.get(path, params={"date_from": "2025-01-02", "date_to": "2025-01-02"},
                          headers=admin_auth_headers)
    assert response.status_code == 200, response.text
    [item] = response.json()
    assert item["total_amount"] == "5.00" and item["paid_count"] == 2
    assert item["currency"] == "UZS" and item["requires_reconciliation"] is False
    assert set(item) == {"currency", "requires_reconciliation", "total_amount", "cash_amount",
                         "card_amount", "refunded_amount", "net_total_amount", "net_cash_amount",
                         "net_card_amount", "pending_amount", "paid_count", "cancelled_count", "pending_count"}
    response = client.get(path, params={"date_from": "2025-02-01", "date_to": "2025-02-02"},
                          headers=admin_auth_headers)
    assert response.status_code == 200 and response.json() == []
    response = client.get(path, params={"date_from": "2025-02-02", "date_to": "2025-02-01"},
                          headers=admin_auth_headers)
    assert response.status_code == 422


def test_unknown_visit_makes_all_potential_pending_buckets_incomplete(client, db_session, test_patient, admin_auth_headers):
    _visit(db_session, test_patient, "10.00", "UZS")
    _visit(db_session, test_patient, "20.00", "")
    response = client.get("/api/v1/cashier/stats/by-currency", headers=admin_auth_headers)
    assert response.status_code == 200, response.text
    unknown, uzs = response.json()
    assert unknown["currency"] is None and unknown["pending_amount"] is None
    assert uzs["currency"] == "UZS" and uzs["pending_amount"] is None and uzs["pending_count"] is None
    assert uzs["requires_reconciliation"] is True


def test_zero_price_unknown_visit_does_not_invent_or_block_debt(client, db_session, test_patient, admin_auth_headers):
    _visit(db_session, test_patient, "10.00", "UZS")
    _visit(db_session, test_patient, "0.00", "")
    response = client.get("/api/v1/cashier/stats", headers=admin_auth_headers)
    assert response.status_code == 200, response.text
    assert Decimal(str(response.json()["pending_amount"])) == Decimal("10.00")


def test_sqlite_refreshes_cached_allocation_before_report(tmp_path):
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session

    import app.db.base  # noqa: F401
    from app.db.base_class import Base
    from app.models.patient import Patient
    from app.services.cashier_stats_snapshot import cashier_daily_stats

    engine = create_engine(f"sqlite:///{tmp_path / 'daily.sqlite'}")
    Base.metadata.create_all(engine)
    try:
        with Session(engine, expire_on_commit=False) as first:
            patient = Patient(first_name="SYNTHETIC", last_name="Cache")
            first.add(patient)
            first.flush()
            visit = _visit(first, patient, "10.00", "UZS")
            payment = _payment(first, visit, "10.00", "UZS")
            link = PaymentVisit(payment_id=payment.id, visit_id=visit.id, amount=Decimal("10.00"))
            first.add(link)
            first.commit()
            assert first.get(PaymentVisit, link.id).amount == Decimal("10.00")
            first.commit()
            with Session(engine) as other:
                other.get(PaymentVisit, link.id).amount = Decimal("9.00")
                other.commit()
            [bucket] = cashier_daily_stats(first, date_from=None, date_to=None, excluded=("closed",))
            assert bucket["total_amount"] == "10.00"
            assert bucket["pending_amount"] is None and bucket["requires_reconciliation"] is True
    finally:
        engine.dispose()


def test_orphan_refund_makes_even_known_currency_totals_incomplete():
    from app.services.cashier_stats_snapshot import daily_stats_from_snapshot

    snapshot = {"visits": [], "links": [], "external": [], "deposit_refunds": [], "orphan_external": True,
                "payments": [{"id": 1, "visit": 2, "patient": 3, "amount": "10.00", "refund": "0.00",
                              "currency": "UZS", "method": "cash", "status": "paid", "period": True}]}
    unknown, uzs = daily_stats_from_snapshot(snapshot)
    assert unknown["currency"] is None and unknown["paid_count"] is None
    assert uzs["currency"] == "UZS" and uzs["total_amount"] is None and uzs["paid_count"] is None
    assert uzs["net_total_amount"] is None and uzs["pending_amount"] is None
    assert uzs["requires_reconciliation"] is True


def test_unbound_credit_requires_reconciliation(client, db_session, test_patient, admin_auth_headers):
    visit = _visit(db_session, test_patient, "10.00", "UZS")
    _payment(db_session, visit, "10.00", "UZS")
    deposit = PatientDeposit(patient_id=test_patient.id, balance=Decimal("2.00"), currency="UZS")
    db_session.add(deposit)
    db_session.flush()
    db_session.add(DepositTransaction(deposit_id=deposit.id, transaction_type="credit",
                                      amount=Decimal("2.00"), balance_after=Decimal("2.00")))
    db_session.commit()
    response = client.get("/api/v1/cashier/stats/by-currency", headers=admin_auth_headers)
    assert response.status_code == 200, response.text
    unknown, uzs = response.json()
    assert unknown["currency"] is None and unknown["requires_reconciliation"] is True
    assert uzs["currency"] == "UZS" and uzs["requires_reconciliation"] is True
    assert uzs["total_amount"] is None and uzs["net_total_amount"] is None
    assert uzs["paid_count"] is None and uzs["pending_amount"] is None


@pytest.mark.parametrize("refund_status", ["approved", "processing", "completed", "unrecognized"])
def test_unbound_external_refund_keeps_gross_but_marks_net_and_debt_unknown(
    client, db_session, test_patient, admin_auth_headers, refund_status,
):
    visit = _visit(db_session, test_patient, "100.00", "UZS")
    payment = _payment(db_session, visit, "80.00", "UZS")
    db_session.add(RefundRequest(patient_id=test_patient.id, payment_id=payment.id,
        original_amount=Decimal("80.00"), refund_amount=Decimal("5.00"), commission_amount=Decimal("0"),
        refund_type="cash", status=refund_status))
    db_session.commit()
    response = client.get("/api/v1/cashier/stats/by-currency", headers=admin_auth_headers)
    assert response.status_code == 200, response.text
    [item] = response.json()
    assert item["total_amount"] == "80.00" and item["paid_count"] == 1
    assert item["refunded_amount"] is None and item["net_total_amount"] is None
    assert item["pending_amount"] is None and item["pending_count"] is None
    assert item["requires_reconciliation"] is True
    assert client.get("/api/v1/cashier/stats", headers=admin_auth_headers).status_code == 409


@pytest.mark.parametrize("refund_status", ["pending", "rejected", "cancelled"])
def test_refund_status_known_not_to_be_a_payout_preserves_current_totals(
    client, db_session, test_patient, admin_auth_headers, refund_status,
):
    visit = _visit(db_session, test_patient, "100.00", "UZS")
    payment = _payment(db_session, visit, "80.00", "UZS")
    db_session.add(RefundRequest(patient_id=test_patient.id, payment_id=payment.id,
        original_amount=Decimal("80.00"), refund_amount=Decimal("5.00"), commission_amount=Decimal("0"),
        refund_type="cash", status=refund_status))
    db_session.commit()
    response = client.get("/api/v1/cashier/stats/by-currency", headers=admin_auth_headers)
    assert response.status_code == 200, response.text
    [item] = response.json()
    assert item["net_total_amount"] == "80.00" and item["pending_amount"] == "20.00"
    assert item["requires_reconciliation"] is False


def test_ambiguous_multi_visit_payment_never_invents_pending_allocation(client, db_session, test_patient, admin_auth_headers):
    first = _visit(db_session, test_patient, "20.00", "UZS")
    second = _visit(db_session, test_patient, "20.00", "UZS")
    payment = _payment(db_session, first, "20.00", "UZS")
    db_session.add_all([PaymentVisit(payment_id=payment.id, visit_id=first.id, amount=Decimal("10.00")),
                        PaymentVisit(payment_id=payment.id, visit_id=second.id, amount=Decimal("10.00"))])
    db_session.commit()
    response = client.get("/api/v1/cashier/stats/by-currency", headers=admin_auth_headers)
    assert response.status_code == 200, response.text
    [item] = response.json()
    assert item["total_amount"] == "20.00"
    assert item["pending_amount"] is None and item["pending_count"] is None
    assert item["requires_reconciliation"] is True


def _daily_pg_app(guarded_pg, monkeypatch):
    import importlib.util
    from pathlib import Path

    from fastapi import FastAPI
    from sqlalchemy import text
    from sqlalchemy.orm import Session

    from app.api.deps import get_db
    from app.api.v1.endpoints.cashier import router
    from app.core.config import settings
    from app.db.capability_namespace import capability_schema_name
    from app.models.user import User
    from tests.conftest import mint_access_token
    from tests.integration.test_deposit_refund_evidence_pg import install_deposit_guards

    engine, runtime, ids = guarded_pg
    schema, runtime_role = engine.dialect.default_schema_name, runtime.url.username
    quote = engine.dialect.identifier_preparer.quote_identifier
    qs = quote(schema)
    for key in ("DOCTOR_PRICE_DB_SCHEMA", "DOCTOR_PRICE_DB_SCHEMA_OWNER",
                "INVITATION_DB_SCHEMA", "INVITATION_DB_SCHEMA_OWNER"):
        monkeypatch.setattr(settings, key, None)
    with engine.begin() as conn:
        install_deposit_guards(conn, schema)
        owner = conn.execute(text("SELECT current_user")).scalar_one()
        private = quote(capability_schema_name(schema))
        capability = conn.execute(text("""
          SELECT r.rolname FROM pg_catalog.pg_proc p JOIN pg_catalog.pg_roles r ON r.oid=p.proowner
          WHERE p.oid=pg_catalog.to_regprocedure(:name)
        """), {"name": f"{private}.financial_probe_group(integer)"}).scalar_one()
        for table in ("refund_requests", "deposit_transactions"):
            conn.execute(text(f'ALTER TABLE {qs}."{table}" ENABLE ROW LEVEL SECURITY'))
            conn.execute(text(f'ALTER TABLE {qs}."{table}" FORCE ROW LEVEL SECURITY'))
    script = Path(__file__).resolve().parents[3] / "scripts/provision_encounter_financial_role.py"
    spec = importlib.util.spec_from_file_location("daily_finance_provision", script)
    provisioner = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(provisioner)
    provisioner.provision(engine, schema=schema, backend_role=runtime_role, capability_role=capability,
                          expected_owner=owner)
    with Session(engine) as db:
        token = mint_access_token(db.get(User, ids["stage"]))
        db.add(Payment(visit_id=ids["visit"], amount=Decimal("4.00"), currency="UZS", method="cash", status="paid"))
        db.commit()
    app = FastAPI()
    app.include_router(router, prefix="/api/v1/cashier")

    def runtime_db():
        with Session(runtime) as db:
            yield db
            db.rollback()

    app.dependency_overrides[get_db] = runtime_db
    headers = {"Authorization": f"Bearer {token}"}
    return engine, runtime, ids, app, headers, schema, runtime_role, capability


def test_daily_http_nonowner_proves_refund_visibility(guarded_pg, monkeypatch):
    from fastapi.testclient import TestClient
    from sqlalchemy import text

    engine, _, _, app, headers, schema, runtime_role, _ = _daily_pg_app(guarded_pg, monkeypatch)
    qs = engine.dialect.identifier_preparer.quote_identifier(schema)
    path = "/api/v1/cashier/stats/by-currency"
    with TestClient(app) as http:
        response = http.get(path, headers=headers)
        assert response.status_code == 200, response.text
        [item] = response.json()
        assert item["total_amount"] == "4.00" and item["pending_amount"] == "6.00"
        with engine.begin() as conn:
            assert not conn.execute(text("SELECT pg_catalog.has_table_privilege(:role,:table,'SELECT')"),
                                    {"role": runtime_role, "table": f"{qs}.refund_requests"}).scalar_one()
            assert not conn.execute(text("SELECT pg_catalog.has_column_privilege(:role,:table,'bank_card_number','SELECT')"),
                                    {"role": runtime_role, "table": f"{qs}.refund_requests"}).scalar_one()
            conn.execute(text(f"ALTER POLICY financial_backend_select ON {qs}.refund_requests USING (false)"))
        assert http.get(path, headers=headers).status_code == 503
        with engine.begin() as conn:
            conn.execute(text(f"ALTER POLICY financial_backend_select ON {qs}.refund_requests USING (true)"))
            conn.execute(text(f"ALTER POLICY financial_backend_select ON {qs}.deposit_transactions USING (false)"))
        assert http.get(path, headers=headers).status_code == 503
        with engine.begin() as conn:
            conn.execute(text(f"ALTER POLICY financial_backend_select ON {qs}.deposit_transactions USING (true)"))
            conn.execute(text(f"ALTER POLICY benefit_cap_select ON {qs}.encounter_benefit_allocations USING (false)"))
        assert http.get(path, headers=headers).status_code == 503


def test_daily_http_nonowner_unbound_credit_requires_reconciliation(guarded_pg, monkeypatch):
    from fastapi.testclient import TestClient
    from sqlalchemy.orm import Session

    engine, _, ids, app, headers, _, _, _ = _daily_pg_app(guarded_pg, monkeypatch)
    with Session(engine) as db:
        visit = db.get(Visit, ids["visit"])
        deposit = PatientDeposit(patient_id=visit.patient_id, balance=Decimal("2.00"), currency="UZS")
        db.add(deposit)
        db.flush()
        db.add(DepositTransaction(deposit_id=deposit.id, transaction_type="credit",
                                  amount=Decimal("2.00"), balance_after=Decimal("2.00")))
        db.commit()
    with TestClient(app) as http:
        response = http.get("/api/v1/cashier/stats/by-currency", headers=headers)
    assert response.status_code == 200, response.text
    unknown, uzs = response.json()
    assert unknown["currency"] is None and unknown["requires_reconciliation"] is True
    assert uzs["currency"] == "UZS" and uzs["requires_reconciliation"] is True
    assert uzs["total_amount"] is None and uzs["paid_count"] is None


@pytest.mark.parametrize("evidence_loss", ["disabled guard", "missing column grant"])
def test_daily_http_nonowner_separates_only_verified_manual_credits(guarded_pg, monkeypatch, evidence_loss):
    from fastapi.testclient import TestClient
    from sqlalchemy import text
    from sqlalchemy.orm import Session

    from app.api.v1.endpoints.force_majeure import AddDepositRequest
    from app.services.force_majeure_api_service import ForceMajeureApiService

    engine, runtime, ids, app, headers, schema, runtime_role, _ = _daily_pg_app(guarded_pg, monkeypatch)
    with Session(engine) as db:
        credit = ForceMajeureApiService(db).add_to_deposit(
            request=AddDepositRequest(patient_id=ids["patient"], amount=Decimal("2.00"), client_request_id=uuid4()),
            current_user_id=ids["stage"],
        )
        assert credit["balance"] == 2
    with runtime.connect() as conn:
        assert conn.execute(text("""
            SELECT pg_catalog.has_column_privilege(CURRENT_USER,'deposit_transactions','client_request_id','SELECT')
              AND NOT pg_catalog.has_table_privilege(CURRENT_USER,'deposit_transactions','SELECT')
              AND NOT pg_catalog.has_column_privilege(CURRENT_USER,'deposit_transactions','description','SELECT')
        """)).scalar_one()

    quote = engine.dialect.identifier_preparer.quote_identifier
    table = f"{quote(schema)}.deposit_transactions"
    path = "/api/v1/cashier/stats/by-currency"
    with TestClient(app) as http:
        response = http.get(path, headers=headers)
        assert response.status_code == 200, response.text
        [item] = response.json()
        assert item["total_amount"] == "4.00" and item["pending_amount"] == "6.00"
        assert item["refunded_amount"] == "0.00" and item["requires_reconciliation"] is False
        with engine.begin() as conn:
            if evidence_loss == "disabled guard":
                conn.exec_driver_sql(f"ALTER TABLE {table} DISABLE TRIGGER trg_protect_manual_deposit_receipt")
            else:
                conn.exec_driver_sql(f"REVOKE SELECT (client_request_id) ON {table} FROM {quote(runtime_role)}")
        response = http.get(path, headers=headers)
        assert response.status_code == 200, response.text
        unknown, proved_currency = response.json()
        assert unknown["currency"] is None and unknown["requires_reconciliation"] is True
        assert proved_currency["currency"] == "UZS" and proved_currency["total_amount"] is None


def test_daily_report_uses_one_postgres_snapshot_during_concurrent_writes(guarded_pg, monkeypatch):
    import time
    from concurrent.futures import ThreadPoolExecutor

    from fastapi.testclient import TestClient
    from sqlalchemy import text

    from app.db.capability_namespace import capability_schema_name

    engine, runtime, ids, app, headers, schema, runtime_role, capability = _daily_pg_app(guarded_pg, monkeypatch)
    quote = engine.dialect.identifier_preparer.quote_identifier
    private, qs, qr, qc = map(quote, (capability_schema_name(schema), schema, runtime_role, capability))
    # Synthetic wrapper holds an advisory barrier inside the STABLE quote
    # function. The report's statement snapshot must predate both writes.
    barrier_key = 7340881001
    with engine.begin() as conn:
        conn.execute(text(f"ALTER FUNCTION {private}.encounter_benefit_quote(integer) RENAME TO encounter_benefit_quote_original"))
        conn.execute(text(f"""
          CREATE FUNCTION {private}.encounter_benefit_quote(target_visit integer) RETURNS jsonb
          LANGUAGE plpgsql STABLE SECURITY DEFINER SET search_path=pg_catalog SET row_security=on AS $$
          BEGIN
            PERFORM pg_catalog.pg_advisory_xact_lock({barrier_key});
            RETURN {private}.encounter_benefit_quote_original(target_visit);
          END $$
        """))
        conn.execute(text(f"ALTER FUNCTION {private}.encounter_benefit_quote(integer) OWNER TO {qc}"))
        conn.execute(text(f"REVOKE ALL ON FUNCTION {private}.encounter_benefit_quote(integer) FROM PUBLIC"))
        conn.execute(text(f"GRANT EXECUTE ON FUNCTION {private}.encounter_benefit_quote(integer) TO {qr}"))

    with engine.connect() as holder:
        transaction = holder.begin()
        holder.execute(text("SELECT pg_catalog.pg_advisory_xact_lock(:key)"), {"key": barrier_key})

        def report():
            with TestClient(app) as http:
                return http.get("/api/v1/cashier/stats/by-currency", headers=headers)

        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(report)
            deadline = time.monotonic() + 15
            while time.monotonic() < deadline:
                with engine.connect() as observer:
                    blocked = observer.execute(text("""
                      SELECT EXISTS (SELECT 1 FROM pg_catalog.pg_stat_activity
                        WHERE usename=:role AND pg_catalog.cardinality(pg_catalog.pg_blocking_pids(pid))>0)
                    """), {"role": runtime_role}).scalar_one()
                if blocked:
                    break
                if future.done():
                    raise AssertionError(f"report did not reach the barrier: {future.result().text}")
                time.sleep(0.02)
            else:
                raise AssertionError("report did not wait at the synthetic snapshot barrier")
            with engine.begin() as writer:
                writer.execute(text(f"UPDATE {qs}.payments SET amount=8.00 WHERE visit_id=:visit"), {"visit": ids["visit"]})
                writer.execute(text(f"UPDATE {qs}.visit_services SET price=20.00 WHERE visit_id=:visit"), {"visit": ids["visit"]})
            transaction.commit()
            response = future.result(timeout=15)
    assert response.status_code == 200, response.text
    [before] = response.json()
    assert before["total_amount"] == "4.00" and before["pending_amount"] == "6.00"
    with TestClient(app) as http:
        response = http.get("/api/v1/cashier/stats/by-currency", headers=headers)
    assert response.status_code == 200, response.text
    [after] = response.json()
    assert after["total_amount"] == "8.00" and after["pending_amount"] == "12.00"
