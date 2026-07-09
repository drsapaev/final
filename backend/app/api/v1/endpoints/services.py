"""Backward-compatible shim for services_ep package."""
from __future__ import annotations

from app.api.v1.endpoints.services_ep import router  # noqa: F401
from app.api.v1.endpoints.services_ep._categories import list_service_categories  # noqa: F401
from app.api.v1.endpoints.services_ep._services import get_queue_groups  # noqa: F401

__all__ = ["router"]
