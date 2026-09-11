from __future__ import annotations

import pytest

from app.services.payment_providers.manager import PaymentProviderManager


@pytest.mark.unit
def test_payme_checkout_advertises_only_supported_outbound_operations():
    manager = PaymentProviderManager(
        {
            "payme": {
                "enabled": True,
                "merchant_id": "test-merchant",
                "secret_key": "test-secret",
                "base_url": "https://checkout.test.paycom.uz",
                "api_url": "https://api.test.paycom.uz",
            }
        }
    )

    provider = manager.get_provider("payme")
    assert provider is not None
    cancel_result = provider.cancel_payment("clinic-payment-1")
    status_result = provider.check_payment_status("clinic-payment-1")
    features = manager.get_provider_info()["payme"]["features"]

    assert cancel_result.success is False
    assert "не поддерживается" in cancel_result.error_message
    assert status_result.success is False
    assert status_result.payment_id == "clinic-payment-1"
    assert "Merchant API" in status_result.error_message
    assert status_result.provider_data == {
        "status_source": "merchant_api_webhook"
    }
    assert features["check_status"] is False
    assert features["cancel"] is False
    assert features["registrar_invoice_payment"] is False


@pytest.mark.unit
def test_click_advertises_registrar_invoice_payment_capability():
    manager = PaymentProviderManager(
        {
            "click": {
                "enabled": True,
                "service_id": "test-service",
                "merchant_id": "test-merchant",
                "secret_key": "test-secret",
            }
        }
    )

    features = manager.get_provider_info()["click"]["features"]

    assert manager.supports_registrar_invoice_payment("CLICK") is True
    assert features["registrar_invoice_payment"] is True
    assert manager.supports_registrar_invoice_payment("payme") is False
