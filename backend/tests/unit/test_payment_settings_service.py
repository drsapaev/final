from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

import pytest

from app.models.clinic import ClinicSettings
from app.schemas.payment_settings import PaymentProviderSettings
from app.services.payment_settings_service import (
    PaymentSettingsDomainError,
    PaymentSettingsService,
)


@pytest.mark.unit
class TestPaymentSettingsService:
    def test_get_payment_settings_returns_default_when_missing(self, db_session):
        service = PaymentSettingsService(db_session)

        settings = service.get_payment_settings()

        assert settings.default_provider == "click"
        assert "click" in settings.enabled_providers

    def test_save_payment_settings_validates_default_provider(self, db_session):
        service = PaymentSettingsService(db_session)
        settings = PaymentProviderSettings(
            default_provider="click",
            enabled_providers=["payme"],
        )

        with pytest.raises(PaymentSettingsDomainError) as exc_info:
            service.save_payment_settings(settings, username="admin")

        assert exc_info.value.status_code == 400
        assert "по умолчанию" in exc_info.value.detail

    def test_save_payment_settings_persists_json(self, db_session):
        service = PaymentSettingsService(db_session)
        settings = PaymentProviderSettings(
            default_provider="click",
            enabled_providers=["click"],
        )
        settings.click.service_id = "svc"
        settings.click.merchant_id = "merchant"
        settings.click.secret_key = "secret"

        result = service.save_payment_settings(settings, username="admin")

        db_record = (
            db_session.query(ClinicSettings)
            .filter(ClinicSettings.key == "payment_providers")
            .first()
        )
        assert result["success"] is True
        assert db_record is not None
        assert '"default_provider":"click"' in db_record.value

    def test_test_payment_provider_click_missing_fields(self, db_session):
        service = PaymentSettingsService(db_session)

        result = service.test_payment_provider(provider_name="click", config={})

        assert result["success"] is False
        assert "Не заполнены обязательные поля" in result["message"]

    def test_test_payment_provider_click_success(self, db_session):
        service = PaymentSettingsService(db_session)
        fake_result = SimpleNamespace(
            success=True,
            payment_url="https://pay.local",
            payment_id="provider-1",
            error_message=None,
        )

        with patch(
            "app.services.payment_settings_service.ClickProvider.create_payment",
            return_value=fake_result,
        ):
            result = service.test_payment_provider(
                provider_name="click",
                config={
                    "service_id": "svc",
                    "merchant_id": "merchant",
                    "secret_key": "secret",
                },
            )

        assert result["success"] is True
        assert result["details"]["payment_url_created"] is True
        assert result["details"]["payment_id"] == "provider-1"

    def test_get_payment_providers_info_has_expected_keys(self):
        info = PaymentSettingsService.get_payment_providers_info()

        assert "available_providers" in info
        assert "default_urls" in info
        provider_names = {p["name"] for p in info["available_providers"]}
        assert {"click", "payme"} <= provider_names
