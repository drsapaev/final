"""auth_svc — split from authentication_service.py.

Re-exports AuthenticationService for backward compatibility.
"""
from __future__ import annotations

from app.services.auth_svc._base import *  # noqa: F401, F403
from app.services.auth_svc._base import AuthenticationServiceMixinBase
from app.services.auth_svc._tokens import TokensMixin
from app.services.auth_svc._auth import AuthMixin
from app.services.auth_svc._management import ManagementMixin

__all__ = ["AuthenticationService"]


class AuthenticationService(
    TokensMixin,
    AuthMixin,
    ManagementMixin,
    AuthenticationServiceMixinBase,
):
    """Composed of focused mixin modules."""

    def __init__(self):
        self.algorithm = "HS256"
        self.access_token_expire_minutes = settings.ACCESS_TOKEN_EXPIRE_MINUTES
        self.refresh_token_expire_days = 30
        self.password_reset_expire_hours = 1
        self.email_verification_expire_hours = 24
        self.session_expire_hours = 24
        self.max_login_attempts = 5
        self.lockout_duration_minutes = 15
