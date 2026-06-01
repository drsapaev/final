from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.models.user import User


@pytest.fixture
def admin_token(client: TestClient, admin_user: User, admin_password: str) -> str:
    response = client.post(
        "/api/v1/authentication/login",
        json={"username": admin_user.username, "password": admin_password},
    )
    assert response.status_code == 200
    return response.json()["access_token"]


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
