from __future__ import annotations

import pytest


@pytest.fixture
def doctor_headers(client, test_doctor_user):
    response = client.post(
        "/api/v1/authentication/login",
        json={"username": test_doctor_user.username, "password": "doctor123"},
    )
    assert response.status_code == 200
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.integration
@pytest.mark.parametrize(
    ("path", "expected_key"),
    [
        ("/api/v1/specialized/dentistry/patients", "patients"),
        ("/api/v1/specialized/dentistry/visits", "visits"),
        ("/api/v1/specialized/cardiology/patients", "patients"),
        ("/api/v1/specialized/cardiology/visits", "visits"),
    ],
)
def test_specialized_panel_endpoints_accept_list_role_dependencies(
    client,
    auth_headers,
    path: str,
    expected_key: str,
):
    response = client.get(path, headers=auth_headers)

    assert response.status_code == 200, response.text
    body = response.json()
    assert expected_key in body


@pytest.mark.integration
@pytest.mark.parametrize(
    "path",
    [
        "/api/v1/specialized/dentistry/patients",
        "/api/v1/specialized/dentistry/visits",
        "/api/v1/specialized/cardiology/patients",
        "/api/v1/specialized/cardiology/visits",
    ],
)
def test_doctor_can_still_read_clinical_specialized_panel_lists(
    client,
    doctor_headers,
    path: str,
):
    response = client.get(path, headers=doctor_headers)

    assert response.status_code == 200, response.text


@pytest.mark.integration
@pytest.mark.parametrize(
    "path",
    [
        "/api/v1/specialized/cardiology/analytics",
        "/api/v1/specialized/dentistry/analytics",
        "/api/v1/specialized/specialized/statistics",
    ],
)
def test_doctor_cannot_read_specialized_financial_analytics(
    client,
    doctor_headers,
    path: str,
):
    response = client.get(path, headers=doctor_headers)

    assert response.status_code == 403


@pytest.mark.integration
@pytest.mark.parametrize(
    ("path", "expected_key"),
    [
        ("/api/v1/specialized/cardiology/analytics", "total_revenue"),
        ("/api/v1/specialized/dentistry/analytics", "total_revenue"),
        ("/api/v1/specialized/specialized/statistics", "total"),
    ],
)
def test_admin_can_read_specialized_financial_analytics(
    client,
    auth_headers,
    path: str,
    expected_key: str,
):
    response = client.get(path, headers=auth_headers)

    assert response.status_code == 200, response.text
    assert expected_key in response.json()
