"""Regression tests for P1-3 CSRF exemption boundaries.

P1-3 (post-merge stabilization): verifies that the CSRF middleware
correctly exempts Telegram webhook endpoints while NOT exempting
sibling admin endpoints that share a path prefix.

Security contract:
- /api/v1/telegram/webhook          → CSRF exempt (server-to-server webhook)
- /api/v1/telegram/webhook/enhanced → CSRF exempt (server-to-server webhook)
- /api/v1/telegram/bot/webhook      → CSRF exempt (server-to-server webhook)
- /api/v1/telegram/webhook/test     → CSRF PROTECTED (browser-facing admin endpoint)
- /api/v1/telegram/send-message     → CSRF PROTECTED (browser-facing admin endpoint)

The over-exemption bug: before P1-3 fix, the middleware used
`path.startswith(exempt)` for ALL exempt paths. Adding
`/api/v1/telegram/webhook` to the exempt list caused
`/api/v1/telegram/webhook/test` to also be exempted (prefix match),
even though /webhook/test is an admin endpoint that should have CSRF
protection.

Fix: split exempt paths into two sets:
- CSRF_EXEMPT_PREFIXES: prefix-match (e.g. /payments/webhook/ for /click)
- CSRF_EXEMPT_EXACT: exact-match only (Telegram webhooks)

Run:
    pytest backend/tests/regression/test_p1_3_csrf_exemption_boundaries.py -v
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest
from starlette.testclient import TestClient

BACKEND_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BACKEND_DIR))

os.environ.setdefault("DATABASE_URL", "sqlite:///./test_p1_3_csrf.db")
os.environ.setdefault("ENV", "dev")
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-p1-3-csrf-regression-32")
os.environ.setdefault("ALLOW_SQLITE_DATABASE_URL", "1")
os.environ.setdefault("TESTING", "1")


@pytest.mark.unit
class TestCSRFExemptionBoundaries:
    """P1-3: verify CSRF exemption boundaries for Telegram webhook paths."""

    @pytest.fixture
    def csrf_client(self):
        """Create a test client with CSRF middleware enabled."""
        from app.middleware.csrf_middleware import CSRFMiddleware

        # Build a minimal Starlette app with just the CSRF middleware
        # and a dummy handler that returns 200 for any POST.
        from starlette.applications import Starlette
        from starlette.routing import Route

        async def dummy_handler(request):
            from starlette.responses import JSONResponse
            return JSONResponse({"status": "ok"})

        routes = [
            Route("/api/v1/telegram/webhook", dummy_handler, methods=["POST"]),
            Route("/api/v1/telegram/webhook/enhanced", dummy_handler, methods=["POST"]),
            Route("/api/v1/telegram/webhook/test", dummy_handler, methods=["POST"]),
            Route("/api/v1/telegram/bot/webhook", dummy_handler, methods=["POST"]),
            Route("/api/v1/telegram/send-message", dummy_handler, methods=["POST"]),
            Route("/api/v1/payments/webhook/click", dummy_handler, methods=["POST"]),
        ]

        app = Starlette(routes=routes)
        app.add_middleware(CSRFMiddleware, enabled=True)

        with TestClient(app) as client:
            yield client

    def test_telegram_webhook_exempt_from_csrf(self, csrf_client):
        """POST /api/v1/telegram/webhook without CSRF token → NOT 403.

        This is a server-to-server webhook from Telegram Bot API.
        It authenticates via X-Telegram-Bot-Api-Secret-Token header,
        not CSRF tokens.
        """
        response = csrf_client.post("/api/v1/telegram/webhook")
        assert response.status_code != 403, (
            f"Telegram webhook should be CSRF-exempt, got 403. "
            f"Response: {response.status_code}"
        )

    def test_telegram_webhook_enhanced_exempt_from_csrf(self, csrf_client):
        """POST /api/v1/telegram/webhook/enhanced without CSRF token → NOT 403.

        This is also a server-to-server webhook with its own secret validation.
        """
        response = csrf_client.post("/api/v1/telegram/webhook/enhanced")
        assert response.status_code != 403, (
            f"Telegram enhanced webhook should be CSRF-exempt, got 403. "
            f"Response: {response.status_code}"
        )

    def test_telegram_bot_webhook_exempt_from_csrf(self, csrf_client):
        """POST /api/v1/telegram/bot/webhook without CSRF token → NOT 403.

        This is the second Telegram webhook endpoint (telegram_bot router).
        """
        response = csrf_client.post("/api/v1/telegram/bot/webhook")
        assert response.status_code != 403, (
            f"Telegram bot webhook should be CSRF-exempt, got 403. "
            f"Response: {response.status_code}"
        )

    def test_telegram_webhook_test_csrf_protected(self, csrf_client):
        """POST /api/v1/telegram/webhook/test without CSRF token → 403.

        This is a browser-facing admin endpoint (require_roles("Admin")).
        It must NOT be exempted from CSRF just because it shares a path
        prefix with /telegram/webhook.

        Before P1-3 fix: this was incorrectly exempted (prefix match).
        After P1-3 fix: exact match only — /webhook/test is NOT exempted.
        """
        response = csrf_client.post("/api/v1/telegram/webhook/test")
        assert response.status_code == 403, (
            f"Telegram /webhook/test (admin endpoint) should be CSRF-protected, "
            f"got {response.status_code}. This is the P1-3 over-exemption bug — "
            f"the path matches /telegram/webhook as a prefix."
        )

    def test_telegram_send_message_csrf_protected(self, csrf_client):
        """POST /api/v1/telegram/send-message without CSRF token → 403.

        This is a browser-facing admin endpoint, not a webhook.
        """
        response = csrf_client.post("/api/v1/telegram/send-message")
        assert response.status_code == 403, (
            f"Telegram /send-message (admin endpoint) should be CSRF-protected, "
            f"got {response.status_code}."
        )

    def test_payments_webhook_prefix_still_works(self, csrf_client):
        """POST /api/v1/payments/webhook/click without CSRF token → NOT 403.

        The /payments/webhook/ prefix exemption must still work —
        PayMe/Click/Kaspi callbacks use HMAC signatures, not CSRF tokens.
        This test verifies that the P1-3 fix did not break the existing
        prefix-based exemption for payment webhooks.
        """
        response = csrf_client.post("/api/v1/payments/webhook/click")
        assert response.status_code != 403, (
            f"Payments webhook should be CSRF-exempt (prefix match), got 403. "
            f"Response: {response.status_code}"
        )


@pytest.mark.unit
class TestCSRFExemptSets:
    """P1-3: verify the CSRF_EXEMPT_EXACT set contains exactly the right paths."""

    def test_exact_exempt_set_contains_telegram_webhooks(self):
        """CSRF_EXEMPT_EXACT must contain exactly the 3 Telegram webhook paths."""
        from app.middleware.csrf_middleware import CSRF_EXEMPT_EXACT

        assert "/api/v1/telegram/webhook" in CSRF_EXEMPT_EXACT
        assert "/api/v1/telegram/webhook/enhanced" in CSRF_EXEMPT_EXACT
        assert "/api/v1/telegram/bot/webhook" in CSRF_EXEMPT_EXACT

    def test_exact_exempt_set_does_not_contain_admin_endpoints(self):
        """CSRF_EXEMPT_EXACT must NOT contain admin endpoints."""
        from app.middleware.csrf_middleware import CSRF_EXEMPT_EXACT

        assert "/api/v1/telegram/webhook/test" not in CSRF_EXEMPT_EXACT
        assert "/api/v1/telegram/send-message" not in CSRF_EXEMPT_EXACT

    def test_prefix_set_does_not_contain_telegram_webhooks(self):
        """CSRF_EXEMPT_PREFIXES must NOT contain Telegram webhook paths
        (they are in CSRF_EXEMPT_EXACT, not PREFIXES)."""
        from app.middleware.csrf_middleware import CSRF_EXEMPT_PREFIXES

        # Telegram webhooks should NOT be in the prefix set
        assert "/api/v1/telegram/webhook" not in CSRF_EXEMPT_PREFIXES
        assert "/api/v1/telegram/bot/webhook" not in CSRF_EXEMPT_PREFIXES
