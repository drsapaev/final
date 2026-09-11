from __future__ import annotations

import base64
from decimal import Decimal

import pytest

from app.services.payment_providers.payme import PayMeProvider


def _decode_checkout_params(payment_url: str, base_url: str) -> str:
    encoded_params = payment_url.removeprefix(f"{base_url.rstrip('/')}/")
    return base64.b64decode(encoded_params).decode("utf-8")


@pytest.mark.unit
def test_payme_checkout_url_uses_documented_base64_path_contract():
    base_url = "https://checkout.test.paycom.uz/"
    return_url = "https://clinic.example/оплата?payment_id=42"
    cancel_url = "https://clinic.example/payment/cancel?payment_id=42"
    provider = PayMeProvider(
        {
            "merchant_id": "test-merchant",
            "secret_key": "test-secret",
            "base_url": base_url,
        }
    )

    result = provider.create_payment(
        amount=Decimal("123.45"),
        currency="UZS",
        order_id="clinic_42_1700000000",
        description="Оплата визита #42",
        return_url=return_url,
        cancel_url=cancel_url,
    )

    assert result.success is True
    assert result.payment_url is not None
    assert result.payment_url.startswith("https://checkout.test.paycom.uz/")
    assert "?" not in result.payment_url

    decoded_params = _decode_checkout_params(result.payment_url, base_url)
    assert decoded_params == (
        "m=test-merchant;"
        "ac.order_id=clinic_42_1700000000;"
        "a=12345;"
        "l=ru;"
        f"c={return_url}"
    )
    assert "cr=" not in decoded_params
    assert cancel_url not in decoded_params
    assert result.provider_data["amount_tiyin"] == 12345


@pytest.mark.unit
def test_payme_checkout_url_omits_empty_callback():
    base_url = "https://checkout.test.paycom.uz"
    provider = PayMeProvider(
        {
            "merchant_id": "test-merchant",
            "secret_key": "test-secret",
            "base_url": base_url,
        }
    )

    result = provider.create_payment(
        amount=Decimal("5.00"),
        currency="UZS",
        order_id="clinic_5",
        description="Оплата визита #5",
    )

    assert result.success is True
    assert result.payment_url is not None
    assert _decode_checkout_params(result.payment_url, base_url) == (
        "m=test-merchant;ac.order_id=clinic_5;a=500;l=ru"
    )
