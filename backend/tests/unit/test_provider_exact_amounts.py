"""Provider unit conversion tests; no live provider requests."""
from decimal import Decimal
from unittest.mock import Mock

import pytest

from app.services.money_input import MoneyInputError
from app.services.payment_providers.click import ClickProvider
from app.services.payment_providers.kaspi import KaspiProvider
from app.services.payment_providers.payme import PayMeProvider


@pytest.fixture
def providers():
    return {
        "click": ClickProvider({"service_id": "synthetic", "merchant_id": "synthetic", "secret_key": "synthetic"}),
        "payme": PayMeProvider({"merchant_id": "synthetic", "secret_key": "synthetic"}),
        "kaspi": KaspiProvider({"merchant_id": "synthetic", "secret_key": "synthetic"}),
    }


@pytest.mark.parametrize("value,minor", [
    (Decimal("0.29"), 29), (0.29, 29), ("0.29", 29),
    (Decimal("1.15"), 115), (1.15, 115), ("1.15", 115),
    (Decimal("9999999999.99"), 999999999999),
])
@pytest.mark.parametrize("provider", ["click", "payme"])
def test_uzs_checkout_uses_exact_tiyin(providers, provider, value, minor):
    adapter = providers[provider]
    assert adapter.format_amount(value, "UZS") == minor
    result = adapter.create_payment(amount=value, currency="UZS", order_id="synthetic-order", description="synthetic")
    assert result.success
    assert result.provider_data["amount_tiyin"] == minor


@pytest.mark.parametrize("value", [
    True, False, None, Decimal("NaN"), Decimal("Infinity"), float("nan"), float("inf"),
    Decimal("-1.00"), Decimal("0.00"), Decimal("0.001"), "1e-1000", Decimal("10000000000"),
])
@pytest.mark.parametrize("provider", ["click", "payme"])
def test_invalid_uzs_amount_fails_without_url(providers, provider, value):
    adapter = providers[provider]
    with pytest.raises(MoneyInputError):
        adapter.format_amount(value, "UZS")
    result = adapter.create_payment(amount=value, currency="UZS", order_id="synthetic-order", description="synthetic")
    assert not result.success
    assert result.payment_url is None


@pytest.mark.parametrize("value", [Decimal("7"), Decimal("7.00"), "7", 7, 7.0])
def test_kaspi_checkout_accepts_only_whole_tenge(providers, value):
    adapter = providers["kaspi"]
    assert adapter.format_amount(value, "KZT") == 7
    result = adapter.create_payment(amount=value, currency="KZT", order_id="synthetic-order", description="synthetic")
    assert result.success and result.provider_data["amount_kzt"] == 7


@pytest.mark.parametrize("value", [
    Decimal("7.01"), "0.001", Decimal("0"), Decimal("-1"), True,
    Decimal("NaN"), Decimal("Infinity"), Decimal("10000000000"),
])
def test_invalid_kaspi_checkout_never_creates_url(providers, value):
    adapter = providers["kaspi"]
    with pytest.raises(MoneyInputError):
        adapter.format_amount(value, "KZT")
    result = adapter.create_payment(amount=value, currency="KZT", order_id="synthetic-order", description="synthetic")
    assert not result.success and result.payment_url is None


@pytest.mark.parametrize("value", [Decimal("0"), 0, Decimal("0.01"), Decimal("1.01"),
                                    Decimal("-1"), True, Decimal("NaN"), Decimal("Infinity"), Decimal("10000000000")])
def test_invalid_kaspi_refund_never_contacts_provider(providers, monkeypatch, value):
    import app.services.payment_providers.kaspi as module

    post = Mock(side_effect=AssertionError("no real network"))
    monkeypatch.setattr(module.httpx, "post", post)
    result = providers["kaspi"].refund_payment("synthetic-id", amount=value)
    assert not result.success
    post.assert_not_called()


@pytest.mark.parametrize("amount,expected", [(None, None), (Decimal("7"), 7), (7.0, 7)])
def test_kaspi_full_and_partial_refund_request(providers, monkeypatch, amount, expected):
    import app.services.payment_providers.kaspi as module

    fake_response = Mock()
    fake_response.json.return_value = {"status": "synthetic"}
    post = Mock(return_value=fake_response)
    monkeypatch.setattr(module.httpx, "post", post)
    result = providers["kaspi"].refund_payment("synthetic-id", amount=amount)
    assert result.success
    payload = post.call_args.kwargs["json"]
    if expected is None:
        assert "amount" not in payload
    else:
        assert payload["amount"] == expected


def test_unknown_currency_is_rejected(providers):
    with pytest.raises(MoneyInputError):
        providers["click"].format_amount(Decimal("1"), "USD")
