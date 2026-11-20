from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.models.payment import Payment, PaymentVisit
from app.models.payment_webhook import PaymentTransaction, PaymentWebhook
from app.models.user import User
from app.models.visit import Visit
from app.services.analytics import AnalyticsService
from app.services.billing_service import BillingService
from app.services.billing_service_pkg import _payments as billing_payments
from app.services.queue_service import queue_service


@pytest.fixture
def admin_token(client: TestClient, admin_user: User, admin_password: str) -> str:
    from tests.conftest import mint_access_token

    return mint_access_token(admin_user)


@pytest.fixture
def doctor_token(client: TestClient, test_doctor_user: User) -> str:
    response = client.post(
        "/api/v1/authentication/login",
        json={"username": test_doctor_user.username, "password": "doctor123"},
    )
    assert response.status_code == 200
    return response.json()["access_token"]


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.parametrize(
    ("path", "expected_keys"),
    [
        ("/api/v1/analytics/appointment-flow", ["summary", "status_distribution", "conversion_rates"]),
        ("/api/v1/analytics/revenue-breakdown", ["total_revenue", "total_transactions", "daily_revenue"]),
        ("/api/v1/analytics/payment-providers", ["providers", "summary", "period"]),
        ("/api/v1/analytics/kpi-metrics", ["metrics", "summary", "period"]),
    ],
)
def test_analytics_legacy_contracts_exist(
    client: TestClient,
    admin_token: str,
    path: str,
    expected_keys: list[str],
) -> None:
    response = client.get(
        path,
        headers=_auth_headers(admin_token),
        params={"start_date": "2026-03-08", "end_date": "2026-04-07"},
    )

    assert response.status_code == 200, response.text
    payload: dict[str, Any] = response.json()
    for key in expected_keys:
        assert key in payload


def test_revenue_counts_settled_payments_once_and_keeps_currencies_separate(
    client: TestClient, admin_token: str, db_session, test_patient, monkeypatch,
) -> None:
    created_at = datetime(2032, 6, 7, 12, tzinfo=UTC)
    cardio = Visit(patient_id=test_patient.id, visit_date=created_at.date(), department="cardiology")
    lab = Visit(patient_id=test_patient.id, visit_date=created_at.date(), department="laboratory")
    db_session.add_all([cardio, lab])
    db_session.flush()

    online = Payment(
        visit_id=cardio.id, amount=Decimal("44.25"), currency="UZS",
        status="completed", method="click", provider="click", created_at=created_at,
    )
    ambiguous = Payment(
        visit_id=cardio.id, amount=Decimal("50.00"), currency="UZS",
        status="paid", method="cash", created_at=created_at,
    )
    db_session.add_all([online, ambiguous])
    db_session.add(Payment(
        visit_id=cardio.id, amount=Decimal("999.00"), currency="UZS",
        status="paid", method="cash", created_at=created_at + timedelta(hours=12),
    ))
    for visit_id, amount, currency, status in (
        (cardio.id, "125.50", "UZS", "paid"),
        (lab.id, "75.00", "UZS", "paid"),
        (cardio.id, "10.50", "USD", "paid"),
        (cardio.id, "33.20", "", "paid"),
        (cardio.id, "999.00", "UZS", "pending"),
        (cardio.id, "777.00", "UZS", "failed"),
    ):
        db_session.add(Payment(
            visit_id=visit_id, amount=Decimal(amount), currency=currency,
            status=status, method="cash", created_at=created_at,
        ))
    db_session.flush()
    db_session.add_all([
        PaymentVisit(payment_id=online.id, visit_id=cardio.id, amount=online.amount),
        PaymentVisit(payment_id=ambiguous.id, visit_id=lab.id, amount=ambiguous.amount),
    ])
    for _ in range(2):
        external_id = f"synthetic-{uuid4()}"
        receipt = PaymentWebhook(
            provider="click", webhook_id=external_id, transaction_id=external_id,
            amount=4425, currency="UZS", raw_data={}, status="success", created_at=created_at,
        )
        db_session.add(receipt)
        db_session.flush()
        db_session.add(PaymentTransaction(
            provider="click", transaction_id=external_id, amount=4425,
            currency="UZS", status="success", payment_id=online.id, webhook_id=receipt.id,
            created_at=created_at,
        ))
    db_session.commit()

    dashboard = AnalyticsService.calculate_revenue(
        db_session, created_at - timedelta(hours=1), created_at + timedelta(hours=1),
    )
    assert dashboard["total_revenue"] == 294.75
    assert dashboard["total_transactions"] == 4
    assert dashboard["by_provider"] == {"click": 44.25}
    assert dashboard["daily_revenue"] == {"2032-06-07": 294.75}
    assert dashboard["by_currency"]["USD"] == {"total_revenue": 10.50, "total_transactions": 1}
    assert dashboard["unclassified_transactions"] == 1
    assert dashboard["unattributed_transactions"] == 1

    response = client.get(
        "/api/v1/analytics/revenue-breakdown",
        headers=_auth_headers(admin_token),
        params={"start_date": "2032-06-07", "end_date": "2032-06-07", "department": "cardiology"},
    )
    assert response.status_code == 200, response.text
    filtered = response.json()
    assert filtered["currency"] == "UZS"
    assert filtered["basis"] == "gross_settled_payments"
    assert filtered["total_revenue"] == 169.75
    assert filtered["total_transactions"] == 2
    assert filtered["by_currency"]["USD"]["total_revenue"] == 10.50
    assert filtered["provider_breakdown"]["click"]["total_amount"] == 44.25
    assert filtered["department_breakdown"] == {"cardiology": {"visits": 1, "total_revenue": 169.75}}
    assert filtered["daily_revenue"] == [{"date": "2032-06-07", "amount": 169.75}]

    monkeypatch.setattr(queue_service, "get_local_timestamp", lambda db: created_at + timedelta(days=1))
    trends = client.get("/api/v1/analytics/trends", headers=_auth_headers(admin_token), params={"days": 2})
    assert trends.status_code == 200, trends.text
    assert trends.json()["revenue_trend"] == [
        {"date": "2032-06-06", "revenue": 0.0},
        {"date": "2032-06-07", "revenue": 1293.75},
    ]

    providers = client.get(
        "/api/v1/analytics/payment-providers",
        headers=_auth_headers(admin_token),
        params={"start_date": "2032-06-07", "end_date": "2032-06-07", "department": "cardiology"},
    )
    assert providers.status_code == 200, providers.text
    provider_report = providers.json()
    summary = provider_report["summary"]
    assert summary["total_transactions"] == 1
    assert summary["total_revenue"] == 44.25
    assert summary["total_commission"] is None
    assert provider_report["providers"]["click"]["success_rate"] is None


def test_revenue_groups_payments_by_posting_day(
    client: TestClient,
    admin_token: str,
    db_session,
    test_patient,
    monkeypatch,
) -> None:
    posting_day = datetime(2034, 7, 12, tzinfo=UTC)
    order_day = posting_day - timedelta(days=1)
    visit = Visit(
        patient_id=test_patient.id, visit_date=order_day.date(), department="cardiology"
    )
    db_session.add(visit)
    db_session.flush()
    db_session.add_all(
        [
            Payment(
                visit_id=visit.id,
                amount=Decimal("60.25"),
                currency="UZS",
                status="paid",
                method="click",
                provider="click",
                created_at=order_day + timedelta(hours=10),
                paid_at=posting_day + timedelta(hours=11),
            ),
            Payment(
                visit_id=visit.id,
                amount=Decimal("5.00"),
                currency="UZS",
                status="paid",
                method="cash",
                created_at=order_day + timedelta(hours=10),
            ),
        ]
    )
    db_session.commit()

    response = client.get(
        "/api/v1/analytics/revenue-breakdown",
        headers=_auth_headers(admin_token),
        params={
            "start_date": order_day.date().isoformat(),
            "end_date": posting_day.date().isoformat(),
        },
    )
    assert response.status_code == 200, response.text
    assert response.json()["daily_revenue"] == [
        {"date": order_day.date().isoformat(), "amount": 5.00},
        {"date": posting_day.date().isoformat(), "amount": 60.25},
    ]

    on_posting_day = AnalyticsService.calculate_revenue(
        db_session,
        posting_day,
        posting_day + timedelta(hours=23),
    )
    assert on_posting_day["total_revenue"] == 60.25
    assert on_posting_day["by_provider"] == {"click": 60.25}

    monkeypatch.setattr(
        queue_service, "get_local_timestamp", lambda db: posting_day + timedelta(days=1)
    )
    response = client.get(
        "/api/v1/analytics/trends",
        headers=_auth_headers(admin_token),
        params={"days": 2},
    )
    assert response.status_code == 200, response.text
    assert response.json()["revenue_trend"] == [
        {"date": order_day.date().isoformat(), "revenue": 5.00},
        {"date": posting_day.date().isoformat(), "revenue": 60.25},
    ]


def test_payment_confirmation_records_an_absolute_utc_time(
    db_session, test_patient, monkeypatch
) -> None:
    confirmed_at = datetime(2034, 7, 12, 6, 30, tzinfo=UTC)
    clock_time = confirmed_at

    class ConfirmationClock(datetime):
        @classmethod
        def now(cls, tz=None):
            return clock_time.astimezone(tz)

    monkeypatch.setattr(billing_payments, "datetime", ConfirmationClock)
    monkeypatch.setattr(
        BillingService,
        "_get_local_timestamp_naive",
        lambda self: confirmed_at.replace(tzinfo=None) + timedelta(hours=5),
    )
    visit = Visit(
        patient_id=test_patient.id,
        visit_date=confirmed_at.date(),
        department="cardiology",
    )
    db_session.add(visit)
    db_session.flush()
    payment = Payment(
        visit_id=visit.id,
        amount=Decimal("32.00"),
        currency="UZS",
        status="pending",
        method="click",
    )
    db_session.add(payment)
    db_session.flush()

    service = BillingService(db_session)
    settled = service.update_payment_status(payment.id, "paid", commit=False)
    assert settled.paid_at == confirmed_at
    clock_time += timedelta(days=1)
    assert (
        service.update_payment_status(payment.id, "paid", commit=False).paid_at
        == confirmed_at
    )


def test_predictive_endpoint_returns_flat_forecasts(
    client: TestClient,
    admin_token: str,
) -> None:
    response = client.get(
        "/api/v1/analytics/predictive",
        headers=_auth_headers(admin_token),
        params={
            "start_date": "2026-03-08",
            "end_date": "2026-04-07",
            "forecast_days": 5,
        },
    )

    assert response.status_code == 200, response.text
    payload: dict[str, Any] = response.json()

    assert isinstance(payload.get("forecasts"), list)
    assert payload["forecasts"], "expected non-empty forecast list"

    first_forecast = payload["forecasts"][0]
    assert first_forecast["metric"] in {"revenue", "patients", "appointments", "efficiency"}
    assert {"period", "value", "confidence", "trend", "unit", "factors"} <= set(
        first_forecast
    )
    assert "revenue" not in first_forecast
    assert "patients" not in first_forecast
    assert "appointments" not in first_forecast
    assert "efficiency" not in first_forecast


def test_appointment_flow_uses_string_dimension_keys(
    client: TestClient,
    admin_token: str,
) -> None:
    response = client.get(
        "/api/v1/analytics/appointment-flow",
        headers=_auth_headers(admin_token),
        params={"start_date": "2026-03-08", "end_date": "2026-04-07"},
    )

    assert response.status_code == 200, response.text
    payload: dict[str, Any] = response.json()

    assert all(
        isinstance(key, str) for key in payload.get("status_distribution", {}).keys()
    )
    assert all(
        isinstance(key, str)
        for key in payload.get("department_performance", {}).keys()
    )
    assert all(
        isinstance(key, str)
        for key in payload.get("day_of_week_distribution", {}).keys()
    )


def test_predictive_auxiliary_routes_are_alive(
    client: TestClient,
    admin_token: str,
) -> None:
    base_params = {
        "start_date": "2026-03-08",
        "end_date": "2026-04-07",
    }

    accuracy = client.get(
        "/api/v1/analytics/predictive/accuracy",
        headers=_auth_headers(admin_token),
        params=base_params,
    )
    scenarios = client.get(
        "/api/v1/analytics/predictive/scenarios",
        headers=_auth_headers(admin_token),
        params={**base_params, "scenario": "realistic"},
    )
    insights = client.get(
        "/api/v1/analytics/predictive/insights",
        headers=_auth_headers(admin_token),
        params={**base_params, "insight_type": "all"},
    )

    assert accuracy.status_code == 200, accuracy.text
    assert scenarios.status_code == 200, scenarios.text
    assert insights.status_code == 200, insights.text


@pytest.mark.parametrize(
    "path",
    [
        "/api/v1/analytics/predictive",
        "/api/v1/analytics/predictive/accuracy",
        "/api/v1/analytics/predictive/scenarios",
        "/api/v1/analytics/predictive/insights",
    ],
)
def test_doctor_cannot_read_predictive_financial_analytics(
    client: TestClient,
    doctor_token: str,
    path: str,
) -> None:
    response = client.get(
        path,
        headers=_auth_headers(doctor_token),
        params={"start_date": "2026-03-08", "end_date": "2026-04-07"},
    )

    assert response.status_code == 403


@pytest.mark.parametrize(
    "path",
    [
        "/api/v1/analytics/kpi-metrics",
        "/api/v1/analytics/predictive",
        "/api/v1/analytics/advanced/revenue/advanced",
        "/api/v1/analytics/export/revenue/export/json",
        "/api/v1/analytics/visualization/revenue",
    ],
)
def test_patient_cannot_read_staff_analytics_extension_routes(
    client: TestClient,
    patient_token: str,
    path: str,
) -> None:
    response = client.get(
        path,
        headers=_auth_headers(patient_token),
        params={"start_date": "2026-03-08", "end_date": "2026-04-07"},
    )

    assert response.status_code == 403


@pytest.mark.parametrize(
    "path",
    [
        "/api/v1/analytics/revenue-breakdown",
        "/api/v1/analytics/payment-providers",
    ],
)
def test_doctor_cannot_read_legacy_revenue_analytics(
    client: TestClient,
    doctor_token: str,
    path: str,
) -> None:
    response = client.get(
        path,
        headers=_auth_headers(doctor_token),
        params={"start_date": "2026-03-08", "end_date": "2026-04-07"},
    )

    assert response.status_code == 403


@pytest.mark.parametrize(
    "path",
    [
        "/api/v1/analytics/kpi-metrics",
        "/api/v1/analytics/kpi-trends",
        "/api/v1/analytics/kpi-comparison",
    ],
)
def test_doctor_cannot_read_kpi_financial_analytics(
    client: TestClient,
    doctor_token: str,
    path: str,
) -> None:
    response = client.get(
        path,
        headers=_auth_headers(doctor_token),
        params={"start_date": "2026-03-08", "end_date": "2026-04-07"},
    )

    assert response.status_code == 403


@pytest.mark.parametrize(
    "path",
    [
        "/api/v1/analytics/advanced/kpi",
        "/api/v1/analytics/advanced/doctors/performance",
        "/api/v1/analytics/advanced/revenue/advanced",
        "/api/v1/analytics/advanced/predictive",
        "/api/v1/analytics/advanced/comprehensive/advanced",
    ],
)
def test_doctor_cannot_read_advanced_financial_analytics(
    client: TestClient,
    doctor_token: str,
    path: str,
) -> None:
    response = client.get(
        path,
        headers=_auth_headers(doctor_token),
        params={"start_date": "2026-03-08", "end_date": "2026-04-07"},
    )

    assert response.status_code == 403


@pytest.mark.parametrize(
    "path",
    [
        "/api/v1/analytics/visualization/dashboard",
        "/api/v1/analytics/visualization/kpi",
        "/api/v1/analytics/visualization/revenue",
        "/api/v1/analytics/visualization/comprehensive",
    ],
)
def test_doctor_cannot_read_financial_analytics_visualizations(
    client: TestClient,
    doctor_token: str,
    path: str,
) -> None:
    response = client.get(
        path,
        headers=_auth_headers(doctor_token),
        params={"start_date": "2026-03-08", "end_date": "2026-04-07"},
    )

    assert response.status_code == 403


@pytest.mark.parametrize(
    ("path", "params"),
    [
        (
            "/api/v1/analytics/ai/usage-analytics",
            {"start_date": "2026-03-08", "end_date": "2026-04-07"},
        ),
        ("/api/v1/analytics/ai/usage-summary", {"days": 30}),
        ("/api/v1/analytics/ai/function-performance/diagnosis", {"days": 7}),
    ],
)
def test_doctor_cannot_read_ai_usage_cost_telemetry(
    client: TestClient,
    doctor_token: str,
    path: str,
    params: dict[str, Any],
) -> None:
    response = client.get(path, headers=_auth_headers(doctor_token), params=params)

    assert response.status_code == 403


def test_admin_can_read_ai_usage_cost_summary(
    client: TestClient,
    admin_token: str,
) -> None:
    response = client.get(
        "/api/v1/analytics/ai/usage-summary",
        headers=_auth_headers(admin_token),
        params={"days": 30},
    )

    assert response.status_code == 200, response.text
    payload: dict[str, Any] = response.json()
    assert "total_cost_usd" in payload
    assert "daily_average_cost" in payload


def test_admin_can_read_advanced_revenue_analytics(
    client: TestClient,
    admin_token: str,
) -> None:
    response = client.get(
        "/api/v1/analytics/advanced/revenue/advanced",
        headers=_auth_headers(admin_token),
        params={"start_date": "2026-03-08", "end_date": "2026-04-07"},
    )

    assert response.status_code == 200, response.text
    assert "total_revenue" in response.json()


def test_admin_can_read_revenue_analytics_visualization(
    client: TestClient,
    admin_token: str,
) -> None:
    response = client.get(
        "/api/v1/analytics/visualization/revenue",
        headers=_auth_headers(admin_token),
        params={"start_date": "2026-03-08", "end_date": "2026-04-07"},
    )

    assert response.status_code == 200, response.text
    assert "revenue_data" in response.json()


@pytest.mark.parametrize(
    "path",
    [
        "/api/v1/analytics/export/kpi/export/json",
        "/api/v1/analytics/export/comprehensive/export/json",
        "/api/v1/analytics/export/revenue/export/json",
    ],
)
def test_doctor_cannot_export_clinic_financial_analytics(
    client: TestClient,
    doctor_token: str,
    path: str,
) -> None:
    response = client.get(
        path,
        headers=_auth_headers(doctor_token),
        params={"start_date": "2026-03-08", "end_date": "2026-04-07"},
    )

    assert response.status_code == 403


def test_admin_can_export_revenue_analytics(
    client: TestClient,
    admin_token: str,
) -> None:
    response = client.get(
        "/api/v1/analytics/export/revenue/export/json",
        headers=_auth_headers(admin_token),
        params={"start_date": "2026-03-08", "end_date": "2026-04-07"},
    )

    assert response.status_code == 200, response.text
