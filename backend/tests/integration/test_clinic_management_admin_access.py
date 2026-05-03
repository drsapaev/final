import pytest


from tests.auth_test_credentials import (
    ADMIN_PASSWORD,
)

def _login_admin(client, admin_user):
    response = client.post(
        "/api/v1/authentication/login",
        json={"username": admin_user.username, "password": ADMIN_PASSWORD},
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest.mark.integration
def test_clinic_management_stats_and_health_are_admin_accessible(
    client,
    admin_user,
):
    headers = _login_admin(client, admin_user)

    stats_response = client.get("/api/v1/clinic/stats", headers=headers)
    assert stats_response.status_code == 200, stats_response.text
    stats = stats_response.json()
    assert "total_branches" in stats
    assert "system_health" in stats

    health_response = client.get("/api/v1/clinic/health", headers=headers)
    assert health_response.status_code == 200, health_response.text
    health = health_response.json()
    assert "status" in health


@pytest.mark.integration
def test_clinic_management_stats_and_health_do_not_use_request_state_auth_chain(
    client,
    admin_user,
    monkeypatch,
):
    import app.api.deps as deps_module

    def _legacy_auth_chain_called(*args, **kwargs):
        raise AssertionError("Legacy request.state auth chain was called")

    # Если clinic endpoints снова будут опираться на request.state dependency path,
    # этот тест упадет на вызове legacy helpers.
    monkeypatch.setattr(deps_module, "require_authentication", _legacy_auth_chain_called)
    monkeypatch.setattr(deps_module, "get_current_user_from_request", _legacy_auth_chain_called)

    headers = _login_admin(client, admin_user)

    stats_response = client.get("/api/v1/clinic/stats", headers=headers)
    assert stats_response.status_code == 200, stats_response.text

    health_response = client.get("/api/v1/clinic/health", headers=headers)
    assert health_response.status_code == 200, health_response.text
