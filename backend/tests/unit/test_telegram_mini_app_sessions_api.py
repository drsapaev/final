"""Real JSON/Bearer contracts for the patient devices screen."""

import uuid

import pytest

from app.api.v1.endpoints import admin_telegram
from app.main import app
from app.models.patient_access_audit import PatientAccessAuditLog
from app.models.telegram_config import TelegramConfig
from app.services.telegram_mini_app_jwt import (
    exchange_init_data_for_jwt,
    revoke_patient_sessions,
)
from tests.unit.test_telegram_mini_app_jwt import (
    BOT_TOKEN,
    create_session,
    link_patient,
    signed_init_data,
)

PREFIX = "/api/v1/telegram/mini-app"


@pytest.fixture
def linked(db_session, test_patient, monkeypatch):
    monkeypatch.setattr(
        admin_telegram, "_get_configured_bot_token", lambda db: BOT_TOKEN
    )
    db_session.add(TelegramConfig(bot_token=BOT_TOKEN, active=True))
    db_session.commit()
    return link_patient(db_session, test_patient)


def test_exchange_accepts_json_and_sets_no_store(client, linked):
    response = client.post(
        PREFIX + "/auth/exchange", json={"init_data": signed_init_data()}
    )
    assert response.status_code == 200, response.text
    assert response.headers["cache-control"] == "no-store"
    pair = response.json()
    response = client.post(
        PREFIX + "/sessions/list",
        json={},
        headers={"Authorization": f"Bearer {pair['access_token']}"},
    )
    assert response.status_code == 200, response.text
    assert response.json()["sessions"][0]["is_current"] is True
    assert set(response.json()["sessions"][0]) == {
        "id",
        "device_label",
        "created_at",
        "last_active_at",
        "expires_at",
        "is_current",
    }
    rotated = client.post(
        PREFIX + "/auth/refresh",
        json={"refresh_token": pair["refresh_token"]},
    )
    assert rotated.status_code == 200, rotated.text
    assert rotated.json()["refresh_token"] != pair["refresh_token"]


def test_session_management_requires_jwt_not_init_data(client, linked):
    response = client.post(
        PREFIX + "/sessions/list", json={"init_data": signed_init_data()}
    )
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


@pytest.mark.parametrize(
    "field,value",
    [
        ("patient_id", None),
        ("chat_id", 730002),
        ("active", False),
        ("blocked", True),
        ("notifications_enabled", False),
        ("appointment_reminders", False),
    ],
)
def test_restored_link_requires_new_launch_and_hides_old_device(
    client, linked, db_session, field, value
):
    first = client.post(
        PREFIX + "/auth/exchange", json={"init_data": signed_init_data()}
    )
    assert first.status_code == 200, first.text
    old = first.json()
    old_headers = {"Authorization": f"Bearer {old['access_token']}"}
    listed = client.post(PREFIX + "/sessions/list", json={}, headers=old_headers)
    old_id = listed.json()["sessions"][0]["id"]
    original = getattr(linked, field)
    setattr(linked, field, value)
    db_session.commit()
    setattr(linked, field, original)
    db_session.commit()

    for path in ("/sessions/list", "/patient/manifest"):
        denied = client.post(
            PREFIX + path,
            json={"initData": signed_init_data()},
            headers=old_headers,
        )
        assert denied.status_code == 401, denied.text
    denied_refresh = client.post(
        PREFIX + "/auth/refresh", json={"refresh_token": old["refresh_token"]}
    )
    assert denied_refresh.status_code == 401, denied_refresh.text

    fresh = client.post(
        PREFIX + "/auth/exchange", json={"init_data": signed_init_data()}
    )
    assert fresh.status_code == 200, fresh.text
    fresh_headers = {"Authorization": f"Bearer {fresh.json()['access_token']}"}
    current = client.post(PREFIX + "/sessions/list", json={}, headers=fresh_headers)
    assert current.status_code == 200, current.text
    assert current.json()["total"] == 1
    assert current.json()["sessions"][0]["id"] != old_id
    assert current.json()["sessions"][0]["is_current"] is True


def test_consumed_init_data_cannot_bypass_logout_without_bearer(
    client, linked, db_session
):
    launch = signed_init_data()
    pair = exchange_init_data_for_jwt(db_session, launch, bot_token=BOT_TOKEN)
    revoke_patient_sessions(db_session, pair["access_token"], logout=True)
    for path in ("/patient/manifest", "/cabinet/summary", "/forms/preview"):
        response = client.post(PREFIX + path, json={"initData": launch})
        assert response.status_code == 401, response.text


def test_bearer_reads_manifest_and_cabinet_then_revocation_blocks_fallback(
    client,
    linked,
    db_session,
):
    pair = create_session(db_session)
    headers = {"Authorization": f"Bearer {pair['access_token']}"}
    for path in ("/patient/manifest", "/cabinet/summary", "/forms/preview"):
        response = client.post(PREFIX + path, json={}, headers=headers)
        assert response.status_code == 200, response.text
    revoke_patient_sessions(db_session, pair["access_token"], logout=True)
    response = client.post(
        PREFIX + "/patient/manifest",
        json={"initData": signed_init_data()},
        headers=headers,
    )
    assert response.status_code == 401


@pytest.mark.parametrize(
    "path,body",
    [
        ("/cabinet/summary", {}),
        ("/forms/preview", {}),
        ("/forms/submissions", {"formId": "patient_intake", "answers": {}}),
        ("/reports/download", {"reportId": 1}),
        ("/booking/departments", {}),
        ("/booking/services", {}),
        ("/appointments/preview", {"appointmentDate": "2099-01-01"}),
    ],
)
def test_protected_patient_routes_reject_invalid_bearer_before_data(
    client,
    linked,
    path,
    body,
):
    response = client.post(
        PREFIX + path,
        json={**body, "initData": signed_init_data()},
        headers={"Authorization": "Bearer invalid-synthetic-token"},
    )
    assert response.status_code == 401, response.text


def test_revoke_others_current_guard_logout_and_audit(client, linked, db_session):
    other = create_session(db_session)
    current = create_session(db_session)
    headers = {"Authorization": f"Bearer {current['access_token']}"}
    listed = client.post(PREFIX + "/sessions/list", json={}, headers=headers).json()
    current_id = next(row["id"] for row in listed["sessions"] if row["is_current"])
    response = client.post(
        PREFIX + f"/sessions/{current_id}/revoke",
        json={},
        headers=headers,
    )
    assert response.status_code == 400
    response = client.post(PREFIX + "/sessions/revoke-all", json={}, headers=headers)
    assert response.status_code == 200
    assert response.json()["revoked_count"] == 1
    assert (
        client.post(
            PREFIX + "/sessions/list",
            json={},
            headers={"Authorization": f"Bearer {other['access_token']}"},
        ).status_code
        == 401
    )
    assert (
        client.post(
            PREFIX + f"/sessions/{uuid.uuid4()}/revoke",
            json={},
            headers=headers,
        ).status_code
        == 404
    )
    assert (
        client.post(PREFIX + "/auth/logout", json={}, headers=headers).status_code
        == 200
    )
    assert (
        client.post(PREFIX + "/sessions/list", json={}, headers=headers).status_code
        == 401
    )
    actions = {
        row.action
        for row in db_session.query(PatientAccessAuditLog).filter(
            PatientAccessAuditLog.resource_type == "session_management"
        )
    }
    assert {"view", "revoke_others", "logout"}.issubset(actions)


def test_credentials_are_scrubbed_from_validation_and_telemetry(client, linked, caplog):
    from app.core.pii_masker import mask_pii, mask_pii_text

    secret = "SYNTHETIC-INIT-DATA-PRIVATE"
    response = client.post(
        PREFIX + "/auth/exchange", json={"init_data": {"secret": secret}}
    )
    assert response.status_code == 422
    assert secret not in response.text
    assert secret not in caplog.text
    assert secret not in str(mask_pii({"initData": secret, "init_data": secret}))
    assert secret not in mask_pii_text('{"init_data":"' + secret + '"}')


def test_openapi_session_contract_is_explicit_and_ids_are_unique():
    schema = app.openapi()
    models = schema["components"]["schemas"]
    assert models["TelegramMiniAppExchangeRequest"]["required"] == ["init_data"]
    assert (
        models["TelegramMiniAppExchangeRequest"]["properties"]["init_data"]["format"]
        == "password"
    )
    assert set(models["TelegramMiniAppTokenResponse"]["properties"]) == {
        "access_token",
        "refresh_token",
        "token_type",
        "expires_in",
    }
    assert set(models["TelegramMiniAppSessionItem"]["properties"]) == {
        "id",
        "device_label",
        "created_at",
        "last_active_at",
        "expires_at",
        "is_current",
    }
    route = schema["paths"][PREFIX + "/sessions/list"]["post"]
    assert route["security"] == [{"TelegramMiniAppPatientBearer": []}]
    ids = [
        operation["operationId"]
        for path in schema["paths"].values()
        for operation in path.values()
        if isinstance(operation, dict) and "operationId" in operation
    ]
    assert len(ids) == len(set(ids))
