"""Regression: GET /admin/wizard-settings must return 200.

The handler returned a bare WizardSettingsResponse model while the route
declares response_model=dict[str, Any] — FastAPI's serialize_response
raised dict_type AFTER the handler's try/except, so every GET 500'd once
the settings row existed (Sentry request.completed x57, 2026-09-30).
"""
from __future__ import annotations

from app.api.deps import create_access_token
from app.core.security import get_password_hash
from app.models.clinic import ClinicSettings
from app.models.user import User


def _admin(db, username: str) -> User:
    user = User(
        username=username,
        email=f"{username}@test.local",
        full_name=f"Wizard {username}",
        hashed_password=get_password_hash("Passw0rd!123"),
        role="Admin",
        is_active=True,
        is_superuser=False,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _auth(user: User) -> dict[str, str]:
    return {
        "Authorization": "Bearer "
        + create_access_token({"sub": str(user.id), "role": user.role})
    }


def test_get_wizard_settings_returns_200_with_row(client, db_session):
    user = _admin(db_session, "wiz_row")
    db_session.add(
        ClinicSettings(
            key="wizard_use_new_version",
            category="wizard",
            value={"enabled": True, "updated_by": user.id},
        )
    )
    db_session.commit()

    r = client.get("/api/v1/admin/wizard-settings", headers=_auth(user))
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["use_new_wizard"] is True
    assert "updated_at" in body


def test_get_wizard_settings_returns_200_without_row(client, db_session):
    """Missing row takes the default branch — same return shape, same bug."""
    user = _admin(db_session, "wiz_norow")
    r = client.get("/api/v1/admin/wizard-settings", headers=_auth(user))
    assert r.status_code == 200, r.text
    assert r.json()["use_new_wizard"] is False
