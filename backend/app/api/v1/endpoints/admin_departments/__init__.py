"""admin_departments — split from app.api.v1.endpoints.admin_departments.py."""
from __future__ import annotations

from app.api.v1.endpoints.admin_departments import (
    _crud,  # noqa: F401
    _services,  # noqa: F401
)
from app.api.v1.endpoints.admin_departments._helpers import *  # noqa: F401, F403
from app.api.v1.endpoints.admin_departments._helpers import (  # noqa: F401
    router,
    _collect_department_overview,
    _ensure_department_integrations,
)

__all__ = ["router", "_collect_department_overview", "_ensure_department_integrations"]
