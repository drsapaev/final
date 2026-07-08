"""Backward-compatible shim for auth_svc package."""
from __future__ import annotations

from app.services.auth_svc import AuthenticationService  # noqa: F401
from app.services.auth_svc._management import get_authentication_service  # noqa: F401

__all__ = ["AuthenticationService", "get_authentication_service"]
