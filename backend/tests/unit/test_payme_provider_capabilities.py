from __future__ import annotations

import pytest

from app.services.payment_providers.manager import PaymentProviderManager


@pytest.mark.unit
def test_payme_checkout_does_not_advertise_outbound_cancel_support():
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
    result = provider.cancel_payment("clinic-payment-1")

    assert result.success is False
    assert "не поддерживается" in result.error_message
    assert manager.get_provider_info()["payme"]["features"]["cancel"] is False
