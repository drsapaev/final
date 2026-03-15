from __future__ import annotations

import pytest

from app.models.clinic import ClinicSettings


def _valid_click_settings() -> dict:
    return {
        "default_provider": "click",
        "enabled_providers": ["click"],
        "click": {
            "enabled": True,
            "test_mode": True,
            "service_id": "svc-1",
            "merchant_id": "merchant-1",
            "secret_key": "secret-1",
            "base_url": "https://api.click.uz/v2",
        },
        "payme": {
            "enabled": False,
            "test_mode": True,
            "merchant_id": "",
            "secret_key": "",
            "base_url": "https://checkout.paycom.uz",
            "api_url": "https://api.paycom.uz",
        },
    }


@pytest.mark.integration
def test_payment_settings_endpoint_returns_default_settings_when_missing(
    client,
    auth_headers,
):
    response = client.get(
        "/api/v1/admin/payment-provider-settings",
        headers=auth_headers,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["default_provider"] == "click"
    assert "click" in payload["enabled_providers"]


@pytest.mark.integration
def test_payment_settings_endpoint_round_trips_saved_provider_config(
    client,
    db_session,
    auth_headers,
):
    payload = _valid_click_settings()

    save_response = client.post(
        "/api/v1/admin/payment-provider-settings",
        json=payload,
        headers=auth_headers,
    )

    assert save_response.status_code == 200
    assert save_response.json() == {
        "success": True,
        "message": "Настройки сохранены успешно",
    }

    db_record = (
        db_session.query(ClinicSettings)
        .filter(ClinicSettings.key == "payment_providers")
        .one()
    )
    assert '"merchant_id":"merchant-1"' in db_record.value

    get_response = client.get(
        "/api/v1/admin/payment-provider-settings",
        headers=auth_headers,
    )

    assert get_response.status_code == 200
    fetched_payload = get_response.json()
    assert fetched_payload["default_provider"] == "click"
    assert fetched_payload["enabled_providers"] == ["click"]
    assert fetched_payload["click"]["merchant_id"] == "merchant-1"
    assert fetched_payload["click"]["secret_key"] == "secret-1"


@pytest.mark.integration
def test_payment_settings_endpoint_rejects_invalid_default_provider(
    client,
    auth_headers,
):
    response = client.post(
        "/api/v1/admin/payment-provider-settings",
        json={
            "default_provider": "click",
            "enabled_providers": ["payme"],
            "click": {
                "enabled": False,
                "test_mode": True,
                "service_id": "",
                "merchant_id": "",
                "secret_key": "",
                "base_url": "https://api.click.uz/v2",
            },
            "payme": {
                "enabled": True,
                "test_mode": True,
                "merchant_id": "merchant-2",
                "secret_key": "secret-2",
                "base_url": "https://checkout.paycom.uz",
                "api_url": "https://api.paycom.uz",
            },
        },
        headers=auth_headers,
    )

    assert response.status_code == 400
    assert "по умолчанию" in response.json()["detail"]


@pytest.mark.integration
def test_payment_settings_endpoint_surfaces_provider_test_contract(
    client,
    auth_headers,
):
    response = client.post(
        "/api/v1/admin/test-payment-provider",
        json={"provider": "click", "config": {}},
        headers=auth_headers,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is False
    assert "Не заполнены обязательные поля" in payload["message"]


@pytest.mark.integration
def test_payment_settings_endpoint_returns_provider_info_contract(
    client,
    auth_headers,
):
    response = client.get(
        "/api/v1/admin/payment-providers-info",
        headers=auth_headers,
    )

    assert response.status_code == 200
    payload = response.json()
    provider_names = {item["name"] for item in payload["available_providers"]}
    assert {"click", "payme"} <= provider_names
    assert "default_urls" in payload
