from __future__ import annotations

import pytest

from app.models.activation import Activation, ActivationStatus
from app.models.clinic import Branch, ClinicSettings
from app.models.user import User
from app.models.user_profile import (
    UserNotificationSettings,
    UserPreferences,
    UserProfile,
)


def build_payload(**overrides):
    payload = {
        "clinic": {
            "name": "Central Clinic",
            "address": "Main street 1",
            "phone": "+998901112233",
            "email": "clinic@example.com",
            "timezone": "Asia/Tashkent",
            "logo_url": "https://example.com/logo.png",
        },
        "branch": {
            "name": "Main Branch",
            "address": "Main street 1",
            "phone": "+998901112233",
            "email": "branch@example.com",
            "timezone": "Asia/Tashkent",
        },
        "admin": {
            "username": "admin",
            "password": "strongpass123",
            "full_name": "Clinic Admin",
            "email": "admin@example.com",
        },
        "activation_key": None,
    }
    payload.update(overrides)
    return payload


@pytest.mark.integration
def test_setup_status_is_minimal_and_false_on_fresh_install(client):
    response = client.get("/api/v1/setup/status")

    assert response.status_code == 200, response.text
    assert response.json() == {"initialized": False}


@pytest.mark.integration
def test_setup_initialize_creates_ssot_entities(client, db_session):
    response = client.post("/api/v1/setup/initialize", json=build_payload())

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["initialized"] is True
    assert body["activation_applied"] is False

    status_response = client.get("/api/v1/setup/status")
    assert status_response.status_code == 200, status_response.text
    assert status_response.json() == {"initialized": True}

    assert db_session.query(ClinicSettings).filter(ClinicSettings.key == "clinic_name").count() == 1
    assert db_session.query(Branch).count() == 1
    assert db_session.query(User).filter(User.username == "admin").count() == 1
    assert db_session.query(UserProfile).count() == 1
    assert db_session.query(UserPreferences).count() == 1
    assert db_session.query(UserNotificationSettings).count() == 1


@pytest.mark.integration
def test_setup_initialize_is_atomic_when_activation_fails(client, db_session):
    response = client.post(
        "/api/v1/setup/initialize",
        json=build_payload(activation_key="CQ-MISSING-KEY-00000-00000"),
    )

    assert response.status_code == 400, response.text
    assert "Activation failed" in response.json()["detail"]

    assert db_session.query(ClinicSettings).count() == 0
    assert db_session.query(Branch).count() == 0
    assert db_session.query(User).count() == 0


@pytest.mark.integration
def test_setup_initialize_applies_activation_when_key_exists(client, db_session):
    activation = Activation(
        key="CQ-TEST-ABCDE-FGHIJ-KLMNO",
        machine_hash=None,
        status=ActivationStatus.ISSUED,
    )
    db_session.add(activation)
    db_session.commit()

    response = client.post(
        "/api/v1/setup/initialize",
        json=build_payload(activation_key=activation.key),
    )

    assert response.status_code == 200, response.text
    assert response.json()["activation_applied"] is True

    db_session.refresh(activation)
    assert activation.status == ActivationStatus.ACTIVE
    assert activation.machine_hash


@pytest.mark.integration
def test_setup_initialize_rejects_second_run(client):
    first = client.post("/api/v1/setup/initialize", json=build_payload())
    assert first.status_code == 200, first.text

    second = client.post("/api/v1/setup/initialize", json=build_payload())
    assert second.status_code == 409, second.text
