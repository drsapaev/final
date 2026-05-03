from __future__ import annotations

from fastapi.testclient import TestClient

from app.models.user import User


from tests.auth_test_credentials import (
    ADMIN_PASSWORD,
)

def admin_token(client: TestClient, admin_user: User) -> str:
    response = client.post(
        "/api/v1/auth/minimal-login",
        json={"username": admin_user.username, "password": ADMIN_PASSWORD},
    )
    assert response.status_code == 200
    return response.json()["access_token"]


def test_admin_static_routes_are_not_shadowed_by_dynamic_routes(
    client: TestClient,
    admin_user: User,
):
    token = admin_token(client, admin_user)
    headers = {"Authorization": f"Bearer {token}"}

    system_info = client.get("/api/v1/clinic/system/info", headers=headers)
    assert system_info.status_code in (200, 404)
    assert system_info.status_code != 422

    doctors_stats = client.get("/api/v1/admin/doctors/stats", headers=headers)
    assert doctors_stats.status_code in (200, 500)
    assert doctors_stats.status_code != 422

    departments_overview = client.get(
        "/api/v1/admin/departments/overview", headers=headers
    )
    assert departments_overview.status_code in (200, 500)
    assert departments_overview.status_code != 422
    if departments_overview.status_code == 200:
        body = departments_overview.json()
        assert body.get("success") is True
        data = body.get("data") or {}
        assert "departments" in data and "totals" in data

