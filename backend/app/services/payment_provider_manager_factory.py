"""Factory for constructing and caching payment provider manager."""

from __future__ import annotations

from threading import Lock

from app.core.config import settings
from app.services.payment_providers.manager import PaymentProviderManager

_payment_manager: PaymentProviderManager | None = None
_payment_manager_lock = Lock()


def _build_provider_config() -> dict[str, dict[str, object]]:
    return {
        "click": {
            "enabled": getattr(settings, "CLICK_ENABLED", True),
            "service_id": getattr(settings, "CLICK_SERVICE_ID", "test_service"),
            "merchant_id": getattr(settings, "CLICK_MERCHANT_ID", "test_merchant"),
            "secret_key": getattr(settings, "CLICK_SECRET_KEY", "test_secret"),
            "base_url": getattr(settings, "CLICK_BASE_URL", "https://api.click.uz/v2"),
        },
        "payme": {
            "enabled": getattr(settings, "PAYME_ENABLED", True),
            "merchant_id": getattr(settings, "PAYME_MERCHANT_ID", "test_merchant"),
            "secret_key": getattr(settings, "PAYME_SECRET_KEY", "test_secret"),
            "base_url": getattr(
                settings, "PAYME_BASE_URL", "https://checkout.paycom.uz"
            ),
            "api_url": getattr(settings, "PAYME_API_URL", "https://api.paycom.uz"),
        },
        "kaspi": {
            "enabled": getattr(settings, "KASPI_ENABLED", True),
            "merchant_id": getattr(settings, "KASPI_MERCHANT_ID", "test_merchant"),
            "secret_key": getattr(settings, "KASPI_SECRET_KEY", "test_secret"),
            "base_url": getattr(settings, "KASPI_BASE_URL", "https://kaspi.kz/pay"),
            "api_url": getattr(settings, "KASPI_API_URL", "https://api.kaspi.kz/pay/v1"),
        },
    }


def get_payment_manager() -> PaymentProviderManager:
    """Return singleton payment provider manager configured from settings."""
    global _payment_manager

    if _payment_manager is not None:
        return _payment_manager

    with _payment_manager_lock:
        if _payment_manager is None:
            _payment_manager = PaymentProviderManager(_build_provider_config())

    return _payment_manager


def reset_payment_manager_for_tests() -> None:
    """Reset cached manager for deterministic unit tests."""
    global _payment_manager
    _payment_manager = None
