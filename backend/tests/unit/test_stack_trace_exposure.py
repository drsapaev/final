#!/usr/bin/env python3
"""
Unit tests for stack-trace-exposure hardening.

Closes CodeQL regressions for:
  - py/stack-trace-exposure #55 (tenant_scope_middleware)
  - py/stack-trace-exposure #1123, #1124 (registrar_integration/_queue_profiles)
  - py/stack-trace-exposure #1175, #1176 (main.py /health)
  - py/stack-trace-exposure #325-#1199 (downstream false positives whose taint
    source was the debug-mode leak in general_exception_handler)

Tests verify that:
1. The global exception handler NEVER includes str(exc) in the response,
   regardless of log level (the previous debug-mode leak is closed).
2. Tenant-scope middleware returns a generic message, not str(error).
3. Queue profiles fallback responses don't include "error": str(e).
"""
from __future__ import annotations

import logging
import re
import sys
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[2]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


# ============================================================
# Test 1: general_exception_handler — no str(exc) in response body
# ============================================================

class TestGeneralExceptionHandler:
    """Verify that the global Exception handler never leaks exception details.

    The previous implementation included `str(exc)` in the response when
    `logger.level <= logging.DEBUG`. This was an info-leak vector — setting
    LOG_LEVEL=DEBUG for troubleshooting would surface exception messages
    (including stack-trace fragments) to clients.

    The fix removes the conditional entirely; the response always contains
    only a generic message and a request_id.
    """

    def _read_handler_source(self) -> str:
        """Read exception_handlers.py source and extract the general_exception_handler."""
        src = (BACKEND_DIR / "app" / "core" / "exception_handlers.py").read_text()
        # Find the general_exception_handler function body
        match = re.search(
            r'async def general_exception_handler\([^)]*\)[^:]*:(.*?)(?=\n    @|\n    async def|\n    def |\Z)',
            src,
            re.DOTALL,
        )
        assert match, "could not find general_exception_handler in source"
        return match.group(1)

    def test_no_str_exc_in_response_content(self) -> None:
        """The response content dict must not include str(exc) anywhere."""
        body = self._read_handler_source()
        # The response content dict is constructed inside the function.
        # Verify str(exc) does NOT appear in the JSONResponse content section.
        # Split on "return JSONResponse(" — only check the response body.
        parts = body.split("return JSONResponse(")
        assert len(parts) >= 2, "could not locate return JSONResponse in handler"
        response_body = parts[1]
        assert "str(exc)" not in response_body, (
            f"str(exc) leaked into JSONResponse body:\n{response_body[:500]}"
        )

    def test_no_conditional_debug_mode_leak(self) -> None:
        """The previous implementation had `str(exc) if logger.level <= DEBUG else ...`.
        This conditional must be GONE from executable code (docstring references are OK)."""
        body = self._read_handler_source()
        # Strip docstrings before checking
        body_no_doc = re.sub(r'""".*?"""', '', body, flags=re.DOTALL)
        assert "logger.level" not in body_no_doc, (
            "logger.level still referenced in general_exception_handler executable code — "
            "the debug-mode info-leak conditional may still be present."
        )
        assert "logging.DEBUG" not in body_no_doc, (
            "logging.DEBUG still referenced in general_exception_handler executable code"
        )

    def test_response_contains_generic_message_and_request_id(self) -> None:
        """The response must contain a generic message and request_id (for support)."""
        body = self._read_handler_source()
        assert "internal_server_error" in body, "response must include error type"
        assert "request_id" in body, "response must include request_id for support"


# ============================================================
# Test 2: tenant_scope_middleware — no str(error) in response
# ============================================================

class TestTenantScopeMiddleware:
    """Verify that tenant_scope_middleware returns a generic message, not str(error)."""

    def _read_middleware_source(self) -> str:
        src = (BACKEND_DIR / "app" / "middleware" / "tenant_scope_middleware.py").read_text()
        return src

    def test_no_str_error_in_json_response(self) -> None:
        """The 400 response must not include str(error)."""
        src = self._read_middleware_source()
        # Find JSONResponse blocks and verify none of them include str(error)
        json_response_blocks = re.findall(
            r'JSONResponse\([^)]*content=\{[^}]*\}', src, re.DOTALL
        )
        for block in json_response_blocks:
            assert "str(error)" not in block, (
                f"str(error) leaked into JSONResponse:\n{block}"
            )

    def test_response_returns_generic_detail(self) -> None:
        """The tenant_scope_rejected response must use a generic detail message."""
        src = self._read_middleware_source()
        assert "Tenant scope rejected" in src or "tenant_scope_rejected" in src, (
            "tenant_scope_middleware should return a generic rejection message"
        )


# ============================================================
# Test 3: _queue_profiles.py — no "error": str(e) in fallback responses
# ============================================================

class TestQueueProfilesFallback:
    """Verify that queue profiles fallback responses don't expose exception details."""

    def _read_source(self) -> str:
        return (BACKEND_DIR / "app" / "api" / "v1" / "endpoints" / "registrar_integration" / "_queue_profiles.py").read_text()

    def test_no_error_str_e_in_responses(self) -> None:
        """Fallback responses must not include `"error": str(e)`."""
        src = self._read_source()
        # Find all return dict bodies
        return_blocks = re.findall(r'return\s*\{[^}]*\}', src, re.DOTALL)
        for block in return_blocks:
            assert '"error": str(e)' not in block, (
                f"fallback response leaks str(e):\n{block}"
            )
            assert "'error': str(e)" not in block, (
                f"fallback response leaks str(e):\n{block}"
            )

    def test_fallback_still_includes_source_marker(self) -> None:
        """The fallback marker `"source": "fallback_error"` should still be present
        so the frontend can detect the fallback path (just without the error details)."""
        src = self._read_source()
        count = src.count('"source": "fallback_error"')
        assert count == 2, f"expected 2 fallback markers, found {count}"


# ============================================================
# Test 4: Cross-cutting — no py/stack-trace-exposure patterns in critical files
# ============================================================

class TestNoStackTraceExposurePatterns:
    """Sanity check: none of the files we modified contain the original leak patterns."""

    @pytest.mark.parametrize("filepath,pattern", [
        ("app/core/exception_handlers.py", "str(exc)\n                    if logger.level"),
        ("app/middleware/tenant_scope_middleware.py", '"detail": str(error)'),
        ("app/api/v1/endpoints/registrar_integration/_queue_profiles.py", '"error": str(e)'),
    ])
    def test_no_leak_pattern(self, filepath: str, pattern: str) -> None:
        full_path = BACKEND_DIR / filepath
        src = full_path.read_text()
        assert pattern not in src, (
            f"leak pattern {pattern!r} still present in {filepath}"
        )
