"""Synthetic PostgreSQL regression for clinic-local cashier reporting."""

from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.models.clinic import ClinicSettings
from app.models.payment import Payment
from tests.integration.test_cashier_daily_currency import _daily_pg_app
from tests.integration.test_staff_confirmation_guard_pg import guarded_pg  # noqa: F401


@pytest.mark.parametrize("report", ["daily", "hourly"])
def test_cashier_report_uses_clinic_day_independent_of_session_timezone(guarded_pg, monkeypatch, report):
    engine, runtime, ids, app, headers, _, _, _ = _daily_pg_app(guarded_pg, monkeypatch)
    with Session(engine) as db:
        setting = db.query(ClinicSettings).filter_by(key="timezone").one_or_none()
        if setting is None:
            setting = ClinicSettings(key="timezone")
            db.add(setting)
        setting.category = "queue"
        setting.value = "Asia/Tashkent"
        payment = db.query(Payment).filter_by(visit_id=ids["visit"]).one()
        payment.created_at = datetime(2025, 1, 1, 20, 30, tzinfo=UTC)
        db.commit()

    def runtime_db_for(zone):
        def runtime_db():
            with Session(runtime) as db:
                db.execute(text("SELECT pg_catalog.set_config('TimeZone', :zone, true)"), {"zone": zone})
                yield db
                db.rollback()
        return runtime_db

    observed = {}
    for zone in ("UTC", "Asia/Tashkent"):
        app.dependency_overrides[get_db] = runtime_db_for(zone)
        with TestClient(app) as http:
            if report == "daily":
                response = http.get("/api/v1/cashier/stats/by-currency", headers=headers,
                                    params={"date_from": "2025-01-02", "date_to": "2025-01-02"})
            else:
                response = http.get("/api/v1/cashier/stats/hourly/by-currency", headers=headers,
                                    params={"target_date": "2025-01-02"})
        assert response.status_code == 200, response.text
        observed[zone] = response.json()

    assert observed["UTC"] == observed["Asia/Tashkent"]
    if report == "daily":
        assert observed["UTC"][0]["total_amount"] == "4.00"
    else:
        assert observed["UTC"][0]["hour"] == 1
        assert observed["UTC"][0]["amount"] == "4.00"
