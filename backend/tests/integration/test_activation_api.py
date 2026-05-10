from __future__ import annotations

import pytest


def _login_admin(client, admin_user):
    response = client.post(
        "/api/v1/authentication/login",
        json={"username": admin_user.username, "password": "admin123"},
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest.mark.integration
def test_activation_issue_list_revoke_roundtrip(client, admin_user):
    headers = _login_admin(client, admin_user)

    issue_response = client.post(
        "/api/v1/activation/issue",
        json={
            "days": 30,
            "status": "trial",
            "meta": "{\"description\":\"QA smoke\",\"max_devices\":1}",
        },
        headers=headers,
    )
    assert issue_response.status_code == 200, issue_response.text
    issued = issue_response.json()
    assert issued["key"]
    assert issued["status"] == "trial"

    list_response = client.get(
        "/api/v1/activation/list",
        params={"key_like": issued["key"]},
        headers=headers,
    )
    assert list_response.status_code == 200, list_response.text
    listed = list_response.json()
    assert listed["total"] >= 1
    assert any(row["key"] == issued["key"] for row in listed["items"])

    status_response = client.get("/api/v1/activation/status", headers=headers)
    assert status_response.status_code == 200, status_response.text
    assert "ok" in status_response.json()

    revoke_response = client.post(
        "/api/v1/activation/revoke",
        json={"key": issued["key"]},
        headers=headers,
    )
    assert revoke_response.status_code == 200, revoke_response.text
    assert revoke_response.json()["ok"] is True

    revoked_list_response = client.get(
        "/api/v1/activation/list",
        params={"key_like": issued["key"], "status": "revoked"},
        headers=headers,
    )
    assert revoked_list_response.status_code == 200, revoked_list_response.text
    revoked_listed = revoked_list_response.json()
    assert any(row["status"] == "revoked" for row in revoked_listed["items"])


@pytest.mark.integration
def test_activation_list_rejects_non_admin_access(client, registrar_user):
    response = client.post(
        "/api/v1/authentication/login",
        json={"username": registrar_user.username, "password": "registrar123"},
    )
    assert response.status_code == 200, response.text
    headers = {"Authorization": f"Bearer {response.json()['access_token']}"}

    list_response = client.get("/api/v1/activation/list", headers=headers)
    assert list_response.status_code == 403, list_response.text
