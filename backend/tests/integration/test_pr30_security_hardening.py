"""
PR-30 — Sprint 3 quick security hardening.

Tests for:
1. CORS allow_methods is an explicit list (not ["*"])
2. CSRF auto-enabled in production (CSRF_ENABLED defaults to True when IS_PROD)
3. CSRF cookie secure flag matches IS_PROD
4. SENTRY_DSN removed from .env.example files (default empty)
5. ENABLE_DEV_AUTH fallback code removed from main.py
"""
from __future__ import annotations

import os
import re
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[3]
BACKEND_DIR = REPO_ROOT / "backend"
MAIN_PY = BACKEND_DIR / "app" / "main.py"
AUTH_PY = BACKEND_DIR / "app" / "api" / "v1" / "endpoints" / "auth.py"
BACKEND_ENV_EXAMPLE = BACKEND_DIR / ".env.example"
FRONTEND_ENV_EXAMPLE = REPO_ROOT / "frontend" / ".env.example"


# ---------- 1. CORS allow_methods ----------

def test_cors_allow_methods_is_explicit_list_not_wildcard():
    """CORS middleware must NOT use allow_methods=['*'].

    Wildcard methods allow dangerous verbs like CONNECT/TRACE/PATCH
    that the API never uses. Restrict to the actual method set.
    """
    src = MAIN_PY.read_text(encoding="utf-8")
    # The wildcard pattern under allow_methods must be gone.
    assert '"allow_methods": ["*"]' not in src, (
        "CORS allow_methods still uses wildcard ['*'] — must use explicit list"
    )
    # Verify an explicit list is present.
    assert re.search(
        r'"allow_methods":\s*\[\s*"GET"[^]]*"OPTIONS"\s*\]',
        src,
    ), "Expected explicit allow_methods list including GET..OPTIONS not found"


# ---------- 2. CSRF auto-enable in production ----------

def test_csrf_auto_enabled_in_production():
    """CSRF_ENABLED must default to ON when IS_PROD is True.

    Currently CSRF_ENABLED defaults to '0' (off). In production this
    is a security hole — form-based admin endpoints are unprotected.
    Fix: when IS_PROD and CSRF_ENABLED env var is unset, default to True.
    """
    src = MAIN_PY.read_text(encoding="utf-8")
    # Look for the pattern: CSRF_ENABLED should consult IS_PROD.
    # Acceptable forms:
    #   CSRF_ENABLED = os.getenv("CSRF_ENABLED", "1" if IS_PROD else "0") == "1"
    #   CSRF_ENABLED = (os.getenv("CSRF_ENABLED", "1" if IS_PROD else "0") == "1")
    assert "IS_PROD" in src, "IS_PROD not found in main.py"
    pattern = re.compile(
        r'CSRF_ENABLED\s*=\s*.*os\.getenv\(\s*["\']CSRF_ENABLED["\']\s*,\s*["\']1["\']\s+if\s+IS_PROD',
        re.DOTALL,
    )
    assert pattern.search(src), (
        "CSRF_ENABLED must default to '1' when IS_PROD is True — "
        "pattern not found in main.py"
    )


# ---------- 3. CSRF cookie secure flag ----------

def test_csrf_cookie_secure_follows_is_prod():
    """The /auth/csrf-token cookie must set secure=True in production.

    Currently secure=False always — cookie sent over plain HTTP,
    allowing MITM interception. Fix: secure=IS_PROD (or equivalent).
    """
    src = AUTH_PY.read_text(encoding="utf-8")
    # Look for set_cookie call with secure= parameter
    # The fix should reference IS_PROD or ENV == 'production'
    # Pattern: set_cookie(..., secure=<something with IS_PROD or production>)
    assert re.search(
        r"set_cookie\([^)]*secure\s*=\s*(?:IS_PROD|is_prod|ENV\s*==\s*[\"']production[\"'])",
        src,
        re.DOTALL,
    ), (
        "CSRF cookie set_cookie must use secure=IS_PROD (or is_prod) or ENV=='production' — not found"
    )


# ---------- 4. SENTRY_DSN removed from .env.example ----------

def test_backend_env_example_sentry_dsn_is_empty_or_commented():
    """backend/.env.example must NOT ship an active SENTRY_DSN.

    Currently has a hardcoded DSN that sends errors to a shared Sentry
    project when anyone copies .env.example → .env. Fix: comment out
    or set to empty string so dev clones don't auto-report.
    """
    text = BACKEND_ENV_EXAMPLE.read_text(encoding="utf-8")
    # Find any line that sets SENTRY_DSN to a non-empty URL
    for line in text.splitlines():
        stripped = line.strip()
        # Skip commented lines
        if stripped.startswith("#"):
            continue
        # Match: SENTRY_DSN="https://..." or SENTRY_DSN=https://...
        m = re.match(r'^SENTRY_DSN\s*=\s*["\']?(https?://[^"\']+)', stripped)
        assert not m, (
            f"backend/.env.example has active SENTRY_DSN URL — must be commented or empty: {stripped}"
        )


def test_frontend_env_example_sentry_dsn_is_empty_or_commented():
    """frontend/.env.example must NOT ship an active VITE_SENTRY_DSN."""
    if not FRONTEND_ENV_EXAMPLE.exists():
        pytest.skip("frontend/.env.example not found")
    text = FRONTEND_ENV_EXAMPLE.read_text(encoding="utf-8")
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        m = re.match(r'^VITE_SENTRY_DSN\s*=\s*["\']?(https?://[^"\']+)', stripped)
        assert not m, (
            f"frontend/.env.example has active VITE_SENTRY_DSN URL — must be commented or empty: {stripped}"
        )


# ---------- 5. ENABLE_DEV_AUTH fallback removed ----------

def test_enable_dev_auth_fallback_branch_removed_from_main():
    """The _USE_DEV_AUTH_FALLBACK branch and ENABLE_DEV_AUTH env var
    support must be removed from main.py.

    The branch is dead code in production (raises RuntimeError before
    reaching it) and a security risk in non-prod environments where
    ENABLE_DEV_AUTH=true could be set accidentally, registering fake
    /auth/login and /auth/me endpoints that return dev tokens.
    """
    src = MAIN_PY.read_text(encoding="utf-8")
    assert "_USE_DEV_AUTH_FALLBACK" not in src, (
        "_USE_DEV_AUTH_FALLBACK branch still present in main.py — remove it"
    )
    assert "ENABLE_DEV_AUTH" not in src, (
        "ENABLE_DEV_AUTH env var support still in main.py — remove it"
    )


def test_dev_auth_fallback_raises_runtime_error_on_import_failure(monkeypatch):
    """If app.api.deps auth imports fail, the app MUST raise RuntimeError
    unconditionally — regardless of environment.

    Previously the dev fallback would silently register dummy auth
    endpoints in non-prod. Now: fail loudly everywhere.
    """
    # We verify by reading source — the try/except for the auth import
    # must raise RuntimeError unconditionally, not just in IS_PROD.
    src = MAIN_PY.read_text(encoding="utf-8")
    # Find the try/except block around `from app.api.deps import`
    # The except branch must raise RuntimeError unconditionally.
    # We accept:
    #   except Exception as e:
    #       raise RuntimeError("Authentication dependencies unavailable") from e
    # without any IS_PROD gate.
    pattern = re.compile(
        r'except\s+Exception\s+as\s+\w+\s*:[^\n]*\n'
        r'\s*raise\s+RuntimeError\s*\(\s*["\']Authentication dependencies unavailable',
        re.MULTILINE,
    )
    assert pattern.search(src), (
        "Auth import except block must raise RuntimeError unconditionally "
        "(not gated by IS_PROD) — pattern not found in main.py"
    )
