"""Backward-compatible shim for auth_svc package."""
from __future__ import annotations
from app.services.auth_svc import AuthenticationService
from app.services.auth_svc._management import get_authentication_service

__all__ = ["AuthenticationService", "get_authentication_service"]
