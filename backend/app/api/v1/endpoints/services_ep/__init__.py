"""services_ep — split from services.py."""
from __future__ import annotations

from app.api.v1.endpoints.services_ep import (
    _categories,  # noqa: F401
    _services,  # noqa: F401
)
from app.api.v1.endpoints.services_ep._helpers import *  # noqa: F401, F403
from app.api.v1.endpoints.services_ep._helpers import router

__all__ = ["router"]
