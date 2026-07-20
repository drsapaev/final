"""Characterization tests for FCM notification endpoints (PR-2).

These tests reproduce the HTTP 500 errors described in the backend audit:
all FCM endpoints touched the non-existent `User.fcm_token` field (the real
column is `User.device_token`), and called non-existent
`crud_user.update_user`, `crud_user.get_users_by_ids`,
`crud_user.get_users_with_fcm_tokens` functions.

Audit: /home/z/my-project/download/AUDIT_PR1_MOBILE_EXTENDED.md
"""
from __future__ import annotations

from datetime import datetime
from uuid import uuid4

import pytest

from app.core.security import get_password_hash
from app.models.user import User


def _suffix() -> str:
    return uuid4().hex[:10]


def _make_user(db_session, *, role: str = "Patient") -> User:
    s = _suffix()
    user = User(
        username=f"fcm_{role.lower()}_{s}",
        email=f"fcm-{role.lower()}-{s}@test.local",
        full_name=f"FCM Test {role}",
        hashed_password=get_password_hash("pass123"),
        role=role,
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def _login(client, user: User) -> dict[str, str]:
    response = client.post(
        "/api/v1/authentication/login",
        json={"username": user.username, "password": "pass123"},
    )
    assert response.status_code == 200, response.text
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_register_fcm_token_returns_200(client, db_session):
    """POST /api/v1/fcm/register-token should return 200, not 500."""
    user = _make_user(db_session)
    headers = _login(client, user)

    response = client.post(
        "/api/v1/fcm/register-token",
        headers=headers,
        json={
            "device_token": "abc123token",
            "device_type": "android",
            "device_info": {"model": "Pixel 8"},
        },
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["success"] is True

    # Verify token was actually persisted
    db_session.expire_all()
    refreshed = db_session.query(User).filter(User.id == user.id).first()
    assert refreshed.device_token == "abc123token"


def test_unregister_fcm_token_returns_200(client, db_session):
    """DELETE /api/v1/fcm/unregister-token should return 200, not 500."""
    user = _make_user(db_session)
    user.device_token = "tok-to-clear"
    db_session.commit()

    headers = _login(client, user)

    response = client.delete("/api/v1/fcm/unregister-token", headers=headers)

    assert response.status_code == 200, response.text
    db_session.expire_all()
    refreshed = db_session.query(User).filter(User.id == user.id).first()
    assert refreshed.device_token is None


def test_get_user_tokens_returns_200(client, db_session):
    """GET /api/v1/fcm/user-tokens (admin) should return 200, not 500."""
    admin = _make_user(db_session, role="Admin")
    # Seed a user with a token
    _make_user(db_session)
    headers = _login(client, admin)

    response = client.get("/api/v1/fcm/user-tokens", headers=headers)

    assert response.status_code == 200, response.text
    body = response.json()
    assert "users" in body
    assert "total_count" in body


def test_get_fcm_status_returns_200(client, db_session):
    """GET /api/v1/fcm/status (admin) should return 200, not 500."""
    admin = _make_user(db_session, role="Admin")
    headers = _login(client, admin)

    response = client.get("/api/v1/fcm/status", headers=headers)

    assert response.status_code == 200, response.text
    body = response.json()
    assert "fcm_service" in body
    assert "timestamp" in body


def test_register_token_idempotent(client, db_session):
    """Repeated register-token calls should overwrite the previous token."""
    user = _make_user(db_session)
    headers = _login(client, user)

    r1 = client.post(
        "/api/v1/fcm/register-token",
        headers=headers,
        json={"device_token": "first-token", "device_type": "web"},
    )
    assert r1.status_code == 200

    r2 = client.post(
        "/api/v1/fcm/register-token",
        headers=headers,
        json={"device_token": "second-token", "device_type": "android"},
    )
    assert r2.status_code == 200

    db_session.expire_all()
    refreshed = db_session.query(User).filter(User.id == user.id).first()
    assert refreshed.device_token == "second-token"
