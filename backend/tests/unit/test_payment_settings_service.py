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


@pytest.mark.unit
class TestPaymentSettingsServiceCredentialLeakPrevention:
    """Verify that exception text and provider error_message passthrough never
    reach the HTTP response. Only business-level messages (formed by the
    service itself from safe inputs) may be returned to the client."""

    SECRET_IN_EXCEPTION = "Click: secret_key=super_secret_123 leaked via init"

    def test_test_payment_provider_click_init_exception_does_not_leak_str_exc(
        self, db_session, caplog
    ):
        """When ClickProvider.__init__() raises, str(exc) must NOT appear in
        the returned message — only a generic Russian string is returned."""
        service = PaymentSettingsService(db_session)

        with patch(
            "app.services.payment_settings_service.ClickProvider",
            side_effect=ValueError(self.SECRET_IN_EXCEPTION),
        ):
            result = service.test_payment_provider(
                provider_name="click",
                config={
                    "service_id": "svc",
                    "merchant_id": "merchant",
                    "secret_key": "super_secret_123",
                },
            )

        assert result["success"] is False
        assert self.SECRET_IN_EXCEPTION not in result["message"]
        assert "super_secret_123" not in result["message"]
        assert "Ошибка инициализации провайдера" in result["message"]
        # Exception must be logged with exc_info for devops.
        assert any(
            "Click provider init failed" in rec.message
            and rec.exc_info is not None
            for rec in caplog.records
        )

    def test_test_payment_provider_click_create_payment_exception_does_not_leak(
        self, db_session, caplog
    ):
        """When provider.create_payment() raises an exception whose str()
        contains a credential-like fragment, that fragment must NOT appear in
        the returned message."""
        service = PaymentSettingsService(db_session)

        # Simulate httpx.HTTPStatusError-like exception carrying URL+status.
        # str(exc) contains the URL endpoint but (per httpx 2.7+) no query
        # params or body — still, we treat all str(exc) as untrusted.
        class FakeException(Exception):
            pass

        fake_exc_text = (
            "Client error '401 Unauthorized' for url "
            "'https://api.click.uz/v2/services/payment/status'"
        )

        with patch(
            "app.services.payment_settings_service.ClickProvider"
        ) as MockClick:
            MockClick.return_value.create_payment.side_effect = FakeException(
                fake_exc_text
            )
            result = service.test_payment_provider(
                provider_name="click",
                config={
                    "service_id": "svc",
                    "merchant_id": "merchant",
                    "secret_key": "secret",
                },
            )

        assert result["success"] is False
        assert fake_exc_text not in result["message"]
        assert "api.click.uz" not in result["message"]
        assert "Ошибка инициализации провайдера" in result["message"]

    def test_test_payment_provider_payme_init_exception_does_not_leak_str_exc(
        self, db_session, caplog
    ):
        """Same as Click test, but for PayMe provider init path."""
        service = PaymentSettingsService(db_session)
        secret_in_exc = "PayMe: merchant_id=leaked_merchant_xyz"

        with patch(
            "app.services.payment_settings_service.PayMeProvider",
            side_effect=ValueError(secret_in_exc),
        ):
            result = service.test_payment_provider(
                provider_name="payme",
                config={
                    "merchant_id": "leaked_merchant_xyz",
                    "secret_key": "secret",
                },
            )

        assert result["success"] is False
        assert secret_in_exc not in result["message"]
        assert "leaked_merchant_xyz" not in result["message"]
        assert "Ошибка инициализации провайдера" in result["message"]

    def test_test_payment_provider_payme_create_payment_exception_does_not_leak(
        self, db_session
    ):
        """Same as Click create_payment test, but for PayMe."""
        service = PaymentSettingsService(db_session)

        class FakeException(Exception):
            pass

        fake_exc_text = "Server error '500' for url 'https://api.paycom.uz/api'"

        with patch(
            "app.services.payment_settings_service.PayMeProvider"
        ) as MockPayMe:
            MockPayMe.return_value.create_payment.side_effect = FakeException(
                fake_exc_text
            )
            result = service.test_payment_provider(
                provider_name="payme",
                config={"merchant_id": "m", "secret_key": "s"},
            )

        assert result["success"] is False
        assert fake_exc_text not in result["message"]
        assert "api.paycom.uz" not in result["message"]

    def test_test_payment_provider_provider_error_message_not_passthrough_click(
        self, db_session, caplog
    ):
        """When provider.create_payment() returns PaymentResult(success=False,
        error_message=<text>), the error_message must NOT be embedded in the
        HTTP response AND must NOT be logged verbatim — it's a provider-library
        passthrough that may contain credential fragments. Only safe metadata
        (provider name, operation) is logged for devops correlation."""
        service = PaymentSettingsService(db_session)
        dangerous_error_message = "Auth failed: signature=md5(secret_key+timestamp)"

        fake_result = SimpleNamespace(
            success=False,
            payment_url=None,
            payment_id=None,
            error_message=dangerous_error_message,
        )

        with patch(
            "app.services.payment_settings_service.ClickProvider"
        ) as MockClick:
            MockClick.return_value.create_payment.return_value = fake_result
            result = service.test_payment_provider(
                provider_name="click",
                config={
                    "service_id": "svc",
                    "merchant_id": "merchant",
                    "secret_key": "secret",
                },
            )

        assert result["success"] is False
        assert dangerous_error_message not in result["message"]
        assert "signature=md5" not in result["message"]
        assert "Ошибка создания тестового платежа" in result["message"]
        # Safe metadata must be logged for devops correlation.
        assert any(
            "Click test payment failed" in rec.message
            and "provider=click" in rec.message
            for rec in caplog.records
        )
        # The dangerous error_message must NOT appear in logs verbatim.
        assert all(
            dangerous_error_message not in rec.message for rec in caplog.records
        )

    def test_test_payment_provider_provider_error_message_not_passthrough_payme(
        self, db_session, caplog
    ):
        """Same as Click provider_error_message test, but for PayMe."""
        service = PaymentSettingsService(db_session)
        dangerous_error_message = "PayMe auth: Basic base64(Paycom:secret)"

        fake_result = SimpleNamespace(
            success=False,
            payment_url=None,
            payment_id=None,
            error_message=dangerous_error_message,
        )

        with patch(
            "app.services.payment_settings_service.PayMeProvider"
        ) as MockPayMe:
            MockPayMe.return_value.create_payment.return_value = fake_result
            result = service.test_payment_provider(
                provider_name="payme",
                config={"merchant_id": "m", "secret_key": "s"},
            )

        assert result["success"] is False
        assert dangerous_error_message not in result["message"]
        assert "base64(Paycom" not in result["message"]
        assert "Ошибка создания тестового платежа" in result["message"]
        # Safe metadata must be logged for devops correlation.
        assert any(
            "PayMe test payment failed" in rec.message
            and "provider=payme" in rec.message
            for rec in caplog.records
        )
        # The dangerous error_message must NOT appear in logs verbatim.
        assert all(
            dangerous_error_message not in rec.message for rec in caplog.records
        )

    def test_test_payment_provider_outer_exception_does_not_leak_str_exc(
        self, db_session, caplog
    ):
        """When _test_click_provider itself raises unexpectedly (not caught
        by its own try/except), the outer test_payment_provider except must
        also NOT embed str(exc) in the response."""
        service = PaymentSettingsService(db_session)
        secret_in_outer = "RuntimeError: config contained secret_key=TOPSECRET"

        with patch.object(
            service,
            "_test_click_provider",
            side_effect=RuntimeError(secret_in_outer),
        ):
            result = service.test_payment_provider(
                provider_name="click",
                config={"service_id": "svc", "merchant_id": "m", "secret_key": "x"},
            )

        assert result["success"] is False
        assert secret_in_outer not in result["message"]
        assert "TOPSECRET" not in result["message"]
        assert "Внутренняя ошибка тестирования провайдера" in result["message"]
        # Outer exception must be logged with exc_info.
        assert any(
            "Payment provider test failed" in rec.message
            and rec.exc_info is not None
            for rec in caplog.records
        )

    def test_business_message_missing_fields_preserved(self, db_session):
        """Business message 'Не заполнены обязательные поля: ...' is formed
        by the service from field NAMES (not values) — safe to return."""
        service = PaymentSettingsService(db_session)

        result = service.test_payment_provider(provider_name="click", config={})

        assert result["success"] is False
        assert "Не заполнены обязательные поля" in result["message"]
        assert "service_id" in result["message"]
        assert "merchant_id" in result["message"]
        assert "secret_key" in result["message"]

    def test_business_message_unsupported_provider_preserved(self, db_session):
        """Business message 'Неподдерживаемый провайдер: ...' is formed from
        the user's own input (provider_name) — safe to return."""
        service = PaymentSettingsService(db_session)

        result = service.test_payment_provider(
            provider_name="kaspi", config={}
        )

        assert result["success"] is False
        assert "Неподдерживаемый провайдер: kaspi" in result["message"]
