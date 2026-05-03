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


def test_system_webhook_stats_route_is_not_captured_by_webhook_id_route(
    client: TestClient,
    admin_user: User,
):
    token = admin_token(client, admin_user)
    response = client.get(
        "/api/v1/webhooks/system/stats",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert "total_webhooks" in payload
    assert "active_webhooks" in payload
    assert "pending_retries" in payload

