"""auth_svc — split from authentication_service.py.

Re-exports AuthenticationService for backward compatibility.
"""
from __future__ import annotations

from app.services.auth_svc._auth import AuthMixin
from app.services.auth_svc._base import *  # noqa: F401, F403
from app.services.auth_svc._base import AuthenticationServiceMixinBase
from app.services.auth_svc._management import ManagementMixin
from app.services.auth_svc._tokens import TokensMixin

__all__ = ["AuthenticationService"]


class AuthenticationService(
    TokensMixin,
    AuthMixin,
    ManagementMixin,
    AuthenticationServiceMixinBase,
):
    """Composed of focused mixin modules."""

    def __init__(self):
        # Delegate to MRO so TokensMixin.__init__() (the single source of
        # truth) runs and sets all token/session/lockout attributes from
        # settings.  Do NOT re-set them here — that was the bug that caused
        # refresh_token_expire_days=30 despite settings.REFRESH_TOKEN_EXPIRE_DAYS=7.
        super().__init__()
