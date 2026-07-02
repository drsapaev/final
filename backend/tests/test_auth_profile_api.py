from __future__ import annotations

from app.models.user import User
from app.models.user_profile import UserProfile


def test_auth_csrf_token_endpoint_sets_cookie(client):
    response = client.get("/api/v1/auth/csrf-token")

    assert response.status_code == 200
    data = response.json()
    assert data["csrf_token"]
    assert response.cookies.get("csrf_token") == data["csrf_token"]


def test_get_self_profile_bootstraps_missing_profile(
    client, auth_headers, admin_user, db_session
):
    existing_profile = (
        db_session.query(UserProfile).filter(UserProfile.user_id == admin_user.id).first()
    )
    if existing_profile is not None:
        db_session.delete(existing_profile)
        db_session.commit()

    db_session.expire_all()
    assert (
        db_session.query(UserProfile).filter(UserProfile.user_id == admin_user.id).first()
        is None
    )

    response = client.get("/api/v1/authentication/profile", headers=auth_headers)

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == admin_user.id
    assert data["username"] == admin_user.username
    assert data["role"] == admin_user.role
    assert "two_factor_enabled" in data
    assert "updated_at" in data
    assert (
        db_session.query(UserProfile).filter(UserProfile.user_id == admin_user.id).first()
        is not None
    )


def test_update_self_profile_persists_user_and_profile_fields(
    client, auth_headers, admin_user, db_session
):
    response = client.put(
        "/api/v1/authentication/profile",
        headers=auth_headers,
        json={
            "full_name": "Updated Admin",
            "first_name": "Updated",
            "last_name": "Admin",
            "email": "updated-admin@test.com",
            "phone": "+998901234567",
            "bio": "Updated biography",
            "language": "en",
            "timezone": "Asia/Tashkent",
            "website": "https://example.test/profile",
        },
    )

    assert response.status_code == 200
    data = response.json()

    assert data["full_name"] == "Updated Admin"
    assert data["first_name"] == "Updated"
    assert data["last_name"] == "Admin"
    assert data["email"] == "updated-admin@test.com"
    assert data["phone"] == "+998901234567"
    assert data["bio"] == "Updated biography"
    assert data["language"] == "en"
    assert data["timezone"] == "Asia/Tashkent"
    assert data["website"] == "https://example.test/profile"
    assert data["email_verified"] is False
    assert data["phone_verified"] is False

    db_session.expire_all()
    user = db_session.query(User).filter(User.id == admin_user.id).first()
    profile = (
        db_session.query(UserProfile).filter(UserProfile.user_id == admin_user.id).first()
    )

    assert user is not None
    assert profile is not None
    assert user.full_name == "Updated Admin"
    assert user.email == "updated-admin@test.com"
    assert profile.full_name == "Updated Admin"
    assert profile.phone == "+998901234567"
    assert profile.bio == "Updated biography"
    assert profile.language == "en"
    assert profile.timezone == "Asia/Tashkent"


def test_registrar_can_read_and_update_own_profile(
    client, registrar_auth_headers, registrar_user, db_session
):
    get_response = client.get(
        "/api/v1/authentication/profile", headers=registrar_auth_headers
    )
    assert get_response.status_code == 200
    assert get_response.json()["id"] == registrar_user.id

    put_response = client.put(
        "/api/v1/authentication/profile",
        headers=registrar_auth_headers,
        json={
            "full_name": "Registrar Updated",
            "phone": "+998909999999",
        },
    )
    assert put_response.status_code == 200
    assert put_response.json()["full_name"] == "Registrar Updated"
    assert put_response.json()["phone"] == "+998909999999"
