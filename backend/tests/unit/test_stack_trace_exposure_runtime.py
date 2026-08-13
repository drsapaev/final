#!/usr/bin/env python3
"""
RUNTIME regression test for py/stack-trace-exposure.

Unlike test_stack_trace_exposure.py (which does static source-code pattern
matching), this test actually TRIGGERS the general_exception_handler with
an exception containing a synthetic sensitive payload, and asserts the
HTTP response body does NOT contain that payload — even when LOG_LEVEL=DEBUG.

This proves the fix works at runtime, not just that CodeQL is silenced.

Closes CodeQL regression for:
  - py/stack-trace-exposure #1175, #1176 (main.py /health downstream)
  - py/stack-trace-exposure #325-#1199 (all downstream false positives
    whose taint source was the debug-mode leak in general_exception_handler)

The previous implementation had:
    "detail": (
        str(exc)
        if logger.level <= logging.DEBUG
        else "Обратитесь к администратору"
    ),

Setting LOG_LEVEL=DEBUG would cause ALL unhandled exceptions to surface
their message to the client. This test verifies that condition is gone.
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

BACKEND_DIR = Path(__file__).resolve().parents[2]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.core.exception_handlers import register_exception_handlers  # noqa: E402


# ============================================================
# Synthetic app with an endpoint that raises a known payload
# ============================================================

SYNTHETIC_SECRET = "SYNTHETIC_SECRET_PAYLOAD_7f3a2b8c"
SYNTHETIC_STACK_FRAGMENT = "Traceback (most recent call last)"


def _build_test_app() -> FastAPI:
    """Build a minimal FastAPI app with the production exception handler
    and a single endpoint that raises an exception containing the synthetic secret."""
    app = FastAPI()
    register_exception_handlers(app)

    @app.get("/test/raise")
    async def raise_exception(request: Request):
        raise RuntimeError(
            f"Database error: connection refused — password={SYNTHETIC_SECRET} "
            f"in query: SELECT * FROM users WHERE password='{SYNTHETIC_SECRET}'"
        )

    return app


# ============================================================
# Runtime tests — prove no sensitive data in HTTP response
# ============================================================

class TestStackTraceExposureRuntime:
    """Runtime verification that exception details do NOT leak to the HTTP
    response body, regardless of log level.

    The previous implementation had a conditional:
        str(exc) if logger.level <= logging.DEBUG else "..."
    This test verifies that condition is GONE — even at DEBUG level, the
    response must NOT contain the exception message.
    """

    @pytest.fixture
    def client(self):
        app = _build_test_app()
        return TestClient(app, raise_server_exceptions=False)

    def test_no_secret_in_response_at_default_log_level(self, client):
        """At default log level (INFO), exception details must not leak."""
        response = client.get("/test/raise")
        assert response.status_code == 500
        body = response.json()
        assert SYNTHETIC_SECRET not in response.text, (
            f"Synthetic secret leaked into response body at INFO level: {response.text}"
        )
        assert SYNTHETIC_SECRET not in str(body), (
            f"Synthetic secret leaked into JSON body at INFO level: {body}"
        )

    def test_no_secret_in_response_at_debug_log_level(self, client, caplog):
        """At DEBUG log level, exception details must STILL not leak.

        This is the critical test — the previous implementation would have
        leaked str(exc) when logger.level <= logging.DEBUG.
        """
        # Set root logger to DEBUG (simulates LOG_LEVEL=DEBUG env var)
        with caplog.at_level(logging.DEBUG):
            response = client.get("/test/raise")

        assert response.status_code == 500
        assert SYNTHETIC_SECRET not in response.text, (
            f"Synthetic secret leaked into response body at DEBUG level: {response.text}"
        )

        # Parse JSON body
        body = response.json()
        assert SYNTHETIC_SECRET not in str(body), (
            f"Synthetic secret leaked into JSON body at DEBUG level: {body}"
        )

        # Verify the detail field is generic, not the exception message
        assert body.get("detail") == "Обратитесь к администратору" or body.get("detail") == "Contact administrator", (
            f"detail field should be generic, got: {body.get('detail')!r}"
        )

    def test_no_stack_trace_fragment_in_response(self, client):
        """Python traceback fragments must not appear in the response."""
        response = client.get("/test/raise")
        assert response.status_code == 500
        assert SYNTHETIC_STACK_FRAGMENT not in response.text, (
            f"Stack trace fragment found in response: {response.text}"
        )
        assert "Traceback" not in response.text, (
            f"Literal 'Traceback' found in response: {response.text}"
        )
        assert "File \"" not in response.text, (
            f"File path fragment from traceback found in response: {response.text}"
        )

    def test_response_structure_is_safe(self, client):
        """The response must have the expected safe structure."""
        response = client.get("/test/raise")
        assert response.status_code == 500
        body = response.json()

        # Must contain error type and request_id (for support correlation)
        assert "error" in body, "response must include error type"
        assert body["error"] == "internal_server_error"
        assert "request_id" in body, "response must include request_id for support"

        # detail must NOT contain the exception message
        detail = body.get("detail", "")
        assert SYNTHETIC_SECRET not in detail, (
            f"detail field contains secret: {detail!r}"
        )

    def test_exception_is_logged_server_side(self, client, caplog):
        """The full exception (with secret) IS logged server-side via exc_info=True.
        This verifies the fix doesn't break observability — operators can still
        see the full error in logs, just not in the HTTP response."""
        with caplog.at_level(logging.ERROR):
            response = client.get("/test/raise")

        assert response.status_code == 500

        # The secret SHOULD appear in logs (server-side), NOT in the response
        assert SYNTHETIC_SECRET in caplog.text, (
            "Secret should be in server-side logs (for debugging) but wasn't found"
        )
        assert SYNTHETIC_SECRET not in response.text, (
            "Secret should NOT be in client-facing response but was found"
        )

    def test_different_exception_types_dont_leak(self, client):
        """Test with different exception types to verify the handler is generic.

        Note: FastAPI has built-in handlers for ValueError/KeyError that return
        400 with the exception message in the body. This is FastAPI's default
        behavior, NOT our global exception handler. Our handler only catches
        exceptions that propagate past FastAPI's built-in handlers (RuntimeError,
        TypeError, etc.).

        This test verifies that RuntimeError (which our handler catches) does
        not leak the secret, regardless of the exception type."""
        app = client.app

        @app.get("/test/raise/type")
        async def raise_type_error(request: Request):
            raise TypeError(f"Type mismatch: {SYNTHETIC_SECRET}")

        @app.get("/test/raise/runtime")
        async def raise_runtime_error(request: Request):
            raise RuntimeError(f"Runtime error: {SYNTHETIC_SECRET}")

        # These exception types are NOT caught by FastAPI's built-in handlers,
        # so they propagate to our global handler.
        for path in ["/test/raise/type", "/test/raise/runtime"]:
            response = client.get(path)
            assert response.status_code == 500, (
                f"{path}: expected 500 (our global handler), got {response.status_code}"
            )
            assert SYNTHETIC_SECRET not in response.text, (
                f"{path}: secret leaked into response: {response.text}"
            )


# ============================================================
# Tenant-scope middleware runtime test
# ============================================================

class TestTenantScopeRuntime:
    """Runtime verification that tenant_scope_middleware's str(error) does not
    leak stack traces. The error is constrained to ValueError (no stack trace),
    so str(error) is just the message — safe to return."""

    def test_tenant_scope_error_message_is_safe(self):
        """Verify that resolve_tenant_scope raises ValueError (not Exception),
        so str(error) contains only the message, not a stack trace."""
        from app.core.tenant_scope import resolve_tenant_scope

        # Call with conflicting branch IDs to trigger ValueError
        try:
            resolve_tenant_scope(
                header_branch_id="branch-1",
                query_branch_id=None,
                user_branch_id="branch-2",  # conflicts with header
            )
            assert False, "should have raised ValueError"
        except ValueError as e:
            msg = str(e)
            # The message should be a human-readable description, not a stack trace
            assert "Traceback" not in msg
            assert "File \"" not in msg
            assert "branch" in msg.lower()  # mentions the actual problem
        except Exception as e:
            assert False, f"should have raised ValueError, got {type(e).__name__}: {e}"
