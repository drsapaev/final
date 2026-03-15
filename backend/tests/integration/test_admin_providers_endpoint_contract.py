from __future__ import annotations

import pytest

from app.models.payment_webhook import PaymentProvider


@pytest.mark.integration
def test_admin_providers_endpoint_supports_frontend_crud_payload(
    client,
    db_session,
    auth_headers,
):
    list_response = client.get("/api/v1/admin/providers", headers=auth_headers)

    assert list_response.status_code == 200
    assert list_response.json() == []

    create_response = client.post(
        "/api/v1/admin/providers",
        json={
            "name": "Payme",
            "code": "payme",
            "description": "Frontend-only extra field should not break create",
            "is_active": True,
            "secret_key": "payme-secret",
            "webhook_url": "https://example.com/payme/webhook",
            "api_url": "https://example.com/payme/api",
        },
        headers=auth_headers,
    )

    assert create_response.status_code == 200
    created_payload = create_response.json()
    provider_id = created_payload["id"]
    assert created_payload["name"] == "Payme"
    assert created_payload["code"] == "payme"
    assert created_payload["is_active"] is True
    assert created_payload["webhook_url"] == "https://example.com/payme/webhook"

    get_response = client.get(
        f"/api/v1/admin/providers/{provider_id}",
        headers=auth_headers,
    )

    assert get_response.status_code == 200
    assert get_response.json()["code"] == "payme"

    update_response = client.put(
        f"/api/v1/admin/providers/{provider_id}",
        json={
            "name": "Click",
            "code": "click",
            "description": "Frontend-only extra field should not break update",
            "is_active": False,
            "secret_key": "click-secret",
            "webhook_url": "https://example.com/click/webhook",
            "api_url": "https://example.com/click/api",
        },
        headers=auth_headers,
    )

    assert update_response.status_code == 200
    updated_payload = update_response.json()
    assert updated_payload["name"] == "Click"
    assert updated_payload["code"] == "click"
    assert updated_payload["is_active"] is False
    assert updated_payload["webhook_url"] == "https://example.com/click/webhook"

    persisted = (
        db_session.query(PaymentProvider)
        .filter(PaymentProvider.id == provider_id)
        .one()
    )
    assert persisted.name == "Click"
    assert persisted.code == "click"
    assert persisted.is_active is False
    assert persisted.webhook_url == "https://example.com/click/webhook"
    assert persisted.secret_key == "click-secret"

    delete_response = client.delete(
        f"/api/v1/admin/providers/{provider_id}",
        headers=auth_headers,
    )

    assert delete_response.status_code == 200
    assert delete_response.json()["success"] is True

    deleted = (
        db_session.query(PaymentProvider)
        .filter(PaymentProvider.id == provider_id)
        .first()
    )
    assert deleted is None


@pytest.mark.integration
def test_admin_providers_endpoint_rejects_duplicate_provider_codes(
    client,
    auth_headers,
):
    first_response = client.post(
        "/api/v1/admin/providers",
        json={
            "name": "Click",
            "code": "click",
            "is_active": True,
            "secret_key": "click-secret",
            "webhook_url": "https://example.com/click/webhook",
        },
        headers=auth_headers,
    )
    assert first_response.status_code == 200

    duplicate_response = client.post(
        "/api/v1/admin/providers",
        json={
            "name": "Click Duplicate",
            "code": "click",
            "is_active": True,
            "secret_key": "duplicate-secret",
            "webhook_url": "https://example.com/click/webhook-2",
        },
        headers=auth_headers,
    )

    assert duplicate_response.status_code == 400
    assert "уже существует" in duplicate_response.json()["detail"]
