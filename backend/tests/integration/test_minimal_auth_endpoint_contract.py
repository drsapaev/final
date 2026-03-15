from __future__ import annotations

import pytest

from app.core.security import get_password_hash
from app.models.user import User


@pytest.mark.integration
def test_minimal_login_endpoint_preserves_email_login_and_remember_me_contract(
    client,
    db_session,
):
    user = User(
        username="minimal_auth_user",
        email="minimal-auth@example.com",
        full_name="Minimal Auth User",
        hashed_password=get_password_hash("minimal-secret"),
        role="Registrar",
        is_active=True,
        is_superuser=False,
    )
    db_session.add(user)
    db_session.commit()

    response = client.post(
        "/api/v1/auth/minimal-login",
        json={
            "username": user.email,
            "password": "minimal-secret",
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
        "username": "minimal_auth_user",
        "email": "minimal-auth@example.com",
        "full_name": "Minimal Auth User",
        "role": "Registrar",
        "is_active": True,
        "is_superuser": False,
    }


@pytest.mark.integration
def test_minimal_login_endpoint_rejects_invalid_password(
    client,
    db_session,
):
    user = User(
        username="minimal_auth_invalid_password",
        email="minimal-auth-invalid@example.com",
        hashed_password=get_password_hash("correct-password"),
        role="Doctor",
        is_active=True,
        is_superuser=False,
    )
    db_session.add(user)
    db_session.commit()

    response = client.post(
        "/api/v1/auth/minimal-login",
        json={
            "username": user.username,
            "password": "wrong-password",
        },
    )

    assert response.status_code == 401
    assert response.json() == {"detail": "Неверные учетные данные"}
