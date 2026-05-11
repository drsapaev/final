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
            "enabled": settings.CLICK_ENABLED,
            "service_id": settings.CLICK_SERVICE_ID,
            "merchant_id": settings.CLICK_MERCHANT_ID,
            "secret_key": settings.CLICK_SECRET_KEY,
            "base_url": settings.CLICK_BASE_URL,
        },
        "payme": {
            "enabled": settings.PAYME_ENABLED,
            "merchant_id": settings.PAYME_MERCHANT_ID,
            "secret_key": settings.PAYME_SECRET_KEY,
            "base_url": settings.PAYME_BASE_URL,
            "api_url": settings.PAYME_API_URL,
        },
        "kaspi": {
            "enabled": settings.KASPI_ENABLED,
            "merchant_id": settings.KASPI_MERCHANT_ID,
            "secret_key": settings.KASPI_SECRET_KEY,
            "base_url": settings.KASPI_BASE_URL,
            "api_url": settings.KASPI_API_URL,
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
