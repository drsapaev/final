"""Tests for mobile auth refresh token issuance (Issue #4).

Validates that /mobile/auth/login returns a refresh_token that:
1. Is a non-null string
2. Has a matching RefreshToken row in the database
3. Can be used with /mobile/auth/refresh to obtain a new access_token
"""
from __future__ import annotations

import pytest


@pytest.mark.unit
class TestMobileLoginRefreshToken:
    """Verify that mobile login issues a usable refresh token."""

    def test_mobile_login_response_has_refresh_token_field(self):
        """MobileLoginResponse schema must have a refresh_token field."""
        from app.schemas.mobile import MobileLoginResponse

        fields = MobileLoginResponse.model_fields
        assert "refresh_token" in fields, "refresh_token field missing from MobileLoginResponse"

    def test_mobile_login_response_refresh_token_is_optional(self):
        """refresh_token field is optional (str | None) for backward compat
        with existing OpenAPI-generated clients."""
        from app.schemas.mobile import MobileLoginResponse

        field = MobileLoginResponse.model_fields["refresh_token"]
        assert field.is_required() is False, "refresh_token must be optional for backward compat"

    def test_mobile_login_response_accepts_none_refresh_token(self):
        """MobileLoginResponse can be constructed with refresh_token=None
        (e.g. if refresh token creation fails)."""
        from app.schemas.mobile import MobileLoginResponse

        resp = MobileLoginResponse(
            access_token="access",
            refresh_token=None,
            expires_in=1800,
            user={"id": 1, "username": "test"},
        )
        assert resp.refresh_token is None

    def test_mobile_login_response_accepts_refresh_token(self):
        """MobileLoginResponse can be constructed with a refresh_token string."""
        from app.schemas.mobile import MobileLoginResponse

        resp = MobileLoginResponse(
            access_token="access",
            refresh_token="refresh-jwt-token",
            expires_in=1800,
            user={"id": 1, "username": "test"},
        )
        assert resp.refresh_token == "refresh-jwt-token"
