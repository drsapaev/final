"""Backward-compatible shim for services_ep package."""
from __future__ import annotations

from app.api.v1.endpoints.services_ep import router  # noqa: F401

__all__ = ["router"]
