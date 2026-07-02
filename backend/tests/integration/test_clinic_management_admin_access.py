import pytest

from app.api.v1.endpoints import clinic_management


def _login_admin(client, admin_user, admin_password):
    response = client.post(
        "/api/v1/authentication/login",
        json={"username": admin_user.username, "password": admin_password},
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest.mark.integration
def test_clinic_management_stats_and_health_are_admin_accessible(
    client,
    admin_user,
    admin_password,
):
    headers = _login_admin(client, admin_user, admin_password)

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
def test_clinic_license_expiring_route_dispatches_before_license_id(
    client,
    admin_user,
    admin_password,
    monkeypatch,
):
    def _fake_expiring_licenses(*, db, days_ahead):
        return [
            {
                "id": 7,
                "name": "Expiring License",
                "license_type": "software",
                "license_key": "license-key",
                "status": "active",
                "issued_by": None,
                "issued_date": None,
                "expires_date": None,
                "renewal_date": None,
                "cost": None,
                "features": None,
                "restrictions": None,
                "notes": None,
                "created_at": None,
                "updated_at": None,
                "activations_count": 0,
            }
        ]

    monkeypatch.setattr(
        clinic_management.license_management,
        "get_expiring_licenses",
        _fake_expiring_licenses,
    )
    headers = _login_admin(client, admin_user, admin_password)

    response = client.get("/api/v1/clinic/licenses/expiring", headers=headers)

    assert response.status_code == 200, response.text
    assert response.json()[0]["name"] == "Expiring License"


@pytest.mark.integration
def test_clinic_management_stats_and_health_do_not_use_request_state_auth_chain(
    client,
    admin_user,
    admin_password,
    monkeypatch,
):
    import app.api.deps as deps_module

    def _legacy_auth_chain_called(*args, **kwargs):
        raise AssertionError("Legacy request.state auth chain was called")

    # Если clinic endpoints снова будут опираться на request.state dependency path,
    # этот тест упадет на вызове legacy helpers.
    monkeypatch.setattr(deps_module, "require_authentication", _legacy_auth_chain_called)
    monkeypatch.setattr(deps_module, "get_current_user_from_request", _legacy_auth_chain_called)

    headers = _login_admin(client, admin_user, admin_password)

    stats_response = client.get("/api/v1/clinic/stats", headers=headers)
    assert stats_response.status_code == 200, stats_response.text

    health_response = client.get("/api/v1/clinic/health", headers=headers)
    assert health_response.status_code == 200, health_response.text
