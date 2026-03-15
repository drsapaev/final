from __future__ import annotations

import pytest

from app.core.security import get_password_hash
from app.models.user import User


@pytest.mark.integration
def test_admin_users_endpoint_returns_admin_payload_shape(
    client,
    db_session,
    auth_headers,
):
    db_session.add(
        User(
            username="alpha_admin_users",
            email="alpha-admin-users@example.com",
            full_name="Alpha Admin Users",
            hashed_password=get_password_hash("secret"),
            role="Registrar",
            is_active=True,
            is_superuser=False,
        )
    )
    db_session.commit()

    response = client.get("/api/v1/admin/users", headers=auth_headers)

    assert response.status_code == 200
    payload = response.json()
    assert isinstance(payload, list)
    assert payload

    ids = [row["id"] for row in payload]
    assert ids == sorted(ids)

    alpha_row = next(row for row in payload if row["username"] == "alpha_admin_users")
    assert alpha_row == {
        "id": alpha_row["id"],
        "username": "alpha_admin_users",
        "full_name": "Alpha Admin Users",
        "email": "alpha-admin-users@example.com",
        "role": "Registrar",
        "is_active": True,
    }


@pytest.mark.integration
def test_admin_users_endpoint_rejects_non_admin_role(
    client,
    cardio_auth_headers,
):
    response = client.get("/api/v1/admin/users", headers=cardio_auth_headers)

    assert response.status_code == 403
