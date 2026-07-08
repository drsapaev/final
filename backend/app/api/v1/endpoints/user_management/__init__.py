"""user_management — split from app.api.v1.endpoints.user_management.py."""
from __future__ import annotations

from app.api.v1.endpoints.user_management import (
    _exports,  # noqa: F401
    _preferences,  # noqa: F401
    _users,  # noqa: F401
)
from app.api.v1.endpoints.user_management._helpers import *  # noqa: F401, F403
from app.api.v1.endpoints.user_management._helpers import router

__all__ = ["router"]
