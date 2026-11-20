"""Hourly reports must not add or relabel different currencies."""
from datetime import datetime
from decimal import Decimal

from app.models.payment import Payment
from app.models.visit import Visit
from tests.integration.test_staff_confirmation_guard_pg import guarded_pg  # noqa: F401


def _payment(db, patient, amount, currency, *, hour=10):
    visit = Visit(patient_id=patient.id, status="open")
    db.add(visit)
    db.flush()
    db.add(Payment(visit_id=visit.id, amount=Decimal(amount), currency=currency, method="cash",
                   status="paid", created_at=datetime(2099, 1, 1, hour, 30)))
    db.commit()


def test_hourly_uzs_contract_and_auth(client, db_session, test_patient, admin_auth_headers, cardio_auth_headers):
    _payment(db_session, test_patient, "10.25", "UZS")
    path = "/api/v1/cashier/stats/hourly?target_date=2099-01-01"
    assert client.get(path).status_code == 401
    assert client.get(path, headers=cardio_auth_headers).status_code == 403
    response = client.get(path, headers=admin_auth_headers)
    assert response.status_code == 200, response.text
    data = response.json()
    assert len(data) == 24
    assert data[10]["count"] == 1 and Decimal(str(data[10]["amount"])) == Decimal("10.25")


def test_hourly_mixed_and_unknown_never_become_uzs(client, db_session, test_patient, admin_auth_headers):
    _payment(db_session, test_patient, "10.25", "UZS")
    _payment(db_session, test_patient, "2.10", "USD")
    _payment(db_session, test_patient, "3.05", "")
    _payment(db_session, test_patient, "999.99", "bad")
    _payment(db_session, test_patient, "2.25", "USD", hour=11)
    base = "/api/v1/cashier/stats/hourly"
    old = client.get(base + "?target_date=2099-01-01", headers=admin_auth_headers)
    assert old.status_code == 409, old.text
    result = client.get(base + "/by-currency?target_date=2099-01-01", headers=admin_auth_headers)
    assert result.status_code == 200, result.text
    assert result.json() == [
        {"hour": 10, "currency": None, "count": 2, "amount": None, "requires_reconciliation": True},
        {"hour": 10, "currency": "USD", "count": None, "amount": None, "requires_reconciliation": True},
        {"hour": 10, "currency": "UZS", "count": None, "amount": None, "requires_reconciliation": True},
        {"hour": 11, "currency": "USD", "count": 1, "amount": "2.25", "requires_reconciliation": False},
    ]


def test_empty_hourly_report_retains_existing_24_zero_hours(client, admin_auth_headers):
    base = "/api/v1/cashier/stats/hourly"
    old = client.get(base + "?target_date=2099-01-01", headers=admin_auth_headers)
    assert old.status_code == 200, old.text
    assert len(old.json()) == 24 and all(item["count"] == 0 for item in old.json())
    result = client.get(base + "/by-currency?target_date=2099-01-01", headers=admin_auth_headers)
    assert result.status_code == 200 and result.json() == []


def test_hourly_http_pins_auth_and_proves_nonowner_force_rls(guarded_pg, monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from sqlalchemy import text
    from sqlalchemy.orm import Session

    from app.api.deps import get_db
    from app.api.v1.endpoints.cashier import router
    from app.core.config import settings
    from app.models.user import User
    from tests.conftest import mint_access_token

    engine, runtime, ids = guarded_pg
    schema = engine.dialect.default_schema_name
    runtime_role = runtime.url.username
    quote = engine.dialect.identifier_preparer.quote_identifier
    qs, qr = quote(schema), quote(runtime_role)
    for key in ("DOCTOR_PRICE_DB_SCHEMA", "DOCTOR_PRICE_DB_SCHEMA_OWNER",
                "INVITATION_DB_SCHEMA", "INVITATION_DB_SCHEMA_OWNER"):
        monkeypatch.setattr(settings, key, None)
    with Session(engine) as db:
        actor = db.get(User, ids["stage"])
        token = mint_access_token(actor)
        db.add(Payment(visit_id=ids["visit"], amount=Decimal("10.25"), currency="USD", method="cash",
                       status="paid", created_at=datetime(2099, 1, 1, 10, 30)))
        db.commit()
    app = FastAPI()
    app.include_router(router, prefix="/api/v1/cashier")

    def runtime_db():
        with Session(runtime) as db:
            db.connection()
            yield db
            db.rollback()

    app.dependency_overrides[get_db] = runtime_db
    headers = {"Authorization": f"Bearer {token}"}
    path = "/api/v1/cashier/stats/hourly/by-currency?target_date=2099-01-01"
    with TestClient(app) as http:
        response = http.get(path, headers=headers)
        assert response.status_code == 200, response.text
        assert response.json() == [{"hour": 10, "currency": "USD", "count": 1, "amount": "10.25",
                                    "requires_reconciliation": False}]
        with engine.begin() as conn:
            conn.execute(text(f"ALTER POLICY financial_backend_select ON {qs}.payments USING (false)"))
        assert http.get(path, headers=headers).status_code == 503
        with engine.begin() as conn:
            conn.execute(text(f"ALTER POLICY financial_backend_select ON {qs}.payments USING (true)"))
            conn.execute(text(f"REVOKE SELECT (amount) ON {qs}.payments FROM {qr}"))
        assert http.get(path, headers=headers).status_code == 503
        with engine.begin() as conn:
            conn.execute(text(f"GRANT SELECT (amount) ON {qs}.payments TO {qr}"))
            conn.execute(text(f"UPDATE {qs}.users SET role='Doctor' WHERE id=:actor"), {"actor": ids["stage"]})

        def shadowed_runtime_db():
            with Session(runtime) as db:
                db.connection()
                db.execute(text(f"CREATE TEMP TABLE users AS SELECT * FROM {qs}.users WHERE id=:actor"),
                           {"actor": ids["stage"]})
                db.execute(text("UPDATE pg_temp.users SET role='Admin'"))
                db.execute(text(f"SET LOCAL search_path TO pg_temp, {qs}, pg_catalog"))
                yield db
                db.rollback()

        app.dependency_overrides[get_db] = shadowed_runtime_db
        assert http.get(path, headers=headers).status_code == 403
