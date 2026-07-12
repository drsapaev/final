"""
PR-33 — Sprint 4 quick wins: token expiry + mobile auth refresh.

Tests for:
1. High-43: ACCESS_TOKEN_EXPIRE_MINUTES reduced from 10080 (7 days) to <=60 in .env.example
2. New /mobile/auth/refresh endpoint exists for cleaner mobile API surface
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[3]
BACKEND_DIR = REPO_ROOT / "backend"
ENV_EXAMPLE = BACKEND_DIR / ".env.example"
MOBILE_API_PY = BACKEND_DIR / "app" / "api" / "v1" / "endpoints" / "mobile_api.py"


# ---------- 1. High-43: Reduce ACCESS_TOKEN_EXPIRE_MINUTES ----------

def test_env_example_access_token_expiry_is_short():
    """High-43: ACCESS_TOKEN_EXPIRE_MINUTES in .env.example must be <= 60.

    Previously: 10080 (7 days) — way too long for an access token.
    Industry standard: 15-60 minutes. Refresh tokens handle long sessions.

    A stolen access token with 7-day expiry gives an attacker a week of
    access. With 30-minute expiry, the window is 30 minutes max.
    """
    text = ENV_EXAMPLE.read_text(encoding="utf-8")
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        m = re.match(r"^ACCESS_TOKEN_EXPIRE_MINUTES\s*=\s*(\d+)", stripped)
        if m:
            value = int(m.group(1))
            assert value <= 60, (
                f"ACCESS_TOKEN_EXPIRE_MINUTES={value} in .env.example is too long "
                f"(should be <= 60 minutes, was {value}). High-43."
            )
            return
    pytest.fail("ACCESS_TOKEN_EXPIRE_MINUTES not found in .env.example")


# ---------- 2. /mobile/auth/refresh endpoint ----------

def test_mobile_auth_refresh_endpoint_exists():
    """A /mobile/auth/refresh endpoint must exist for the mobile API.

    Mobile clients need a clean refresh endpoint under /mobile/ that
    wraps the same refresh_access_token logic as /authentication/refresh.
    This gives the mobile app a consistent API surface.
    """
    src = MOBILE_API_PY.read_text(encoding="utf-8")
    # Look for a /auth/refresh route (the /mobile prefix is added by the router)
    assert re.search(
        r'@router\.(post|get)\(\s*["\']/?auth/refresh["\']',
        src,
    ), "Expected @router.post('/auth/refresh') endpoint not found in mobile_api.py"


def test_mobile_auth_refresh_returns_access_and_refresh_tokens():
    """The /mobile/auth/refresh endpoint must return both access_token and refresh_token.

    This is required for refresh-token rotation (RFC 6749 §10.4): each refresh
    issues a NEW refresh token and revokes the old one.
    """
    src = MOBILE_API_PY.read_text(encoding="utf-8")
    # Find the refresh endpoint function body and check it returns both tokens
    m = re.search(
        r'@router\.(post|get)\(\s*["\']/?auth/refresh["\'][^@]*?def\s+\w+\([^)]*\)[^:]*:(.*?)(?=\n@|\Z)',
        src,
        re.DOTALL,
    )
    assert m, "Could not extract /auth/refresh endpoint body"
    body = m.group(2)
    assert "access_token" in body, "Refresh endpoint must return access_token"
    assert "refresh_token" in body, "Refresh endpoint must return refresh_token (rotation)"
