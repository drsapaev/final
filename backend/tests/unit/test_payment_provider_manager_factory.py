from __future__ import annotations

from unittest.mock import patch

import pytest

from app.services import payment_provider_manager_factory as factory


@pytest.mark.unit
class TestPaymentProviderManagerFactory:
    def setup_method(self):
        factory.reset_payment_manager_for_tests()

    def teardown_method(self):
        factory.reset_payment_manager_for_tests()

    def test_get_payment_manager_caches_single_instance(self):
        fake_manager = object()

        with patch(
            "app.services.payment_provider_manager_factory.PaymentProviderManager",
            return_value=fake_manager,
        ) as manager_cls:
            first = factory.get_payment_manager()
            second = factory.get_payment_manager()

        assert first is fake_manager
        assert second is fake_manager
        manager_cls.assert_called_once()

    def test_get_payment_manager_builds_expected_provider_config(self):
        fake_manager = object()

        with patch(
            "app.services.payment_provider_manager_factory.PaymentProviderManager",
            return_value=fake_manager,
        ) as manager_cls:
            factory.get_payment_manager()

        config = manager_cls.call_args.args[0]
        assert set(config) == {"click", "payme", "kaspi"}
        assert "service_id" in config["click"]
        assert "merchant_id" in config["payme"]
        assert "api_url" in config["kaspi"]
