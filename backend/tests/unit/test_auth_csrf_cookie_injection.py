#!/usr/bin/env python3
"""
Tests for the /csrf-token bootstrap "never echo" invariant.

Closes CodeQL regression chain:
  - py/cookie-injection #1200 (original echo of request cookie)
  - py/cookie-injection #1316 (format-validation reuse still tainted
    the Set-Cookie value and did not stop attacker-known planted values)

The endpoint must ALWAYS mint a fresh server-side token: no user-supplied
value may flow into Set-Cookie or the response body. Rotation safety on
the client side (single-flight + CSRF 403 recovery with exactly one
retry) is covered by frontend/src/api/__tests__/csrfRecovery.test.ts.
"""
from __future__ import annotations

import re
import secrets
import sys
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[2]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

ENDPOINT = "/api/v1/auth/csrf-token"

# Format-valid attacker values: base64url, 32-128 chars — exactly what the
# removed intermediate "#1200" validation used to accept and reuse.
FORMAT_VALID_PLANTED = (
    secrets.token_urlsafe(32),          # indistinguishable from server-minted
    "A" * 32,                          # minimal length
    "A" * 128,                         # maximal length
    "attacker" + secrets.token_urlsafe(24),  # prefix + random tail
)

# Format-invalid planted values (the original #1200 scenario).
FORMAT_INVALID_PLANTED = (
    "attacker-knows-this",
    "../etc/passwd",
    "' OR '1'='1",
    "<script>alert(1)</script>",
    "A" * 32 + "!",
    "",
)


def _set_cookie_value(response) -> str:
    """Value of the csrf_token cookie from the Set-Cookie header."""
    raw = response.headers["set-cookie"]
    first = raw.split(";")[0].strip()
    assert first.startswith("csrf_token="), first
    return first[len("csrf_token=") :]


class TestCsrfBootstrapNeverEchoes:
    """No request cookie value may survive a bootstrap into Set-Cookie."""

    @pytest.mark.parametrize("planted", FORMAT_VALID_PLANTED)
    def test_format_valid_planted_cookie_is_overwritten(self, client, planted):
        """The #1316 core: a base64url-format planted value (which the old
        format-validation used to REUSE) must be replaced by a fresh
        server-minted token the attacker does not know."""
        response = client.get(ENDPOINT, cookies={"csrf_token": planted})

        assert response.status_code == 200
        body_token = response.json()["csrf_token"]
        cookie_token = _set_cookie_value(response)

        assert body_token != planted, "must NOT reuse a planted cookie value"
        assert cookie_token != planted, "must NOT re-echo a planted cookie value"
        assert body_token == cookie_token, (
            "double-submit pair must agree within one response"
        )

    @pytest.mark.parametrize("planted", FORMAT_INVALID_PLANTED)
    def test_format_invalid_planted_cookie_is_overwritten(self, client, planted):
        """The #1200 case stays closed: arbitrary attacker strings are
        never propagated into the cookie."""
        response = client.get(ENDPOINT, cookies={"csrf_token": planted})

        assert response.status_code == 200
        body_token = response.json()["csrf_token"]
        cookie_token = _set_cookie_value(response)

        assert body_token != planted
        assert cookie_token != planted

    def test_no_cookie_mints_fresh(self, client):
        response = client.get(ENDPOINT)

        assert response.status_code == 200
        token = response.json()["csrf_token"]
        assert token == _set_cookie_value(response)
        assert len(token) == 43  # secrets.token_urlsafe(32)

    def test_two_bootstraps_mint_independent_tokens(self, client):
        """Rotation is expected: each bootstrap returns a fresh token that
        is consistent with the cookie set by the SAME response."""
        r1 = client.get(ENDPOINT)
        r2 = client.get(ENDPOINT)

        t1 = r1.json()["csrf_token"]
        t2 = r2.json()["csrf_token"]
        assert t1 != t2, "server must mint independently per bootstrap"
        assert t1 == _set_cookie_value(r1)
        assert t2 == _set_cookie_value(r2)


class TestMintedTokenFormat:
    def test_minted_token_is_cookie_safe(self, client):
        """The minted token must contain only base64url characters — no
        cookie separators, no whitespace, no padding."""
        response = client.get(ENDPOINT)
        token = response.json()["csrf_token"]

        assert re.fullmatch(r"[A-Za-z0-9_-]{43}", token), token

    def test_minted_token_has_server_entropy(self, client):
        """Two tokens must not collide (32 bytes of entropy)."""
        tokens = {client.get(ENDPOINT).json()["csrf_token"] for _ in range(10)}
        assert len(tokens) == 10
