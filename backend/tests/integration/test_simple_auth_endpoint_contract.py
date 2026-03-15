from __future__ import annotations

import pytest

from app.core.security import get_password_hash
from app.models.user import User


@pytest.mark.integration
def test_simple_login_endpoint_preserves_user_model_login_contract(
    client,
    db_session,
):
    user = User(
        username="simple_auth_user",
        email="simple-auth@example.com",
        full_name="Simple Auth User",
        hashed_password=get_password_hash("simple-secret"),
        role="Doctor",
        is_active=True,
        is_superuser=False,
    )
    db_session.add(user)
    db_session.commit()

    response = client.post(
        "/api/v1/auth/simple-login",
        json={
            "username": user.email,
            "password": "simple-secret",
            "remember_me": True,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["token_type"] == "bearer"
    assert payload["expires_in"] == 24 * 60 * 60
    assert isinstance(payload["access_token"], str)
    assert payload["user"] == {
        "id": user.id,
        "username": "simple_auth_user",
        "email": "simple-auth@example.com",
        "full_name": "Simple Auth User",
        "role": "Doctor",
        "is_active": True,
        "is_superuser": False,
    }


@pytest.mark.integration
def test_auth_me_endpoint_returns_live_authenticated_profile(
    client,
    auth_headers,
    admin_user,
):
    response = client.get("/api/v1/auth/me", headers=auth_headers)

    assert response.status_code == 200
    assert response.json() == {
        "id": admin_user.id,
        "username": admin_user.username,
        "full_name": admin_user.full_name,
        "email": admin_user.email,
        "role": admin_user.role,
        "is_active": admin_user.is_active,
        "is_superuser": admin_user.is_superuser,
    }
