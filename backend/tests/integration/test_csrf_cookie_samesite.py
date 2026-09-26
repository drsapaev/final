#!/usr/bin/env python3
"""Functional pins for the ``csrf_token`` cookie SameSite policy.

PR #3407 (review of the merged 2a64f6d02, P1 follow-up): the documented
split-origin deployment (``VITE_API_BASE_URL``, ops/vps) is same-site —
frontend ``clinic.example.com`` + API ``api.example.com`` — so the cookie's
default ``SameSite=Lax`` travels with ``withCredentials`` POSTs and the
double-submit pair validates. A cross-SITE split (different registrable
domains, e.g. a ``*.vercel.app`` frontend against this API) does NOT send
Lax cookies on cross-site POSTs even with ``withCredentials``, and every
mutating request would die with ``403 missing_cookie``.

Closure: keep ``lax`` as the safe default and give ops an explicit opt-in
(``CSRF_COOKIE_SAMESITE=none``, which forces the Secure flag per the
SameSite=None spec requirement). These tests pin the contract:

- default (unset) -> SameSite=Lax, Secure only in production;
- ``none`` -> SameSite=None AND Secure even outside production;
- ``strict`` -> passed through;
- anything else -> loud 500 (a security-relevant setting must not be
  silently guessed).
"""

from __future__ import annotations


def _cookie_attributes(response) -> list[str]:
    """Lower-cased Set-Cookie attribute list ("name=value" first)."""
    raw = response.headers["set-cookie"]
    return [part.strip().lower() for part in raw.split(";")]


class TestCsrfCookieSameSite:
    ENDPOINT = "/api/v1/auth/csrf-token"

    def test_default_samesite_is_lax(self, client, monkeypatch):
        monkeypatch.delenv("CSRF_COOKIE_SAMESITE", raising=False)
        monkeypatch.delenv("ENV", raising=False)
        response = client.get(self.ENDPOINT)

        assert response.status_code == 200
        attrs = _cookie_attributes(response)
        assert "samesite=lax" in attrs, attrs
        assert "secure" not in attrs, (
            "non-production default must not set Secure "
            "(dev/e2e run behind plain HTTP)"
        )

    def test_production_default_keeps_lax_and_adds_secure(self, client, monkeypatch):
        monkeypatch.delenv("CSRF_COOKIE_SAMESITE", raising=False)
        monkeypatch.setenv("ENV", "production")
        response = client.get(self.ENDPOINT)

        assert response.status_code == 200
        attrs = _cookie_attributes(response)
        assert "samesite=lax" in attrs, attrs
        assert "secure" in attrs, attrs

    def test_samesite_none_forces_secure_even_outside_production(
        self, client, monkeypatch
    ):
        """Cross-site split opt-in: SameSite=None requires Secure (spec),
        otherwise browsers drop the cookie entirely."""
        monkeypatch.setenv("CSRF_COOKIE_SAMESITE", "none")
        monkeypatch.setenv("ENV", "dev")
        response = client.get(self.ENDPOINT)

        assert response.status_code == 200
        attrs = _cookie_attributes(response)
        assert "samesite=none" in attrs, attrs
        assert "secure" in attrs, (
            "SameSite=None without Secure is rejected by browsers — "
            "the endpoint must force the Secure flag in this mode"
        )

    def test_samesite_strict_passes_through(self, client, monkeypatch):
        monkeypatch.setenv("CSRF_COOKIE_SAMESITE", "strict")
        monkeypatch.delenv("ENV", raising=False)
        response = client.get(self.ENDPOINT)

        assert response.status_code == 200
        assert "samesite=strict" in _cookie_attributes(response)

    def test_invalid_value_fails_loudly(self, client, monkeypatch):
        """A typo in a security setting must not silently weaken the cookie."""
        monkeypatch.setenv("CSRF_COOKIE_SAMESITE", "loose")
        response = client.get(self.ENDPOINT)

        assert response.status_code == 500
        assert "CSRF_COOKIE_SAMESITE" in response.json()["detail"]

    def test_empty_value_falls_back_to_default(self, client, monkeypatch):
        """An explicitly empty env value behaves like unset (CI matrices)."""
        monkeypatch.setenv("CSRF_COOKIE_SAMESITE", "")
        monkeypatch.delenv("ENV", raising=False)
        response = client.get(self.ENDPOINT)

        assert response.status_code == 200
        assert "samesite=lax" in _cookie_attributes(response)
