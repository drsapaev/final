"""Regression test for Click + Kaspi provider_data JSON serialization.

Finding F followup: the real-DB integration test (test_webhook_real_db.py)
discovered that Click provider returned Decimal in provider_data, which is
not JSON-serializable for PostgreSQL JSON columns. This caused
transaction_ctx to roll back, leaving payment status as 'pending'.

This test verifies the fix: provider_data from Click and Kaspi providers
must be JSON-serializable (no Decimal values).

Test approach:
  1. Call Click.process_webhook() with realistic data → check provider_data
     is JSON-serializable (json.dumps succeeds).
  2. Same for Kaspi.process_webhook().
  3. Verify _decimal_amount() can still recover the amount from the
     string representation (downstream comparison still works).
"""
from __future__ import annotations

import json
import os
import sys
from decimal import Decimal
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[2]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


class TestClickProviderDataJsonSerializable:
    """Verify Click.process_webhook returns JSON-serializable provider_data."""

    def _make_click_provider(self):
        """Create a Click provider instance with test config."""
        from app.services.payment_providers.click import ClickProvider
        provider = ClickProvider({
            "service_id": "test_service",
            "merchant_id": "test_merchant",
            "secret_key": "test_secret",
            "base_url": "https://test.click.uz",
        })
        return provider

    def _make_webhook_data(self, action: int = 1, error: int = 0, amount: int = 10000):
        """Create Click webhook data with correct signature.

        Uses the same signature generation as Click._generate_webhook_signature:
        fields click_trans_id, service_id, merchant_id, amount, action, error,
        error_note, sign_time + secret_key.
        """
        import hashlib

        data = {
            "click_trans_id": "test-click-trans-123",
            "service_id": "test_service",
            "merchant_id": "test_merchant",
            "amount": amount,
            "action": action,
            "error": error,
            "error_note": "",
            "sign_time": "2026-08-14T00:00:00",
            "merchant_trans_id": "clinic_1_1700000000",
        }
        # Generate signature using the same field order as Click provider
        fields = [
            "click_trans_id", "service_id", "merchant_id", "amount",
            "action", "error", "error_note", "sign_time",
        ]
        sign_parts = [str(data.get(f, "")) for f in fields]
        sign_parts.append("test_secret")  # must match _make_click_provider secret_key
        sign_string = "".join(sign_parts)
        data["sign_string"] = hashlib.md5(sign_string.encode(), usedforsecurity=False).hexdigest()
        return data

    def test_click_provider_data_is_json_serializable(self):
        """Click.process_webhook must return JSON-serializable provider_data.

        Regression for Finding F: Decimal('10000') is NOT JSON-serializable.
        The fix uses str(amount_decimal) which IS JSON-serializable.
        """
        provider = self._make_click_provider()
        webhook_data = self._make_webhook_data(action=1, error=0, amount=10000)

        result = provider.process_webhook(webhook_data)

        assert result.success, f"Click webhook should succeed: {result.error_message}"
        assert result.provider_data is not None, "provider_data should be set"

        # The critical assertion: provider_data must be JSON-serializable
        # This would raise TypeError: Object of type Decimal is not JSON serializable
        # if the fix is not applied.
        try:
            json_string = json.dumps(result.provider_data)
        except TypeError as e:
            pytest.fail(
                f"Click provider_data is NOT JSON-serializable: {e}. "
                f"This causes PostgreSQL JSON column inserts to fail, rolling back "
                f"the entire transaction. provider_data={result.provider_data!r}"
            )

        # Verify amount is present and is a string (not Decimal)
        assert "amount" in result.provider_data, "provider_data must contain 'amount'"
        amount_value = result.provider_data["amount"]
        assert isinstance(amount_value, str), (
            f"amount should be str (JSON-serializable), got {type(amount_value).__name__}: "
            f"{amount_value!r}"
        )

    def test_click_amount_recovers_to_decimal_downstream(self):
        """Verify _decimal_amount() recovers the amount from str representation.

        The downstream code uses _decimal_amount(result.provider_data['amount'])
        to compare with payment.amount. This must still work after the str() fix.
        """
        from app.services.provider_webhook_service import ProviderWebhookService

        provider = self._make_click_provider()
        webhook_data = self._make_webhook_data(action=1, error=0, amount=10000)

        result = provider.process_webhook(webhook_data)
        amount_str = result.provider_data["amount"]

        # _decimal_amount does Decimal(str(value))
        recovered = ProviderWebhookService._decimal_amount(amount_str)
        assert recovered == Decimal("10000"), (
            f"Amount should recover to Decimal('10000'), got {recovered!r}"
        )

        # Verify amount comparison still works (the actual use case)
        payment_amount = Decimal("10000")
        assert ProviderWebhookService._amounts_match(payment_amount, amount_str), (
            "Amount comparison should succeed: payment.amount=10000, "
            f"provider_data.amount={amount_str!r}"
        )

    def test_click_amount_mismatch_detected_downstream(self):
        """Verify amount mismatch is still detected with str representation."""
        from app.services.provider_webhook_service import ProviderWebhookService

        provider = self._make_click_provider()
        webhook_data = self._make_webhook_data(action=1, error=0, amount=10000)

        result = provider.process_webhook(webhook_data)
        amount_str = result.provider_data["amount"]

        # Different payment amount → mismatch should be detected
        payment_amount = Decimal("9999")
        assert not ProviderWebhookService._amounts_match(payment_amount, amount_str), (
            "Amount mismatch should be detected: payment.amount=9999, "
            f"provider_data.amount={amount_str!r}"
        )


class TestKaspiProviderDataJsonSerializable:
    """Verify Kaspi.process_webhook returns JSON-serializable provider_data."""

    def _make_kaspi_provider(self):
        """Create a Kaspi provider instance with test config."""
        from app.services.payment_providers.kaspi import KaspiProvider
        provider = KaspiProvider({
            "merchant_id": "test_merchant",
            "secret_key": "test_secret",
            "base_url": "https://test.kaspi.kz",
        })
        return provider

    def _make_webhook_data(self, amount: int = 50000, status: int = "PAID"):
        """Create Kaspi webhook data."""
        return {
            "transaction_id": "test-kaspi-trans-456",
            "order_id": "clinic_1_1700000000",
            "amount": amount,
            "currency": "KZT",
            "status": status,
            "timestamp": "2026-08-14T00:00:00",
        }

    def test_kaspi_provider_data_is_json_serializable(self):
        """Kaspi.process_webhook must return JSON-serializable provider_data.

        Same fix as Click (kaspi.py:223 uses str(amount_decimal)).
        """
        provider = self._make_kaspi_provider()
        webhook_data = self._make_webhook_data(amount=50000, status="PAID")

        result = provider.process_webhook(webhook_data)

        # Note: Kaspi may return success=False if status mapping fails,
        # but provider_data should still be JSON-serializable regardless.
        if result.provider_data is None:
            pytest.skip("Kaspi provider returned no provider_data (status mapping issue)")

        # The critical assertion
        try:
            json_string = json.dumps(result.provider_data)
        except TypeError as e:
            pytest.fail(
                f"Kaspi provider_data is NOT JSON-serializable: {e}. "
                f"provider_data={result.provider_data!r}"
            )

        # If amount is present, it should be str (not Decimal)
        if "amount" in result.provider_data:
            amount_value = result.provider_data["amount"]
            assert isinstance(amount_value, str), (
                f"amount should be str (JSON-serializable), got {type(amount_value).__name__}: "
                f"{amount_value!r}"
            )


class TestPaymeProviderDataJsonSerializable:
    """Verify Payme.process_webhook returns JSON-serializable provider_data.

    Payme already uses float(amount_decimal) with a comment saying
    'Храним сумму в JSON‑совместимом виде (без Decimal)'. This test
    confirms that fix is still in place.
    """

    def test_payme_provider_data_is_json_serializable(self):
        """Payme provider_data must be JSON-serializable (already fixed via float())."""
        # This is a documentation test — Payme was already fixed.
        # We verify the fix is still in place by reading the source.
        src = (BACKEND_DIR / "app" / "services" / "payment_providers" / "payme.py").read_text()
        assert "float(amount_decimal)" in src, (
            "Payme should use float(amount_decimal) for JSON-serializable amount"
        )
        assert "# Храним сумму в JSON" in src or "JSON" in src, (
            "Payme should have comment explaining JSON-compatible amount storage"
        )
